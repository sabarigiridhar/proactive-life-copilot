"""Date-aligned, fixed-query aggregation for cross-domain analytics."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from life_copilot.analytics.models import (
    AnalyticsOperation,
    AnalyticsRequest,
    AnalyticsResult,
    ComparisonOperator,
    DailyAggregate,
    DailyHealthAggregate,
    DailyLearningAggregate,
    DailyMetric,
    DailyMoneyTotal,
    DailyWealthAggregate,
)
from life_copilot.storage.base import DEFAULT_DB_PATH, _database

MINIMUM_COMPARISON_GROUP_SIZE = 3


def load_daily_aggregates(
    start_date,
    end_date,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[DailyAggregate]:
    """Load each domain independently and join the aggregates by ISO date."""
    start = start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date)
    end = end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)
    with _database(db_path) as conn:
        health_rows = conn.execute(
            """
            SELECT entry_date, sleep_hours, calories_consumed, workout_type
            FROM health_logs
            WHERE entry_date BETWEEN ? AND ?
            ORDER BY entry_date
            """,
            (start, end),
        ).fetchall()
        wealth_rows = conn.execute(
            """
            SELECT entry_date,
                   CASE LOWER(transaction_type)
                       WHEN 'income' THEN 'Income' ELSE 'Expense'
                   END AS transaction_type,
                   UPPER(currency) AS currency,
                   category,
                   ROUND(SUM(amount), 2) AS total,
                   COUNT(*) AS records
            FROM wealth_logs
            WHERE entry_date BETWEEN ? AND ?
            GROUP BY entry_date, LOWER(transaction_type), UPPER(currency), category
            ORDER BY entry_date, transaction_type, currency, category
            """,
            (start, end),
        ).fetchall()
        learning_rows = conn.execute(
            """
            SELECT entry_date,
                   COALESCE(SUM(duration_minutes), 0) AS duration_minutes,
                   COUNT(*) AS sessions,
                   GROUP_CONCAT(DISTINCT topic) AS topics
            FROM learning_logs
            WHERE entry_date BETWEEN ? AND ?
            GROUP BY entry_date
            ORDER BY entry_date
            """,
            (start, end),
        ).fetchall()

    joined: dict[str, dict] = {}
    for row in health_rows:
        aggregate = joined.setdefault(row["entry_date"], {"entry_date": row["entry_date"]})
        aggregate["health"] = DailyHealthAggregate(
            sleep_hours=row["sleep_hours"],
            calories_consumed=row["calories_consumed"],
            workout_logged=bool(row["workout_type"] and row["workout_type"].strip()),
            workout_type=row["workout_type"],
        )
    for row in wealth_rows:
        aggregate = joined.setdefault(row["entry_date"], {"entry_date": row["entry_date"]})
        wealth = aggregate.setdefault("wealth_totals", [])
        wealth.append(
            DailyMoneyTotal(
                transaction_type=row["transaction_type"],
                currency=row["currency"],
                category=row["category"],
                total=row["total"],
                records=row["records"],
            )
        )
    for row in learning_rows:
        aggregate = joined.setdefault(row["entry_date"], {"entry_date": row["entry_date"]})
        aggregate["learning"] = DailyLearningAggregate(
            duration_minutes=row["duration_minutes"],
            sessions=row["sessions"],
            topics=[topic.strip() for topic in (row["topics"] or "").split(",") if topic.strip()],
        )

    results = []
    for entry_date in sorted(joined):
        values = joined[entry_date]
        wealth_totals = values.pop("wealth_totals", None)
        if wealth_totals is not None:
            values["wealth"] = DailyWealthAggregate(totals=wealth_totals)
        results.append(DailyAggregate.model_validate(values))
    return results


def _expense_value(day: DailyAggregate, request: AnalyticsRequest) -> float | None:
    if day.wealth is None:
        return None
    values = [
        row.total
        for row in day.wealth.totals
        if row.transaction_type == "Expense"
        and row.currency.casefold() == request.currency.casefold()
        and (
            request.category is None
            or row.category.casefold() == request.category.casefold()
        )
    ]
    return round(sum(values), 2)


def _metric_value(
    day: DailyAggregate, metric: DailyMetric, request: AnalyticsRequest
) -> float | None:
    if metric == DailyMetric.EXPENSE_AMOUNT:
        return _expense_value(day, request)
    if metric == DailyMetric.SLEEP_HOURS:
        return day.health.sleep_hours if day.health else None
    if metric == DailyMetric.CALORIES_CONSUMED:
        if day.health and day.health.calories_consumed is not None:
            return float(day.health.calories_consumed)
        return None
    if metric == DailyMetric.WORKOUT_LOGGED:
        return float(day.health.workout_logged) if day.health else None
    if metric == DailyMetric.LEARNING_MINUTES:
        return float(day.learning.duration_minutes) if day.learning else None
    if metric == DailyMetric.LEARNING_SESSIONS:
        return float(day.learning.sessions) if day.learning else None
    raise ValueError(f"Unsupported daily metric: {metric}")


def _comparison(operator: ComparisonOperator) -> Callable[[float, float], bool]:
    return {
        ComparisonOperator.GT: lambda value, threshold: value > threshold,
        ComparisonOperator.GTE: lambda value, threshold: value >= threshold,
        ComparisonOperator.LT: lambda value, threshold: value < threshold,
        ComparisonOperator.LTE: lambda value, threshold: value <= threshold,
    }[operator]


def execute_cross_domain(
    request: AnalyticsRequest,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> AnalyticsResult:
    """Compare daily outcome averages above/below an allowlisted threshold."""
    if request.operation != AnalyticsOperation.CROSS_DOMAIN_COMPARISON:
        raise ValueError("A cross-domain analytics request is required.")

    days = load_daily_aggregates(
        request.start_date,
        request.end_date,
        db_path=db_path,
    )
    compare = _comparison(request.comparison_operator)
    evidence = []
    condition_values = []
    comparison_values = []
    for day in days:
        outcome_value = _metric_value(day, request.outcome_metric, request)
        condition_value = _metric_value(day, request.condition_metric, request)
        if outcome_value is None or condition_value is None:
            continue
        condition_met = compare(condition_value, request.threshold)
        evidence.append(
            {
                "entry_date": day.entry_date.isoformat(),
                "outcome_metric": request.outcome_metric.value,
                "outcome_value": outcome_value,
                "condition_metric": request.condition_metric.value,
                "condition_value": condition_value,
                "condition_met": condition_met,
            }
        )
        target = condition_values if condition_met else comparison_values
        target.append(outcome_value)

    condition_average = (
        round(sum(condition_values) / len(condition_values), 2)
        if condition_values
        else None
    )
    comparison_average = (
        round(sum(comparison_values) / len(comparison_values), 2)
        if comparison_values
        else None
    )
    enough_data = (
        len(condition_values) >= MINIMUM_COMPARISON_GROUP_SIZE
        and len(comparison_values) >= MINIMUM_COMPARISON_GROUP_SIZE
    )
    difference = (
        round(condition_average - comparison_average, 2)
        if condition_average is not None and comparison_average is not None
        else None
    )
    if not enough_data or difference is None:
        observation = "insufficient"
    elif difference > 0:
        observation = "higher"
    elif difference < 0:
        observation = "lower"
    else:
        observation = "same"

    data = {
        "outcome_metric": request.outcome_metric,
        "condition_metric": request.condition_metric,
        "comparison_operator": request.comparison_operator,
        "threshold": request.threshold,
        "category": request.category,
        "currency": request.currency
        if DailyMetric.EXPENSE_AMOUNT
        in {request.outcome_metric, request.condition_metric}
        else None,
        "condition_days": len(condition_values),
        "comparison_days": len(comparison_values),
        "condition_average": condition_average,
        "comparison_average": comparison_average,
        "difference": difference,
        "minimum_group_size": MINIMUM_COMPARISON_GROUP_SIZE,
        "enough_data": enough_data,
        "observation": observation,
    }
    return AnalyticsResult(
        operation=request.operation,
        start_date=request.start_date,
        end_date=request.end_date,
        data=data,
        evidence=evidence,
        matched_records=len(evidence),
    )
