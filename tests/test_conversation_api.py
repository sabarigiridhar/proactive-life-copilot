import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.core.settings import Settings
from backend.main import create_app
from life_copilot import storage


class ConversationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            environment="test",
            database_path=root / "conversation-api.db",
            chroma_path=root / "chroma",
            cors_origins=[],
        )
        self.client = TestClient(create_app(self.settings))

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _log_provider(*_args, validator=None, operation=None, **_kwargs):
        if operation == "intent_classification":
            return validator("log")
        if operation == "daily_log_extraction":
            return validator(
                json.dumps(
                    {
                        "health": None,
                        "wealth": [
                            {
                                "transaction_type": "Expense",
                                "amount": 450,
                                "currency": "INR",
                                "category": "Groceries",
                                "merchant": "Market",
                                "notes": None,
                            }
                        ],
                        "learning": [],
                        "confidence": 0.96,
                        "ambiguities": [],
                    }
                )
            )
        raise AssertionError(f"Unexpected provider operation: {operation}")

    @staticmethod
    def _query_provider(*_args, validator=None, operation=None, **_kwargs):
        if operation == "intent_classification":
            return validator("query")
        raise AssertionError(f"Unexpected provider operation: {operation}")

    def _create_expense_draft(self):
        with patch(
            "life_copilot.agent.nodes.generate_gemini_content",
            side_effect=self._log_provider,
        ):
            response = self.client.post(
                "/api/v1/messages",
                json={
                    "message": "I spent 450 on groceries",
                    "entry_date": "2026-09-27",
                },
            )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def test_openapi_documents_message_and_confirmation_routes(self):
        paths = self.client.get("/openapi.json").json()["paths"]

        self.assertIn("/api/v1/messages", paths)
        self.assertIn("/api/v1/logs/confirm", paths)

    def test_log_returns_stable_thread_and_draft_without_saving(self):
        data = self._create_expense_draft()

        self.assertTrue(data["thread_id"])
        self.assertEqual(data["response_type"], "log_draft")
        self.assertEqual(data["draft"]["entry_date"], "2026-09-27")
        self.assertEqual(data["draft"]["wealth"][0]["amount"], 450)
        self.assertEqual(
            storage.list_domain_logs("wealth", db_path=self.settings.database_path),
            [],
        )
        messages = storage.get_chat_messages(
            data["thread_id"], db_path=self.settings.database_path
        )
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])

    def test_confirm_persists_draft_and_confirmation_metadata(self):
        draft_data = self._create_expense_draft()

        response = self.client.post(
            "/api/v1/logs/confirm",
            json={
                "thread_id": draft_data["thread_id"],
                "draft": draft_data["draft"],
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["response_type"], "confirmation")
        self.assertEqual(data["saved"]["wealth"], 1)
        self.assertEqual(len(data["record_ids"]["wealth"]), 1)
        records = storage.list_domain_logs(
            "wealth", db_path=self.settings.database_path
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["amount"], 450)
        messages = storage.get_chat_messages(
            draft_data["thread_id"], db_path=self.settings.database_path
        )
        self.assertEqual(messages[-1]["metadata"]["event"], "confirmed_records")

    def test_query_returns_evidence_and_preserves_supplied_thread_id(self):
        storage.init_sqlite_db(self.settings.database_path)
        storage.insert_wealth_log(
            "2026-09-27",
            "Expense",
            450,
            "INR",
            "Groceries",
            "Market",
            None,
            db_path=self.settings.database_path,
        )
        thread_id = "query-thread-1"

        with patch(
            "life_copilot.agent.nodes.generate_gemini_content",
            side_effect=self._query_provider,
        ):
            response = self.client.post(
                "/api/v1/messages",
                json={
                    "thread_id": thread_id,
                    "message": (
                        "How much did I spend from 2026-09-27 to 2026-09-27?"
                    ),
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["thread_id"], thread_id)
        self.assertEqual(data["response_type"], "query_answer")
        self.assertEqual(
            data["date_range"],
            {"start_date": "2026-09-27", "end_date": "2026-09-27"},
        )
        self.assertTrue(data["evidence"])
        self.assertIn("450", data["assistant_text"])

    def test_unresolved_reference_returns_clarification_without_provider_call(self):
        with patch(
            "life_copilot.agent.nodes.generate_gemini_content"
        ) as provider_call:
            response = self.client.post(
                "/api/v1/messages",
                json={
                    "thread_id": "clarify-thread-1",
                    "message": "Add 50 more to that",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["response_type"], "clarification")
        self.assertIsNone(data["draft"])
        self.assertIn("cannot tell", data["assistant_text"])
        provider_call.assert_not_called()

    def test_blank_message_and_invalid_thread_id_are_rejected(self):
        blank = self.client.post("/api/v1/messages", json={"message": "   "})
        invalid_thread = self.client.post(
            "/api/v1/messages",
            json={"thread_id": "not allowed/id", "message": "hello"},
        )

        self.assertEqual(blank.status_code, 422)
        self.assertEqual(invalid_thread.status_code, 422)
        self.assertEqual(blank.json()["error"]["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()
