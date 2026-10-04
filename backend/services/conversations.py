"""Application services for messages and confirmed log drafts."""

from __future__ import annotations

from uuid import uuid4

from backend.core.settings import Settings
from backend.models.conversations import (
    ConfirmLogData,
    ConfirmLogRequest,
    MessageData,
    MessageRequest,
    SavedRecordCounts,
    SavedRecordIds,
)
from backend.repositories.conversations import initialize_conversation, store_message
from life_copilot.agent import workflow
from life_copilot.services.drafts import save_confirmed_draft


def _response_type(state: dict) -> str:
    if state.get("draft"):
        return "log_draft"
    if state.get("reference_route") == "clarify" or state.get(
        "awaiting_clarification"
    ):
        return "clarification"
    if state.get("intent") == "error":
        return "error"
    if state.get("intent") == "query":
        return "query_answer"
    return "message"


def send_message(request: MessageRequest, settings: Settings) -> MessageData:
    """Run one thread-scoped graph turn and persist both chat messages."""
    thread_id = request.thread_id or uuid4().hex
    initialize_conversation(thread_id, settings.database_path)
    store_message(
        thread_id,
        "user",
        request.message,
        db_path=settings.database_path,
    )

    state = workflow.app_brain.invoke(
        {
            "thread_id": thread_id,
            "db_path": str(settings.database_path),
            "chroma_path": str(settings.chroma_path),
            "user_message": request.message,
            "source": request.source,
            "entry_date": request.entry_date,
            "draft": None,
            "ai_response": "",
            "evidence": [],
            "date_range": None,
            "confidence": None,
        },
        config=workflow.thread_config(thread_id),
    )
    assistant_text = state.get("ai_response") or "No response was generated."
    response_type = _response_type(state)
    metadata = {
        "response_type": response_type,
        "evidence": state.get("evidence") or [],
        "date_range": state.get("date_range"),
        "confidence": state.get("confidence"),
    }
    store_message(
        thread_id,
        "assistant",
        assistant_text,
        db_path=settings.database_path,
        metadata=metadata,
    )
    return MessageData(
        thread_id=thread_id,
        response_type=response_type,
        assistant_text=assistant_text,
        draft=state.get("draft"),
        evidence=state.get("evidence") or [],
        date_range=state.get("date_range"),
        confidence=state.get("confidence"),
    )


def _confirmation_text(result: dict, operation: str) -> str:
    total = result["health"] + result["wealth"] + result["learning"]
    action = "Updated" if operation == "update" else "Saved"
    text = f"{action} {total} confirmed record(s)."
    if result["vector_warnings"]:
        text += " Learning was saved, but vector indexing needs attention."

    status = result["daily_status"]
    missing = [
        label
        for label, complete in (
            ("Health", status["health_complete"]),
            ("Wealth", status["wealth_reviewed"]),
            ("Learning", status["learning_complete"]),
        )
        if not complete
    ]
    if missing:
        return (
            f"{text} Still pending for {status['entry_date']}: "
            f"{', '.join(missing)}. Would you like to log one of those next?"
        )
    return f"{text} Your check-in for {status['entry_date']} is complete."


def confirm_log(request: ConfirmLogRequest, settings: Settings) -> ConfirmLogData:
    """Persist a validated draft and attach its records to conversation memory."""
    initialize_conversation(request.thread_id, settings.database_path)
    result = save_confirmed_draft(
        request.draft,
        db_path=settings.database_path,
        chroma_path=settings.chroma_path,
    )
    entities = workflow.remember_confirmed_draft(
        request.thread_id,
        result,
        db_path=settings.database_path,
    )
    assistant_text = _confirmation_text(result, request.draft.operation)
    store_message(
        request.thread_id,
        "assistant",
        assistant_text,
        db_path=settings.database_path,
        metadata={"event": "confirmed_records", "entities": entities},
    )
    warnings = (
        ["Learning was saved, but vector indexing needs attention."]
        if result["vector_warnings"]
        else []
    )
    return ConfirmLogData(
        thread_id=request.thread_id,
        assistant_text=assistant_text,
        saved=SavedRecordCounts(
            health=result["health"],
            wealth=result["wealth"],
            learning=result["learning"],
        ),
        record_ids=SavedRecordIds.model_validate(result["record_ids"]),
        daily_status=result["daily_status"],
        entities=entities,
        warnings=warnings,
    )
