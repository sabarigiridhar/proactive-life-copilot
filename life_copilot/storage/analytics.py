"""Fixed, parameterized SQL calculations for allowlisted analytics."""

from datetime import date, timedelta
from pathlib import Path

from life_copilot.analytics.models import (
    AnalyticsOperation,
    AnalyticsRequest,
    AnalyticsResult,
)
from life_copilot.storage.base import DEFAULT_DB_PATH, _database
from life_copilot.storage.cross_domain import execute_cross_domain


def _wealth_filters(request: AnalyticsRequest) -> tuple[str, list]:
    clauses = [
        "entry_date BETWEEN ? AND ?",
        "LOWER(transaction_type) = LOWER(?)",
    ]
    params = [
        request.start_date.isoformat(),
        request.end_date.isoformat(),
        request.transaction_type,
    ]
    if request.category:
        clauses.append("LOWER(category) = LOWER(?)")
        params.append(request.category)
    return " AND ".join(clauses), params


def _wealth_total(request: AnalyticsRequest, db_path: str | Path) -> AnalyticsResult:
    where, params = _wealth_filters(request)
    with _database(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT currency, ROUND(SUM(amount), 2) AS total, COUNT(*) AS records
            FROM wealth_logs WHERE {where}
            GROUP BY currency ORDER BY currency
            """,
            params,
        ).fetchall()
    totals = [dict(row) for row in rows]
    return AnalyticsResult(
        operation=request.operation,
        start_date=request.start_date,
        end_date=request.end_date,
        data={"transaction_type": request.transaction_type, "totals": totals},
        evidence=totals,
        matched_records=sum(row["records"] for row in rows),
    )


def _wealth_grouped(
    request: AnalyticsRequest, db_path: str | Path, *, by_date: bool
) -> AnalyticsResult:
    where, params = _wealth_filters(request)
    group_column = "entry_date" if by_date else "category"
    with _database(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT {group_column} AS label, currency,
                   ROUND(SUM(amount), 2) AS total, COUNT(*) AS records
            FROM wealth_logs WHERE {where}
            GROUP BY {group_column}, currency
            ORDER BY {group_column if by_date else 'total DESC'}, currency
            LIMIT ?
            """,
            [*params, request.limit],
        ).fetchall()
    groups = [dict(row) for row in rows]
    return AnalyticsResult(
        operation=request.operation,
        start_date=request.start_date,
        end_date=request.end_date,
        data={"transaction_type": request.transaction_type, "groups": groups},
        evidence=groups,
        matched_records=sum(row["records"] for row in rows),
    )


def _health_averages(
    request: AnalyticsRequest, db_path: str | Path
) -> AnalyticsResult:
    with _database(db_path) as conn:
        row = conn.execute(
            """
            SELECT ROUND(AVG(sleep_hours), 2) AS average_sleep_hours,
                   ROUND(AVG(calories_consumed), 2) AS average_calories,
                   COUNT(sleep_hours) AS sleep_records,
                   COUNT(calories_consumed) AS calorie_records
            FROM health_logs WHERE entry_date BETWEEN ? AND ?
            """,
            (request.start_date.isoformat(), request.end_date.isoformat()),
        ).fetchone()
    data = dict(row)
    matched = max(data["sleep_records"], data["calorie_records"])
    return AnalyticsResult(
        operation=request.operation,
        start_date=request.start_date,
        end_date=request.end_date,
        data=data,
        evidence=[data],
        matched_records=matched,
    )


def _workout_dates(request: AnalyticsRequest, db_path: str | Path) -> list[dict]:
    with _database(db_path) as conn:
        rows = conn.execute(
            """
            SELECT entry_date, workout_type
            FROM health_logs
            WHERE entry_date BETWEEN ? AND ?
              AND workout_type IS NOT NULL AND TRIM(workout_type) <> ''
            ORDER BY entry_date
            """,
            (
                request.start_date.isoformat(),
                request.end_date.isoformat(),
            ),
        ).fetchall()
    return [dict(row) for row in rows]


def _workout_frequency(
    request: AnalyticsRequest, db_path: str | Path
) -> AnalyticsResult:
    workouts = _workout_dates(request, db_path)
    return AnalyticsResult(
        operation=request.operation,
        start_date=request.start_date,
        end_date=request.end_date,
        data={"workout_days": len(workouts), "workouts": workouts},
        evidence=workouts,
        matched_records=len(workouts),
    )


def _workout_streak(
    request: AnalyticsRequest, db_path: str | Path
) -> AnalyticsResult:
    workouts = _workout_dates(request, db_path)
    dates = sorted({date.fromisoformat(row["entry_date"]) for row in workouts})
    longest = 0
    run = 0
    previous = None
    for workout_date in dates:
        run = run + 1 if previous and workout_date == previous + timedelta(days=1) else 1
        longest = max(longest, run)
        previous = workout_date

    current = 0
    expected = request.end_date
    for workout_date in reversed(dates):
        if workout_date != expected:
            break
        current += 1
        expected -= timedelta(days=1)

    data = {"current_streak_days": current, "longest_streak_days": longest}
    return AnalyticsResult(
        operation=request.operation,
        start_date=request.start_date,
        end_date=request.end_date,
        data=data,
        evidence=workouts,
        matched_records=len(workouts),
    )


def execute_analytics(
    request: AnalyticsRequest, db_path: str | Path = DEFAULT_DB_PATH
) -> AnalyticsResult:
    """Dispatch only to known calculations; no caller-provided SQL is executed."""
    operations = {
        AnalyticsOperation.WEALTH_TOTAL: _wealth_total,
        AnalyticsOperation.WEALTH_CATEGORY_BREAKDOWN: lambda item, path: _wealth_grouped(
            item, path, by_date=False
        ),
        AnalyticsOperation.WEALTH_DAILY_TREND: lambda item, path: _wealth_grouped(
            item, path, by_date=True
        ),
        AnalyticsOperation.HEALTH_AVERAGES: _health_averages,
        AnalyticsOperation.WORKOUT_FREQUENCY: _workout_frequency,
        AnalyticsOperation.WORKOUT_STREAK: _workout_streak,
        AnalyticsOperation.CROSS_DOMAIN_COMPARISON: execute_cross_domain,
    }
    return operations[request.operation](request, db_path)
