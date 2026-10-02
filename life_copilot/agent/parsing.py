"""Validation helpers for model extraction payloads and entry dates."""

import json
import re
from datetime import date, timedelta

from life_copilot.models import DailyLogDraft, ExtractionPayload, InputSource

def missing_draft_domains(draft: DailyLogDraft) -> list[str]:
    """Return domains not represented in the current draft."""
    missing = []
    if draft.health is None:
        missing.append("Health")
    if not draft.wealth:
        missing.append("Wealth")
    if not draft.learning:
        missing.append("Learning")
    return missing

def resolve_entry_date(user_message: str, today: date | None = None) -> date:
    """Resolve an explicit ISO date, yesterday, or today from a message."""
    base_date = today or date.today()
    explicit_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", user_message)
    if explicit_date:
        try:
            return date.fromisoformat(explicit_date.group(0))
        except ValueError as exc:
            raise ValueError(
                f"'{explicit_date.group(0)}' is not a valid calendar date."
            ) from exc

    lowered = user_message.lower()
    if re.search(r"\byesterday\b", lowered):
        return base_date - timedelta(days=1)
    return base_date

def parse_extraction_payload(
    raw_payload: str | dict,
    user_message: str,
    source: InputSource = "text",
    today: date | None = None,
) -> DailyLogDraft:
    """Validate untrusted model output and attach trusted request metadata."""
    data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    extracted = ExtractionPayload.model_validate(data)
    return DailyLogDraft(
        entry_date=resolve_entry_date(user_message, today=today),
        source=source,
        original_input=user_message,
        health=extracted.health,
        wealth=extracted.wealth,
        learning=extracted.learning,
        confidence=extracted.confidence,
        ambiguities=extracted.ambiguities,
    )
