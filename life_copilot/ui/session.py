"""Streamlit session-state and durable chat helpers."""

import uuid

import streamlit as st

from life_copilot import storage


def initialize_session() -> None:
    """Initialize the database-backed conversation and transient UI state."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = uuid.uuid4().hex
    storage.init_sqlite_db()
    storage.create_chat_thread(st.session_state.thread_id)

    if "messages" not in st.session_state:
        messages = storage.get_chat_messages(st.session_state.thread_id, limit=100)
        if not messages:
            greeting = "Hi! Log your day via text, voice, or photo."
            storage.add_chat_message(
                st.session_state.thread_id, "assistant", greeting
            )
            messages = storage.get_chat_messages(st.session_state.thread_id)
        st.session_state.messages = [
            {
                "role": message["role"],
                "content": message["content"],
                "metadata": message.get("metadata"),
            }
            for message in messages
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
    """Keep rendered session state and durable conversation history in sync."""
    storage.add_chat_message(
        st.session_state.thread_id, role, content, metadata=metadata
    )
    st.session_state.messages.append(
        {"role": role, "content": content, "metadata": metadata}
    )
