"""Streamlit pages for the Life Copilot application."""

from datetime import date

import streamlit as st

from life_copilot.ui.api_client import ApiClientError, get_api_client
from life_copilot.ui.dashboard import (
    dashboard_period,
    render_life_panel,
    render_wealth_panel,
)
from life_copilot.ui.draft_review import render_draft_review
from life_copilot.ui.evidence import render_message_evidence
from life_copilot.ui.record_maintenance import render_record_maintenance
from life_copilot.ui.session import append_message, initialize_session, register_source


def _render_messages() -> None:
    with st.container(
        height=330,
        border=True,
        key="conversation_history",
    ):
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if (message.get("metadata") or {}).get("event") == "api_error":
                    st.error(message["content"])
                else:
                    st.markdown(message["content"])
                render_message_evidence(message.get("metadata"))


def _reset_composer() -> None:
    st.session_state.input_source = "text"
    st.session_state.pop("audio_processed", None)
    st.session_state.pop("image_processed", None)
    st.session_state.widget_key += 1


def _render_pending_draft(api) -> None:
    action, edited_data = render_draft_review(st.session_state.pending_draft)
    if action == "cancel":
        st.session_state.pending_draft = None
        append_message("assistant", "Draft cancelled. Nothing was saved.")
        _reset_composer()
        st.rerun()
    if action != "confirm":
        return

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
        _reset_composer()
        st.rerun()
    except ApiClientError as exc:
        st.error(f"The confirmed draft could not be saved: {exc}")


def _render_media_inputs(api, current_text_key: str) -> None:
    audio_column, image_column = st.columns(2, gap="small")
    with audio_column:
        audio_value = st.audio_input(
            "Record voice",
            label_visibility="collapsed",
            key=f"audio_{st.session_state.widget_key}",
        )
    with image_column:
        uploaded_image = st.file_uploader(
            "Upload image",
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


def _render_composer(api, current_text_key: str) -> None:
    _render_media_inputs(api, current_text_key)
    current_text = st.text_area(
        "Log your day",
        height=76,
        label_visibility="collapsed",
        placeholder="Log your day or ask about your records...",
        key=current_text_key,
    )
    send = st.button(
        "Send",
        icon=":material/send:",
        use_container_width=True,
        type="primary",
        disabled=not current_text.strip(),
    )
    if not send:
        return

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
    _reset_composer()
    st.rerun()


def _render_chat_workspace(api, current_text_key: str) -> None:
    st.subheader("Copilot")
    _render_messages()
    if st.session_state.pending_draft:
        _render_pending_draft(api)
    else:
        _render_composer(api, current_text_key)


def run_app() -> None:
    """Render the API-backed home dashboard and central chat workspace."""
    api = get_api_client()
    initialize_session()

    current_text_key = f"text_area_{st.session_state.widget_key}"
    if current_text_key not in st.session_state:
        st.session_state[current_text_key] = ""

    progress_date = (
        st.session_state.pending_draft.get("entry_date")
        if st.session_state.pending_draft
        else date.today().isoformat()
    )
    today = date.today()
    start_date, end_date = dashboard_period(today)

    st.title("Life Copilot")
    st.caption(today.strftime("%A, %d %B %Y"))
    try:
        with st.spinner("Loading your dashboard..."):
            dashboard = api.get_dashboard_summary(
                status_date=date.fromisoformat(progress_date),
                start_date=start_date,
                end_date=end_date,
            )
    except ApiClientError as exc:
        st.error(str(exc))
        st.info("Start the FastAPI backend and reload this page.")
        return

    with st.container(key="home_grid"):
        wealth_column, chat_column, life_column = st.columns(
            [1.0, 1.7, 1.05],
            gap="large",
            vertical_alignment="top",
        )
        with wealth_column:
            render_wealth_panel(dashboard)
        with chat_column:
            _render_chat_workspace(api, current_text_key)
        with life_column:
            render_life_panel(dashboard)


def run_records_page() -> None:
    """Render the existing API-backed record correction workspace."""
    st.title("Records")
    api = get_api_client()
    initialize_session()
    render_record_maintenance(api)
