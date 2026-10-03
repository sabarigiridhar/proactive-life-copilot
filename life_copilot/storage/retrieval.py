"""Read-only structured and semantic retrieval helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from life_copilot.storage.base import (
    DEFAULT_CHROMA_PATH,
    DEFAULT_DB_PATH,
    DOMAIN_SELECTS,
    LEARNING_COLLECTION,
    _database,
    _persistent_chroma_client,
)

def query_sqlite(
    query_string: str, db_path: str | Path = DEFAULT_DB_PATH
):
    """Reject legacy free-form SQL; callers must use typed analytics."""
    return "Error: Free-form SQL is disabled. Use the typed analytics service."


def search_learning_vectors(
    query_text: str,
    n_results: int = 3,
    chroma_path: str | Path = DEFAULT_CHROMA_PATH,
    *,
    topic: str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    collection=None,
):
    """Find semantically similar learning notes with metadata filters."""
    if collection is None:
        client = _persistent_chroma_client(chroma_path)
        collection = client.get_collection(name=LEARNING_COLLECTION)

    count = collection.count()
    if count == 0:
        return {"ids": [[]], "metadatas": [[]], "distances": [[]]}

    conditions = []
    if topic:
        conditions.append({"topic": {"$eq": topic}})
    if start_date and end_date and str(start_date) == str(end_date):
        conditions.append({"date": {"$eq": str(start_date)}})
    else:
        if start_date:
            start_ordinal = date.fromisoformat(str(start_date)).toordinal()
            conditions.append({"date_ordinal": {"$gte": start_ordinal}})
        if end_date:
            end_ordinal = date.fromisoformat(str(end_date)).toordinal()
            conditions.append({"date_ordinal": {"$lte": end_ordinal}})

    arguments = {
        "query_texts": [query_text],
        "n_results": min(max(1, int(n_results)), count),
        "include": ["metadatas", "distances"],
    }
    if len(conditions) == 1:
        arguments["where"] = conditions[0]
    elif conditions:
        arguments["where"] = {"$and": conditions}
    return collection.query(**arguments)


def get_learning_records_by_ids(
    record_ids: list[int], db_path: str | Path = DEFAULT_DB_PATH
) -> dict[int, dict]:
    """Return authoritative SQLite learning rows keyed by record ID."""
    unique_ids = list(dict.fromkeys(int(record_id) for record_id in record_ids))
    if not unique_ids:
        return {}
    placeholders = ", ".join("?" for _ in unique_ids)
    with _database(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT {DOMAIN_SELECTS['learning']}
            FROM learning_logs
            WHERE id IN ({placeholders})
            """,
            unique_ids,
        ).fetchall()
    return {row["id"]: dict(row) for row in rows}


def list_learning_search_candidates(
    *,
    topic: str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    limit: int = 500,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """List bounded SQLite candidates for verified fallback retrieval."""
    clauses = []
    parameters: list[object] = []
    if topic:
        clauses.append("LOWER(topic) = LOWER(?)")
        parameters.append(topic)
    if start_date:
        clauses.append("entry_date >= ?")
        parameters.append(str(start_date))
    if end_date:
        clauses.append("entry_date <= ?")
        parameters.append(str(end_date))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(min(max(1, int(limit)), 500))
    with _database(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT {DOMAIN_SELECTS['learning']}
            FROM learning_logs
            {where}
            ORDER BY entry_date DESC, id DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()
    return [dict(row) for row in rows]


def list_learning_topics(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[str]:
    """List known topics for conservative natural-language filter matching."""
    with _database(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT topic
            FROM learning_logs
            WHERE topic IS NOT NULL AND TRIM(topic) != ''
            ORDER BY LENGTH(topic) DESC, topic
            """
        ).fetchall()
    return [row["topic"] for row in rows]
