import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from life_copilot.ui import main as ui_main
from life_copilot.ui.api_client import (
    ApiClientError,
    ConfirmationResult,
    DailyStatusResult,
    DashboardResult,
    MessageResult,
    RecordPageResult,
)


class FakeApi:
    def __init__(self, records=None):
        self.records = records or []
        self.messages = []
        self.confirmed_drafts = []

    def get_dashboard_summary(self, *, status_date):
        status = DailyStatusResult(
            entry_date=status_date,
            health_complete=False,
            wealth_reviewed=False,
            learning_complete=False,
            is_complete=False,
        )
        return DashboardResult(status_date=status_date, daily_status=status)

    def list_records(self, domain, *, page=1, page_size=50):
        items = self.records if domain == "wealth" else []
        return RecordPageResult(
            domain=domain,
            items=items,
            page=page,
            page_size=page_size,
            total=len(items),
            total_pages=1 if items else 0,
        )

    def send_message(self, *, thread_id, message, source="text"):
        self.messages.append((thread_id, message, source))
        if "spent" in message.lower():
            return MessageResult(
                thread_id=thread_id,
                response_type="log_draft",
                assistant_text="I prepared 1 record(s). Review the draft before saving.",
                draft={
                    "entry_date": "2026-10-04",
                    "source": source,
                    "original_input": message,
                    "health": None,
                    "wealth": [
                        {
                            "transaction_type": "Expense",
                            "amount": 120,
                            "currency": "INR",
                            "category": "Food",
                            "merchant": "Cafe",
                            "notes": None,
                        }
                    ],
                    "learning": [],
                    "confidence": 0.95,
                    "ambiguities": [],
                    "operation": "create",
                    "target_domain": None,
                    "target_record_id": None,
                },
            )
        return MessageResult(
            thread_id=thread_id,
            response_type="query_answer",
            assistant_text="Your total expenses are 350.",
            evidence=[{"currency": "INR", "total": 350.0}],
            date_range={
                "start_date": "2026-10-04",
                "end_date": "2026-10-04",
            },
            confidence=1.0,
        )

    def confirm_log(self, *, thread_id, draft):
        self.confirmed_drafts.append(draft)
        return ConfirmationResult(
            thread_id=thread_id,
            assistant_text="Saved 1 confirmed record(s).",
            daily_status=DailyStatusResult(
                entry_date=date(2026, 10, 4),
                health_complete=False,
                wealth_reviewed=True,
                learning_complete=False,
                is_complete=False,
            ),
        )


class UnavailableApi:
    def get_dashboard_summary(self, *, status_date):
        raise ApiClientError(
            "The Life Copilot API is unavailable. Check that the backend is running."
        )


class MessageFailureApi(FakeApi):
    def send_message(self, *, thread_id, message, source="text"):
        raise ApiClientError("The message could not be processed safely.")


class StreamlitInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.app_path = cls.root / "app.py"

    def _run(self, api):
        with patch.object(ui_main, "get_api_client", return_value=api):
            return AppTest.from_file(str(self.app_path)).run(timeout=20)

    def test_query_uses_api_neutral_status_and_clears_input_after_reply(self):
        source = (self.root / "life_copilot" / "ui" / "main.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('st.spinner("Processing your message...")', source)
        self.assertNotIn("app_brain", source)
        self.assertNotIn("life_copilot.agent", source)
        api = FakeApi()

        with patch.object(ui_main, "get_api_client", return_value=api):
            app = AppTest.from_file(str(self.app_path)).run(timeout=20)
            app.text_area[0].input("What is my today expense").run(timeout=20)
            send_button = next(button for button in app.button if button.label == "Send")
            send_button.click().run(timeout=20)

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertEqual(app.text_area[0].value, "")
        self.assertTrue(any("350" in item.value for item in app.markdown))
        self.assertTrue(any(item.label == "Evidence" for item in app.expander))
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(api.messages[0][1], "What is my today expense")

    def test_log_draft_is_confirmed_through_api(self):
        api = FakeApi()
        with patch.object(ui_main, "get_api_client", return_value=api):
            app = AppTest.from_file(str(self.app_path)).run(timeout=20)
            app.text_area[0].input("I spent 120 at Cafe").run(timeout=20)
            next(button for button in app.button if button.label == "Send").click().run(
                timeout=20
            )
            confirm = next(
                button for button in app.button if button.label == "Confirm and save"
            )
            confirm.click().run(timeout=20)

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertEqual(len(api.confirmed_drafts), 1)
        self.assertEqual(api.confirmed_drafts[0]["wealth"][0]["amount"], 120)
        self.assertTrue(
            any("Saved 1 confirmed" in item.value for item in app.markdown)
        )

    def test_api_unavailable_state_is_visible_without_crashing(self):
        app = self._run(UnavailableApi())

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(any("API is unavailable" in item.value for item in app.error))
        self.assertTrue(any("Start the FastAPI backend" in item.value for item in app.info))

    def test_message_api_failure_is_rendered_as_an_error(self):
        api = MessageFailureApi()
        with patch.object(ui_main, "get_api_client", return_value=api):
            app = AppTest.from_file(str(self.app_path)).run(timeout=20)
            app.text_area[0].input("Log something").run(timeout=20)
            next(button for button in app.button if button.label == "Send").click().run(
                timeout=20
            )

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(
            any("could not be processed safely" in item.value for item in app.error)
        )

    def test_maintenance_renders_a_legacy_zero_wealth_amount_from_api(self):
        api = FakeApi(
            records=[
                {
                    "id": 1,
                    "entry_date": "2026-10-02",
                    "transaction_type": "Expense",
                    "amount": 0.0,
                    "currency": "INR",
                    "category": "General",
                    "merchant": None,
                    "notes": "Legacy zero-value record",
                    "source": "legacy",
                    "created_at": "2026-10-02 00:00:00",
                    "updated_at": "2026-10-02 00:00:00",
                }
            ]
        )
        app = self._run(api)

        self.assertEqual([str(item.value) for item in app.exception], [])
        amount_input = next(
            field for field in app.number_input if field.label == "Amount"
        )
        self.assertEqual(amount_input.value, 0.0)
        self.assertTrue(
            any("greater than zero" in item.value for item in app.warning)
        )


if __name__ == "__main__":
    unittest.main()
