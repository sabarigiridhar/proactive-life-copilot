"""Persistence helpers for structured logs and learning vectors."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from life_copilot.storage.migrations import run_migrations

DEFAULT_DB_PATH = Path("life_copilot.db")
DEFAULT_CHROMA_PATH = Path("chroma_data")
LEARNING_COLLECTION = "learning_summaries"

DOMAIN_TABLES = {
    "wealth": "wealth_logs",
    "health": "health_logs",
    "learning": "learning_logs",
}

DOMAIN_SELECTS = {
    "wealth": """
        id, entry_date, transaction_type, amount, currency, category,
        merchant, notes, source, created_at, updated_at
    """,
    "health": """
        id, entry_date, sleep_hours, workout_type, calories_consumed,
        notes, source, created_at, updated_at
    """,
    "learning": """
        id, entry_date, topic, summary_text, duration_minutes,
        url_reference, source, created_at, updated_at
    """,
}


def _connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _database(db_path: str | Path = DEFAULT_DB_PATH):
    conn = _connect(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _persistent_chroma_client(chroma_path: str | Path):
    # Chroma imports native optional dependencies, so keep SQLite-only paths
    # usable even when those dependencies are unavailable.
    import chromadb

    return chromadb.PersistentClient(path=str(chroma_path))


def init_sqlite_db(db_path: str | Path = DEFAULT_DB_PATH) -> list[int]:
    """Create or migrate the SQLite database to the latest schema."""
    return run_migrations(db_path)
