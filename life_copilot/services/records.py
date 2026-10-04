"""Validated edit and delete workflows for saved Life Copilot records."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from life_copilot import storage
from life_copilot.models import HealthLog, LearningLog, WealthLog


def _entry_date(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError("Entry date must be a valid YYYY-MM-DD date.") from exc


def update_saved_record(
    domain: str,
    record_id: int,
    payload: dict,
    *,
    db_path: str | Path = storage.DEFAULT_DB_PATH,
    vector_collection=None,
    chroma_path: str | Path = storage.DEFAULT_CHROMA_PATH,
) -> dict:
    """Validate and update one saved record, including derived state."""
    normalized = domain.lower()
    existing = storage.get_domain_log(normalized, record_id, db_path=db_path)
    if existing is None:
        raise KeyError(f"{normalized.title()} record {record_id} was not found.")

    new_date = _entry_date(payload.get("entry_date"))
    old_date = existing["entry_date"]
    warnings = []

    if normalized == "wealth":
        validated = WealthLog.model_validate(payload)
        updated = storage.update_wealth_record(
            record_id,
            new_date,
            validated.transaction_type,
            validated.amount,
            validated.currency,
            validated.category,
            validated.merchant,
            validated.notes,
            db_path=db_path,
        )
    elif normalized == "health":
        validated = HealthLog.model_validate(payload)
        updated = storage.update_health_record(
            record_id,
            new_date,
            validated.sleep_hours,
            validated.workout_type,
            validated.calories_consumed,
            validated.notes,
            db_path=db_path,
        )
    elif normalized == "learning":
        validated = LearningLog.model_validate(payload)
        updated = storage.update_learning_record(
            record_id,
            new_date,
            validated.topic,
            validated.summary_text,
            validated.duration_minutes,
            validated.url_reference,
            db_path=db_path,
        )
        try:
            collection = vector_collection
            if collection is None:
                collection = storage.init_chroma_db(chroma_path)
            storage.delete_learning_vector(
                collection,
                record_id,
                existing["entry_date"],
                existing["topic"],
            )
            storage.add_learning_vector(
                collection,
                record_id,
                new_date,
                validated.topic,
                validated.summary_text,
                validated.url_reference,
            )
        except Exception as exc:
            warnings.append(f"Vector index update failed: {exc}")
    else:
        raise ValueError(f"Unsupported domain: {domain}")

    if not updated:
        raise KeyError(f"{normalized.title()} record {record_id} was not found.")

    affected_dates = {old_date, new_date}
    statuses = {
        affected_date: storage.recalculate_daily_status(
            affected_date, db_path=db_path
        )
        for affected_date in affected_dates
    }
    return {
        "record": storage.get_domain_log(normalized, record_id, db_path=db_path),
        "statuses": statuses,
        "warnings": warnings,
    }


def delete_saved_record(
    domain: str,
    record_id: int,
    *,
    db_path: str | Path = storage.DEFAULT_DB_PATH,
    vector_collection=None,
    chroma_path: str | Path = storage.DEFAULT_CHROMA_PATH,
) -> dict:
    """Delete one record and recalculate completion for its date."""
    normalized = domain.lower()
    existing = storage.get_domain_log(normalized, record_id, db_path=db_path)
    if existing is None:
        raise KeyError(f"{normalized.title()} record {record_id} was not found.")

    warnings = []
    if normalized == "learning":
        try:
            collection = vector_collection
            if collection is None:
                collection = storage.init_chroma_db(chroma_path)
            storage.delete_learning_vector(
                collection,
                record_id,
                existing["entry_date"],
                existing["topic"],
            )
        except Exception as exc:
            warnings.append(f"Vector index deletion failed: {exc}")

    if not storage.delete_domain_log(normalized, record_id, db_path=db_path):
        raise KeyError(f"{normalized.title()} record {record_id} was not found.")

    status = storage.recalculate_daily_status(
        existing["entry_date"], db_path=db_path
    )
    return {"deleted": existing, "status": status, "warnings": warnings}
