"""Analytics execution and deterministic user-facing answer formatting."""

from pathlib import Path

from life_copilot.analytics.models import (
    AnalyticsOperation,
    AnalyticsRequest,
    AnalyticsResult,
)
from life_copilot.storage.analytics import execute_analytics
from life_copilot.storage.base import DEFAULT_DB_PATH


def run_analytics(
    request: AnalyticsRequest, db_path: str | Path = DEFAULT_DB_PATH
) -> AnalyticsResult:
    return execute_analytics(request, db_path=db_path)


def _date_text(result: AnalyticsResult) -> str:
    if result.start_date == result.end_date:
        return f"on {result.start_date.isoformat()}"
    return f"from {result.start_date.isoformat()} to {result.end_date.isoformat()}"


def answer_analytics_request(result: AnalyticsResult) -> str:
    """Create a grounded answer using only calculated result values."""
    period = _date_text(result)
    operation = result.operation
    if operation == AnalyticsOperation.WEALTH_TOTAL:
        totals = result.data.totals
        if not totals:
            return f"No {result.data.transaction_type.lower()} records were found {period}."
        amounts = ", ".join(
            f"{row.currency} {row.total:.2f}" for row in totals
        )
        return (
            f"Your total {result.data.transaction_type.lower()} amount {period} "
            f"is {amounts} across {result.matched_records} transaction(s)."
        )
    if operation in {
        AnalyticsOperation.WEALTH_CATEGORY_BREAKDOWN,
        AnalyticsOperation.WEALTH_DAILY_TREND,
    }:
        groups = result.data.groups
        if not groups:
            return f"No matching transactions were found {period}."
        details = "; ".join(
            f"{row.label}: {row.currency} {row.total:.2f}"
            for row in groups
        )
        label = "category breakdown" if "category" in operation.value else "daily trend"
        return f"Your {result.data.transaction_type.lower()} {label} {period} is {details}."
    if operation == AnalyticsOperation.HEALTH_AVERAGES:
        data = result.data
        parts = []
        if data.average_sleep_hours is not None:
            parts.append(f"average sleep was {data.average_sleep_hours:.2f} hours")
        if data.average_calories is not None:
            parts.append(f"average calories were {data.average_calories:.2f}")
        return f"No health measurements were found {period}." if not parts else f"{period.title()}, " + " and ".join(parts) + "."
    if operation == AnalyticsOperation.WORKOUT_FREQUENCY:
        return f"You logged workouts on {result.data.workout_days} day(s) {period}."
    return (
        f"Your current workout streak is {result.data.current_streak_days} day(s), "
        f"and your longest streak {period} is {result.data.longest_streak_days} day(s)."
    )
