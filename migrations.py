"""Versioned SQLite schema migrations for Life Copilot."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

LATEST_SCHEMA_VERSION = 3


WEALTH_SCHEMA = """
CREATE TABLE wealth_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    category TEXT NOT NULL,
    merchant TEXT,
    notes TEXT,
    source TEXT NOT NULL DEFAULT 'text',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

HEALTH_SCHEMA = """
CREATE TABLE health_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL UNIQUE,
    sleep_hours REAL,
    workout_type TEXT,
    calories_consumed INTEGER,
    notes TEXT,
    source TEXT NOT NULL DEFAULT 'text',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

LEARNING_SCHEMA = """
CREATE TABLE learning_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    topic TEXT NOT NULL,
    summary_text TEXT,
    duration_minutes INTEGER,
    url_reference TEXT,
    source TEXT NOT NULL DEFAULT 'text',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

DAILY_STATUS_SCHEMA = """
CREATE TABLE daily_status (
    entry_date TEXT PRIMARY KEY,
    health_complete INTEGER NOT NULL DEFAULT 0 CHECK (health_complete IN (0, 1)),
    wealth_reviewed INTEGER NOT NULL DEFAULT 0 CHECK (wealth_reviewed IN (0, 1)),
    learning_complete INTEGER NOT NULL DEFAULT 0 CHECK (learning_complete IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _latest_meaningful(values: Iterable, ignored: tuple = (None, "")):
    candidates = [value for value in values if value not in ignored]
    return candidates[-1] if candidates else None


def _combine_distinct(values: Iterable, ignored: tuple = (None, "", "None")):
    result = []
    for value in values:
        if value in ignored or value in result:
            continue
        result.append(str(value))
    return ", ".join(result) or None


def _migrate_wealth(conn: sqlite3.Connection, now: str) -> None:
    if _table_exists(conn, "wealth_logs"):
        conn.execute("ALTER TABLE wealth_logs RENAME TO wealth_logs_v0")

    conn.execute(WEALTH_SCHEMA)

    if not _table_exists(conn, "wealth_logs_v0"):
        return

    conn.execute(
        """
        INSERT INTO wealth_logs (
            id, entry_date, transaction_type, amount, currency, category,
            merchant, notes, source, created_at, updated_at
        )
        SELECT id, date, transaction_type, amount, COALESCE(currency, 'INR'),
               COALESCE(category, 'General'), merchant, notes, 'legacy', ?, ?
        FROM wealth_logs_v0
        """,
        (now, now),
    )
    conn.execute("DROP TABLE wealth_logs_v0")


def _migrate_health(conn: sqlite3.Connection, now: str) -> None:
    if _table_exists(conn, "health_logs"):
        conn.execute("ALTER TABLE health_logs RENAME TO health_logs_v0")

    conn.execute(HEALTH_SCHEMA)

    if not _table_exists(conn, "health_logs_v0"):
        return

    rows = conn.execute(
        """
        SELECT id, date, sleep_hours, workout_type, calories_consumed, notes
        FROM health_logs_v0
        ORDER BY date, id
        """
    ).fetchall()

    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(row["date"], []).append(row)

    for entry_date, daily_rows in grouped.items():
        # Legacy inserts frequently used zero for missing numbers. Prefer the
        # latest positive value when one exists, while preserving a real zero
        # when it is the only recorded value.
        sleep_values = [row["sleep_hours"] for row in daily_rows]
        calorie_values = [row["calories_consumed"] for row in daily_rows]
        sleep_hours = _latest_meaningful(sleep_values, (None, "", 0))
        if sleep_hours is None:
            sleep_hours = _latest_meaningful(sleep_values)
        calories = _latest_meaningful(calorie_values, (None, "", 0))
        if calories is None:
            calories = _latest_meaningful(calorie_values)

        conn.execute(
            """
            INSERT INTO health_logs (
                id, entry_date, sleep_hours, workout_type, calories_consumed,
                notes, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'legacy', ?, ?)
            """,
            (
                max(row["id"] for row in daily_rows),
                entry_date,
                sleep_hours,
                _combine_distinct(row["workout_type"] for row in daily_rows),
                calories,
                _combine_distinct(row["notes"] for row in daily_rows),
                now,
                now,
            ),
        )

    conn.execute("DROP TABLE health_logs_v0")


def _migrate_learning(conn: sqlite3.Connection, now: str) -> None:
    if _table_exists(conn, "learning_logs"):
        conn.execute("ALTER TABLE learning_logs RENAME TO learning_logs_v0")

    conn.execute(LEARNING_SCHEMA)

    if not _table_exists(conn, "learning_logs_v0"):
        return

    conn.execute(
        """
        INSERT INTO learning_logs (
            id, entry_date, topic, summary_text, duration_minutes,
            url_reference, source, created_at, updated_at
        )
        SELECT id, date, COALESCE(topic, ''), NULL, duration_minutes,
               url_reference, 'legacy', ?, ?
        FROM learning_logs_v0
        """,
        (now, now),
    )
    conn.execute("DROP TABLE learning_logs_v0")


def _migration_001_daily_data_model(conn: sqlite3.Connection) -> None:
    now = _utc_now()
    _migrate_wealth(conn, now)
    _migrate_health(conn, now)
    _migrate_learning(conn, now)
    conn.execute(
        "CREATE INDEX idx_wealth_entry_date ON wealth_logs(entry_date)"
    )
    conn.execute(
        "CREATE INDEX idx_learning_entry_date ON learning_logs(entry_date)"
    )
    conn.execute("CREATE INDEX idx_learning_topic ON learning_logs(topic)")


def _migration_002_original_input(conn: sqlite3.Connection) -> None:
    """Keep the source text privately alongside each confirmed record."""
    for table_name in ("wealth_logs", "health_logs", "learning_logs"):
        columns = {
            row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")
        }
        if "original_input" not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN original_input TEXT")


def _migration_003_daily_status(conn: sqlite3.Connection) -> None:
    """Track daily completion independently of the current chat session."""
    conn.execute(DAILY_STATUS_SCHEMA)
    now = _utc_now()
    conn.execute(
        """
        WITH dates AS (
            SELECT entry_date FROM health_logs
            UNION
            SELECT entry_date FROM wealth_logs
            UNION
            SELECT entry_date FROM learning_logs
        )
        INSERT INTO daily_status (
            entry_date, health_complete, wealth_reviewed, learning_complete,
            created_at, updated_at
        )
        SELECT
            dates.entry_date,
            EXISTS(
                SELECT 1 FROM health_logs
                WHERE health_logs.entry_date = dates.entry_date
            ),
            EXISTS(
                SELECT 1 FROM wealth_logs
                WHERE wealth_logs.entry_date = dates.entry_date
            ),
            EXISTS(
                SELECT 1 FROM learning_logs
                WHERE learning_logs.entry_date = dates.entry_date
            ),
            ?, ?
        FROM dates
        WHERE dates.entry_date IS NOT NULL AND TRIM(dates.entry_date) <> ''
        """,
        (now, now),
    )


MIGRATIONS = (
    (1, "daily_data_model", _migration_001_daily_data_model),
    (2, "original_input_metadata", _migration_002_original_input),
    (3, "daily_completion_status", _migration_003_daily_status),
)


def run_migrations(db_path: str | Path = "life_copilot.db") -> list[int]:
    """Apply all pending migrations atomically and return applied versions."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    applied_now: list[int] = []

    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied = {
            row[0] for row in conn.execute("SELECT version FROM schema_migrations")
        }

        for version, name, migration in MIGRATIONS:
            if version in applied:
                continue
            migration(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, _utc_now()),
            )
            applied_now.append(version)

        conn.commit()
        return applied_now
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
