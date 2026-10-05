"""Persistence helpers for local application preferences."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from life_copilot.storage.base import DEFAULT_DB_PATH, _database, init_sqlite_db


def get_app_preferences(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict:
    init_sqlite_db(db_path)
    with _database(db_path) as conn:
        row = conn.execute(
            """
            SELECT default_currency, weekly_spending_limit,
                   weekly_learning_minutes, weekly_workouts,
                   sleep_hours_target, updated_at
            FROM app_preferences
            WHERE id = 1
            """
        ).fetchone()
    return dict(row)


def update_app_preferences(
    *,
    default_currency: str,
    weekly_spending_limit: float | None,
    weekly_learning_minutes: int,
    weekly_workouts: int,
    sleep_hours_target: float,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict:
    init_sqlite_db(db_path)
    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _database(db_path) as conn:
        conn.execute(
            """
            UPDATE app_preferences
            SET default_currency = ?, weekly_spending_limit = ?,
                weekly_learning_minutes = ?, weekly_workouts = ?,
                sleep_hours_target = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                default_currency,
                weekly_spending_limit,
                weekly_learning_minutes,
                weekly_workouts,
                sleep_hours_target,
                updated_at,
            ),
        )
    return get_app_preferences(db_path)
