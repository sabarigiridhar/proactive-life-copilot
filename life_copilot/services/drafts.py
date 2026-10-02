"""Persistence service for user-confirmed extraction drafts."""

from pathlib import Path

from life_copilot import storage as db_utils
from life_copilot.models import DailyLogDraft
from life_copilot.services.records import update_saved_record

def save_confirmed_draft(
    draft_data: DailyLogDraft | dict,
    db_path: str | Path = db_utils.DEFAULT_DB_PATH,
    vector_collection=None,
) -> dict:
    """Validate and persist a user-confirmed draft."""
    draft = (
        draft_data
        if isinstance(draft_data, DailyLogDraft)
        else DailyLogDraft.model_validate(draft_data)
    )
    entry_date = draft.entry_date.isoformat()
    original_input = draft.original_input
    result = {
        "health": 0,
        "wealth": 0,
        "learning": 0,
        "record_ids": {"health": [], "wealth": [], "learning": []},
        "vector_warnings": [],
    }

    if draft.operation == "update":
        domain = draft.target_domain
        record_id = draft.target_record_id
        if domain == "wealth":
            payload = {"entry_date": entry_date, **draft.wealth[0].model_dump()}
        elif domain == "health" and draft.health:
            payload = {"entry_date": entry_date, **draft.health.model_dump()}
        elif domain == "learning" and draft.learning:
            payload = {"entry_date": entry_date, **draft.learning[0].model_dump()}
        else:
            raise ValueError("The update draft does not contain its target record.")
        update_result = update_saved_record(
            domain,
            record_id,
            payload,
            db_path=db_path,
            vector_collection=vector_collection,
        )
        result[domain] = 1
        result["record_ids"][domain].append(record_id)
        result["vector_warnings"].extend(update_result["warnings"])
        result["daily_status"] = update_result["statuses"][entry_date]
        return result

    if draft.health:
        health = draft.health
        health_id = db_utils.insert_health_log(
            entry_date,
            health.sleep_hours,
            health.workout_type,
            health.calories_consumed,
            health.notes,
            source=draft.source,
            original_input=original_input,
            db_path=db_path,
        )
        result["health"] = 1
        result["record_ids"]["health"].append(health_id)

    for wealth in draft.wealth:
        wealth_id = db_utils.insert_wealth_log(
            entry_date,
            wealth.transaction_type,
            wealth.amount,
            wealth.currency,
            wealth.category,
            wealth.merchant,
            wealth.notes,
            source=draft.source,
            original_input=original_input,
            db_path=db_path,
        )
        result["wealth"] += 1
        result["record_ids"]["wealth"].append(wealth_id)

    collection = vector_collection
    vector_available = True
    for learning in draft.learning:
        learning_id = db_utils.insert_learning_log(
            entry_date,
            learning.topic,
            learning.duration_minutes,
            learning.url_reference,
            summary_text=learning.summary_text,
            source=draft.source,
            original_input=original_input,
            db_path=db_path,
        )
        result["learning"] += 1
        result["record_ids"]["learning"].append(learning_id)

        if vector_available:
            try:
                collection = collection or db_utils.init_chroma_db()
                db_utils.add_learning_vector(
                    collection,
                    learning_id,
                    entry_date,
                    learning.topic,
                    learning.summary_text,
                    learning.url_reference,
                )
            except Exception as exc:
                vector_available = False
                result["vector_warnings"].append(
                    f"Learning row {learning_id} was saved, but vector indexing failed: {exc}"
                )

    result["daily_status"] = db_utils.update_daily_status(
        entry_date,
        health_complete=draft.health is not None,
        wealth_reviewed=bool(draft.wealth),
        learning_complete=bool(draft.learning),
        db_path=db_path,
    )
    return result
