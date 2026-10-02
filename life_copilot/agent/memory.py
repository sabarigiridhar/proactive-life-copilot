"""Bounded conversation context and rolling summarization."""

from life_copilot import storage as db_utils
from life_copilot.agent.provider import genai
from life_copilot.agent.state import DailyState, _state_db_path
from life_copilot.config import MODAL

RECENT_MESSAGE_LIMIT = 8

def _format_memory_context(state: DailyState) -> str:
    """Render the bounded persisted context supplied to model prompts."""
    sections = []
    if state.get("conversation_summary"):
        sections.append(f"Earlier conversation summary:\n{state['conversation_summary']}")
    recent = state.get("recent_messages") or []
    if recent:
        messages = "\n".join(
            f"{message['role']}: {message['content']}" for message in recent
        )
        sections.append(f"Recent messages:\n{messages}")
    return "\n\n".join(sections) or "No prior conversation context."

def _summarize_messages(previous_summary: str | None, messages: list[dict]) -> str:
    """Create a compact rolling summary, with a deterministic offline fallback."""
    transcript = "\n".join(
        f"{message['role']}: {message['content']}" for message in messages
    )
    prompt = f"""
    Update this concise conversation summary for a personal life-tracking assistant.
    Preserve concrete dates, amounts, activities, topics, and unresolved references.
    Do not invent details. Return only the updated summary.

    Previous summary:
    {previous_summary or 'None'}

    Messages to add:
    {transcript}
    """
    try:
        summary = genai.GenerativeModel(MODAL).generate_content(prompt).text.strip()
        if summary:
            return summary
    except Exception:
        pass

    combined = "\n".join(part for part in (previous_summary, transcript) if part)
    return combined[-4000:]

def load_memory_node(state: DailyState):
    """Load a bounded conversation window and roll older messages into a summary."""
    thread_id = state.get("thread_id")
    if not thread_id:
        return {"recent_messages": [], "conversation_summary": None}

    db_path = _state_db_path(state)
    window = db_utils.get_memory_window(
        thread_id, recent_limit=RECENT_MESSAGE_LIMIT, db_path=db_path
    )
    summary = window["summary"]
    older = window["unsummarized_messages"]
    if older:
        summary = _summarize_messages(summary, older)
        db_utils.update_chat_summary(
            thread_id, summary, older[-1]["id"], db_path=db_path
        )

    entities = state.get("last_confirmed_entities")
    if not entities:
        entities = db_utils.get_last_confirmed_entities(thread_id, db_path=db_path)
    return {
        "recent_messages": window["recent_messages"],
        "conversation_summary": summary,
        "last_confirmed_entities": entities,
    }
