"""AI-backed intent, retrieval, and extraction graph nodes."""

import json

from pydantic import ValidationError

from life_copilot import storage as db_utils
from life_copilot.agent.memory import _format_memory_context
from life_copilot.agent.parsing import missing_draft_domains, parse_extraction_payload
from life_copilot.agent.provider import genai
from life_copilot.agent.state import DailyState, _state_db_path
from life_copilot.analytics.router import route_analytics_request
from life_copilot.analytics.service import answer_analytics_request, run_analytics
from life_copilot.config import MODAL


def _is_learning_query(message: str) -> bool:
    lowered = message.lower()
    return any(
        term in lowered
        for term in ("learn", "learning", "studied", "study", "topic", "course")
    )


def _answer_learning_query(state: DailyState) -> str:
    """Preserve semantic learning search until P2-US3 hardens that path."""
    question = state.get("user_message", "")
    results = db_utils.search_learning_vectors(question)
    prompt = (
        f"Answer the question '{question}' using only these retrieved learning notes: "
        f"{results}. If the notes do not answer it, say so."
    )
    return genai.GenerativeModel(MODAL).generate_content(prompt).text

def classify_intent_node(state: DailyState):
    """Determine whether the user wants to log data or query history."""
    prompt = f"""
    Conversation context:
    {_format_memory_context(state)}

    Analyze the latest user message: "{state['user_message']}"
    Is the user trying to record new health, wealth, or learning information,
    or asking a question about previously stored data?
    Respond with ONLY one word: "log" or "query".
    """
    model = genai.GenerativeModel(MODAL)
    intent = model.generate_content(prompt).text.strip().lower()
    if intent not in {"log", "query"}:
        intent = "log"
    return {"intent": intent}

def answer_query_node(state: DailyState):
    """Route a question to an allowlisted calculation and format its result."""
    try:
        if _is_learning_query(state.get("user_message", "")):
            return {
                "ai_response": _answer_learning_query(state),
                "draft": None,
            }
        request = route_analytics_request(state)
        result = run_analytics(request, db_path=_state_db_path(state))
        answer = answer_analytics_request(result)
    except ValueError as exc:
        answer = str(exc)
    except Exception:
        answer = "I could not calculate that safely from the stored records."
    return {"ai_response": answer, "draft": None}

def extract_data_node(state: DailyState):
    """Extract a validated draft without writing to either database."""
    user_message = state.get("user_message", "").strip()
    source = state.get("source", "text")
    prompt = f"""
    You are a data extractor. Use conversation context only to resolve references;
    extract facts for the latest message only.

    Conversation context:
    {_format_memory_context(state)}

    Read this latest message:
    "{user_message}"

    Return one JSON object with exactly these keys:
    - "health": one object or null
    - "wealth": an array of zero or more transaction objects
    - "learning": an array of zero or more learning-session objects
    - "confidence": a number from 0 to 1
    - "ambiguities": an array of short questions or uncertainty descriptions

    Health fields: sleep_hours, workout_type, calories_consumed, notes.
    Wealth fields: transaction_type (Income or Expense), amount, currency,
    category, merchant, notes.
    Learning fields: topic, duration_minutes, summary_text, url_reference.

    Rules:
    - Use null for every unmentioned optional value. Never use zero as a placeholder.
    - Keep each purchase, income item, and learning session separate.
    - Never add unrelated amounts together.
    - Extract only information supported by the message.
    - Return valid JSON only.
    """

    model = genai.GenerativeModel("gemini-3.1-flash-lite")
    try:
        response = model.generate_content(
            prompt, generation_config={"response_mime_type": "application/json"}
        )
        draft = parse_extraction_payload(response.text, user_message, source)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return {
            "draft": None,
            "ai_response": f"I could not create a valid draft: {exc}",
        }

    count = (1 if draft.health else 0) + len(draft.wealth) + len(draft.learning)
    missing = missing_draft_domains(draft)
    response_text = f"I prepared {count} record(s). Review the draft before saving."
    if missing:
        response_text += (
            f" This draft does not include {', '.join(missing)}. "
            "Would you like to log the missing areas after confirming this draft?"
        )
    return {
        "draft": draft.model_dump(mode="json"),
        "ai_response": response_text,
    }
