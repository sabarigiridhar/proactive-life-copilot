"""Health routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.core.dependencies import RequestIdDep, SettingsDep
from backend.models.responses import ApiResponse, success_response
from backend.services.health import get_health


router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse)
def health(settings: SettingsDep, request_id: RequestIdDep) -> ApiResponse:
    return success_response(get_health(settings), request_id)
