"""Shared API response models."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


ResponseData = TypeVar("ResponseData")


class ApiResponse(BaseModel, Generic[ResponseData]):
    success: bool = True
    data: ResponseData | None = None
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


def success_response(data: ResponseData, request_id: str) -> ApiResponse[ResponseData]:
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
