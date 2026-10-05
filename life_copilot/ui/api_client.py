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


class LearningSearchRequestResult(BaseModel):
    query_text: str
    topic: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    limit: int


class LearningSearchHitResult(BaseModel):
    record_id: int
    entry_date: date
    topic: str
    summary_text: str
    duration_minutes: int | None = None
    url_reference: str | None = None
    distance: float | None = None


class LearningSearchResult(BaseModel):
    request: LearningSearchRequestResult
    hits: list[LearningSearchHitResult] = Field(default_factory=list)
    mode: Literal["vector", "sqlite_fallback", "empty"]
    warning: str | None = None


class DashboardDateRangeResult(BaseModel):
    start_date: date
    end_date: date


class CurrencySummaryResult(BaseModel):
    currency: str
    total: float
    records: int


class CurrencyNetResult(BaseModel):
    currency: str
    income: float
    expense: float
    net: float


class CategorySummaryResult(CurrencySummaryResult):
    category: str


class DailyWealthResult(BaseModel):
    entry_date: date
    currency: str
    income: float
    expense: float
    net: float


class WealthDashboardResult(BaseModel):
    income: list[CurrencySummaryResult]
    expenses: list[CurrencySummaryResult]
    net: list[CurrencyNetResult]
    categories: list[CategorySummaryResult]
    daily: list[DailyWealthResult]


class DailyHealthResult(BaseModel):
    entry_date: date
    sleep_hours: float | None = None
    calories_consumed: int | None = None
    workout_type: str | None = None


class HealthDashboardResult(BaseModel):
    average_sleep_hours: float | None = None
    average_calories: float | None = None
    sleep_records: int
    calorie_records: int
    workout_days: int
    daily: list[DailyHealthResult]


class TopicSummaryResult(BaseModel):
    topic: str
    minutes: int
    sessions: int


class DailyLearningResult(BaseModel):
    entry_date: date
    minutes: int
    sessions: int


class LearningDashboardResult(BaseModel):
    total_minutes: int
    sessions: int
    learning_days: int
    current_streak_days: int
    longest_streak_days: int
    topics: list[TopicSummaryResult]
    daily: list[DailyLearningResult]


class DashboardResult(BaseModel):
    date_range: DashboardDateRangeResult
    status_date: date
    daily_status: DailyStatusResult
    wealth: WealthDashboardResult
    health: HealthDashboardResult
    learning: LearningDashboardResult


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

    def get_dashboard_summary(
        self,
        *,
        status_date: date,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> DashboardResult:
        params = {"status_date": status_date.isoformat()}
        if start_date is not None:
            params["start_date"] = start_date.isoformat()
        if end_date is not None:
            params["end_date"] = end_date.isoformat()
        return self._request(
            "GET",
            "/dashboard/summary",
            DashboardResult,
            params=params,
        )

    def search_learning(
        self,
        query: str,
        *,
        topic: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 10,
    ) -> LearningSearchResult:
        params: dict[str, Any] = {"query": query, "limit": limit}
        optional_params = {
            "topic": topic,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }
        params.update(
            {key: value for key, value in optional_params.items() if value is not None}
        )
        return self._request(
            "GET",
            "/learning/search",
            LearningSearchResult,
            params=params,
        )

    def list_records(
        self,
        domain: Literal["wealth", "health", "learning"],
        *,
        page: int = 1,
        page_size: int = 50,
        start_date: date | None = None,
        end_date: date | None = None,
        search: str | None = None,
        source: str | None = None,
        transaction_type: Literal["Income", "Expense"] | None = None,
        currency: str | None = None,
        category: str | None = None,
        merchant: str | None = None,
        workout_type: str | None = None,
        topic: str | None = None,
    ) -> RecordPageResult:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        optional_params = {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "search": search,
            "source": source,
            "transaction_type": transaction_type,
            "currency": currency,
            "category": category,
            "merchant": merchant,
            "workout_type": workout_type,
            "topic": topic,
        }
        params.update(
            {key: value for key, value in optional_params.items() if value is not None}
        )
        return self._request(
            "GET",
            f"/logs/{domain}",
            RecordPageResult,
            params=params,
        )

    def list_all_records(
        self,
        domain: Literal["wealth", "health", "learning"],
        **filters,
    ) -> list[dict[str, Any]]:
        """Load all filtered records through bounded API pages."""
        records: list[dict[str, Any]] = []
        page_number = 1
        while True:
            page = self.list_records(
                domain,
                page=page_number,
                page_size=200,
                **filters,
            )
            records.extend(page.items)
            if page_number >= page.total_pages or not page.items:
                return records
            if page_number >= 500:
                raise ApiClientError(
                    "The filtered record set is too large to load safely."
                )
            page_number += 1

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
