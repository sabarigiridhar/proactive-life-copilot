"""ChromaDB synchronization and learning-index maintenance."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from life_copilot.storage.base import (
    DEFAULT_CHROMA_PATH,
    DEFAULT_DB_PATH,
    LEARNING_COLLECTION,
    _database,
    _persistent_chroma_client,
)

def init_chroma_db(chroma_path: str | Path = DEFAULT_CHROMA_PATH):
    """Return the persistent learning-summary collection."""
    client = _persistent_chroma_client(chroma_path)
    return client.get_or_create_collection(name=LEARNING_COLLECTION)


def add_learning_vector(
    collection,
    learning_id: int,
    entry_date: str,
    topic: str,
    summary_text: str,
    url_reference: str | None,
):
    """Upsert a learning summary using its SQLite row ID as the stable key."""
    collection.upsert(
        documents=[summary_text],
        metadatas=[
            {
                "sqlite_id": learning_id,
                "date": entry_date,
                "topic": topic,
                "url": url_reference or "None",
            }
        ],
        ids=[f"learning_{learning_id}"],
    )


def delete_learning_vector(
    collection,
    learning_id: int,
    legacy_entry_date: str | None = None,
    legacy_topic: str | None = None,
) -> None:
    """Delete a learning vector using its stable SQLite-backed ID."""
    ids = [f"learning_{learning_id}"]
    if legacy_entry_date and legacy_topic:
        legacy_id = f"learning_{legacy_entry_date}_{legacy_topic.replace(' ', '_')}"
        if legacy_id not in ids:
            ids.append(legacy_id)
    collection.delete(ids=ids)


def _read_legacy_chroma_records(chroma_path: str | Path):
    """Read legacy documents when the Chroma Python package cannot load."""
    sqlite_path = Path(chroma_path) / "chroma.sqlite3"
    if not sqlite_path.exists():
        return {"documents": [], "metadatas": []}

    query = """
        SELECT e.id, em.key, em.string_value
        FROM embeddings e
        JOIN segments s ON s.id = e.segment_id
        JOIN collections c ON c.id = s.collection
        JOIN embedding_metadata em ON em.id = e.id
        WHERE c.name = ?
          AND em.key IN ('chroma:document', 'date', 'topic')
        ORDER BY e.id
    """
    records: dict[int, dict[str, str]] = {}
    conn = sqlite3.connect(sqlite_path)
    try:
        for record_id, key, value in conn.execute(query, (LEARNING_COLLECTION,)):
            records.setdefault(record_id, {})[key] = value
    finally:
        conn.close()

    return {
        "documents": [record.get("chroma:document") for record in records.values()],
        "metadatas": [
            {"date": record.get("date"), "topic": record.get("topic")}
            for record in records.values()
        ],
    }


def backfill_learning_summaries_from_chroma(
    db_path: str | Path = DEFAULT_DB_PATH,
    chroma_path: str | Path = DEFAULT_CHROMA_PATH,
) -> int:
    """Recover legacy summaries from Chroma before rebuilding stable IDs."""
    try:
        client = _persistent_chroma_client(chroma_path)
        collection = client.get_collection(name=LEARNING_COLLECTION)
        stored = collection.get(include=["documents", "metadatas"])
    except Exception:
        stored = _read_legacy_chroma_records(chroma_path)

    candidates: dict[tuple[str, str], list[str]] = {}
    for document, metadata in zip(
        stored.get("documents") or [], stored.get("metadatas") or []
    ):
        if not document or not metadata:
            continue
        key = (str(metadata.get("date", "")), str(metadata.get("topic", "")))
        candidates.setdefault(key, []).append(document)

    updated = 0
    with _database(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, entry_date, topic
            FROM learning_logs
            WHERE summary_text IS NULL OR TRIM(summary_text) = ''
            ORDER BY id
            """
        ).fetchall()
        for row in rows:
            documents = candidates.get((row["entry_date"], row["topic"]), [])
            if not documents:
                continue
            conn.execute(
                "UPDATE learning_logs SET summary_text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (documents.pop(0), row["id"]),
            )
            updated += 1
    return updated


def rebuild_learning_vectors(
    db_path: str | Path = DEFAULT_DB_PATH,
    chroma_path: str | Path = DEFAULT_CHROMA_PATH,
) -> int:
    """Atomically rebuild learning vectors from the SQLite source of truth."""
    client = _persistent_chroma_client(chroma_path)
    temporary_name = f"{LEARNING_COLLECTION}_rebuild"
    backup_name = f"{LEARNING_COLLECTION}_previous"

    for stale_name in (temporary_name, backup_name):
        try:
            client.delete_collection(stale_name)
        except Exception:
            pass

    temporary = client.create_collection(name=temporary_name)
    with _database(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, entry_date, topic, summary_text, url_reference
            FROM learning_logs
            ORDER BY id
            """
        ).fetchall()

    for row in rows:
        add_learning_vector(
            temporary,
            row["id"],
            row["entry_date"],
            row["topic"],
            row["summary_text"] or row["topic"] or "No summary",
            row["url_reference"],
        )

    try:
        current = client.get_collection(name=LEARNING_COLLECTION)
    except Exception:
        current = None

    if current is not None:
        current.modify(name=backup_name)
    temporary.modify(name=LEARNING_COLLECTION)
    if current is not None:
        client.delete_collection(backup_name)
    return len(rows)
