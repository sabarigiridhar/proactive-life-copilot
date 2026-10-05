"""SQLite repository for conversation history and rolling summaries."""

from __future__ import annotations

import json
from pathlib import Path

from life_copilot.storage.base import DEFAULT_DB_PATH, _database


def create_chat_thread(
    thread_id: str,
    title: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    """Create a conversation thread if it does not already exist."""
    with _database(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO chat_threads (
                id, title, created_at, updated_at
            ) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (thread_id, title),
        )
        return cursor.rowcount == 1


def add_chat_message(
    thread_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Persist one ordered user or assistant message."""
    if role not in {"user", "assistant"}:
        raise ValueError("Chat role must be 'user' or 'assistant'.")
    if not content.strip():
        raise ValueError("Chat content cannot be empty.")
    create_chat_thread(thread_id, db_path=db_path)
    with _database(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_messages (
                thread_id, role, content, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                thread_id,
                role,
                content.strip(),
                json.dumps(metadata) if metadata else None,
            ),
        )
        conn.execute(
            """
            UPDATE chat_threads
            SET title = CASE
                    WHEN ? = 'user' AND (title IS NULL OR TRIM(title) = '')
                        THEN SUBSTR(?, 1, 80)
                    ELSE title
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (role, content.strip(), thread_id),
        )
        return cursor.lastrowid


def list_chat_threads(
    *,
    limit: int = 50,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return recently active conversation threads with lightweight summaries."""
    limit = max(1, min(int(limit), 100))
    with _database(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                threads.id,
                COALESCE(
                    NULLIF(TRIM(threads.title), ''),
                    (
                        SELECT first_user.content
                        FROM chat_messages AS first_user
                        WHERE first_user.thread_id = threads.id
                          AND first_user.role = 'user'
                        ORDER BY first_user.id
                        LIMIT 1
                    ),
                    'New conversation'
                ) AS title,
                threads.created_at,
                threads.updated_at,
                COUNT(messages.id) AS message_count,
                (
                    SELECT recent.content
                    FROM chat_messages AS recent
                    WHERE recent.thread_id = threads.id
                    ORDER BY recent.id DESC
                    LIMIT 1
                ) AS last_message
            FROM chat_threads AS threads
            LEFT JOIN chat_messages AS messages ON messages.thread_id = threads.id
            GROUP BY threads.id
            ORDER BY threads.updated_at DESC, threads.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_chat_thread(
    thread_id: str,
    *,
    message_limit: int = 200,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict | None:
    """Return one conversation and its recent chronological messages."""
    with _database(db_path) as conn:
        row = conn.execute(
            """
            SELECT id,
                   COALESCE(
                       NULLIF(TRIM(title), ''),
                       (
                           SELECT first_user.content
                           FROM chat_messages AS first_user
                           WHERE first_user.thread_id = chat_threads.id
                             AND first_user.role = 'user'
                           ORDER BY first_user.id
                           LIMIT 1
                       ),
                       'New conversation'
                   ) AS title,
                   created_at, updated_at
            FROM chat_threads
            WHERE id = ?
            """,
            (thread_id,),
        ).fetchone()
    if row is None:
        return None
    thread = dict(row)
    thread["messages"] = get_chat_messages(
        thread_id,
        limit=message_limit,
        db_path=db_path,
    )
    return thread


def get_chat_messages(
    thread_id: str,
    *,
    limit: int = 50,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return the most recent messages in chronological order."""
    limit = max(1, min(int(limit), 500))
    with _database(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, metadata_json, created_at
            FROM (
                SELECT id, role, content, metadata_json, created_at
                FROM chat_messages
                WHERE thread_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id
            """,
            (thread_id, limit),
        ).fetchall()
    messages = []
    for row in rows:
        message = dict(row)
        message["metadata"] = (
            json.loads(message.pop("metadata_json"))
            if message.get("metadata_json")
            else None
        )
        messages.append(message)
    return messages


def get_memory_window(
    thread_id: str,
    *,
    recent_limit: int = 8,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict:
    """Return a bounded recent window and older messages awaiting summary."""
    recent = get_chat_messages(
        thread_id, limit=recent_limit, db_path=db_path
    )
    with _database(db_path) as conn:
        thread = conn.execute(
            """
            SELECT summary, summary_through_message_id
            FROM chat_threads WHERE id = ?
            """,
            (thread_id,),
        ).fetchone()
        summary = thread["summary"] if thread else None
        summarized_through = thread["summary_through_message_id"] if thread else 0
        recent_start_id = recent[0]["id"] if recent else 2**63 - 1
        rows = conn.execute(
            """
            SELECT id, role, content, created_at
            FROM chat_messages
            WHERE thread_id = ? AND id > ? AND id < ?
            ORDER BY id
            """,
            (thread_id, summarized_through, recent_start_id),
        ).fetchall()
    return {
        "summary": summary,
        "summary_through_message_id": summarized_through,
        "recent_messages": recent,
        "unsummarized_messages": [dict(row) for row in rows],
    }


def update_chat_summary(
    thread_id: str,
    summary: str,
    through_message_id: int,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """Persist a rolling summary through a specific message ID."""
    with _database(db_path) as conn:
        conn.execute(
            """
            UPDATE chat_threads
            SET summary = ?, summary_through_message_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (summary.strip(), through_message_id, thread_id),
        )


def get_last_confirmed_entities(
    thread_id: str, db_path: str | Path = DEFAULT_DB_PATH
) -> list[dict]:
    """Recover the latest confirmed entity references from message metadata."""
    with _database(db_path) as conn:
        rows = conn.execute(
            """
            SELECT metadata_json
            FROM chat_messages
            WHERE thread_id = ? AND metadata_json IS NOT NULL
            ORDER BY id DESC
            """,
            (thread_id,),
        ).fetchall()
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if metadata.get("event") == "confirmed_records":
            return metadata.get("entities") or []
    return []
