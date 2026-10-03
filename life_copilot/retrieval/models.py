"""Validated contracts for semantic learning retrieval."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LearningSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(min_length=1, max_length=2000)
    topic: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    limit: int = Field(default=3, ge=1, le=20)

    @field_validator("query_text", "topic", mode="before")
    @classmethod
    def strip_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class LearningSearchHit(BaseModel):
    record_id: int = Field(gt=0)
    entry_date: date
    topic: str
    summary_text: str
    duration_minutes: int | None = None
    url_reference: str | None = None
    distance: float | None = None


class LearningSearchResult(BaseModel):
    request: LearningSearchRequest
    hits: list[LearningSearchHit] = Field(default_factory=list)
    mode: Literal["vector", "sqlite_fallback", "empty"]
    warning: str | None = None
