"""LangGraph routing, validated extraction, and confirmed draft persistence."""

from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import TypedDict

import google.generativeai as genai
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from pydantic import ValidationError

import db_utils
from Constants import MODAL
from schemas import DailyLogDraft, ExtractionPayload, InputSource

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


class DailyState(TypedDict, total=False):
    user_message: str
    source: InputSource
    intent: str
    draft: dict | None
    ai_response: str


def missing_draft_domains(draft: DailyLogDraft) -> list[str]:
    """Return domains not represented in the current draft."""
    missing = []
    if draft.health is None:
        missing.append("Health")
    if not draft.wealth:
        missing.append("Wealth")
    if not draft.learning:
        missing.append("Learning")
    return missing


def resolve_entry_date(user_message: str, today: date | None = None) -> date:
    """Resolve an explicit ISO date, yesterday, or today from a message."""
    base_date = today or date.today()
    explicit_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", user_message)
    if explicit_date:
        try:
            return date.fromisoformat(explicit_date.group(0))
        except ValueError as exc:
            raise ValueError(
                f"'{explicit_date.group(0)}' is not a valid calendar date."
            ) from exc

    lowered = user_message.lower()
    if re.search(r"\byesterday\b", lowered):
        return base_date - timedelta(days=1)
    return base_date


def parse_extraction_payload(
    raw_payload: str | dict,
    user_message: str,
    source: InputSource = "text",
    today: date | None = None,
) -> DailyLogDraft:
    """Validate untrusted model output and attach trusted request metadata."""
    data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    extracted = ExtractionPayload.model_validate(data)
    return DailyLogDraft(
        entry_date=resolve_entry_date(user_message, today=today),
        source=source,
        original_input=user_message,
        health=extracted.health,
        wealth=extracted.wealth,
        learning=extracted.learning,
        confidence=extracted.confidence,
        ambiguities=extracted.ambiguities,
    )


def classify_intent_node(state: DailyState):
    """Determine whether the user wants to log data or query history."""
    prompt = f"""
    Analyze this user message: "{state['user_message']}"
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
    """Handle existing SQL or vector retrieval queries."""
    model = genai.GenerativeModel(MODAL)
    router_prompt = f"""
    The user asked: "{state['user_message']}"
    If this is about spending or health, write a SQLite query for:
    - wealth_logs(id, entry_date, transaction_type, amount, currency, category, merchant, notes)
    - health_logs(id, entry_date, sleep_hours, workout_type, calories_consumed, notes)
    Return ONLY a raw SQL SELECT statement.

    If it is about learning, return exactly "VECTOR" followed by the search topic.
    """
    decision = model.generate_content(router_prompt).text.strip()
    decision = decision.replace("```sql", "").replace("```", "").strip()
    print(f"Decision made by AI: {decision}")

    if decision.startswith("SELECT"):
        raw_results = db_utils.query_sqlite(decision)
        final_prompt = (
            f"The user asked: '{state['user_message']}'. The database returned: "
            f"{raw_results}. Answer naturally in 1-2 sentences."
        )
        print(f"Final prompt for SQL query: {final_prompt}")
    else:
        search_term = decision.replace("VECTOR", "").strip()
        raw_results = db_utils.search_learning_vectors(search_term)
        final_prompt = (
            f"The user asked: '{state['user_message']}'. The learning notes returned: "
            f"{raw_results}. Answer naturally."
        )
        print(f"Final prompt for vector search: {final_prompt}")

    answer = model.generate_content(final_prompt).text
    print(f"Final AI response: {answer}")
    return {"ai_response": answer, "draft": None}


def extract_data_node(state: DailyState):
    """Extract a validated draft without writing to either database."""
    user_message = state.get("user_message", "").strip()
    source = state.get("source", "text")
    prompt = f"""
    You are a data extractor. Read this message:
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


def save_confirmed_draft(
    draft_data: DailyLogDraft | dict,
    db_path: str | Path = db_utils.DEFAULT_DB_PATH,
    vector_collection=None,
) -> dict:
    """Validate and persist a user-confirmed draft."""
    draft = (
        draft_data
        if isinstance(draft_data, DailyLogDraft)
        else DailyLogDraft.model_validate(draft_data)
    )
    entry_date = draft.entry_date.isoformat()
    original_input = draft.original_input
    result = {"health": 0, "wealth": 0, "learning": 0, "vector_warnings": []}

    if draft.health:
        health = draft.health
        db_utils.insert_health_log(
            entry_date,
            health.sleep_hours,
            health.workout_type,
            health.calories_consumed,
            health.notes,
            source=draft.source,
            original_input=original_input,
            db_path=db_path,
        )
        result["health"] = 1

    for wealth in draft.wealth:
        db_utils.insert_wealth_log(
            entry_date,
            wealth.transaction_type,
            wealth.amount,
            wealth.currency,
            wealth.category,
            wealth.merchant,
            wealth.notes,
            source=draft.source,
            original_input=original_input,
            db_path=db_path,
        )
        result["wealth"] += 1

    collection = vector_collection
    vector_available = True
    for learning in draft.learning:
        learning_id = db_utils.insert_learning_log(
            entry_date,
            learning.topic,
            learning.duration_minutes,
            learning.url_reference,
            summary_text=learning.summary_text,
            source=draft.source,
            original_input=original_input,
            db_path=db_path,
        )
        result["learning"] += 1

        if vector_available:
            try:
                collection = collection or db_utils.init_chroma_db()
                db_utils.add_learning_vector(
                    collection,
                    learning_id,
                    entry_date,
                    learning.topic,
                    learning.summary_text,
                    learning.url_reference,
                )
            except Exception as exc:
                vector_available = False
                result["vector_warnings"].append(
                    f"Learning row {learning_id} was saved, but vector indexing failed: {exc}"
                )

    result["daily_status"] = db_utils.update_daily_status(
        entry_date,
        health_complete=draft.health is not None,
        wealth_reviewed=bool(draft.wealth),
        learning_complete=bool(draft.learning),
        db_path=db_path,
    )
    return result


def route_intent(state: DailyState):
    return "answer_query" if state.get("intent") == "query" else "extract_data"


workflow = StateGraph(DailyState)
workflow.add_node("classify_intent", classify_intent_node)
workflow.add_node("answer_query", answer_query_node)
workflow.add_node("extract_data", extract_data_node)
workflow.set_entry_point("classify_intent")
workflow.add_conditional_edges(
    "classify_intent",
    route_intent,
    {"answer_query": "answer_query", "extract_data": "extract_data"},
)
workflow.add_edge("answer_query", END)
workflow.add_edge("extract_data", END)

app_brain = workflow.compile()
