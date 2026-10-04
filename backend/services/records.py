"""Application services for record maintenance and dashboard summaries."""

from __future__ import annotations

from datetime import date, timedelta
from math import ceil

from pydantic import ValidationError

from backend.core.settings import Settings
from backend.models.records import (
    CurrencyNet,
    DashboardQuery,
    DashboardSummary,
    HealthDashboard,
    LearningDashboard,
    RecordDeletionData,
    RecordDomain,
    RecordListQuery,
    RecordMutationData,
    RecordPage,
    RecordPatch,
    WealthDashboard,
)
from backend.repositories.records import list_records, load_dashboard_rows
from life_copilot import storage
from life_copilot.services.records import delete_saved_record, update_saved_record


DOMAIN_QUERY_FIELDS = {
    RecordDomain.WEALTH: {"transaction_type", "currency", "category", "merchant"},
    RecordDomain.HEALTH: {"workout_type"},
    RecordDomain.LEARNING: {"topic"},
}
DOMAIN_RECORD_FIELDS = {
    RecordDomain.WEALTH: {
        "entry_date",
        "transaction_type",
        "amount",
        "currency",
        "category",
        "merchant",
        "notes",
    },
    RecordDomain.HEALTH: {
        "entry_date",
        "sleep_hours",
        "workout_type",
        "calories_consumed",
        "notes",
    },
    RecordDomain.LEARNING: {
        "entry_date",
        "topic",
        "summary_text",
        "duration_minutes",
        "url_reference",
    },
}


class RecordInputError(ValueError):
    pass


def _invalid_domain_fields(values: dict, allowed: set[str]) -> set[str]:
    return {key for key, value in values.items() if value is not None and key not in allowed}


def get_record_page(
    domain: RecordDomain,
    query: RecordListQuery,
    settings: Settings,
) -> RecordPage:
    values = query.model_dump()
    common = {"page", "page_size", "start_date", "end_date", "search", "source"}
    invalid = _invalid_domain_fields(values, common | DOMAIN_QUERY_FIELDS[domain])
    if invalid:
        names = ", ".join(sorted(invalid))
        raise RecordInputError(f"These filters do not apply to {domain.value}: {names}.")

    items, total = list_records(domain, query, db_path=settings.database_path)
    return RecordPage(
        domain=domain,
        items=items,
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=ceil(total / query.page_size) if total else 0,
    )


def patch_record(
    domain: RecordDomain,
    record_id: int,
    patch: RecordPatch,
    settings: Settings,
) -> RecordMutationData:
    storage.init_sqlite_db(settings.database_path)
    existing = storage.get_domain_log(
        domain.value, record_id, db_path=settings.database_path
    )
    if existing is None:
        raise KeyError(record_id)

    changes = patch.model_dump(exclude_unset=True)
    invalid = set(changes) - DOMAIN_RECORD_FIELDS[domain]
    if invalid:
        names = ", ".join(sorted(invalid))
        raise RecordInputError(f"These fields do not apply to {domain.value}: {names}.")
    payload = {
        field: changes.get(field, existing.get(field))
        for field in DOMAIN_RECORD_FIELDS[domain]
    }
    result = update_saved_record(
        domain.value,
        record_id,
        payload,
        db_path=settings.database_path,
        chroma_path=settings.chroma_path,
    )
    warnings = (
        ["The record was updated, but vector indexing needs attention."]
        if result["warnings"]
        else []
    )
    return RecordMutationData(
        domain=domain,
        record=result["record"],
        statuses=result["statuses"],
        warnings=warnings,
    )


def remove_record(
    domain: RecordDomain,
    record_id: int,
    settings: Settings,
) -> RecordDeletionData:
    storage.init_sqlite_db(settings.database_path)
    result = delete_saved_record(
        domain.value,
        record_id,
        db_path=settings.database_path,
        chroma_path=settings.chroma_path,
    )
    warnings = (
        ["The record was deleted, but vector indexing needs attention."]
        if result["warnings"]
        else []
    )
    return RecordDeletionData(
        domain=domain,
        deleted_id=record_id,
        status=result["status"],
        warnings=warnings,
    )


