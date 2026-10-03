"""LangGraph assembly and thread-scoped checkpoint operations."""

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from life_copilot import storage as db_utils
from life_copilot.agent.memory import load_memory_node
from life_copilot.agent.nodes import answer_query_node, classify_intent_node, extract_data_node
from life_copilot.agent.references import resolve_reference_node
from life_copilot.agent.state import DailyState

def thread_config(thread_id: str) -> dict:
    """Build the LangGraph configuration used to isolate a conversation."""
    return {"configurable": {"thread_id": thread_id}}

def _entity_from_record(domain: str, record: dict) -> dict:
    fields = {
        "wealth": ("amount", "currency", "category", "merchant", "notes"),
        "health": ("workout_type", "sleep_hours", "calories_consumed", "notes"),
        "learning": ("topic", "duration_minutes", "url_reference"),
    }[domain]
    entity = {
        "domain": domain,
        "record_id": record["id"],
        "entry_date": record["entry_date"],
    }
    entity.update({field: record.get(field) for field in fields})
    return entity

def remember_confirmed_draft(
    thread_id: str,
    result: dict,
    *,
    db_path: str | Path = db_utils.DEFAULT_DB_PATH,
) -> list[dict]:
    """Store exact confirmed record references in checkpoint state and metadata."""
    entities = []
    for domain, record_ids in result.get("record_ids", {}).items():
        for record_id in record_ids:
            record = db_utils.get_domain_log(domain, record_id, db_path=db_path)
            if record:
                entities.append(_entity_from_record(domain, record))
    app_brain.update_state(
        thread_config(thread_id),
        {"last_confirmed_entities": entities, "awaiting_clarification": None},
    )
    return entities

def route_intent(state: DailyState):
    if state.get("intent") == "error":
        return "error"
    return "answer_query" if state.get("intent") == "query" else "extract_data"

def route_reference(state: DailyState):
    return state.get("reference_route", "continue")

workflow = StateGraph(DailyState)
workflow.add_node("load_memory", load_memory_node)
workflow.add_node("resolve_reference", resolve_reference_node)
workflow.add_node("classify_intent", classify_intent_node)
workflow.add_node("answer_query", answer_query_node)
workflow.add_node("extract_data", extract_data_node)
workflow.set_entry_point("load_memory")
workflow.add_edge("load_memory", "resolve_reference")
workflow.add_conditional_edges(
    "resolve_reference",
    route_reference,
    {"continue": "classify_intent", "resolved": END, "clarify": END},
)
workflow.add_conditional_edges(
    "classify_intent",
    route_intent,
    {"answer_query": "answer_query", "extract_data": "extract_data", "error": END},
)
workflow.add_edge("answer_query", END)
workflow.add_edge("extract_data", END)

memory_checkpointer = MemorySaver()
app_brain = workflow.compile(checkpointer=memory_checkpointer)
