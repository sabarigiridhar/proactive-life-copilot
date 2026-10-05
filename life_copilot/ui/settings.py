"""Preferences, provider status, export, and local backup controls."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date

import streamlit as st

from life_copilot.ui.api_client import ApiClientError, get_api_client


PUBLIC_EXPORT_FIELDS = {
    "wealth": (
        "id",
        "entry_date",
        "transaction_type",
        "amount",
        "currency",
        "category",
        "merchant",
        "notes",
        "source",
        "created_at",
        "updated_at",
    ),
    "health": (
        "id",
        "entry_date",
        "sleep_hours",
        "workout_type",
        "calories_consumed",
        "notes",
        "source",
        "created_at",
        "updated_at",
    ),
    "learning": (
        "id",
        "entry_date",
        "topic",
        "summary_text",
        "duration_minutes",
        "url_reference",
        "source",
        "created_at",
        "updated_at",
    ),
}


def _public_record(record: dict, fields: tuple[str, ...]) -> dict:
    return {field: record.get(field) for field in fields}


def _records_export(records: dict[str, list[dict]]) -> bytes:
    """Build a portable ZIP containing public JSON and per-domain CSV files."""
    normalized = {
        domain: [_public_record(record, PUBLIC_EXPORT_FIELDS[domain]) for record in rows]
        for domain, rows in records.items()
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "life-copilot-records.json",
            json.dumps(normalized, indent=2, default=str),
        )
        for domain, rows in normalized.items():
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=PUBLIC_EXPORT_FIELDS[domain])
            writer.writeheader()
            writer.writerows(rows)
            archive.writestr(f"{domain}.csv", stream.getvalue())
    return output.getvalue()


def _render_preferences(api, settings) -> None:
    st.subheader("Preferences and weekly targets")
    st.caption(
        "These local targets support dashboard design now and can migrate to the "
        "full goals service in the Proactive Copilot phase."
    )
    preferences = settings.preferences
    with st.form("app_preferences"):
        currency_column, spending_column = st.columns(2, gap="medium")
        with currency_column:
            currency = st.text_input(
                "Preferred currency",
                value=preferences.default_currency,
                max_chars=8,
                help="Use an ISO-style code such as INR, USD, or EUR.",
            )
        with spending_column:
            spending_limit = st.number_input(
                "Weekly spending limit",
                min_value=0.0,
                value=float(preferences.weekly_spending_limit or 0),
                step=100.0,
                help="Use 0 when no spending limit is configured.",
            )

        learning_column, workout_column, sleep_column = st.columns(3, gap="medium")
        with learning_column:
            learning_minutes = st.number_input(
                "Weekly learning minutes",
                min_value=0,
                max_value=10080,
                value=preferences.weekly_learning_minutes,
                step=15,
            )
        with workout_column:
            weekly_workouts = st.number_input(
                "Weekly workouts",
                min_value=0,
                max_value=14,
                value=preferences.weekly_workouts,
                step=1,
            )
        with sleep_column:
            sleep_target = st.number_input(
                "Sleep target (hours)",
                min_value=0.0,
                max_value=24.0,
                value=float(preferences.sleep_hours_target),
                step=0.5,
            )
        save = st.form_submit_button(
            "Save settings",
            icon=":material/save:",
            type="primary",
            use_container_width=True,
        )

    if not save:
        return
    normalized_currency = currency.strip().upper()
    if len(normalized_currency) < 3:
        st.error("Enter a valid currency code with at least three characters.")
        return
    try:
        with st.spinner("Saving settings..."):
            api.update_settings(
                {
                    "default_currency": normalized_currency,
                    "weekly_spending_limit": spending_limit or None,
                    "weekly_learning_minutes": learning_minutes,
                    "weekly_workouts": weekly_workouts,
                    "sleep_hours_target": sleep_target,
                }
            )
    except ApiClientError as exc:
        st.error(f"Settings could not be saved: {exc}")
        return
    st.session_state.settings_flash = "Settings saved."
    st.rerun()


def _render_provider_status(settings) -> None:
    st.subheader("Model configuration")
    st.caption("Configuration status is shown without reading or displaying API keys.")
    for provider in settings.providers:
        with st.container(border=True):
            name_column, model_column, status_column = st.columns(
                [1, 1.2, 0.55], gap="medium", vertical_alignment="center"
            )
            with name_column:
                st.markdown(f"**{provider.provider}**")
                st.caption(provider.capability)
            with model_column:
                st.code(provider.model, language=None)
            with status_column:
                if provider.configured:
                    st.success("Configured", icon=":material/check_circle:")
                else:
                    st.warning("Missing", icon=":material/warning:")


def _render_data_tools(api) -> None:
    st.subheader("Data tools")
    st.caption(
        "Record exports omit private original inputs and chat history. Local snapshots "
        "remain on this computer and are not uploaded anywhere."
    )
    export_column, backup_column = st.columns(2, gap="large")
    with export_column:
        with st.container(border=True):
            st.markdown("**Portable records export**")
            st.caption("Create JSON plus separate wealth, health, and learning CSV files.")
            prepare = st.button(
                "Prepare export",
                icon=":material/archive:",
                use_container_width=True,
            )
            if prepare:
                try:
                    with st.spinner("Preparing records export..."):
                        records = {
                            domain: api.list_all_records(domain)
                            for domain in ("wealth", "health", "learning")
                        }
                        st.session_state.records_export = _records_export(records)
                except ApiClientError as exc:
                    st.error(f"Records could not be exported: {exc}")
            export_data = st.session_state.get("records_export")
            if export_data:
                st.download_button(
                    "Download records ZIP",
                    data=export_data,
                    file_name=f"life-copilot-records-{date.today().isoformat()}.zip",
                    mime="application/zip",
                    icon=":material/download:",
                    on_click="ignore",
                    use_container_width=True,
                )

    with backup_column:
        with st.container(border=True):
            st.markdown("**Local data snapshot**")
            st.caption("Copy the SQLite database and learning vector index to backups/.")
            create = st.button(
                "Create local snapshot",
                icon=":material/backup:",
                use_container_width=True,
            )
            if create:
                try:
                    with st.spinner("Creating local snapshot..."):
                        backup = api.create_backup()
                except ApiClientError as exc:
                    st.error(f"The local snapshot could not be created: {exc}")
                else:
                    st.success(f"Created {backup.backup_name}.")
                    st.caption("Includes: " + ", ".join(backup.includes))
                    for warning in backup.warnings:
                        st.warning(warning)
            st.caption(
                "Restore validation and retention controls remain planned for the "
                "Production Readiness phase."
            )


def run_settings_page() -> None:
    """Render persistent preferences and operational configuration status."""
    st.title("Settings")
    st.caption(date.today().strftime("%A, %d %B %Y"))
    api = get_api_client()

    flash = st.session_state.pop("settings_flash", None)
    if flash:
        st.success(flash)

    try:
        with st.spinner("Loading settings..."):
            settings = api.get_settings()
    except ApiClientError as exc:
        st.error(f"Settings could not be loaded: {exc}")
        return

    _render_preferences(api, settings)
    st.divider()
    _render_provider_status(settings)
    st.divider()
    _render_data_tools(api)
