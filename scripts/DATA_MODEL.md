# Life Copilot Data Model

This document describes schema version 1, introduced by `P1-US1`.

## Ownership Rules

- SQLite is the source of truth for every log and the full learning summary.
- ChromaDB is a rebuildable search index for learning summaries.
- Wealth and learning allow multiple rows for the same `entry_date`.
- Health allows exactly one row per `entry_date`; later writes merge into that row.
- Chroma document IDs use `learning_<sqlite_id>` to avoid date/topic collisions.

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

## Migration Behavior

`migrations.py` records applied versions in `schema_migrations`. Each migration runs in one SQLite transaction, and rerunning it does not alter an already migrated database.

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
