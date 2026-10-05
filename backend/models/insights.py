"""Typed contracts for weekly reviews and their supporting evidence."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class WeeklyReview(BaseModel):
    id: int = Field(gt=0)
    period_start: date
    period_end: date
    title: str
    summary: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class WeeklyReviewsData(BaseModel):
    reviews: list[WeeklyReview] = Field(default_factory=list)
    generation_available: bool = False
    message: str | None = None
