"""Persistence helpers for structured logs and learning vectors."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from migrations import run_migrations

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


# ==========================================
# 1. SQLITE SETUP AND WRITES
# ==========================================
def init_sqlite_db(db_path: str | Path = DEFAULT_DB_PATH) -> list[int]:
    """Create or migrate the SQLite database to the latest schema."""
    return run_migrations(db_path)


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


# ==========================================
# 2. CHROMADB SETUP AND SYNCHRONIZATION
# ==========================================
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


# ==========================================
# 3. RETRIEVAL FUNCTIONS
# ==========================================
def query_sqlite(
    query_string: str, db_path: str | Path = DEFAULT_DB_PATH
):
    """Execute a read-only SELECT query against structured data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        if not query_string.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries are allowed."
        cursor.execute(query_string)
        return cursor.fetchall()
    except Exception as exc:
        return f"SQL Error: {exc}"
    finally:
        conn.close()


def search_learning_vectors(
    query_text: str,
    n_results: int = 3,
    chroma_path: str | Path = DEFAULT_CHROMA_PATH,
):
    """Find semantically similar learning notes."""
    client = _persistent_chroma_client(chroma_path)
    collection = client.get_collection(name=LEARNING_COLLECTION)
    return collection.query(query_texts=[query_text], n_results=n_results)


if __name__ == "__main__":
    applied = init_sqlite_db()
    init_chroma_db()
    print(f"Database ready. Applied migrations: {applied or 'none'}")
