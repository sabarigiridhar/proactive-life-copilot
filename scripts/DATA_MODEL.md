# Life Copilot Data Model

This document describes the current SQLite schema through version 4.

## Ownership Rules

- SQLite is the source of truth for every log and the full learning summary.
- ChromaDB is a rebuildable search index for learning summaries.
- Wealth and learning allow multiple rows for the same `entry_date`.
- Health allows exactly one row per `entry_date`; later writes merge into that row.
- Chroma document IDs use `learning_<sqlite_id>` to avoid date/topic collisions.
- Chroma metadata includes the topic, ISO date, and numeric `date_ordinal`; SQLite remains authoritative for every field returned to the user.

## Shared Fields

All domain tables contain:

- `id`: SQLite-generated integer identity.
- `entry_date`: logical date in `YYYY-MM-DD` form.
- `source`: input origin such as `text`, `voice`, `image`, or `legacy`.
- `original_input`: private source text attached only after confirmation.
- `created_at` and `updated_at`: audit timestamps.

`wealth_logs` stores one transaction per row. `health_logs.entry_date` is unique. `learning_logs` stores `summary_text` in addition to topic, duration, and URL so Chroma can be recreated from SQLite.

For health upserts, omitted values remain unchanged. Explicit scalar measurements such as sleep hours replace their earlier value, while distinct workout types and notes are appended. This allows separate meal and workout messages to contribute to the same daily summary without erasing one another.

## Draft Confirmation Boundary

AI extraction creates a validated `DailyLogDraft` in session state; it does not write to SQLite or ChromaDB. The draft contains a resolved entry date, source, confidence, ambiguities, optional health record, and arrays of wealth and learning records. The user can edit fields or exclude records, then confirm or cancel. Confirm validates and saves the values currently shown in the form; no intermediate save action is required. Only `save_confirmed_draft()` may persist a draft.

Confirmed rows retain their input source and original text for private troubleshooting. When several confirmed health messages update one day, distinct original inputs are retained together and differing source types become `mixed`.

## Daily Completion

`daily_status` contains one row per `entry_date` with `health_complete`, `wealth_reviewed`, and `learning_complete` flags. Confirming a partial draft sets only its represented domains; later drafts for the same date advance the remaining flags without clearing prior progress. Migration 3 backfills this table from existing logs, so the UI reflects database state rather than the current chat session.

## Record Maintenance

Confirmed records are fetched through an allowlisted domain repository that never returns `original_input` to the maintenance UI. Edits are revalidated with the same Pydantic domain models used for drafts and replace the selected record's editable fields exactly. Moving or deleting a record recalculates completion for every affected date.

Learning updates upsert `learning_<sqlite_id>` in ChromaDB and remove any matching legacy date/topic ID. Learning deletion removes the vector and SQLite row. If Chroma is unavailable, SQLite remains authoritative and the UI reports that vector synchronization needs attention. Deletion always requires a separate permanent-delete confirmation.

## Learning Retrieval

Learning search applies exact topic and date metadata filters before vector ranking. Each ranked Chroma ID is hydrated from `learning_logs`; stale vector IDs are discarded and vector documents are never shown as authoritative content. If Chroma is empty or unavailable, a bounded keyword ranking over filtered SQLite records returns a clearly labeled fallback. The fixture in `tests/fixtures/learning_retrieval_cases.json` measures whether expected summaries appear within each case's top-k results.

## Conversation Memory

`chat_threads` stores a stable thread ID, rolling summary, summary cursor, and timestamps. `chat_messages` stores ordered user and assistant messages plus optional JSON metadata. Confirmed-record metadata contains domain and SQLite IDs, allowing follow-up references to target exact records after a Streamlit rerun.

LangGraph also uses an in-process checkpointer keyed by `thread_id`; thread IDs must be supplied on every invocation. Model prompts receive at most eight recent messages plus the rolling summary. Older messages are summarized once and the cursor prevents repeated processing. A reference such as "add 50 more to that" creates a validated update draft. If several recent records could match, the graph requests a record ID, merchant, category, or ordinal before creating the draft.

## Safe Analytics

Structured questions are converted to an `AnalyticsRequest` with an allowlisted operation, bounded date range, validated filters, and result limit. Supported operations include wealth totals, category breakdowns, daily trends, health averages, workout metrics, and cross-domain threshold comparisons.

Each operation executes fixed parameterized SQL from `life_copilot/storage/analytics.py`. The model may return validated routing JSON but never executable SQL. User-facing answers are formatted directly from `AnalyticsResult`, including the calculation period and matched-record count where relevant. Free-form SQL is disabled, and analytics requests cannot span more than 367 inclusive days or return more than 100 grouped rows.

Cross-domain analysis loads typed daily health, wealth, and learning aggregates using fixed queries, then joins them by `entry_date` in Python. Comparisons include only dates containing both requested metrics. Expense metrics remain scoped to one currency and optional category. Results return `text`, daily `evidence`, `date_range`, and `confidence`; this metadata is persisted with the chat message and displayed in the UI. At least three dates are required in both threshold groups before reporting a directional observation, and responses explicitly avoid causal claims.

## Migration Behavior

`life_copilot/storage/migrations.py` records applied versions in `schema_migrations`. Version 4 adds conversation memory. Each migration runs in one SQLite transaction, and rerunning it does not alter an already migrated database.

Legacy wealth and learning rows retain their IDs and remain separate. Duplicate health rows are consolidated by date:

- The highest legacy ID becomes the daily row ID.
- The latest positive sleep/calorie value is retained because the old application used zero for missing values.
- Distinct workout types and notes are combined so information is not discarded.
- Migrated rows receive `source = legacy`.

Run the guarded migration command from the repository root:

```powershell
python scripts/migrate_database.py --rebuild-vectors
```

The command creates a timestamped backup under ignored `backups/`, migrates SQLite, recovers available legacy summaries from Chroma, and rebuilds the vector index with stable IDs.
