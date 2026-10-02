"""SQLite repository for health, wealth, and learning records."""

from __future__ import annotations

from pathlib import Path

from life_copilot.storage.base import (
    DEFAULT_DB_PATH,
    DOMAIN_SELECTS,
    DOMAIN_TABLES,
    _database,
)

def insert_wealth_log(
    entry_date,
    transaction_type,
    amount,
    currency,
    category,
    merchant,
    notes,
    source="text",
    original_input=None,
    db_path: str | Path = DEFAULT_DB_PATH,
):
    """Insert one wealth transaction and return its SQLite row ID."""
    with _database(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO wealth_logs (
                entry_date, transaction_type, amount, currency, category,
                merchant, notes, source, original_input, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                entry_date,
                transaction_type,
                amount,
                currency,
                category,
                merchant,
                notes,
                source,
                original_input,
            ),
        )
        return cursor.lastrowid


def insert_health_log(
    entry_date,
    sleep_hours,
    workout_type,
    calories_consumed,
    notes,
    source="text",
    original_input=None,
    db_path: str | Path = DEFAULT_DB_PATH,
):
    """Insert or update the single health summary for a date."""
    with _database(db_path) as conn:
        conn.execute(
            """
            INSERT INTO health_logs (
                entry_date, sleep_hours, workout_type, calories_consumed,
                notes, source, original_input, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(entry_date) DO UPDATE SET
                sleep_hours = COALESCE(excluded.sleep_hours, health_logs.sleep_hours),
                workout_type = CASE
                    WHEN excluded.workout_type IS NULL
                         OR TRIM(excluded.workout_type) = ''
                         OR LOWER(TRIM(excluded.workout_type)) = 'none'
                        THEN health_logs.workout_type
                    WHEN health_logs.workout_type IS NULL
                         OR TRIM(health_logs.workout_type) = ''
                         OR LOWER(TRIM(health_logs.workout_type)) = 'none'
                        THEN excluded.workout_type
                    WHEN INSTR(
                             ', ' || LOWER(TRIM(health_logs.workout_type)) || ', ',
                             ', ' || LOWER(TRIM(excluded.workout_type)) || ', '
                         ) > 0
                        THEN health_logs.workout_type
                    ELSE health_logs.workout_type || ', ' || excluded.workout_type
                END,
                calories_consumed = COALESCE(
                    excluded.calories_consumed, health_logs.calories_consumed
                ),
                notes = CASE
                    WHEN excluded.notes IS NULL OR TRIM(excluded.notes) = ''
                        THEN health_logs.notes
                    WHEN health_logs.notes IS NULL OR TRIM(health_logs.notes) = ''
                        THEN excluded.notes
                    WHEN INSTR(
                             ', ' || LOWER(TRIM(health_logs.notes)) || ', ',
                             ', ' || LOWER(TRIM(excluded.notes)) || ', '
                         ) > 0
                        THEN health_logs.notes
                    ELSE health_logs.notes || ', ' || excluded.notes
                END,
                source = CASE
                    WHEN health_logs.source = excluded.source THEN health_logs.source
                    ELSE 'mixed'
                END,
                original_input = CASE
                    WHEN excluded.original_input IS NULL
                         OR TRIM(excluded.original_input) = ''
                        THEN health_logs.original_input
                    WHEN health_logs.original_input IS NULL
                         OR TRIM(health_logs.original_input) = ''
                        THEN excluded.original_input
                    WHEN INSTR(
                             LOWER(health_logs.original_input),
                             LOWER(excluded.original_input)
                         ) > 0
                        THEN health_logs.original_input
                    ELSE health_logs.original_input || CHAR(10) || '---' ||
                         CHAR(10) || excluded.original_input
                END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                entry_date,
                sleep_hours,
                workout_type,
                calories_consumed,
                notes,
                source,
                original_input,
            ),
        )
        row = conn.execute(
            "SELECT id FROM health_logs WHERE entry_date = ?", (entry_date,)
        ).fetchone()
        return row["id"]


def insert_learning_log(
    entry_date,
    topic,
    duration_minutes,
    url_reference,
    summary_text=None,
    source="text",
    original_input=None,
    db_path: str | Path = DEFAULT_DB_PATH,
):
    """Insert one learning session and return its SQLite row ID."""
    with _database(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO learning_logs (
                entry_date, topic, summary_text, duration_minutes,
                url_reference, source, original_input, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                entry_date,
                topic,
                summary_text,
                duration_minutes,
                url_reference,
                source,
                original_input,
            ),
        )
        return cursor.lastrowid

def list_domain_logs(
    domain: str,
    *,
    limit: int = 50,
    offset: int = 0,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """List recent records for an allowlisted domain without private metadata."""
    normalized = domain.lower()
    if normalized not in DOMAIN_TABLES:
        raise ValueError(f"Unsupported domain: {domain}")
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    table = DOMAIN_TABLES[normalized]
    columns = DOMAIN_SELECTS[normalized]
    with _database(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM {table}
            ORDER BY entry_date DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def get_domain_log(
    domain: str, record_id: int, db_path: str | Path = DEFAULT_DB_PATH
) -> dict | None:
    """Fetch one record by domain and ID without returning original input."""
    normalized = domain.lower()
    if normalized not in DOMAIN_TABLES:
        raise ValueError(f"Unsupported domain: {domain}")
    table = DOMAIN_TABLES[normalized]
    columns = DOMAIN_SELECTS[normalized]
    with _database(db_path) as conn:
        row = conn.execute(
            f"SELECT {columns} FROM {table} WHERE id = ?", (record_id,)
        ).fetchone()
    return dict(row) if row else None


def update_wealth_record(
    record_id: int,
    entry_date: str,
    transaction_type: str,
    amount: float,
    currency: str,
    category: str,
    merchant: str | None,
    notes: str | None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    with _database(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE wealth_logs
            SET entry_date = ?, transaction_type = ?, amount = ?, currency = ?,
                category = ?, merchant = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                entry_date,
                transaction_type,
                amount,
                currency,
                category,
                merchant,
                notes,
                record_id,
            ),
        )
        return cursor.rowcount == 1


def update_health_record(
    record_id: int,
    entry_date: str,
    sleep_hours: float | None,
    workout_type: str | None,
    calories_consumed: int | None,
    notes: str | None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    with _database(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE health_logs
            SET entry_date = ?, sleep_hours = ?, workout_type = ?,
                calories_consumed = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                entry_date,
                sleep_hours,
                workout_type,
                calories_consumed,
                notes,
                record_id,
            ),
        )
        return cursor.rowcount == 1


def update_learning_record(
    record_id: int,
    entry_date: str,
    topic: str,
    summary_text: str,
    duration_minutes: int | None,
    url_reference: str | None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    with _database(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE learning_logs
            SET entry_date = ?, topic = ?, summary_text = ?,
                duration_minutes = ?, url_reference = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                entry_date,
                topic,
                summary_text,
                duration_minutes,
                url_reference,
                record_id,
            ),
        )
        return cursor.rowcount == 1


def delete_domain_log(
    domain: str, record_id: int, db_path: str | Path = DEFAULT_DB_PATH
) -> bool:
    """Delete one allowlisted record by ID."""
    normalized = domain.lower()
    if normalized not in DOMAIN_TABLES:
        raise ValueError(f"Unsupported domain: {domain}")
    table = DOMAIN_TABLES[normalized]
    with _database(db_path) as conn:
        cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        return cursor.rowcount == 1
