"""Main Streamlit screen for Life Copilot."""

import os
from datetime import date

import google.generativeai as genai
import streamlit as st
from groq import Groq
from PIL import Image
from pydantic import ValidationError

from life_copilot import storage
from life_copilot.agent import workflow
from life_copilot.models import DailyLogDraft
from life_copilot.services.drafts import save_confirmed_draft
from life_copilot.ui.draft_review import render_draft_review
from life_copilot.ui.record_maintenance import render_record_maintenance
from life_copilot.ui.session import append_message, initialize_session, register_source


def run_app() -> None:
    st.set_page_config(page_title="Life Copilot", page_icon="LC")
    st.title("Life Copilot")
    st.caption("Track your Wealth, Health, and Learning.")

    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    initialize_session()

    current_text_key = f"text_area_{st.session_state.widget_key}"
    if current_text_key not in st.session_state:
        st.session_state[current_text_key] = ""

    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    today_status = storage.get_daily_status(date.today().isoformat())
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
        action, edited_data = render_draft_review(st.session_state.pending_draft)
        if action == "cancel":
            st.session_state.pending_draft = None
            append_message("assistant", "Draft cancelled. Nothing was saved.")
            st.session_state.widget_key += 1
            st.rerun()
        elif action == "confirm":
            try:
                validated = DailyLogDraft.model_validate(edited_data)
                result = save_confirmed_draft(validated)
                entities = workflow.remember_confirmed_draft(
                    st.session_state.thread_id, result
                )
                total = result["health"] + result["wealth"] + result["learning"]
                action_word = "Updated" if validated.operation == "update" else "Saved"
                message = f"{action_word} {total} confirmed record(s)."
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
                append_message(
                    "assistant",
                    message,
                    metadata={"event": "confirmed_records", "entities": entities},
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
                    register_source("voice")
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
                    register_source("image")
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
                    append_message("user", user_message)
                    with st.spinner("Processing your message..."):
                        try:
                            new_state = workflow.app_brain.invoke(
                                {
                                    "user_message": user_message,
                                    "source": st.session_state.input_source,
                                    "intent": "log",
                                    "draft": None,
                                    "ai_response": "",
                                    "thread_id": st.session_state.thread_id,
                                },
                                config=workflow.thread_config(st.session_state.thread_id),
                            )
                            ai_response = new_state.get(
                                "ai_response", "No response was generated."
                            )
                            if new_state.get("draft"):
                                st.session_state.pending_draft = new_state["draft"]
                        except Exception as exc:
                            ai_response = f"An error occurred: {exc}"

                    append_message("assistant", ai_response)
                    st.session_state.input_source = "text"
                    if "audio_processed" in st.session_state:
                        del st.session_state["audio_processed"]
                    if "image_processed" in st.session_state:
                        del st.session_state["image_processed"]
                    st.session_state.widget_key += 1
                    st.rerun()
