"""Editable confirmation form for AI-extracted daily-log drafts."""

from datetime import date

import streamlit as st

def _empty_to_none(value: str):
    cleaned = value.strip()
    return cleaned or None

def render_draft_review(draft: dict):
    """Render a pending draft and return an action plus edited payload."""
    form_key = f"draft_form_{st.session_state.widget_key}"
    with st.form(form_key):
        st.subheader("Review draft")
        if draft.get("operation") == "update":
            st.caption(
                f"This will update {draft['target_domain'].title()} record "
                f"#{draft['target_record_id']}."
            )
        confidence = float(draft.get("confidence", 0.8))
        st.caption(f"Extraction confidence: {confidence:.0%}")
        for ambiguity in draft.get("ambiguities", []):
            st.warning(ambiguity)

        entry_date = st.date_input(
            "Entry date",
            value=date.fromisoformat(draft["entry_date"]),
            key=f"{form_key}_date",
        )

        edited_health = None
        health = draft.get("health")
        if health:
            st.markdown("#### Health")
            include_health = st.checkbox(
                "Include health record", value=True, key=f"{form_key}_health_include"
            )
            health_col1, health_col2 = st.columns(2)
            with health_col1:
                sleep_hours = st.number_input(
                    "Sleep hours",
                    min_value=0.0,
                    max_value=24.0,
                    value=health.get("sleep_hours"),
                    step=0.5,
                    key=f"{form_key}_sleep",
                )
                workout_type = st.text_input(
                    "Workout type",
                    value=health.get("workout_type") or "",
                    key=f"{form_key}_workout",
                )
            with health_col2:
                calories_consumed = st.number_input(
                    "Calories consumed",
                    min_value=0,
                    max_value=20000,
                    value=health.get("calories_consumed"),
                    step=1,
                    key=f"{form_key}_calories",
                )
                health_notes = st.text_area(
                    "Health notes",
                    value=health.get("notes") or "",
                    key=f"{form_key}_health_notes",
                )
            if include_health:
                edited_health = {
                    "sleep_hours": sleep_hours,
                    "workout_type": _empty_to_none(workout_type),
                    "calories_consumed": calories_consumed,
                    "notes": _empty_to_none(health_notes),
                }

        edited_wealth = []
        if draft.get("wealth"):
            st.markdown("#### Wealth")
        for index, wealth in enumerate(draft.get("wealth", [])):
            with st.expander(f"Transaction {index + 1}", expanded=True):
                include = st.checkbox(
                    "Include transaction",
                    value=True,
                    key=f"{form_key}_wealth_{index}_include",
                )
                col1, col2 = st.columns(2)
                with col1:
                    transaction_type = st.selectbox(
                        "Type",
                        ["Expense", "Income"],
                        index=0 if wealth["transaction_type"] == "Expense" else 1,
                        key=f"{form_key}_wealth_{index}_type",
                    )
                    amount = st.number_input(
                        "Amount",
                        min_value=0.01,
                        value=float(wealth["amount"]),
                        key=f"{form_key}_wealth_{index}_amount",
                    )
                    currency = st.text_input(
                        "Currency",
                        value=wealth.get("currency") or "INR",
                        key=f"{form_key}_wealth_{index}_currency",
                    )
                with col2:
                    category = st.text_input(
                        "Category",
                        value=wealth.get("category") or "",
                        key=f"{form_key}_wealth_{index}_category",
                    )
                    merchant = st.text_input(
                        "Merchant",
                        value=wealth.get("merchant") or "",
                        key=f"{form_key}_wealth_{index}_merchant",
                    )
                    wealth_notes = st.text_area(
                        "Notes",
                        value=wealth.get("notes") or "",
                        key=f"{form_key}_wealth_{index}_notes",
                    )
                if include:
                    edited_wealth.append(
                        {
                            "transaction_type": transaction_type,
                            "amount": amount,
                            "currency": currency,
                            "category": category,
                            "merchant": _empty_to_none(merchant),
                            "notes": _empty_to_none(wealth_notes),
                        }
                    )

        edited_learning = []
        if draft.get("learning"):
            st.markdown("#### Learning")
        for index, learning in enumerate(draft.get("learning", [])):
            with st.expander(f"Learning session {index + 1}", expanded=True):
                include = st.checkbox(
                    "Include learning session",
                    value=True,
                    key=f"{form_key}_learning_{index}_include",
                )
                topic = st.text_input(
                    "Topic",
                    value=learning.get("topic") or "",
                    key=f"{form_key}_learning_{index}_topic",
                )
                summary = st.text_area(
                    "Summary",
                    value=learning.get("summary_text") or "",
                    key=f"{form_key}_learning_{index}_summary",
                )
                learning_col1, learning_col2 = st.columns(2)
                with learning_col1:
                    duration = st.number_input(
                        "Duration in minutes",
                        min_value=0,
                        max_value=1440,
                        value=learning.get("duration_minutes"),
                        step=1,
                        key=f"{form_key}_learning_{index}_duration",
                    )
                with learning_col2:
                    url = st.text_input(
                        "Reference URL",
                        value=learning.get("url_reference") or "",
                        key=f"{form_key}_learning_{index}_url",
                    )
                if include:
                    edited_learning.append(
                        {
                            "topic": topic,
                            "summary_text": summary,
                            "duration_minutes": duration,
                            "url_reference": _empty_to_none(url),
                        }
                    )

        edited = {
            "entry_date": entry_date.isoformat(),
            "source": draft["source"],
            "original_input": draft["original_input"],
            "health": edited_health,
            "wealth": edited_wealth,
            "learning": edited_learning,
            "confidence": confidence,
            "ambiguities": draft.get("ambiguities", []),
            "operation": draft.get("operation", "create"),
            "target_domain": draft.get("target_domain"),
            "target_record_id": draft.get("target_record_id"),
        }

        action_col1, action_col2 = st.columns(2)
        with action_col1:
            confirm = st.form_submit_button(
                "Confirm and save", type="primary", use_container_width=True
            )
        with action_col2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)

    if confirm:
        return "confirm", edited
    if cancel:
        return "cancel", None
    return None, None
