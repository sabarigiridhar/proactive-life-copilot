"""Read-only structured and semantic retrieval helpers."""

from __future__ import annotations

from pathlib import Path

from life_copilot.storage.base import (
    DEFAULT_CHROMA_PATH,
    DEFAULT_DB_PATH,
    LEARNING_COLLECTION,
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
):
    """Find semantically similar learning notes."""
    client = _persistent_chroma_client(chroma_path)
    collection = client.get_collection(name=LEARNING_COLLECTION)
    return collection.query(query_texts=[query_text], n_results=n_results)
