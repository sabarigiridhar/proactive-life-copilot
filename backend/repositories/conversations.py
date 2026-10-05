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


def list_conversations(*, db_path: Path, limit: int = 50) -> list[dict]:
    storage.init_sqlite_db(db_path)
    return storage.list_chat_threads(limit=limit, db_path=db_path)


def load_conversation(
    thread_id: str,
    *,
    db_path: Path,
    message_limit: int = 200,
) -> dict | None:
    storage.init_sqlite_db(db_path)
    return storage.get_chat_thread(
        thread_id,
        message_limit=message_limit,
        db_path=db_path,
    )
