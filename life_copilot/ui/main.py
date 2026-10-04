"""Main Streamlit screen for Life Copilot."""

from datetime import date

import streamlit as st
from life_copilot.ui.api_client import ApiClientError, get_api_client
from life_copilot.ui.draft_review import render_draft_review
from life_copilot.ui.evidence import render_message_evidence
from life_copilot.ui.record_maintenance import render_record_maintenance
from life_copilot.ui.session import append_message, initialize_session, register_source


def run_app() -> None:
    st.set_page_config(page_title="Life Copilot", page_icon="LC")
    st.title("Life Copilot")
    st.caption("Track your Wealth, Health, and Learning.")

    api = get_api_client()
    initialize_session()

    current_text_key = f"text_area_{st.session_state.widget_key}"
    if current_text_key not in st.session_state:
        st.session_state[current_text_key] = ""

    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if (message.get("metadata") or {}).get("event") == "api_error":
                    st.error(message["content"])
                else:
                    st.markdown(message["content"])
                render_message_evidence(message.get("metadata"))

    progress_date = (
        st.session_state.pending_draft.get("entry_date")
        if st.session_state.pending_draft
        else date.today().isoformat()
    )
    try:
        with st.spinner("Loading daily status..."):
            dashboard = api.get_dashboard_summary(
                status_date=date.fromisoformat(progress_date)
            )
        today_status = dashboard.daily_status
    except ApiClientError as exc:
        st.error(str(exc))
        st.info("Start the FastAPI backend and reload this page.")
        return
    progress_label = (
        "Draft date progress"
        if st.session_state.pending_draft and progress_date != date.today().isoformat()
        else "Today's progress"
    )
    st.caption(f"{progress_label} - {today_status.entry_date.isoformat()}")
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        st.metric("Health", "Logged" if today_status.health_complete else "Pending")
    with status_col2:
        st.metric("Wealth", "Reviewed" if today_status.wealth_reviewed else "Pending")
    with status_col3:
        st.metric(
            "Learning", "Logged" if today_status.learning_complete else "Pending"
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
                with st.spinner("Saving confirmed records..."):
                    result = api.confirm_log(
                        thread_id=st.session_state.thread_id,
                        draft=edited_data,
                    )
                append_message(
                    "assistant",
                    result.assistant_text,
                    metadata={
                        "event": "confirmed_records",
                        "entities": result.entities,
                    },
                )
                st.session_state.pending_draft = None
                st.session_state.widget_key += 1
                st.rerun()
            except ApiClientError as exc:
                st.error(f"The confirmed draft could not be saved: {exc}")
    else:
        render_record_maintenance(api)
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
                    try:
                        transcription = api.transcribe_audio(
                            filename=audio_value.name or "recording.wav",
                            content=audio_value.getvalue(),
                            content_type=audio_value.type or "audio/wav",
                        )
                    except ApiClientError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state[current_text_key] += f" {transcription.text} "
                        st.session_state.audio_processed = True
                        register_source("voice")
                        st.rerun()

            if uploaded_image and "image_processed" not in st.session_state:
                with st.spinner("Analyzing..."):
                    try:
                        extraction = api.extract_image(
                            filename=uploaded_image.name,
                            content=uploaded_image.getvalue(),
                            content_type=uploaded_image.type or "application/octet-stream",
                        )
                    except ApiClientError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state[current_text_key] += f" {extraction.text} "
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
                    response_metadata = None
                    with st.spinner("Processing your message..."):
                        try:
                            response = api.send_message(
                                thread_id=st.session_state.thread_id,
                                message=user_message,
                                source=st.session_state.input_source,
                            )
                            st.session_state.thread_id = response.thread_id
                            ai_response = response.assistant_text
                            if response.draft:
                                st.session_state.pending_draft = response.draft
                            if response.response_type == "query_answer":
                                response_metadata = {
                                    "evidence": response.evidence,
                                    "date_range": response.date_range,
                                    "confidence": response.confidence,
                                }
                        except ApiClientError as exc:
                            ai_response = str(exc)
                            response_metadata = {"event": "api_error"}

                    append_message("assistant", ai_response, metadata=response_metadata)
                    st.session_state.input_source = "text"
                    if "audio_processed" in st.session_state:
                        del st.session_state["audio_processed"]
                    if "image_processed" in st.session_state:
                        del st.session_state["image_processed"]
                    st.session_state.widget_key += 1
                    st.rerun()
