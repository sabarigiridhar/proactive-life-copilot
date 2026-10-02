"""SQLite repository for daily completion status."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from life_copilot.storage.base import DEFAULT_DB_PATH, _database

def update_daily_status(
    entry_date: str,
    *,
    health_complete: bool = False,
    wealth_reviewed: bool = False,
    learning_complete: bool = False,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict:
    """Mark newly completed domains without clearing earlier progress."""
    with _database(db_path) as conn:
        conn.execute(
            """
            INSERT INTO daily_status (
                entry_date, health_complete, wealth_reviewed,
                learning_complete, created_at, updated_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(entry_date) DO UPDATE SET
                health_complete = MAX(
                    daily_status.health_complete, excluded.health_complete
                ),
                wealth_reviewed = MAX(
                    daily_status.wealth_reviewed, excluded.wealth_reviewed
                ),
                learning_complete = MAX(
                    daily_status.learning_complete, excluded.learning_complete
                ),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                entry_date,
                int(health_complete),
                int(wealth_reviewed),
                int(learning_complete),
            ),
        )
    return get_daily_status(entry_date, db_path=db_path)


def get_daily_status(
    entry_date: str, db_path: str | Path = DEFAULT_DB_PATH
) -> dict:
    """Return database-backed completion state for one date."""
    with _database(db_path) as conn:
        row = None
        try:
            row = conn.execute(
                """
                SELECT health_complete, wealth_reviewed, learning_complete
                FROM daily_status WHERE entry_date = ?
                """,
                (entry_date,),
            ).fetchone()
        except sqlite3.OperationalError:
            # Allows the UI to load briefly while migration 3 is still pending.
            pass

        health_exists = conn.execute(
            "SELECT EXISTS(SELECT 1 FROM health_logs WHERE entry_date = ?)",
            (entry_date,),
        ).fetchone()[0]
        wealth_exists = conn.execute(
            "SELECT EXISTS(SELECT 1 FROM wealth_logs WHERE entry_date = ?)",
            (entry_date,),
        ).fetchone()[0]
        learning_exists = conn.execute(
            "SELECT EXISTS(SELECT 1 FROM learning_logs WHERE entry_date = ?)",
            (entry_date,),
        ).fetchone()[0]

    health_complete = bool(health_exists or (row and row["health_complete"]))
    wealth_reviewed = bool(wealth_exists or (row and row["wealth_reviewed"]))
    learning_complete = bool(learning_exists or (row and row["learning_complete"]))
    return {
        "entry_date": entry_date,
        "health_complete": health_complete,
        "wealth_reviewed": wealth_reviewed,
        "learning_complete": learning_complete,
        "is_complete": health_complete and wealth_reviewed and learning_complete,
    }


def recalculate_daily_status(
    entry_date: str, db_path: str | Path = DEFAULT_DB_PATH
) -> dict:
    """Recompute completion after a record is edited, moved, or deleted."""
    with _database(db_path) as conn:
        health_complete = bool(
            conn.execute(
                "SELECT EXISTS(SELECT 1 FROM health_logs WHERE entry_date = ?)",
                (entry_date,),
            ).fetchone()[0]
        )
        wealth_reviewed = bool(
            conn.execute(
                "SELECT EXISTS(SELECT 1 FROM wealth_logs WHERE entry_date = ?)",
                (entry_date,),
            ).fetchone()[0]
        )
        learning_complete = bool(
            conn.execute(
                "SELECT EXISTS(SELECT 1 FROM learning_logs WHERE entry_date = ?)",
                (entry_date,),
            ).fetchone()[0]
        )

        if not any((health_complete, wealth_reviewed, learning_complete)):
            conn.execute("DELETE FROM daily_status WHERE entry_date = ?", (entry_date,))
        else:
            conn.execute(
                """
                INSERT INTO daily_status (
                    entry_date, health_complete, wealth_reviewed,
                    learning_complete, created_at, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(entry_date) DO UPDATE SET
                    health_complete = excluded.health_complete,
                    wealth_reviewed = excluded.wealth_reviewed,
                    learning_complete = excluded.learning_complete,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    entry_date,
                    int(health_complete),
                    int(wealth_reviewed),
                    int(learning_complete),
                ),
            )

    return get_daily_status(entry_date, db_path=db_path)
