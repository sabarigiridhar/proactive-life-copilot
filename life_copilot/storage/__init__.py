"""Persistence APIs for structured logs, conversations, and vectors."""

from life_copilot.storage.base import (
    DEFAULT_CHROMA_PATH,
    DEFAULT_DB_PATH,
    LEARNING_COLLECTION,
    init_sqlite_db,
)
from life_copilot.storage.conversations import (
    add_chat_message,
    create_chat_thread,
    get_chat_messages,
    get_last_confirmed_entities,
    get_memory_window,
    update_chat_summary,
)
from life_copilot.storage.domain_logs import (
    delete_domain_log,
    get_domain_log,
    insert_health_log,
    insert_learning_log,
    insert_wealth_log,
    list_domain_logs,
    update_health_record,
    update_learning_record,
    update_wealth_record,
)
from life_copilot.storage.daily_status import (
    get_daily_status,
    recalculate_daily_status,
    update_daily_status,
)
from life_copilot.storage.retrieval import query_sqlite, search_learning_vectors
from life_copilot.storage.vectors import (
    add_learning_vector,
    backfill_learning_summaries_from_chroma,
    delete_learning_vector,
    init_chroma_db,
    rebuild_learning_vectors,
)

__all__ = [name for name in globals() if not name.startswith("_")]
