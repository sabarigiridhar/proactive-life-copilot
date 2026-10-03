"""Filtered semantic search backed by authoritative SQLite learning rows."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from life_copilot.storage.base import DEFAULT_CHROMA_PATH, DEFAULT_DB_PATH
from life_copilot.storage.retrieval import (
    get_learning_records_by_ids,
    list_learning_search_candidates,
    list_learning_topics,
    search_learning_vectors,
)
from life_copilot.retrieval.models import (
    LearningSearchHit,
    LearningSearchRequest,
    LearningSearchResult,
)

_SEARCH_STOP_WORDS = {
    "a",
    "about",
    "and",
    "did",
    "do",
    "from",
    "i",
    "in",
    "learn",
    "learned",
    "learning",
    "me",
    "my",
    "notes",
    "of",
    "on",
    "show",
    "study",
    "studied",
    "the",
    "what",
}


def _date_filters(message: str, today: date) -> tuple[date | None, date | None]:
    lowered = message.lower()
    explicit = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if explicit:
        parsed = [date.fromisoformat(value) for value in explicit[:2]]
        if len(parsed) == 1 and any(term in lowered for term in ("since", "from")):
            return parsed[0], today
        return parsed[0], parsed[-1]
    if "yesterday" in lowered:
        value = today - timedelta(days=1)
        return value, value
    if "today" in lowered:
        return today, today
    if "this week" in lowered:
        return today - timedelta(days=today.weekday()), today
    if "last week" in lowered:
        this_monday = today - timedelta(days=today.weekday())
        return this_monday - timedelta(days=7), this_monday - timedelta(days=1)
    if "this month" in lowered:
        return today.replace(day=1), today
    if "last month" in lowered:
        last_day = today.replace(day=1) - timedelta(days=1)
        return last_day.replace(day=1), last_day
    recent = re.search(r"\blast\s+(\d+)\s+days?\b", lowered)
    if recent:
        days = max(1, min(int(recent.group(1)), 367))
        return today - timedelta(days=days - 1), today
    return None, None


def _topic_filter(message: str, topics: list[str]) -> str | None:
    for topic in topics:
        if re.search(rf"(?<!\w){re.escape(topic)}(?!\w)", message, re.IGNORECASE):
            return topic

    explicit = re.search(
        r"\btopic\s*:\s*(.+?)(?=\s+(?:from|since|today|yesterday|this|last)\b|[?.!,]|$)",
        message,
        re.IGNORECASE,
    )
    if not explicit:
        return None
    requested = explicit.group(1).strip(" \"'")
    return next(
        (topic for topic in topics if topic.casefold() == requested.casefold()),
        requested,
    )


def create_learning_search_request(
    message: str,
    *,
    today: date | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    limit: int = 3,
) -> LearningSearchRequest:
    """Extract only unambiguous date and known-topic filters from a question."""
    start_date, end_date = _date_filters(message, today or date.today())
    topic = _topic_filter(message, list_learning_topics(db_path))
    return LearningSearchRequest(
        query_text=message,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


def _record_id(vector_id: object, metadata: dict | None) -> int | None:
    value = (metadata or {}).get("sqlite_id")
    if value is None:
        match = re.fullmatch(r"learning_(\d+)", str(vector_id))
        value = match.group(1) if match else None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _hit(record: dict, distance: float | None = None) -> LearningSearchHit:
    return LearningSearchHit(
        record_id=record["id"],
        entry_date=record["entry_date"],
        topic=record["topic"],
        summary_text=record.get("summary_text") or "No summary was recorded.",
        duration_minutes=record.get("duration_minutes"),
        url_reference=record.get("url_reference"),
        distance=distance,
    )


def _keyword_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) > 1 and token not in _SEARCH_STOP_WORDS
    }


def _sqlite_fallback(
    request: LearningSearchRequest,
    *,
    db_path: str | Path,
) -> list[LearningSearchHit]:
    records = list_learning_search_candidates(
        topic=request.topic,
        start_date=request.start_date,
        end_date=request.end_date,
        db_path=db_path,
    )
    query_tokens = _keyword_tokens(request.query_text)
    ranked = []
    for record in records:
        topic_tokens = _keyword_tokens(record["topic"])
        summary_tokens = _keyword_tokens(record.get("summary_text") or "")
        score = 3 * len(query_tokens & topic_tokens) + len(query_tokens & summary_tokens)
        if not query_tokens or request.topic or score:
            ranked.append((score, record["entry_date"], record["id"], record))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [_hit(item[3]) for item in ranked[: request.limit]]


def search_learning_records(
    request: LearningSearchRequest | dict,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    chroma_path: str | Path = DEFAULT_CHROMA_PATH,
    collection=None,
) -> LearningSearchResult:
    """Rank with Chroma, then hydrate and verify every result from SQLite."""
    validated = LearningSearchRequest.model_validate(request)
    vector_warning = None
    try:
        raw = search_learning_vectors(
            validated.query_text,
            validated.limit,
            chroma_path,
            topic=validated.topic,
            start_date=validated.start_date,
            end_date=validated.end_date,
            collection=collection,
        )
        ids = (raw.get("ids") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        ranked_ids = []
        distance_by_id = {}
        for index, vector_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else None
            record_id = _record_id(vector_id, metadata)
            if record_id is None or record_id in distance_by_id:
                continue
            ranked_ids.append(record_id)
            distance_by_id[record_id] = (
                distances[index] if index < len(distances) else None
            )
        records = get_learning_records_by_ids(ranked_ids, db_path)
        hits = [
            _hit(records[record_id], distance_by_id[record_id])
            for record_id in ranked_ids
            if record_id in records
        ]
        if hits:
            return LearningSearchResult(
                request=validated,
                hits=hits,
                mode="vector",
            )
        vector_warning = "The semantic index returned no verified records."
    except Exception:
        vector_warning = "The semantic index is currently unavailable."

    fallback_hits = _sqlite_fallback(validated, db_path=db_path)
    if fallback_hits:
        return LearningSearchResult(
            request=validated,
            hits=fallback_hits,
            mode="sqlite_fallback",
            warning=f"{vector_warning} Showing keyword matches from SQLite.",
        )
    return LearningSearchResult(
        request=validated,
        mode="empty",
        warning=f"{vector_warning} No matching SQLite learning records were found.",
    )


def answer_learning_search(result: LearningSearchResult) -> str:
    """Format a deterministic answer containing only verified record fields."""
    if not result.hits:
        return result.warning or "I could not find a matching learning record."

    lines = [f"I found {len(result.hits)} matching learning record(s):"]
    for hit in result.hits:
        duration = (
            f" ({hit.duration_minutes} minutes)"
            if hit.duration_minutes is not None
            else ""
        )
        link = f" Source: {hit.url_reference}" if hit.url_reference else ""
        lines.append(
            f"- {hit.entry_date.isoformat()} | {hit.topic}{duration}: "
            f"{hit.summary_text} [Learning #{hit.record_id}].{link}"
        )
    if result.mode == "sqlite_fallback" and result.warning:
        lines.append(result.warning)
    return "\n".join(lines)
