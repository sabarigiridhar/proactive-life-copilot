"""Typed contracts for conversation and draft-confirmation endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

from life_copilot.models import DailyLogDraft, InputSource


ThreadId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]


class MessageRequest(BaseModel):
    thread_id: ThreadId | None = None
    message: str = Field(min_length=1, max_length=20_000)
    entry_date: date | None = None
    source: InputSource = "text"

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank.")
        return value


class AnswerDateRange(BaseModel):
    start_date: date
    end_date: date


class MessageData(BaseModel):
    thread_id: ThreadId
    response_type: Literal[
        "log_draft", "query_answer", "clarification", "message", "error"
    ]
    assistant_text: str
    draft: DailyLogDraft | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    date_range: AnswerDateRange | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ConfirmLogRequest(BaseModel):
    thread_id: ThreadId
    draft: DailyLogDraft


class SavedRecordCounts(BaseModel):
    health: int = Field(ge=0)
    wealth: int = Field(ge=0)
    learning: int = Field(ge=0)


class SavedRecordIds(BaseModel):
    health: list[int] = Field(default_factory=list)
    wealth: list[int] = Field(default_factory=list)
    learning: list[int] = Field(default_factory=list)


class DailyStatusData(BaseModel):
    entry_date: date
    health_complete: bool
    wealth_reviewed: bool
    learning_complete: bool
    is_complete: bool


class ConfirmLogData(BaseModel):
    thread_id: ThreadId
    response_type: Literal["confirmation"] = "confirmation"
    assistant_text: str
    saved: SavedRecordCounts
    record_ids: SavedRecordIds
    daily_status: DailyStatusData
    entities: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
