"""Shared API response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiResponse(BaseModel):
    success: bool = True
    data: Any | None = None
    error: ApiError | None = None
    request_id: str


class DependencyHealth(BaseModel):
    status: Literal["ok", "error"]
    detail: str | None = None


class HealthData(BaseModel):
    status: Literal["ok", "degraded"]
    environment: str
    database: DependencyHealth
    vector_store: DependencyHealth


def success_response(data: Any, request_id: str) -> ApiResponse:
    return ApiResponse(success=True, data=data, request_id=request_id)


def error_response(
    *,
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> ApiResponse:
    return ApiResponse(
        success=False,
        error=ApiError(code=code, message=message, details=details),
        request_id=request_id,
    )
