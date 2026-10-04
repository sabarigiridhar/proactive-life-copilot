"""Conversation and draft-confirmation routes."""

from __future__ import annotations

from fastapi import APIRouter, status

from backend.core.dependencies import RequestIdDep, SettingsDep
from backend.models.conversations import (
    ConfirmLogData,
    ConfirmLogRequest,
    MessageData,
    MessageRequest,
)
from backend.models.responses import ApiResponse, success_response
from backend.services.conversations import confirm_log, send_message


router = APIRouter(tags=["conversation"])


@router.post("/messages", response_model=ApiResponse[MessageData])
def post_message(
    payload: MessageRequest,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[MessageData]:
    return success_response(send_message(payload, settings), request_id)


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
