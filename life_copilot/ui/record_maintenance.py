"""Streamlit controls for editing and deleting confirmed records."""

from __future__ import annotations

from datetime import date

import streamlit as st
from pydantic import ValidationError

from life_copilot import storage
from life_copilot.services.records import delete_saved_record, update_saved_record


def _optional_text(value: str):
    cleaned = value.strip()
    return cleaned or None


def _record_label(domain: str, record: dict) -> str:
    if domain == "wealth":
        return (
            f"#{record['id']} | {record['entry_date']} | "
            f"{record['transaction_type']} {record['currency']} {record['amount']:.2f} | "
            f"{record['category']}"
        )
    if domain == "health":
        detail = record.get("workout_type") or record.get("notes") or "Health log"
        return f"#{record['id']} | {record['entry_date']} | {detail}"
    return f"#{record['id']} | {record['entry_date']} | {record['topic']}"


def _render_delete_confirmation(pending: dict) -> None:
    domain = pending["domain"]
    record_id = pending["record_id"]
    record = storage.get_domain_log(domain, record_id)
    if record is None:
        st.session_state.delete_candidate = None
        st.warning("That record no longer exists.")
        return

    st.warning(f"Permanently delete {_record_label(domain, record)}?")
    confirm_col, keep_col = st.columns(2)
    with confirm_col:
        confirm = st.button(
            "Delete permanently",
            type="primary",
            use_container_width=True,
            key="confirm_record_delete",
        )
    with keep_col:
        keep = st.button(
            "Keep record", use_container_width=True, key="cancel_record_delete"
        )

    if confirm:
        try:
            result = delete_saved_record(domain, record_id)
            message = f"Deleted {domain} record #{record_id}."
            if result["warnings"]:
                message += " Vector index cleanup needs attention."
            st.session_state.maintenance_flash = ("success", message)
            st.session_state.delete_candidate = None
            st.rerun()
        except Exception as exc:
            st.error(f"The record could not be deleted: {exc}")
    elif keep:
        st.session_state.delete_candidate = None
        st.rerun()


def _wealth_editor(record: dict, form_key: str) -> dict:
    col1, col2 = st.columns(2)
    with col1:
        transaction_type = st.selectbox(
            "Type",
            ["Expense", "Income"],
            index=0 if record["transaction_type"] == "Expense" else 1,
            key=f"{form_key}_type",
        )
        amount = st.number_input(
            "Amount",
            value=float(record["amount"]),
            step=0.01,
            format="%.2f",
            key=f"{form_key}_amount",
        )
        if amount <= 0:
            st.warning("Enter an amount greater than zero before updating this record.")
        currency = st.text_input(
            "Currency", value=record["currency"], key=f"{form_key}_currency"
        )
    with col2:
        category = st.text_input(
            "Category", value=record["category"], key=f"{form_key}_category"
        )
        merchant = st.text_input(
            "Merchant", value=record.get("merchant") or "", key=f"{form_key}_merchant"
        )
        notes = st.text_area(
            "Notes", value=record.get("notes") or "", key=f"{form_key}_notes"
        )
    return {
        "transaction_type": transaction_type,
        "amount": amount,
        "currency": currency,
        "category": category,
        "merchant": _optional_text(merchant),
        "notes": _optional_text(notes),
    }


def _health_editor(record: dict, form_key: str) -> dict:
    col1, col2 = st.columns(2)
    with col1:
        sleep_hours = st.number_input(
            "Sleep hours",
            min_value=0.0,
            max_value=24.0,
            value=record.get("sleep_hours"),
            step=0.5,
            key=f"{form_key}_sleep",
        )
        workout_type = st.text_input(
            "Workout type",
            value=record.get("workout_type") or "",
            key=f"{form_key}_workout",
        )
    with col2:
        calories = st.number_input(
            "Calories consumed",
            min_value=0,
            max_value=20000,
            value=record.get("calories_consumed"),
            step=1,
            key=f"{form_key}_calories",
        )
        notes = st.text_area(
            "Health notes",
            value=record.get("notes") or "",
            key=f"{form_key}_notes",
        )
    return {
        "sleep_hours": sleep_hours,
        "workout_type": _optional_text(workout_type),
        "calories_consumed": calories,
        "notes": _optional_text(notes),
    }


def _learning_editor(record: dict, form_key: str) -> dict:
    topic = st.text_input(
        "Topic", value=record["topic"], key=f"{form_key}_topic"
    )
    summary = st.text_area(
        "Summary", value=record["summary_text"] or "", key=f"{form_key}_summary"
    )
    col1, col2 = st.columns(2)
    with col1:
        duration = st.number_input(
            "Duration in minutes",
            min_value=0,
            max_value=1440,
            value=record.get("duration_minutes"),
            step=1,
            key=f"{form_key}_duration",
        )
    with col2:
        url = st.text_input(
            "Reference URL",
            value=record.get("url_reference") or "",
            key=f"{form_key}_url",
        )
    return {
        "topic": topic,
        "summary_text": summary,
        "duration_minutes": duration,
        "url_reference": _optional_text(url),
    }


def render_record_maintenance() -> None:
    """Render a compact CRUD panel for confirmed records."""
    if "delete_candidate" not in st.session_state:
        st.session_state.delete_candidate = None

    flash = st.session_state.pop("maintenance_flash", None)
    if flash:
        level, message = flash
        getattr(st, level)(message)

    expanded = st.session_state.delete_candidate is not None
    with st.expander("Manage saved records", expanded=expanded):
        if st.session_state.delete_candidate:
            _render_delete_confirmation(st.session_state.delete_candidate)
            return

        domain = st.selectbox(
            "Domain",
            ["wealth", "health", "learning"],
            format_func=str.title,
            key="maintenance_domain",
        )
        records = storage.list_domain_logs(domain)
        if not records:
            st.info(f"No saved {domain} records.")
            return

        record_by_id = {record["id"]: record for record in records}
        record_id = st.selectbox(
            "Record",
            list(record_by_id),
            format_func=lambda value: _record_label(domain, record_by_id[value]),
            key=f"maintenance_record_{domain}",
        )
        record = record_by_id[record_id]
        form_key = f"maintenance_form_{domain}_{record_id}"

        with st.form(form_key):
            entry_date = st.date_input(
                "Entry date",
                value=date.fromisoformat(record["entry_date"]),
                key=f"{form_key}_date",
            )
            if domain == "wealth":
                payload = _wealth_editor(record, form_key)
            elif domain == "health":
                payload = _health_editor(record, form_key)
            else:
                payload = _learning_editor(record, form_key)
            payload["entry_date"] = entry_date.isoformat()

            update_col, delete_col = st.columns(2)
            with update_col:
                update = st.form_submit_button(
                    "Update record", type="primary", use_container_width=True
                )
            with delete_col:
                request_delete = st.form_submit_button(
                    "Delete record", use_container_width=True
                )

        if update:
            try:
                result = update_saved_record(domain, record_id, payload)
                message = f"Updated {domain} record #{record_id}."
                if result["warnings"]:
                    message += " Vector index synchronization needs attention."
                st.session_state.maintenance_flash = ("success", message)
                st.rerun()
            except (ValidationError, ValueError) as exc:
                st.error(f"Please correct the record: {exc}")
            except Exception as exc:
                st.error(f"The record could not be updated: {exc}")
        elif request_delete:
            st.session_state.delete_candidate = {
                "domain": domain,
                "record_id": record_id,
            }
            st.rerun()
