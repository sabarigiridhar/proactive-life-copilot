"""Streamlit interface for reviewing and confirming Life Copilot drafts."""

from __future__ import annotations

import os
from datetime import date

import google.generativeai as genai
import streamlit as st
from groq import Groq
from PIL import Image
from pydantic import ValidationError

import db_utils
from graph import app_brain, save_confirmed_draft
from record_ui import render_record_maintenance
from schemas import DailyLogDraft

st.set_page_config(page_title="Life Copilot", page_icon="LC")
st.title("Life Copilot")
st.caption("Track your Wealth, Health, and Learning.")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def _register_source(new_source: str) -> None:
    current = st.session_state.input_source
    if current == "text":
        st.session_state.input_source = new_source
    elif current != new_source:
        st.session_state.input_source = "mixed"


def _empty_to_none(value: str):
    cleaned = value.strip()
    return cleaned or None


def _edited_draft_form(draft: dict):
    """Render a pending draft and return an action plus edited payload."""
    form_key = f"draft_form_{st.session_state.widget_key}"
    with st.form(form_key):
        st.subheader("Review draft")
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


if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! Log your day via text, voice, or photo."}
    ]
if "pending_draft" not in st.session_state:
    st.session_state.pending_draft = None
if "widget_key" not in st.session_state:
    st.session_state.widget_key = 0
if "input_source" not in st.session_state:
    st.session_state.input_source = "text"

current_text_key = f"text_area_{st.session_state.widget_key}"
if current_text_key not in st.session_state:
    st.session_state[current_text_key] = ""

chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

today_status = db_utils.get_daily_status(date.today().isoformat())
st.caption(f"Today's progress - {today_status['entry_date']}")
status_col1, status_col2, status_col3 = st.columns(3)
with status_col1:
    st.metric("Health", "Logged" if today_status["health_complete"] else "Pending")
with status_col2:
    st.metric("Wealth", "Reviewed" if today_status["wealth_reviewed"] else "Pending")
with status_col3:
    st.metric(
        "Learning", "Logged" if today_status["learning_complete"] else "Pending"
    )

if st.session_state.pending_draft:
    action, edited_data = _edited_draft_form(st.session_state.pending_draft)
    if action == "cancel":
        st.session_state.pending_draft = None
        st.session_state.messages.append(
            {"role": "assistant", "content": "Draft cancelled. Nothing was saved."}
        )
        st.session_state.widget_key += 1
        st.rerun()
    elif action == "confirm":
        try:
            validated = DailyLogDraft.model_validate(edited_data)
            result = save_confirmed_draft(validated)
            total = result["health"] + result["wealth"] + result["learning"]
            message = f"Saved {total} confirmed record(s)."
            if result["vector_warnings"]:
                message += " Learning was saved, but vector indexing needs attention."
            status = result["daily_status"]
            missing = [
                label
                for label, complete in (
                    ("Health", status["health_complete"]),
                    ("Wealth", status["wealth_reviewed"]),
                    ("Learning", status["learning_complete"]),
                )
                if not complete
            ]
            if missing:
                message += (
                    f" Still pending for {status['entry_date']}: {', '.join(missing)}. "
                    "Would you like to log one of those next?"
                )
            else:
                message += f" Your check-in for {status['entry_date']} is complete."
            st.session_state.messages.append(
                {"role": "assistant", "content": message}
            )
            st.session_state.pending_draft = None
            st.session_state.widget_key += 1
            st.rerun()
        except ValidationError as exc:
            st.error(f"Please correct the draft: {exc}")
        except Exception as exc:
            st.error(f"The confirmed draft could not be saved: {exc}")
else:
    render_record_maintenance()
    input_container = st.container()
    with input_container:
        col1, col2 = st.columns(2)
        with col1:
            audio_value = st.audio_input(
                "Record Voice",
                label_visibility="collapsed",
                key=f"audio_{st.session_state.widget_key}",
            )
        with col2:
            uploaded_image = st.file_uploader(
                "Upload Image",
                type=["jpg", "jpeg", "png"],
                label_visibility="collapsed",
                key=f"image_{st.session_state.widget_key}",
            )

        if audio_value and "audio_processed" not in st.session_state:
            with st.spinner("Transcribing..."):
                transcription = groq_client.audio.transcriptions.create(
                    file=("recording.wav", audio_value.getvalue()),
                    model="whisper-large-v3",
                )
                st.session_state[current_text_key] += f" {transcription.text} "
                st.session_state.audio_processed = True
                _register_source("voice")
                st.rerun()

        if uploaded_image and "image_processed" not in st.session_state:
            with st.spinner("Analyzing..."):
                image = Image.open(uploaded_image)
                vision_model = genai.GenerativeModel("gemini-3.6-flash")
                vision_response = vision_model.generate_content(
                    [
                        "Extract key health, wealth, or learning data from this image in concise text.",
                        image,
                    ]
                )
                st.session_state[current_text_key] += (
                    f" {vision_response.text.strip()} "
                )
                st.session_state.image_processed = True
                _register_source("image")
                st.rerun()

        current_text = st.text_area(
            "Log your day",
            height=68,
            label_visibility="collapsed",
            placeholder="Type your log, or upload media to extract text here...",
            key=current_text_key,
        )

        if st.button("Send", use_container_width=True, type="primary"):
            if current_text.strip():
                user_message = current_text.strip()
                st.session_state.messages.append(
                    {"role": "user", "content": user_message}
                )
                with st.spinner("Preparing a draft..."):
                    try:
                        new_state = app_brain.invoke(
                            {
                                "user_message": user_message,
                                "source": st.session_state.input_source,
                                "intent": "log",
                                "draft": None,
                                "ai_response": "",
                            }
                        )
                        ai_response = new_state.get(
                            "ai_response", "No response was generated."
                        )
                        if new_state.get("draft"):
                            st.session_state.pending_draft = new_state["draft"]
                    except Exception as exc:
                        ai_response = f"An error occurred: {exc}"

                st.session_state.messages.append(
                    {"role": "assistant", "content": ai_response}
                )
                st.session_state.input_source = "text"
                if "audio_processed" in st.session_state:
                    del st.session_state["audio_processed"]
                if "image_processed" in st.session_state:
                    del st.session_state["image_processed"]
                st.rerun()
