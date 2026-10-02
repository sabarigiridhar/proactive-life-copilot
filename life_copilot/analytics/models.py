"""Validated request and result contracts for structured analytics."""

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnalyticsOperation(str, Enum):
    WEALTH_TOTAL = "wealth_total"
    WEALTH_CATEGORY_BREAKDOWN = "wealth_category_breakdown"
    WEALTH_DAILY_TREND = "wealth_daily_trend"
    HEALTH_AVERAGES = "health_averages"
    WORKOUT_FREQUENCY = "workout_frequency"
    WORKOUT_STREAK = "workout_streak"


class AnalyticsRequest(BaseModel):
    """An allowlisted calculation over a bounded date range."""

    model_config = ConfigDict(extra="forbid")

    operation: AnalyticsOperation
    start_date: date
    end_date: date
    transaction_type: Literal["Income", "Expense"] = "Expense"
    category: str | None = Field(default=None, min_length=1, max_length=100)
    limit: int = Field(default=10, ge=1, le=100)

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, value):
        return str(value).strip().title() if value is not None else value

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("Analytics date ranges cannot exceed 367 days.")
        return self


class CurrencyTotal(BaseModel):
    currency: str
    total: float
    records: int = Field(ge=0)


class GroupedTotal(CurrencyTotal):
    label: str


class WealthTotalData(BaseModel):
    transaction_type: Literal["Income", "Expense"]
    totals: list[CurrencyTotal]


class WealthGroupedData(BaseModel):
    transaction_type: Literal["Income", "Expense"]
    groups: list[GroupedTotal]


class HealthAveragesData(BaseModel):
    average_sleep_hours: float | None
    average_calories: float | None
    sleep_records: int = Field(ge=0)
    calorie_records: int = Field(ge=0)


class WorkoutEntry(BaseModel):
    entry_date: date
    workout_type: str


class WorkoutFrequencyData(BaseModel):
    workout_days: int = Field(ge=0)
    workouts: list[WorkoutEntry]


class WorkoutStreakData(BaseModel):
    current_streak_days: int = Field(ge=0)
    longest_streak_days: int = Field(ge=0)


AnalyticsData = (
    WealthTotalData
    | WealthGroupedData
    | HealthAveragesData
    | WorkoutFrequencyData
    | WorkoutStreakData
)


class AnalyticsResult(BaseModel):
    """Deterministic calculation output used to construct a grounded answer."""

    operation: AnalyticsOperation
    start_date: date
    end_date: date
    data: AnalyticsData
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    matched_records: int = Field(default=0, ge=0)
