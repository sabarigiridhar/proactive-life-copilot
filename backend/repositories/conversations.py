"""Persistence adapter for API conversation history."""

from __future__ import annotations

from pathlib import Path

from life_copilot import storage


def initialize_conversation(thread_id: str, db_path: Path) -> None:
    storage.init_sqlite_db(db_path)
    storage.create_chat_thread(thread_id, db_path=db_path)


def store_message(
    thread_id: str,
    role: str,
    content: str,
    *,
    db_path: Path,
    metadata: dict | None = None,
) -> int:
    return storage.add_chat_message(
        thread_id,
        role,
        content,
        metadata=metadata,
        db_path=db_path,
    )
