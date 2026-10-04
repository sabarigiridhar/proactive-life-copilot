import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.core.settings import Settings
from backend.main import create_app
from life_copilot import storage


class FakeVectorCollection:
    def __init__(self):
        self.records = {}
        self.deleted = []

    def upsert(self, documents, metadatas, ids):
        for record_id, document, metadata in zip(ids, documents, metadatas):
            self.records[record_id] = (document, metadata)

    def delete(self, ids):
        self.deleted.extend(ids)
        for record_id in ids:
            self.records.pop(record_id, None)


class RecordsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            environment="test",
            database_path=root / "records-api.db",
            chroma_path=root / "chroma",
            cors_origins=[],
        )
        storage.init_sqlite_db(self.settings.database_path)
        self.client = TestClient(create_app(self.settings))
        self._seed_records()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed_records(self):
        self.wealth_ids = []
        wealth = (
            ("2026-10-01", "Expense", 100, "Food", "Cafe", "Lunch"),
            ("2026-10-02", "Expense", 200, "Food", "Market", "Groceries"),
            ("2026-10-02", "Income", 1000, "Salary", "Employer", None),
            ("2026-10-03", "Expense", 50, "Travel", "Cab", "Ride"),
            ("2026-10-04", "Expense", 25, "Food", "Bakery", "Snack"),
        )
        for entry_date, kind, amount, category, merchant, notes in wealth:
            self.wealth_ids.append(
                storage.insert_wealth_log(
                    entry_date,
                    kind,
                    amount,
                    "INR",
                    category,
                    merchant,
                    notes,
                    original_input="private user message",
                    db_path=self.settings.database_path,
                )
            )

        storage.insert_health_log(
            "2026-10-01",
            7,
            "Running",
            2000,
            None,
            db_path=self.settings.database_path,
        )
        storage.insert_health_log(
            "2026-10-02",
            9,
            "Yoga",
            2200,
            None,
            db_path=self.settings.database_path,
        )
        self.learning_ids = [
            storage.insert_learning_log(
                "2026-10-01",
                "RAG",
                30,
                None,
                "Retrieval notes",
                db_path=self.settings.database_path,
            ),
            storage.insert_learning_log(
                "2026-10-02",
                "Python",
                45,
                "https://example.com/python",
                "Typing notes",
                db_path=self.settings.database_path,
            ),
        ]
        storage.update_daily_status(
            "2026-10-02",
            health_complete=True,
            wealth_reviewed=True,
            learning_complete=True,
            db_path=self.settings.database_path,
        )

    def test_openapi_documents_record_and_dashboard_routes(self):
        paths = self.client.get("/openapi.json").json()["paths"]

        self.assertIn("/api/v1/logs/{domain}", paths)
        self.assertIn("/api/v1/logs/{domain}/{record_id}", paths)
        self.assertIn("/api/v1/dashboard/summary", paths)

    def test_list_logs_is_paginated_and_excludes_private_metadata(self):
        first = self.client.get(
            "/api/v1/logs/wealth", params={"page": 1, "page_size": 2}
        )
        second = self.client.get(
            "/api/v1/logs/wealth", params={"page": 2, "page_size": 2}
        )

        self.assertEqual(first.status_code, 200)
        first_data = first.json()["data"]
        self.assertEqual(first_data["total"], 5)
        self.assertEqual(first_data["total_pages"], 3)
        self.assertEqual(len(first_data["items"]), 2)
        self.assertEqual(second.json()["data"]["page"], 2)
        self.assertNotEqual(
            first_data["items"][0]["id"], second.json()["data"]["items"][0]["id"]
        )
        self.assertNotIn("original_input", first_data["items"][0])

    def test_domain_filters_and_search_are_parameterized_and_scoped(self):
        response = self.client.get(
            "/api/v1/logs/wealth",
            params={
                "start_date": "2026-10-02",
                "end_date": "2026-10-02",
                "transaction_type": "Expense",
                "category": "Food",
                "merchant": "mark",
                "search": "grocer",
            },
        )
        invalid_filter = self.client.get(
            "/api/v1/logs/wealth", params={"topic": "RAG"}
        )
        injection = self.client.get(
            "/api/v1/logs/wealth", params={"search": "%' OR 1=1 --"}
        )

        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["merchant"], "Market")
        self.assertEqual(invalid_filter.status_code, 422)
        self.assertEqual(injection.json()["data"]["total"], 0)

    def test_patch_merges_fields_and_validates_domain_contract(self):
        record_id = self.wealth_ids[0]
        response = self.client.patch(
            f"/api/v1/logs/wealth/{record_id}",
            json={"amount": 125, "notes": None},
        )
        invalid_value = self.client.patch(
            f"/api/v1/logs/wealth/{record_id}", json={"amount": -1}
        )
        invalid_field = self.client.patch(
            f"/api/v1/logs/wealth/{record_id}",
            json={"workout_type": "Yoga"},
        )
        missing = self.client.patch(
            "/api/v1/logs/wealth/999999", json={"amount": 10}
        )

        self.assertEqual(response.status_code, 200)
        record = response.json()["data"]["record"]
        self.assertEqual(record["amount"], 125)
        self.assertEqual(record["category"], "Food")
        self.assertIsNone(record["notes"])
        self.assertEqual(invalid_value.status_code, 422)
        self.assertEqual(invalid_field.status_code, 422)
        self.assertEqual(missing.status_code, 404)

    def test_learning_patch_and_delete_keep_vector_index_synchronized(self):
        record_id = self.learning_ids[0]
        vectors = FakeVectorCollection()
        with patch(
            "life_copilot.services.records.storage.init_chroma_db",
            return_value=vectors,
        ):
            updated = self.client.patch(
                f"/api/v1/logs/learning/{record_id}",
                json={
                    "topic": "Vector search",
                    "summary_text": "Updated retrieval notes",
                },
            )
            self.assertIn(f"learning_{record_id}", vectors.records)
            unconfirmed = self.client.delete(
                f"/api/v1/logs/learning/{record_id}"
            )
            deleted = self.client.delete(
                f"/api/v1/logs/learning/{record_id}", params={"confirm": "true"}
            )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["data"]["record"]["topic"], "Vector search")
        self.assertEqual(unconfirmed.status_code, 422)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["data"]["deleted_id"], record_id)
        self.assertIsNone(
            storage.get_domain_log(
                "learning", record_id, db_path=self.settings.database_path
            )
        )
        self.assertNotIn(f"learning_{record_id}", vectors.records)

    def test_health_date_conflict_returns_409_without_overwriting(self):
        records = storage.list_domain_logs(
            "health", db_path=self.settings.database_path
        )
        october_first = next(
            row for row in records if row["entry_date"] == "2026-10-01"
        )

        response = self.client.patch(
            f"/api/v1/logs/health/{october_first['id']}",
            json={"entry_date": "2026-10-02"},
        )

        self.assertEqual(response.status_code, 409)
        preserved = storage.get_domain_log(
            "health", october_first["id"], db_path=self.settings.database_path
        )
        self.assertEqual(preserved["entry_date"], "2026-10-01")

    def test_dashboard_summary_returns_all_domain_metrics(self):
        response = self.client.get(
            "/api/v1/dashboard/summary",
            params={
                "start_date": "2026-10-01",
                "end_date": "2026-10-02",
                "status_date": "2026-10-02",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["wealth"]["income"][0]["total"], 1000)
        self.assertEqual(data["wealth"]["expenses"][0]["total"], 300)
        self.assertEqual(data["wealth"]["net"][0]["net"], 700)
        self.assertEqual(data["wealth"]["categories"][0]["category"], "Food")
        self.assertEqual(data["health"]["average_sleep_hours"], 8)
        self.assertEqual(data["health"]["average_calories"], 2100)
        self.assertEqual(data["health"]["workout_days"], 2)
        self.assertEqual(data["learning"]["total_minutes"], 75)
        self.assertEqual(data["learning"]["sessions"], 2)
        self.assertEqual(data["learning"]["current_streak_days"], 2)
        self.assertEqual(data["learning"]["longest_streak_days"], 2)
        self.assertTrue(data["daily_status"]["is_complete"])

    def test_dashboard_rejects_invalid_or_oversized_date_ranges(self):
        reversed_range = self.client.get(
            "/api/v1/dashboard/summary",
            params={"start_date": "2026-10-02", "end_date": "2026-10-01"},
        )
        oversized_range = self.client.get(
            "/api/v1/dashboard/summary",
            params={"start_date": "2025-01-01", "end_date": "2026-10-01"},
        )

        self.assertEqual(reversed_range.status_code, 422)
        self.assertEqual(oversized_range.status_code, 422)


if __name__ == "__main__":
    unittest.main()
