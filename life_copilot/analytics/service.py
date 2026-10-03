"""Analytics execution and deterministic user-facing answer formatting."""

from datetime import date, timedelta
from pathlib import Path

from life_copilot.analytics.models import (
    AnalyticsAnswer,
    AnalyticsOperation,
    AnalyticsRequest,
    AnalyticsResult,
    ComparisonOperator,
    DailyMetric,
)
from life_copilot.storage.analytics import execute_analytics
from life_copilot.storage.base import DEFAULT_DB_PATH


class GroundingError(ValueError):
    """Raised when calculated data cannot be reproduced from its evidence."""


def run_analytics(
    request: AnalyticsRequest, db_path: str | Path = DEFAULT_DB_PATH
) -> AnalyticsResult:
    return execute_analytics(request, db_path=db_path)


def _date_text(result: AnalyticsResult) -> str:
    if result.start_date == result.end_date:
        return f"on {result.start_date.isoformat()}"
    return f"from {result.start_date.isoformat()} to {result.end_date.isoformat()}"


def _metric_label(metric: DailyMetric, result: AnalyticsResult) -> str:
    if metric == DailyMetric.EXPENSE_AMOUNT:
        category = result.data.category
        return f"{category} expenses" if category else "expenses"
    return {
        DailyMetric.SLEEP_HOURS: "sleep",
        DailyMetric.CALORIES_CONSUMED: "calories consumed",
        DailyMetric.LEARNING_MINUTES: "learning time",
        DailyMetric.LEARNING_SESSIONS: "learning sessions",
        DailyMetric.WORKOUT_LOGGED: "workout completion",
    }[metric]


def _metric_value(metric: DailyMetric, value: float, result: AnalyticsResult) -> str:
    if metric == DailyMetric.EXPENSE_AMOUNT:
        return f"{result.data.currency} {value:.2f}"
    if metric == DailyMetric.SLEEP_HOURS:
        return f"{value:.2f} hours"
    if metric == DailyMetric.CALORIES_CONSUMED:
        return f"{value:.2f} calories"
    if metric == DailyMetric.LEARNING_MINUTES:
        return f"{value:.2f} minutes"
    if metric == DailyMetric.LEARNING_SESSIONS:
        return f"{value:.2f} sessions"
    return f"{value:.2f} per day"


def _operator_text(operator: ComparisonOperator) -> str:
    return {
        ComparisonOperator.GT: "more than",
        ComparisonOperator.GTE: "at least",
        ComparisonOperator.LT: "less than",
        ComparisonOperator.LTE: "at most",
    }[operator]


def _cross_domain_text(result: AnalyticsResult) -> str:
    data = result.data
    condition_label = _metric_label(data.condition_metric, result)
    outcome_label = _metric_label(data.outcome_metric, result)
    threshold = _metric_value(data.condition_metric, data.threshold, result)
    condition = (
        f"{condition_label} were {_operator_text(data.comparison_operator)} "
        f"{threshold}"
    )
    if not data.enough_data:
        return (
            f"I found {data.condition_days} qualifying day(s) where {condition} "
            f"and {data.comparison_days} comparison day(s) {_date_text(result)}. "
            f"At least {data.minimum_group_size} days in each group are required, "
            f"so there is not enough data to compare {outcome_label} reliably."
        )

    condition_average = _metric_value(
        data.outcome_metric, data.condition_average, result
    )
    comparison_average = _metric_value(
        data.outcome_metric, data.comparison_average, result
    )
    difference = _metric_value(data.outcome_metric, abs(data.difference), result)
    direction = data.observation
    if direction == "same":
        comparison = "the same as"
    else:
        comparison = f"{difference} {direction} than"
    return (
        f"On {data.condition_days} day(s) when {condition}, average {outcome_label} "
        f"was {condition_average}. Across {data.comparison_days} comparison day(s), "
        f"it was {comparison_average}; the threshold-group average was {comparison} "
        "the comparison average. This is an observational comparison, not evidence "
        "that one metric caused the other."
    )


def _answer_text(result: AnalyticsResult) -> str:
    """Create grounded text using only calculated result values."""
    period = _date_text(result)
    operation = result.operation
    if operation == AnalyticsOperation.CROSS_DOMAIN_COMPARISON:
        return _cross_domain_text(result)
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
        if not parts:
            return f"No health measurements were found {period}."
        return f"{period.title()}, " + " and ".join(parts) + "."
    if operation == AnalyticsOperation.WORKOUT_FREQUENCY:
        return f"You logged workouts on {result.data.workout_days} day(s) {period}."
    return (
        f"Your current workout streak is {result.data.current_streak_days} day(s), "
        f"and your longest streak {period} is {result.data.longest_streak_days} day(s)."
    )


