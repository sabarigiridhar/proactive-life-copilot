import tempfile
import unittest
from pathlib import Path

from life_copilot import storage as db_utils
from pydantic import ValidationError

from life_copilot.services.records import delete_saved_record, update_saved_record


class FakeVectorCollection:
    def __init__(self):
        self.records = {}
        self.deleted_batches = []

    def upsert(self, documents, metadatas, ids):
        for record_id, document, metadata in zip(ids, documents, metadatas):
            self.records[record_id] = (document, metadata)

    def delete(self, ids):
        self.deleted_batches.append(ids)
        for record_id in ids:
            self.records.pop(record_id, None)


class RecordMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "records.db"
        db_utils.init_sqlite_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_repository_fetches_by_id_without_private_original_input(self):
        record_id = db_utils.insert_wealth_log(
            "2026-10-01",
            "Expense",
            100,
            "INR",
            "Food",
            "Cafe",
            "Lunch",
            original_input="private prompt",
            db_path=self.db_path,
        )

        record = db_utils.get_domain_log(
            "wealth", record_id, db_path=self.db_path
        )
        listed = db_utils.list_domain_logs("wealth", db_path=self.db_path)

        self.assertEqual(record["id"], record_id)
        self.assertEqual(listed[0]["id"], record_id)
        self.assertNotIn("original_input", record)
        self.assertNotIn("original_input", listed[0])
        with self.assertRaises(ValueError):
            db_utils.list_domain_logs("unknown", db_path=self.db_path)

    def test_validated_wealth_update_moves_daily_completion(self):
        record_id = db_utils.insert_wealth_log(
            "2026-10-01",
            "Expense",
            100,
            "INR",
            "Food",
            None,
            None,
            db_path=self.db_path,
        )
        db_utils.update_daily_status(
            "2026-10-01", wealth_reviewed=True, db_path=self.db_path
        )

        result = update_saved_record(
            "wealth",
            record_id,
            {
                "entry_date": "2026-10-02",
                "transaction_type": "Income",
                "amount": 500,
                "currency": "inr",
                "category": "Refund",
                "merchant": None,
                "notes": "Correction",
            },
            db_path=self.db_path,
        )

        self.assertEqual(result["record"]["entry_date"], "2026-10-02")
        self.assertEqual(result["record"]["transaction_type"], "Income")
        self.assertEqual(result["record"]["currency"], "INR")
        self.assertFalse(
            db_utils.get_daily_status(
                "2026-10-01", db_path=self.db_path
            )["wealth_reviewed"]
        )
        self.assertTrue(
            db_utils.get_daily_status(
                "2026-10-02", db_path=self.db_path
            )["wealth_reviewed"]
        )

        with self.assertRaises(ValidationError):
            update_saved_record(
                "wealth",
                record_id,
                {
                    "entry_date": "2026-10-02",
                    "transaction_type": "Expense",
                    "amount": -1,
                    "currency": "INR",
                    "category": "Food",
                },
                db_path=self.db_path,
            )

    def test_delete_health_record_clears_completion(self):
        record_id = db_utils.insert_health_log(
            "2026-10-02",
            8,
            None,
            None,
            None,
            db_path=self.db_path,
        )
        db_utils.update_daily_status(
            "2026-10-02", health_complete=True, db_path=self.db_path
        )

        result = delete_saved_record(
            "health", record_id, db_path=self.db_path
        )

        self.assertEqual(result["deleted"]["id"], record_id)
        self.assertFalse(result["status"]["health_complete"])
        self.assertIsNone(
            db_utils.get_domain_log("health", record_id, db_path=self.db_path)
        )

    def test_learning_update_and_delete_keep_vector_id_synchronized(self):
        record_id = db_utils.insert_learning_log(
            "2026-10-01",
            "RAG",
            30,
            None,
            "Old summary",
            db_path=self.db_path,
        )
        db_utils.update_daily_status(
            "2026-10-01", learning_complete=True, db_path=self.db_path
        )
        collection = FakeVectorCollection()
        db_utils.add_learning_vector(
            collection,
            record_id,
            "2026-10-01",
            "RAG",
            "Old summary",
            None,
        )

        result = update_saved_record(
            "learning",
            record_id,
            {
                "entry_date": "2026-10-02",
                "topic": "Advanced RAG",
                "summary_text": "Updated summary",
                "duration_minutes": 60,
                "url_reference": "https://example.com/rag",
            },
            db_path=self.db_path,
            vector_collection=collection,
        )

        stable_id = f"learning_{record_id}"
        self.assertEqual(result["warnings"], [])
        self.assertEqual(collection.records[stable_id][0], "Updated summary")
        self.assertEqual(
            collection.records[stable_id][1]["topic"], "Advanced RAG"
        )
        self.assertIn(
            f"learning_2026-10-01_RAG", collection.deleted_batches[0]
        )

        deleted = delete_saved_record(
            "learning",
            record_id,
            db_path=self.db_path,
            vector_collection=collection,
        )
        self.assertEqual(deleted["warnings"], [])
        self.assertNotIn(stable_id, collection.records)
        self.assertFalse(deleted["status"]["learning_complete"])


if __name__ == "__main__":
    unittest.main()
