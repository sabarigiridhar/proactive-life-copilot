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
    CROSS_DOMAIN_COMPARISON = "cross_domain_comparison"


class DailyMetric(str, Enum):
    SLEEP_HOURS = "sleep_hours"
    CALORIES_CONSUMED = "calories_consumed"
    EXPENSE_AMOUNT = "expense_amount"
    LEARNING_MINUTES = "learning_minutes"
    LEARNING_SESSIONS = "learning_sessions"
    WORKOUT_LOGGED = "workout_logged"


class ComparisonOperator(str, Enum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"


METRIC_DOMAINS = {
    DailyMetric.SLEEP_HOURS: "health",
    DailyMetric.CALORIES_CONSUMED: "health",
    DailyMetric.WORKOUT_LOGGED: "health",
    DailyMetric.EXPENSE_AMOUNT: "wealth",
    DailyMetric.LEARNING_MINUTES: "learning",
    DailyMetric.LEARNING_SESSIONS: "learning",
}


class AnalyticsRequest(BaseModel):
    """An allowlisted calculation over a bounded date range."""

    model_config = ConfigDict(extra="forbid")

    operation: AnalyticsOperation
    start_date: date
    end_date: date
    transaction_type: Literal["Income", "Expense"] = "Expense"
    category: str | None = Field(default=None, min_length=1, max_length=100)
    currency: str = Field(default="INR", min_length=1, max_length=8)
    limit: int = Field(default=10, ge=1, le=100)
    outcome_metric: DailyMetric | None = None
    condition_metric: DailyMetric | None = None
    comparison_operator: ComparisonOperator | None = None
    threshold: float | None = Field(default=None, ge=0)

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, value):
        return str(value).strip().title() if value is not None else value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value):
        return str(value or "INR").strip().upper()

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
        if self.operation == AnalyticsOperation.CROSS_DOMAIN_COMPARISON:
            required = (
                self.outcome_metric,
                self.condition_metric,
                self.comparison_operator,
                self.threshold,
            )
            if any(value is None for value in required):
                raise ValueError(
                    "Cross-domain comparisons require outcome_metric, "
                    "condition_metric, comparison_operator, and threshold."
                )
            if METRIC_DOMAINS[self.outcome_metric] == METRIC_DOMAINS[
                self.condition_metric
            ]:
                raise ValueError("Cross-domain metrics must come from different domains.")
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


class DailyHealthAggregate(BaseModel):
    sleep_hours: float | None = None
    calories_consumed: int | None = None
    workout_logged: bool = False
    workout_type: str | None = None


class DailyMoneyTotal(BaseModel):
    transaction_type: Literal["Income", "Expense"]
    currency: str
    category: str
    total: float
    records: int = Field(ge=1)


class DailyWealthAggregate(BaseModel):
    totals: list[DailyMoneyTotal] = Field(default_factory=list)


class DailyLearningAggregate(BaseModel):
    duration_minutes: int = Field(ge=0)
    sessions: int = Field(ge=1)
    topics: list[str] = Field(default_factory=list)


class DailyAggregate(BaseModel):
    entry_date: date
    health: DailyHealthAggregate | None = None
    wealth: DailyWealthAggregate | None = None
    learning: DailyLearningAggregate | None = None


class CrossDomainComparisonData(BaseModel):
    outcome_metric: DailyMetric
    condition_metric: DailyMetric
    comparison_operator: ComparisonOperator
    threshold: float
    category: str | None = None
    currency: str | None = None
    condition_days: int = Field(ge=0)
    comparison_days: int = Field(ge=0)
    condition_average: float | None = None
    comparison_average: float | None = None
    difference: float | None = None
    minimum_group_size: int = Field(ge=1)
    enough_data: bool
    observation: Literal["higher", "lower", "same", "insufficient"]


AnalyticsData = (
    WealthTotalData
    | WealthGroupedData
    | HealthAveragesData
    | WorkoutFrequencyData
    | WorkoutStreakData
    | CrossDomainComparisonData
)


class AnalyticsResult(BaseModel):
    """Deterministic calculation output used to construct a grounded answer."""

    operation: AnalyticsOperation
    start_date: date
    end_date: date
    data: AnalyticsData
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    matched_records: int = Field(default=0, ge=0)


class AnswerDateRange(BaseModel):
    start_date: date
    end_date: date


class AnalyticsAnswer(BaseModel):
    """Serializable answer contract for UI and future API responses."""

    text: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    date_range: AnswerDateRange
    confidence: float = Field(ge=0, le=1)