def _answer_confidence(result: AnalyticsResult) -> float:
    if result.operation != AnalyticsOperation.CROSS_DOMAIN_COMPARISON:
        return 1.0 if result.matched_records else 0.0
    data = result.data
    if not data.enough_data:
        smallest_group = min(data.condition_days, data.comparison_days)
        return round(
            0.49 * min(smallest_group / data.minimum_group_size, 1.0),
            2,
        )
    extra_days = data.condition_days + data.comparison_days - (
        2 * data.minimum_group_size
    )
    return round(min(0.95, 0.7 + max(extra_days, 0) * 0.03), 2)


def _rounded_average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def verify_analytics_result(result: AnalyticsResult) -> None:
    """Reject numerical result fields that are not reproduced by evidence."""
    operation = result.operation
    if operation == AnalyticsOperation.WEALTH_TOTAL:
        expected = [row.model_dump() for row in result.data.totals]
        matched = sum(row.records for row in result.data.totals)
    elif operation in {
        AnalyticsOperation.WEALTH_CATEGORY_BREAKDOWN,
        AnalyticsOperation.WEALTH_DAILY_TREND,
    }:
        expected = [row.model_dump() for row in result.data.groups]
        matched = sum(row.records for row in result.data.groups)
    elif operation == AnalyticsOperation.HEALTH_AVERAGES:
        expected = [result.data.model_dump()]
        matched = max(result.data.sleep_records, result.data.calorie_records)
    elif operation == AnalyticsOperation.WORKOUT_FREQUENCY:
        expected = [row.model_dump(mode="json") for row in result.data.workouts]
        matched = len(expected)
        if result.data.workout_days != matched:
            raise GroundingError("Workout count did not match its evidence.")
    elif operation == AnalyticsOperation.WORKOUT_STREAK:
        expected = result.evidence
        dates = sorted(
            {date.fromisoformat(row["entry_date"]) for row in result.evidence}
        )
        longest = 0
        run = 0
        previous = None
        for workout_date in dates:
            run = (
                run + 1
                if previous and workout_date == previous + timedelta(days=1)
                else 1
            )
            longest = max(longest, run)
            previous = workout_date
        current = 0
        expected_date = result.end_date
        for workout_date in reversed(dates):
            if workout_date != expected_date:
                break
            current += 1
            expected_date -= timedelta(days=1)
        if (
            result.data.current_streak_days != current
            or result.data.longest_streak_days != longest
        ):
            raise GroundingError("Workout streak did not match its evidence.")
        matched = len(result.evidence)
    else:
        expected = result.evidence
        condition_values = [
            float(row["outcome_value"])
            for row in result.evidence
            if row["condition_met"]
        ]
        comparison_values = [
            float(row["outcome_value"])
            for row in result.evidence
            if not row["condition_met"]
        ]
        condition_average = _rounded_average(condition_values)
        comparison_average = _rounded_average(comparison_values)
        difference = (
            round(condition_average - comparison_average, 2)
            if condition_average is not None and comparison_average is not None
            else None
        )
        if (
            result.data.condition_days != len(condition_values)
            or result.data.comparison_days != len(comparison_values)
            or result.data.condition_average != condition_average
            or result.data.comparison_average != comparison_average
            or result.data.difference != difference
        ):
            raise GroundingError("Cross-domain values did not match their evidence.")
        matched = len(result.evidence)

    if expected != result.evidence or matched != result.matched_records:
        raise GroundingError("Analytics result did not match its evidence.")


def build_analytics_answer(result: AnalyticsResult) -> AnalyticsAnswer:
    """Return text plus machine-readable evidence and trust metadata."""
    verify_analytics_result(result)
    return AnalyticsAnswer(
        text=_answer_text(result),
        evidence=result.evidence,
        date_range={
            "start_date": result.start_date,
            "end_date": result.end_date,
        },
        confidence=_answer_confidence(result),
    )


def answer_analytics_request(result: AnalyticsResult) -> str:
    """Backward-compatible text-only analytics response."""
    return build_analytics_answer(result).text
