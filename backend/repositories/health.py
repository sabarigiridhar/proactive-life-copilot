"""Dependency health checks for persistent stores."""

from __future__ import annotations

from pathlib import Path

from life_copilot.storage import init_chroma_db, init_sqlite_db
from life_copilot.storage.base import _database


def check_database(db_path: Path) -> tuple[bool, str | None]:
    try:
        init_sqlite_db(db_path)
        with _database(db_path) as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:
        return False, exc.__class__.__name__
    return True, None


def check_vector_store(chroma_path: Path) -> tuple[bool, str | None]:
    try:
        collection = init_chroma_db(chroma_path)
        collection.count()
    except Exception as exc:
        return False, exc.__class__.__name__
    return True, None
