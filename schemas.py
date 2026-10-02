"""Validated domain models for Life Copilot extraction and persistence."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

InputSource = Literal["text", "voice", "image", "mixed"]


class WealthLog(BaseModel):
    transaction_type: Literal["Income", "Expense"]
    amount: float = Field(gt=0, description="Amount spent or earned.")
    currency: str = Field(default="INR", min_length=1, max_length=8)
    category: str = Field(min_length=1, max_length=100)
    merchant: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, value):
        return str(value).strip().title() if value is not None else value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value):
        return str(value or "INR").strip().upper()

    @field_validator("category", "merchant", "notes", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class HealthLog(BaseModel):
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    workout_type: str | None = Field(default=None, max_length=200)
    calories_consumed: int | None = Field(default=None, ge=0, le=20000)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("workout_type", "notes", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def require_one_health_value(self):
        if all(
            value is None
            for value in (
                self.sleep_hours,
                self.workout_type,
                self.calories_consumed,
                self.notes,
            )
        ):
            raise ValueError("A health log must contain at least one value.")
        return self


class LearningLog(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    summary_text: str = Field(min_length=1, max_length=10000)
    url_reference: str | None = Field(default=None, max_length=2000)
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)

    @field_validator("topic", "summary_text", "url_reference", mode="before")
    @classmethod
    def strip_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class DailyLogDraft(BaseModel):
    entry_date: date
    source: InputSource = "text"
    original_input: str = Field(min_length=1, max_length=20000, repr=False)
    health: HealthLog | None = None
    wealth: list[WealthLog] = Field(default_factory=list)
    learning: list[LearningLog] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)
    ambiguities: list[str] = Field(default_factory=list)

    @field_validator("original_input", mode="before")
    @classmethod
    def strip_original_input(cls, value):
        return str(value).strip() if value is not None else value

    @field_validator("ambiguities", mode="before")
    @classmethod
    def normalize_ambiguities(cls, value):
        return value or []

    @model_validator(mode="after")
    def require_extracted_record(self):
        if self.health is None and not self.wealth and not self.learning:
            raise ValueError("No health, wealth, or learning information was extracted.")
        return self


class ExtractionPayload(BaseModel):
    """Model-facing shape before trusted metadata is attached."""

    health: HealthLog | None = None
    wealth: list[WealthLog] = Field(default_factory=list)
    learning: list[LearningLog] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)
    ambiguities: list[str] = Field(default_factory=list)

    @field_validator("wealth", "learning", mode="before")
    @classmethod
    def normalize_model_lists(cls, value):
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        return value


class DailyLogState(BaseModel):
    current_date: date
    wealth: list[WealthLog] = Field(default_factory=list)
    health: HealthLog | None = None
    learning: list[LearningLog] = Field(default_factory=list)

    def is_complete(self) -> bool:
        return self.health is not None and bool(self.wealth) and bool(self.learning)
