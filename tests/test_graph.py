import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

import graph
from pydantic import ValidationError
from schemas import DailyLogDraft


class FakeResponse:
    def __init__(self, payload):
        self.text = json.dumps(payload)


class FakeModel:
    def __init__(self, payload):
        self.payload = payload

    def generate_content(self, *_args, **_kwargs):
        return FakeResponse(self.payload)


class FakeVectorCollection:
    def __init__(self):
        self.records = {}

    def upsert(self, documents, metadatas, ids):
        for record_id, document, metadata in zip(ids, documents, metadatas):
            self.records[record_id] = (document, metadata)


class DraftWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "drafts.db"
        graph.db_utils.init_sqlite_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_date_parser_supports_today_yesterday_and_iso_date(self):
        today = date(2026, 10, 2)
        self.assertEqual(graph.resolve_entry_date("log this today", today), today)
        self.assertEqual(
            graph.resolve_entry_date("this happened yesterday", today),
            date(2026, 10, 1),
        )
        self.assertEqual(
            graph.resolve_entry_date("log this for 2026-09-25", today),
            date(2026, 9, 25),
        )

    def test_two_expenses_remain_two_validated_draft_rows(self):
        draft = graph.parse_extraction_payload(
            {
                "health": None,
                "wealth": [
                    {
                        "transaction_type": "expense",
                        "amount": 250,
                        "currency": "inr",
                        "category": "Food",
                        "merchant": "Cafe",
                        "notes": None,
                    },
                    {
                        "transaction_type": "Expense",
                        "amount": 80,
                        "currency": "INR",
                        "category": "Food",
                        "merchant": "Coffee shop",
                        "notes": None,
                    },
                ],
                "learning": [],
                "confidence": 0.93,
                "ambiguities": [],
            },
            "Yesterday I spent 250 on lunch and 80 on coffee",
            today=date(2026, 10, 2),
        )

        self.assertEqual(draft.entry_date, date(2026, 10, 1))
        self.assertEqual(len(draft.wealth), 2)
        self.assertEqual([row.amount for row in draft.wealth], [250, 80])
        self.assertEqual(draft.wealth[0].transaction_type, "Expense")

    def test_missing_numeric_values_stay_none(self):
        draft = graph.parse_extraction_payload(
            {
                "health": {
                    "sleep_hours": None,
                    "workout_type": "running",
                    "calories_consumed": None,
                    "notes": "ran 5 km",
                },
                "wealth": [],
                "learning": [],
                "confidence": 0.8,
                "ambiguities": ["Workout duration was not provided."],
            },
            "I ran 5 km",
            today=date(2026, 10, 2),
        )

        self.assertIsNone(draft.health.sleep_hours)
        self.assertIsNone(draft.health.calories_consumed)
        self.assertEqual(len(draft.ambiguities), 1)

    def test_invalid_domain_values_return_clear_validation_errors(self):
        with self.assertRaises(ValidationError) as context:
            graph.parse_extraction_payload(
                {
                    "health": None,
                    "wealth": [
                        {
                            "transaction_type": "Expense",
                            "amount": 0,
                            "currency": "INR",
                            "category": "Food",
                        }
                    ],
                    "learning": [],
                    "confidence": 0.9,
                    "ambiguities": [],
                },
                "Spent nothing",
                today=date(2026, 10, 2),
            )
        self.assertIn("greater than 0", str(context.exception))

    def test_extraction_creates_draft_without_database_writes(self):
        payload = {
            "health": None,
            "wealth": [
                {
                    "transaction_type": "Expense",
                    "amount": 120,
                    "currency": "INR",
                    "category": "Food",
                    "merchant": None,
                    "notes": None,
                }
            ],
            "learning": [],
            "confidence": 0.9,
            "ambiguities": [],
        }
        with patch.object(
            graph.genai, "GenerativeModel", return_value=FakeModel(payload)
        ):
            result = graph.extract_data_node(
                {"user_message": "Spent 120 on food", "source": "text"}
            )

        self.assertIsNotNone(result["draft"])
        self.assertIn("Health", result["ai_response"])
        self.assertIn("Learning", result["ai_response"])
        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM wealth_logs").fetchone()[0]
        self.assertEqual(count, 0)

    def test_only_confirmed_draft_is_saved_with_private_metadata(self):
        draft = DailyLogDraft.model_validate(
            {
                "entry_date": "2026-10-02",
                "source": "voice",
                "original_input": "Spent 100 and 200 on meals",
                "health": None,
                "wealth": [
                    {
                        "transaction_type": "Expense",
                        "amount": amount,
                        "currency": "INR",
                        "category": "Food",
                    }
                    for amount in (100, 200)
                ],
                "learning": [],
                "confidence": 0.95,
                "ambiguities": [],
            }
        )

        result = graph.save_confirmed_draft(draft, db_path=self.db_path)

        self.assertEqual(result["wealth"], 2)
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT amount, source, original_input FROM wealth_logs ORDER BY id"
            ).fetchall()
        self.assertEqual(
            rows,
            [
                (100.0, "voice", "Spent 100 and 200 on meals"),
                (200.0, "voice", "Spent 100 and 200 on meals"),
            ],
        )

    def test_partial_check_in_can_resume_until_all_domains_are_complete(self):
        shared = {
            "entry_date": "2026-10-02",
            "source": "text",
            "confidence": 0.9,
            "ambiguities": [],
        }
        health_draft = {
            **shared,
            "original_input": "I slept 8 hours",
            "health": {"sleep_hours": 8},
            "wealth": [],
            "learning": [],
        }
        health_result = graph.save_confirmed_draft(
            health_draft, db_path=self.db_path
        )
        self.assertEqual(
            health_result["daily_status"],
            {
                "entry_date": "2026-10-02",
                "health_complete": True,
                "wealth_reviewed": False,
                "learning_complete": False,
                "is_complete": False,
            },
        )

        wealth_draft = {
            **shared,
            "original_input": "Spent 300 on groceries",
            "health": None,
            "wealth": [
                {
                    "transaction_type": "Expense",
                    "amount": 300,
                    "currency": "INR",
                    "category": "Food",
                }
            ],
            "learning": [],
        }
        wealth_result = graph.save_confirmed_draft(
            wealth_draft, db_path=self.db_path
        )
        self.assertTrue(wealth_result["daily_status"]["health_complete"])
        self.assertTrue(wealth_result["daily_status"]["wealth_reviewed"])
        self.assertFalse(wealth_result["daily_status"]["learning_complete"])

        learning_draft = {
            **shared,
            "original_input": "Studied RAG for 45 minutes",
            "health": None,
            "wealth": [],
            "learning": [
                {
                    "topic": "RAG",
                    "summary_text": "Learned retrieval and generation basics.",
                    "duration_minutes": 45,
                }
            ],
        }
        collection = FakeVectorCollection()
        learning_result = graph.save_confirmed_draft(
            learning_draft,
            db_path=self.db_path,
            vector_collection=collection,
        )
        self.assertTrue(learning_result["daily_status"]["is_complete"])
        self.assertEqual(len(collection.records), 1)


if __name__ == "__main__":
    unittest.main()
