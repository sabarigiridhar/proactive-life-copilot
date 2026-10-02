import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import db_utils


class FakeCollection:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.records = {}

    def upsert(self, documents, metadatas, ids):
        for record_id, document, metadata in zip(ids, documents, metadatas):
            self.records[record_id] = (document, metadata)

    def modify(self, name):
        del self.client.collections[self.name]
        self.name = name
        self.client.collections[name] = self


class FakeChromaClient:
    def __init__(self):
        self.collections = {}
        old = FakeCollection(self, db_utils.LEARNING_COLLECTION)
        self.collections[old.name] = old

    def create_collection(self, name):
        collection = FakeCollection(self, name)
        self.collections[name] = collection
        return collection

    def get_collection(self, name):
        if name not in self.collections:
            raise ValueError(name)
        return self.collections[name]

    def delete_collection(self, name):
        if name not in self.collections:
            raise ValueError(name)
        del self.collections[name]


class DatabaseUtilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        db_utils.init_sqlite_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_health_write_upserts_one_daily_row(self):
        first_id = db_utils.insert_health_log(
            "2026-09-27", 7.0, "Running", None, "Morning", db_path=self.db_path
        )
        second_id = db_utils.insert_health_log(
            "2026-09-27", None, None, 2200, None, db_path=self.db_path
        )

        self.assertEqual(first_id, second_id)
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*), sleep_hours, workout_type, calories_consumed, notes
                FROM health_logs WHERE entry_date = '2026-09-27'
                """
            ).fetchone()
        self.assertEqual(row, (1, 7.0, "Running", 2200, "Morning"))

    def test_health_upsert_preserves_meal_when_workout_is_added(self):
        db_utils.insert_health_log(
            "2026-10-02",
            None,
            None,
            450,
            "ate chicken curry",
            source="text",
            original_input="I ate chicken curry",
            db_path=self.db_path,
        )
        db_utils.insert_health_log(
            "2026-10-02",
            None,
            "running",
            None,
            "ran for 5 km",
            source="voice",
            original_input="I ran 5 km",
            db_path=self.db_path,
        )
        # Repeating the same extracted information must not duplicate text.
        db_utils.insert_health_log(
            "2026-10-02",
            None,
            "running",
            None,
            "ran for 5 km",
            source="voice",
            original_input="I ran 5 km",
            db_path=self.db_path,
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT sleep_hours, workout_type, calories_consumed, notes,
                       source, original_input
                FROM health_logs WHERE entry_date = '2026-10-02'
                """
            ).fetchone()

        self.assertEqual(
            row,
            (
                None,
                "running",
                450,
                "ate chicken curry, ran for 5 km",
                "mixed",
                "I ate chicken curry\n---\nI ran 5 km",
            ),
        )

    def test_wealth_and_learning_allow_multiple_rows_per_date(self):
        for amount in (100, 200):
            db_utils.insert_wealth_log(
                "2026-09-27",
                "Expense",
                amount,
                "INR",
                "Food",
                None,
                None,
                db_path=self.db_path,
            )
        first_learning_id = db_utils.insert_learning_log(
            "2026-09-27", "RAG", 30, None, "Retrieval notes", db_path=self.db_path
        )
        second_learning_id = db_utils.insert_learning_log(
            "2026-09-27",
            "LangGraph",
            45,
            None,
            "Graph notes",
            db_path=self.db_path,
        )

        self.assertNotEqual(first_learning_id, second_learning_id)
        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM wealth_logs").fetchone()[0], 2)
            summaries = conn.execute(
                "SELECT summary_text FROM learning_logs ORDER BY id"
            ).fetchall()
        self.assertEqual(summaries, [("Retrieval notes",), ("Graph notes",)])

    def test_learning_vector_uses_sqlite_id(self):
        client = FakeChromaClient()
        collection = client.get_collection(db_utils.LEARNING_COLLECTION)
        db_utils.add_learning_vector(
            collection, 42, "2026-09-27", "RAG", "Summary", None
        )
        self.assertIn("learning_42", collection.records)
        self.assertEqual(collection.records["learning_42"][1]["sqlite_id"], 42)

    def test_rebuild_uses_every_sqlite_learning_row(self):
        ids = [
            db_utils.insert_learning_log(
                "2026-09-27", topic, 30, None, f"{topic} summary", db_path=self.db_path
            )
            for topic in ("RAG", "LangGraph")
        ]
        client = FakeChromaClient()
        with patch.object(db_utils, "_persistent_chroma_client", return_value=client):
            count = db_utils.rebuild_learning_vectors(
                self.db_path, Path(self.temp_dir.name) / "chroma"
            )

        self.assertEqual(count, 2)
        rebuilt = client.get_collection(db_utils.LEARNING_COLLECTION)
        self.assertEqual(set(rebuilt.records), {f"learning_{row_id}" for row_id in ids})


if __name__ == "__main__":
    unittest.main()
