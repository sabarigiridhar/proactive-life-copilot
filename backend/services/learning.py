"""Application services for searching saved learning history."""

from __future__ import annotations

from backend.core.settings import Settings
from life_copilot.retrieval.learning import search_learning_records
from life_copilot.retrieval.models import LearningSearchRequest, LearningSearchResult


def search_learning_history(
    request: LearningSearchRequest,
    settings: Settings,
) -> LearningSearchResult:
    """Search the learning index and hydrate every hit from authoritative SQLite."""
    return search_learning_records(
        request,
        db_path=settings.database_path,
        chroma_path=settings.chroma_path,
    )
