"""Typed HTTP client used by Streamlit to access the public backend API."""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from typing import Any, Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, ValidationError


class ApiClientError(RuntimeError):
    """A safe backend or transport error suitable for display in Streamlit."""

    def __init__(self, message: str, *, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class DailyStatusResult(BaseModel):
    entry_date: date
    health_complete: bool
    wealth_reviewed: bool
    learning_complete: bool
    is_complete: bool


class MessageResult(BaseModel):
    thread_id: str
    response_type: str
    assistant_text: str
    draft: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    date_range: dict[str, Any] | None = None
    confidence: float | None = None


class ConfirmationResult(BaseModel):
    thread_id: str
    assistant_text: str
    daily_status: DailyStatusResult
    entities: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MediaResult(BaseModel):
    text: str


class RecordPageResult(BaseModel):
    domain: str
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
    total_pages: int


class RecordMutationResult(BaseModel):
    domain: str
    record: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class RecordDeletionResult(BaseModel):
    domain: str
    deleted_id: int
    warnings: list[str] = Field(default_factory=list)


class DashboardResult(BaseModel):
    status_date: date
    daily_status: DailyStatusResult


class LifeCopilotApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
    ):
        self.base_url = f"{base_url.rstrip('/')}/"
        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(120.0, connect=5.0),
        )

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        model: type[BaseModel],
        **kwargs,
    ):
        headers = dict(kwargs.pop("headers", {}))
        headers["x-request-id"] = uuid4().hex
        try:
            response = self._client.request(
                method, path.lstrip("/"), headers=headers, **kwargs
            )
        except httpx.RequestError as exc:
            raise ApiClientError(
                "The Life Copilot API is unavailable. Check that the backend is running."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiClientError(
                "The Life Copilot API returned an unreadable response.",
                status_code=response.status_code,
            ) from exc

        if not isinstance(payload, dict):
            raise ApiClientError(
                "The Life Copilot API returned an unexpected response.",
                status_code=response.status_code,
            )

        if not response.is_success or not payload.get("success"):
            error = payload.get("error")
            message = error.get("message") if isinstance(error, dict) else None
            raise ApiClientError(
                message or "The Life Copilot API could not complete the request.",
                status_code=response.status_code,
            )
        try:
            return model.model_validate(payload.get("data"))
        except ValidationError as exc:
            raise ApiClientError(
                "The Life Copilot API returned an unexpected response.",
                status_code=response.status_code,
            ) from exc

    def send_message(
        self,
        *,
        thread_id: str,
        message: str,
        source: Literal["text", "voice", "image", "mixed"] = "text",
    ) -> MessageResult:
        return self._request(
            "POST",
            "/messages",
            MessageResult,
            json={"thread_id": thread_id, "message": message, "source": source},
        )

    def confirm_log(self, *, thread_id: str, draft: dict) -> ConfirmationResult:
        return self._request(
            "POST",
            "/logs/confirm",
            ConfirmationResult,
            json={"thread_id": thread_id, "draft": draft},
        )

    def transcribe_audio(
        self, *, filename: str, content: bytes, content_type: str
    ) -> MediaResult:
        return self._request(
            "POST",
            "/media/transcriptions",
            MediaResult,
            files={"file": (filename, content, content_type)},
        )

    def extract_image(
        self, *, filename: str, content: bytes, content_type: str
    ) -> MediaResult:
        return self._request(
            "POST",
            "/media/extractions",
            MediaResult,
            files={"file": (filename, content, content_type)},
        )

    def get_dashboard_summary(self, *, status_date: date) -> DashboardResult:
        return self._request(
            "GET",
            "/dashboard/summary",
            DashboardResult,
            params={"status_date": status_date.isoformat()},
        )

    def list_records(
        self,
        domain: Literal["wealth", "health", "learning"],
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> RecordPageResult:
        return self._request(
            "GET",
            f"/logs/{domain}",
            RecordPageResult,
            params={"page": page, "page_size": page_size},
        )

    def patch_record(
        self,
        domain: Literal["wealth", "health", "learning"],
        record_id: int,
        payload: dict,
    ) -> RecordMutationResult:
        return self._request(
            "PATCH",
            f"/logs/{domain}/{record_id}",
            RecordMutationResult,
            json=payload,
        )

    def delete_record(
        self,
        domain: Literal["wealth", "health", "learning"],
        record_id: int,
    ) -> RecordDeletionResult:
        return self._request(
            "DELETE",
            f"/logs/{domain}/{record_id}",
            RecordDeletionResult,
            params={"confirm": "true"},
        )


@lru_cache(maxsize=1)
def get_api_client() -> LifeCopilotApiClient:
    base_url = os.getenv(
        "LIFE_COPILOT_API_URL", "http://127.0.0.1:8000/api/v1"
    )
    return LifeCopilotApiClient(base_url)
