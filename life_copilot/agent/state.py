"""Shared LangGraph state shape and state helpers."""

from pathlib import Path
from typing import TypedDict

from life_copilot import storage
from life_copilot.models import InputSource


class DailyState(TypedDict, total=False):
    thread_id: str
    db_path: str
    chroma_path: str
    user_message: str
    source: InputSource
    intent: str
    draft: dict | None
    ai_response: str
    evidence: list[dict]
    date_range: dict | None
    confidence: float | None
    recent_messages: list[dict]
    conversation_summary: str | None
    last_confirmed_entities: list[dict]
    awaiting_clarification: dict | None
    reference_route: str

def _state_db_path(state: DailyState) -> str | Path:
    return state.get("db_path") or storage.DEFAULT_DB_PATH


def _state_chroma_path(state: DailyState) -> str | Path:
    return state.get("chroma_path") or storage.DEFAULT_CHROMA_PATH