def _streaks(days: list[date], end_date: date) -> tuple[int, int]:
    unique_days = sorted(set(days))
    longest = 0
    run = 0
    previous = None
    for current_day in unique_days:
        run = run + 1 if previous == current_day - timedelta(days=1) else 1
        longest = max(longest, run)
        previous = current_day

    current = 0
    expected = end_date
    for current_day in reversed(unique_days):
        if current_day != expected:
            break
        current += 1
        expected -= timedelta(days=1)
    return current, longest


def get_dashboard_summary(
    query: DashboardQuery,
    settings: Settings,
) -> DashboardSummary:
    end_date = query.end_date or date.today()
    start_date = query.start_date or end_date - timedelta(days=6)
    if end_date < start_date:
        raise RecordInputError("end_date must be on or after start_date.")
    if (end_date - start_date).days > 366:
        raise RecordInputError("Dashboard date ranges cannot exceed 367 days.")
    status_date = query.status_date or end_date
    rows = load_dashboard_rows(
        start_date,
        end_date,
        db_path=settings.database_path,
    )

    income = [
        row for row in rows["wealth_totals"]
        if row["transaction_type"].casefold() == "income"
    ]
    expenses = [
        row for row in rows["wealth_totals"]
        if row["transaction_type"].casefold() == "expense"
    ]
    income_by_currency = {row["currency"]: row["total"] for row in income}
    expense_by_currency = {row["currency"]: row["total"] for row in expenses}
    currencies = sorted(set(income_by_currency) | set(expense_by_currency))
    net = [
        CurrencyNet(
            currency=currency,
            income=income_by_currency.get(currency, 0),
            expense=expense_by_currency.get(currency, 0),
            net=round(
                income_by_currency.get(currency, 0)
                - expense_by_currency.get(currency, 0),
                2,
            ),
        )
        for currency in currencies
    ]
    wealth_daily = [
        {
            **row,
            "net": round(row["income"] - row["expense"], 2),
        }
        for row in rows["wealth_daily"]
    ]

    health_rows = rows["health_daily"]
    sleeps = [row["sleep_hours"] for row in health_rows if row["sleep_hours"] is not None]
    calories = [
        row["calories_consumed"]
        for row in health_rows
        if row["calories_consumed"] is not None
    ]
    workout_days = sum(
        bool(row["workout_type"] and row["workout_type"].strip())
        for row in health_rows
    )

    learning_rows = rows["learning_daily"]
    learning_dates = [date.fromisoformat(row["entry_date"]) for row in learning_rows]
    current_streak, longest_streak = _streaks(learning_dates, end_date)
    return DashboardSummary(
        date_range={"start_date": start_date, "end_date": end_date},
        status_date=status_date,
        daily_status=storage.get_daily_status(
            status_date.isoformat(), db_path=settings.database_path
        ),
        wealth=WealthDashboard(
            income=income,
            expenses=expenses,
            net=net,
            categories=rows["wealth_categories"],
            daily=wealth_daily,
        ),
        health=HealthDashboard(
            average_sleep_hours=(
                round(sum(sleeps) / len(sleeps), 2) if sleeps else None
            ),
            average_calories=(
                round(sum(calories) / len(calories), 2) if calories else None
            ),
            sleep_records=len(sleeps),
            calorie_records=len(calories),
            workout_days=workout_days,
            daily=health_rows,
        ),
        learning=LearningDashboard(
            total_minutes=sum(row["minutes"] for row in learning_rows),
            sessions=sum(row["sessions"] for row in learning_rows),
            learning_days=len(learning_rows),
            current_streak_days=current_streak,
            longest_streak_days=longest_streak,
            topics=rows["learning_topics"],
            daily=learning_rows,
        ),
    )
