"""Conversation and draft-confirmation routes."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend.core.dependencies import RequestIdDep, SettingsDep
from backend.models.conversations import (
    CancelLogData,
    CancelLogRequest,
    ConfirmLogData,
    ConfirmLogRequest,
    ConversationDetailData,
    ConversationListData,
    MessageData,
    MessageRequest,
    ThreadId,
)
from backend.models.responses import ApiResponse, success_response
from backend.services.conversations import (
    cancel_log,
    confirm_log,
    get_conversation,
    get_conversations,
    send_message,
)


router = APIRouter(tags=["conversation"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _message_events(
    payload: MessageRequest,
    settings: SettingsDep,
    request_id: str,
) -> Iterator[str]:
    yield _sse_event("status", {"stage": "thinking", "request_id": request_id})
    try:
        result = send_message(payload, settings)
    except Exception:
        logging.exception("Streaming message generation failed")
        yield _sse_event(
            "error",
            {
                "message": "The message could not be completed safely.",
                "request_id": request_id,
            },
        )
        return

    for chunk in re.findall(r"\S+\s*", result.assistant_text):
        yield _sse_event("message.delta", {"delta": chunk})
    yield _sse_event("message.complete", result.model_dump(mode="json"))


@router.get("/conversations", response_model=ApiResponse[ConversationListData])
def get_conversation_list(
    settings: SettingsDep,
    request_id: RequestIdDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> ApiResponse[ConversationListData]:
    return success_response(get_conversations(settings, limit=limit), request_id)


@router.get(
    "/conversations/{thread_id}",
    response_model=ApiResponse[ConversationDetailData],
)
def get_conversation_detail(
    thread_id: ThreadId,
    settings: SettingsDep,
    request_id: RequestIdDep,
    message_limit: int = Query(default=200, ge=1, le=500),
) -> ApiResponse[ConversationDetailData]:
    conversation = get_conversation(
        thread_id,
        settings,
        message_limit=message_limit,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return success_response(conversation, request_id)


@router.post("/messages", response_model=ApiResponse[MessageData])
def post_message(
    payload: MessageRequest,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[MessageData]:
    return success_response(send_message(payload, settings), request_id)


@router.post(
    "/messages/stream",
    response_class=StreamingResponse,
    response_model=None,
    responses={
        200: {
            "description": "Server-Sent Events containing status, delta, and completion events.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
def post_message_stream(
    payload: MessageRequest,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> StreamingResponse:
    return StreamingResponse(
        _message_events(payload, settings, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/logs/confirm",
    response_model=ApiResponse[ConfirmLogData],
    status_code=status.HTTP_201_CREATED,
)
def post_log_confirmation(
    payload: ConfirmLogRequest,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[ConfirmLogData]:
    return success_response(confirm_log(payload, settings), request_id)


@router.post("/logs/cancel", response_model=ApiResponse[CancelLogData])
def post_log_cancellation(
    payload: CancelLogRequest,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[CancelLogData]:
    return success_response(cancel_log(payload, settings), request_id)
