import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from life_copilot.storage.migrations import run_migrations


LEGACY_SCHEMA = """
CREATE TABLE wealth_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    transaction_type TEXT,
    amount REAL,
    currency TEXT,
    category TEXT,
    merchant TEXT,
    notes TEXT
);
CREATE TABLE health_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    sleep_hours REAL,
    workout_type TEXT,
    calories_consumed INTEGER,
    notes TEXT
);
CREATE TABLE learning_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    topic TEXT,
    duration_minutes INTEGER,
    url_reference TEXT
);
"""


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "legacy.db"
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.executescript(LEGACY_SCHEMA)
                conn.executemany(
                    """
                    INSERT INTO wealth_logs
                        (date, transaction_type, amount, currency, category, merchant, notes)
                    VALUES (?, 'Expense', ?, 'INR', 'Food', NULL, NULL)
                    """,
                    [("2026-09-27", 100), ("2026-09-27", 200)],
                )
                conn.executemany(
                    """
                    INSERT INTO health_logs
                        (date, sleep_hours, workout_type, calories_consumed, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        ("2026-09-27", 7.5, "Running", 0, "Felt good"),
                        ("2026-09-27", 0, "Yoga", 2100, "Stretched"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO learning_logs
                        (date, topic, duration_minutes, url_reference)
                    VALUES (?, ?, ?, NULL)
                    """,
                    [
                        ("2026-09-27", "RAG", 30),
                        ("2026-09-27", "LangGraph", 45),
                    ],
                )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_migration_preserves_multi_entry_data_and_merges_health(self):
        self.assertEqual(run_migrations(self.db_path), [1, 2, 3, 4, 5])

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM wealth_logs").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learning_logs").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM health_logs").fetchone()[0], 1)

            health = conn.execute("SELECT * FROM health_logs").fetchone()
            self.assertEqual(health["entry_date"], "2026-09-27")
            self.assertEqual(health["sleep_hours"], 7.5)
            self.assertEqual(health["calories_consumed"], 2100)
            self.assertEqual(health["workout_type"], "Running, Yoga")
            self.assertEqual(health["notes"], "Felt good, Stretched")
            self.assertEqual(health["source"], "legacy")

            learning_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(learning_logs)")
            }
            self.assertIn("summary_text", learning_columns)
            self.assertIn("original_input", learning_columns)
            status = conn.execute(
                """
                SELECT health_complete, wealth_reviewed, learning_complete
                FROM daily_status WHERE entry_date = '2026-09-27'
                """
            ).fetchone()
            self.assertEqual(tuple(status), (1, 1, 1))
            preferences = conn.execute(
                "SELECT * FROM app_preferences WHERE id = 1"
            ).fetchone()
            self.assertEqual(preferences["default_currency"], "INR")
            self.assertEqual(preferences["weekly_learning_minutes"], 300)

    def test_migration_is_repeatable(self):
        self.assertEqual(run_migrations(self.db_path), [1, 2, 3, 4, 5])
        self.assertEqual(run_migrations(self.db_path), [])

        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 5)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM wealth_logs").fetchone()[0], 2)

    def test_health_date_is_unique_after_migration(self):
        run_migrations(self.db_path)
        with closing(sqlite3.connect(self.db_path)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO health_logs
                        (entry_date, source, created_at, updated_at)
                    VALUES ('2026-09-27', 'text', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                )

    def test_fresh_database_gets_latest_schema(self):
        fresh_path = Path(self.temp_dir.name) / "fresh.db"
        self.assertEqual(run_migrations(fresh_path), [1, 2, 3, 4, 5])
        with closing(sqlite3.connect(fresh_path)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(
            {
                "wealth_logs",
                "health_logs",
                "learning_logs",
                "daily_status",
                "chat_threads",
                "chat_messages",
                "app_preferences",
            }
            <= tables
        )


if __name__ == "__main__":
    unittest.main()
