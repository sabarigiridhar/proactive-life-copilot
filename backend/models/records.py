"""Typed contracts for domain records and dashboard summaries."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.conversations import DailyStatusData


class RecordDomain(str, Enum):
    WEALTH = "wealth"
    HEALTH = "health"
    LEARNING = "learning"


class RecordListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
    start_date: date | None = None
    end_date: date | None = None
    search: str | None = Field(default=None, min_length=1, max_length=200)
    source: str | None = Field(default=None, min_length=1, max_length=20)
    transaction_type: Literal["Income", "Expense"] | None = None
    currency: str | None = Field(default=None, min_length=1, max_length=8)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    merchant: str | None = Field(default=None, min_length=1, max_length=200)
    workout_type: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class RecordPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_date: date | None = None
    transaction_type: Literal["Income", "Expense"] | None = None
    amount: float | None = None
    currency: str | None = None
    category: str | None = None
    merchant: str | None = None
    sleep_hours: float | None = None
    workout_type: str | None = None
    calories_consumed: int | None = None
    notes: str | None = None
    topic: str | None = None
    summary_text: str | None = None
    duration_minutes: int | None = None
    url_reference: str | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one record field must be supplied.")
        return self


class RecordBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    entry_date: date
    source: str
    created_at: datetime
    updated_at: datetime


class WealthRecord(RecordBase):
    transaction_type: Literal["Income", "Expense"]
    amount: float = Field(ge=0)
    currency: str
    category: str
    merchant: str | None = None
    notes: str | None = None

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_legacy_transaction_type(cls, value):
        if isinstance(value, str) and value.lower() in {"income", "expense"}:
            return value.title()
        return value


class HealthRecord(RecordBase):
    sleep_hours: float | None = None
    workout_type: str | None = None
    calories_consumed: int | None = None
    notes: str | None = None


class LearningRecord(RecordBase):
    topic: str
    summary_text: str | None = None
    duration_minutes: int | None = None
    url_reference: str | None = None


DomainRecord = Annotated[
    WealthRecord | HealthRecord | LearningRecord,
    Field(union_mode="left_to_right"),
]


class RecordPage(BaseModel):
    domain: RecordDomain
    items: list[DomainRecord]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class RecordMutationData(BaseModel):
    domain: RecordDomain
    record: DomainRecord
    statuses: dict[str, DailyStatusData]
    warnings: list[str] = Field(default_factory=list)


class RecordDeletionData(BaseModel):
    domain: RecordDomain
    deleted_id: int = Field(gt=0)
    status: DailyStatusData
    warnings: list[str] = Field(default_factory=list)


class DashboardDateRange(BaseModel):
    start_date: date
    end_date: date


class CurrencySummary(BaseModel):
    currency: str
    total: float
    records: int = Field(ge=0)


class CurrencyNet(BaseModel):
    currency: str
    income: float
    expense: float
    net: float


class CategorySummary(CurrencySummary):
    category: str


class DailyWealthPoint(BaseModel):
    entry_date: date
    currency: str
    income: float
    expense: float
    net: float


class WealthDashboard(BaseModel):
    income: list[CurrencySummary]
    expenses: list[CurrencySummary]
    net: list[CurrencyNet]
    categories: list[CategorySummary]
    daily: list[DailyWealthPoint]


class DailyHealthPoint(BaseModel):
    entry_date: date
    sleep_hours: float | None = None
    calories_consumed: int | None = None
    workout_type: str | None = None


class HealthDashboard(BaseModel):
    average_sleep_hours: float | None = None
    average_calories: float | None = None
    sleep_records: int = Field(ge=0)
    calorie_records: int = Field(ge=0)
    workout_days: int = Field(ge=0)
    daily: list[DailyHealthPoint]


class TopicSummary(BaseModel):
    topic: str
    minutes: int = Field(ge=0)
    sessions: int = Field(ge=1)


class DailyLearningPoint(BaseModel):
    entry_date: date
    minutes: int = Field(ge=0)
    sessions: int = Field(ge=1)


class LearningDashboard(BaseModel):
    total_minutes: int = Field(ge=0)
    sessions: int = Field(ge=0)
    learning_days: int = Field(ge=0)
    current_streak_days: int = Field(ge=0)
    longest_streak_days: int = Field(ge=0)
    topics: list[TopicSummary]
    daily: list[DailyLearningPoint]


class DashboardSummary(BaseModel):
    date_range: DashboardDateRange
    status_date: date
    daily_status: DailyStatusData
    wealth: WealthDashboard
    health: HealthDashboard
    learning: LearningDashboard


class DashboardQuery(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    status_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be on or after start_date.")
            if (self.end_date - self.start_date).days > 366:
                raise ValueError("Dashboard date ranges cannot exceed 367 days.")
        return self
