"""AI-backed intent, retrieval, and extraction graph nodes."""

from datetime import date

from life_copilot.agent.memory import _format_memory_context
from life_copilot.agent.parsing import missing_draft_domains, parse_extraction_payload
from life_copilot.agent.provider import (
    ProviderCallError,
    ProviderOutputError,
    generate_gemini_content,
)
from life_copilot.agent.state import DailyState, _state_chroma_path, _state_db_path
from life_copilot.analytics.router import route_analytics_request
from life_copilot.analytics.service import build_analytics_answer, run_analytics
from life_copilot.config import MODAL
from life_copilot.retrieval import (
    answer_learning_search,
    create_learning_search_request,
    search_learning_records,
)


def _is_learning_query(message: str) -> bool:
    lowered = message.lower()
    learning_query = any(
        term in lowered
        for term in ("learn", "learning", "studied", "study", "topic", "course")
    )
    other_domain = any(
        term in lowered
        for term in (
            "sleep",
            "slept",
            "calorie",
            "workout",
            "exercise",
            "expense",
            "spend",
            "spent",
            "income",
        )
    )
    return learning_query and not other_domain


def _answer_learning_query(state: DailyState) -> str:
    """Return only SQLite-verified records ranked by semantic relevance."""
    question = state.get("user_message", "")
    db_path = _state_db_path(state)
    request = create_learning_search_request(
        question,
        today=date.today(),
        db_path=db_path,
    )
    result = search_learning_records(
        request,
        db_path=db_path,
        chroma_path=_state_chroma_path(state),
    )
    return answer_learning_search(result)

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
    def validate_intent(text: str) -> str:
        intent = text.strip().lower()
        if intent not in {"log", "query"}:
            raise ProviderOutputError("Intent output was outside the allowlist.")
        return intent

    try:
        intent = generate_gemini_content(
            prompt,
            model_name=MODAL,
            validator=validate_intent,
            operation="intent_classification",
        )
    except ProviderCallError as exc:
        return {
            "intent": "error",
            "draft": None,
            "ai_response": str(exc),
        }
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
        answer = build_analytics_answer(result)
    except ProviderCallError as exc:
        return {"ai_response": str(exc), "draft": None}
    except ValueError as exc:
        return {"ai_response": str(exc), "draft": None}
    except Exception:
        return {
            "ai_response": "I could not calculate that safely from the stored records.",
            "draft": None,
        }
    return {
        "ai_response": answer.text,
        "draft": None,
        "evidence": answer.evidence,
        "date_range": answer.date_range.model_dump(mode="json"),
        "confidence": answer.confidence,
    }

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
    - If the message explicitly says no studying or learning happened, create one
      learning object with topic "No study", duration_minutes 0, and a concise
      summary_text.
    - Keep each purchase, income item, and learning session separate.
    - Never add unrelated amounts together.
    - Extract only information supported by the message.
    - Return valid JSON only.
    """

    try:
        draft = generate_gemini_content(
            prompt,
            model_name=MODAL,
            generation_config={"response_mime_type": "application/json"},
            validator=lambda text: parse_extraction_payload(
                text, user_message, source
            ),
            operation="daily_log_extraction",
        )
    except ProviderCallError as exc:
        return {
            "draft": None,
            "ai_response": str(exc),
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
