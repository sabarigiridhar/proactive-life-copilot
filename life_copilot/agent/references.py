"""Deterministic resolution of follow-up references to saved records."""

import re

from life_copilot import storage as db_utils
from life_copilot.agent.state import DailyState, _state_db_path
from life_copilot.models import DailyLogDraft

REFERENCE_AMOUNT_PATTERN = re.compile(
    r"\b(?:add|increase)\s+(?:(?:rs\.?|inr)\s*)?"
    r"(?P<amount>\d+(?:\.\d+)?)\s+(?:more\s+)?(?:to\s+)?(?:that|it)\b",
    re.IGNORECASE,
)

def _candidate_label(entity: dict) -> str:
    details = entity.get("merchant") or entity.get("category") or "transaction"
    amount = entity.get("amount")
    amount_text = f" {entity.get('currency', 'INR')} {amount:g}" if amount else ""
    return f"#{entity['record_id']} {details}{amount_text}"

def _select_candidate(message: str, candidates: list[dict]) -> dict | None:
    lowered = message.lower()
    id_match = re.search(r"(?:#|record\s*)(\d+)", lowered)
    if id_match:
        record_id = int(id_match.group(1))
        return next(
            (item for item in candidates if item.get("record_id") == record_id), None
        )

    ordinals = {"first": 0, "second": 1, "third": 2, "last": len(candidates) - 1}
    for word, index in ordinals.items():
        if re.search(rf"\b{word}\b", lowered) and 0 <= index < len(candidates):
            return candidates[index]

    matches = []
    for item in candidates:
        searchable = " ".join(
            str(item.get(field) or "")
            for field in ("merchant", "category", "notes", "entry_date")
        ).lower()
        terms = [term for term in re.findall(r"[a-z0-9]+", searchable) if len(term) > 2]
        if any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms):
            matches.append(item)
    return matches[0] if len(matches) == 1 else None

def _wealth_update_draft(
    state: DailyState, candidate: dict, amount_delta: float
) -> DailyLogDraft | None:
    record = db_utils.get_domain_log(
        "wealth", candidate["record_id"], db_path=_state_db_path(state)
    )
    if record is None:
        return None
    wealth = {
        key: record.get(key)
        for key in (
            "transaction_type",
            "amount",
            "currency",
            "category",
            "merchant",
            "notes",
        )
    }
    wealth["amount"] = float(wealth["amount"]) + amount_delta
    return DailyLogDraft(
        entry_date=record["entry_date"],
        source=state.get("source", "text"),
        original_input=state.get("user_message", "Update prior transaction"),
        wealth=[wealth],
        confidence=1.0,
        operation="update",
        target_domain="wealth",
        target_record_id=record["id"],
    )

def _clarification_response(candidates: list[dict]) -> str:
    options = ", ".join(_candidate_label(item) for item in candidates)
    return f"Which transaction did you mean: {options}? Nothing has been changed yet."

def resolve_reference_node(state: DailyState):
    """Resolve deterministic follow-ups before asking the model to classify intent."""
    message = state.get("user_message", "").strip()
    awaiting = state.get("awaiting_clarification")
    if awaiting:
        if message.lower() in {"cancel", "never mind", "nevermind"}:
            return {
                "reference_route": "clarify",
                "awaiting_clarification": None,
                "draft": None,
                "ai_response": "Okay, I cancelled that update.",
            }
        candidates = awaiting.get("candidates", [])
        selected = _select_candidate(message, candidates)
        if selected:
            draft = _wealth_update_draft(state, selected, awaiting["amount_delta"])
            if draft:
                return {
                    "reference_route": "resolved",
                    "awaiting_clarification": None,
                    "draft": draft.model_dump(mode="json"),
                    "ai_response": (
                        f"I prepared an update for {_candidate_label(selected)}. "
                        "Review it before saving."
                    ),
                }
        return {
            "reference_route": "clarify",
            "draft": None,
            "ai_response": _clarification_response(candidates),
        }

    reference = REFERENCE_AMOUNT_PATTERN.search(message)
    if not reference:
        return {"reference_route": "continue", "awaiting_clarification": None}

    candidates = [
        entity
        for entity in (state.get("last_confirmed_entities") or [])
        if entity.get("domain") == "wealth" and entity.get("record_id")
    ]
    if not candidates:
        return {
            "reference_route": "clarify",
            "draft": None,
            "ai_response": (
                "I cannot tell which saved transaction 'that' refers to. "
                "Please name the merchant, category, or record ID."
            ),
        }

    amount_delta = float(reference.group("amount"))
    if len(candidates) > 1:
        return {
            "reference_route": "clarify",
            "awaiting_clarification": {
                "amount_delta": amount_delta,
                "candidates": candidates,
            },
            "draft": None,
            "ai_response": _clarification_response(candidates),
        }

    draft = _wealth_update_draft(state, candidates[0], amount_delta)
    if draft is None:
        return {
            "reference_route": "clarify",
            "draft": None,
            "ai_response": "That transaction no longer exists. Nothing was changed.",
        }
    return {
        "reference_route": "resolved",
        "awaiting_clarification": None,
        "draft": draft.model_dump(mode="json"),
        "ai_response": (
            f"I prepared an update for {_candidate_label(candidates[0])}. "
            "Review it before saving."
        ),
    }
