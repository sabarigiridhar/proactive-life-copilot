"""Streamlit session-state and durable chat helpers."""

import uuid

import streamlit as st


def initialize_session() -> None:
    """Initialize client-side conversation and transient UI state."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = uuid.uuid4().hex

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hi! Log your day via text, voice, or photo.",
                "metadata": None,
            }
        ]

    st.session_state.setdefault("pending_draft", None)
    st.session_state.setdefault("widget_key", 0)
    st.session_state.setdefault("input_source", "text")


def register_source(new_source: str) -> None:
    current = st.session_state.input_source
    if current == "text":
        st.session_state.input_source = new_source
    elif current != new_source:
        st.session_state.input_source = "mixed"


def append_message(role: str, content: str, metadata: dict | None = None) -> None:
    """Append a rendered message; the API owns durable conversation history."""
    st.session_state.messages.append(
        {"role": role, "content": content, "metadata": metadata}
    )
