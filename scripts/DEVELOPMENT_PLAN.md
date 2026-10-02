# Life Copilot Development Plan

## 1. Product Vision

Life Copilot is a personal GenAI application that turns text, voice, and image input into useful records and insights across three areas:

- **Wealth:** income, expenses, categories, merchants, budgets, and trends.
- **Health:** sleep, workouts, calories, mood, and daily consistency.
- **Learning:** topics, notes, source links, time spent, and semantic retrieval.

The finished product should let one user quickly record an event, correct it before saving, inspect historical data, ask questions across domains, and receive proactive weekly insights. It is also a learning project, so each phase should introduce one production AI concept without hiding the implementation behind unnecessary complexity.

## 2. Current Baseline

The repository already contains:

- `app.py`: Streamlit chat UI with text, image, and voice input.
- `graph.py`: LangGraph intent routing, extraction, querying, follow-up, and saving.
- `db_utils.py`: SQLite persistence and ChromaDB retrieval.
- `schemas.py`: Pydantic models for health, wealth, and learning data.
- `life_copilot.db`: local structured storage.
- `chroma_data/`: local vector storage for learning summaries.

Current capabilities include multimodal logging and basic questions over saved data. The largest gaps are reliable daily state, editing/validation, multi-turn memory, safe retrieval, tests, dashboards, and separation between backend and frontend.

## 3. Key Product Decisions

### Daily logging rules

"One log per day" should not mean one row for every domain:

- **Health:** one summary row per date, updated as more information arrives.
- **Wealth:** many transactions per date; each purchase or income item remains separate.
- **Learning:** many sessions per date; each session has its own topic and summary.
- **Daily status:** one row per date that records completion and optional daily reflection.

This preserves detail while still providing a single daily check-in experience.

### UI direction

Keep Streamlit through Phases 0-2 because it supports fast iteration while the data model and AI behavior stabilize. Build the first dashboard and table pages in Streamlit. After FastAPI is complete, migrate to **Next.js with TypeScript** if pixel-level layout, mobile behavior, streaming, or richer charts are still priorities. Avoid rebuilding the UI while backend contracts are changing.

### Source of truth

- SQLite is authoritative for all structured records and metadata.
- ChromaDB is a search index, not the only copy of learning content.
- AI output is a proposal until it passes validation and the user confirms ambiguous values.
- Analytics should be calculated in Python/SQL; the LLM should explain results, not invent or calculate them from memory.

## 4. Target Architecture

```text
Streamlit now / Next.js later
             |
          FastAPI
             |
     Life Copilot service
             |
         LangGraph
       /     |      \
  SQLite  ChromaDB  Gemini/Groq
```

Use these eventual ownership boundaries:

```text
backend/
  api/             # FastAPI routes and request/response models
  agents/          # LangGraph definition, nodes, prompts, and memory
  services/        # logging, querying, analytics, media transcription
  repositories/    # SQLite and ChromaDB access only
  models/          # Pydantic domain and API models
  core/            # settings, errors, logging, retry configuration
frontend/          # Next.js application, added in Phase 3
tests/             # unit, integration, and API tests
scripts/           # migrations, seed data, and maintenance commands
```

Do not move every file at once. First create tests, then extract one responsibility at a time.

## 5. Data Model and Migration Plan

Add versioned SQL migrations before changing existing tables. Back up `life_copilot.db` before the first migration.

Recommended tables:

| Table | Important fields | Rule |
| --- | --- | --- |
| `wealth_logs` | `id`, `logged_at`, `entry_date`, `type`, `amount`, `currency`, `category`, `merchant`, `notes`, `source` | Multiple rows per day |
| `health_logs` | `id`, `entry_date`, `sleep_hours`, `workout_type`, `workout_minutes`, `calories`, `mood`, `notes`, `updated_at` | Unique `entry_date`; upsert |
| `learning_logs` | `id`, `entry_date`, `topic`, `summary_text`, `duration_minutes`, `url`, `source` | Multiple rows per day |
| `daily_status` | `entry_date`, `health_complete`, `wealth_reviewed`, `learning_complete`, `reflection` | One row per day |
| `chat_threads` | `id`, `created_at`, `updated_at`, `title` | One row per conversation |
| `chat_messages` | `id`, `thread_id`, `role`, `content`, `created_at`, `metadata_json` | Ordered conversation history |
| `goals` | `id`, `domain`, `metric`, `target`, `period`, `active` | Used by alerts |
| `insights` | `id`, `period_start`, `period_end`, `type`, `content`, `evidence_json`, `created_at` | Saved proactive reports |

Add `created_at`, `updated_at`, and `source` (`text`, `voice`, `image`, `manual`) where useful. Store learning `summary_text` in SQLite and use the SQLite row ID as the Chroma document ID. This makes vector records replaceable and prevents duplicate IDs for repeated topics.

Migration acceptance checks:

- Existing rows remain readable.
- Running a migration twice is harmless.
- Health has at most one record for a date.
- Multiple expenses and learning sessions can share a date.
- Rebuilding ChromaDB from SQLite produces the same searchable learning set.

## 6. Delivery Roadmap

### Phase 0: Foundation and safety (2-3 days)

**Goal:** make changes repeatable and protect personal data.

Tasks:

1. Add `requirements.txt` or `pyproject.toml` with pinned compatible versions.
2. Add `.env.example` containing variable names only: `GEMINI_API_KEY`, `GROQ_API_KEY`, database path, Chroma path, environment, and log level.
3. Move model names and paths into a typed settings module.
4. Add `pytest`, temporary database fixtures, and CI-friendly test commands.
5. Replace `print` calls with structured logging that never prints private prompts or raw records by default.
6. Add custom errors for validation, provider failure, database failure, and unsupported input.
7. Add migration and backup scripts.
8. Remove temporary audio files in a `finally` block and use unique temporary filenames.

Exit criteria:

- A new developer can install and run the app from documented commands.
- Tests do not read or modify the real database.
- Secrets and personal databases remain ignored by Git.
- Startup reports missing configuration clearly.

### Phase 1: Reliable capture and one daily check-in (Week 1)

**Goal:** logging is correct before retrieval becomes more advanced.

Tasks:

1. Replace dictionary mutation with validated Pydantic models.
2. Allow extraction to return arrays of wealth and learning entries; never combine unrelated purchases.
3. Add an `entry_date` parser so phrases such as "yesterday" are resolved and shown for confirmation.
4. Introduce a draft-confirm-save flow:
   - Extract input.
   - Validate types and required fields.
   - Show a compact editable preview.
   - Ask only for truly missing or ambiguous fields.
   - Save after confirmation.
5. Upsert the health row for a date instead of inserting duplicates.
6. Save partial logs. Missing domains should not block valid data from being recorded.
7. Add edit and delete operations with confirmation.
8. Display today's completion status for health, wealth review, and learning.

Guardrails:

- Reject negative amounts and impossible health values.
- Require `Income` or `Expense` for wealth.
- Never silently convert missing numeric data to zero.
- Preserve the original input and extraction source in metadata for troubleshooting.
- Ask for confirmation when confidence is low or an image total is unclear.

Exit criteria:

- "Spent INR 250 on lunch and INR 80 on coffee" creates two draft transactions.
- A second health message updates today's health record without deleting existing fields.
- Voice, image, and text follow the same validation path.
- The user can correct every extracted field before saving.

### Phase 2: Memory, retrieval, and trustworthy answers (Week 2)

**Goal:** answer multi-turn and cross-domain questions with evidence.

Tasks:

1. Add a LangGraph checkpointer keyed by `thread_id`.
2. Keep a bounded conversation window plus a short stored summary; do not define memory only by elapsed time.
3. Resolve references such as "add 50 more to that" against the last confirmed entity. Ask a clarification when more than one candidate exists.
4. Replace free-form model-generated SQL with one of these safer approaches:
   - Preferred: typed analytics functions selected by the router.
   - Advanced fallback: read-only SQL validated with a parser, table allowlist, row limit, and timeout.
5. Build deterministic analytics functions for totals, category breakdowns, trends, streaks, averages, and date ranges.
6. Add hybrid learning retrieval using semantic similarity plus date/topic metadata filters.
7. Implement cross-domain analysis in Python by joining daily aggregates. Example: compare average sleep on days food spending exceeds INR 1,000.
8. Return an answer object containing `text`, `evidence`, `date_range`, and `confidence`.
9. Add exponential backoff with jitter for retryable provider errors and a clear user message for permanent failures.
10. Require every numerical answer to be traceable to query results. If no data exists, say so directly.

Suggested graph:

```text
START -> normalize input -> classify intent
  -> log: extract -> validate -> clarify/confirm -> persist -> END
  -> query: plan -> retrieve -> calculate -> verify evidence -> respond -> END
  -> edit: resolve entity -> confirm change -> persist -> END
```

Exit criteria:

- Follow-up references work within the same thread.
- Cross-domain answers include the period and records used.
- Provider retries are covered by tests.
- The response never reports a numeric fact absent from retrieved evidence.

### Phase 3: FastAPI backend (Week 3)

**Goal:** make the AI brain usable by any frontend.

Create these initial routes under `/api/v1`:

| Method and route | Purpose |
| --- | --- |
| `POST /messages` | Send text and receive a response plus drafts/evidence |
| `POST /media/transcriptions` | Convert audio to text |
| `POST /media/extractions` | Extract candidate data from an image |
| `POST /logs/confirm` | Confirm and persist a draft |
| `GET /logs/{domain}` | Paginated, filtered table data |
| `PATCH /logs/{domain}/{id}` | Edit a record |
| `DELETE /logs/{domain}/{id}` | Delete after explicit confirmation |
| `GET /dashboard/summary` | Totals, trends, meters, and daily status |
| `GET /insights/weekly` | Retrieve generated weekly reviews |
| `GET /health` | Service and dependency status |

Example message contract:

```json
{
  "thread_id": "optional-uuid",
  "message": "I spent 450 on groceries",
  "entry_date": "2026-09-27"
}
```

The response should include a stable `thread_id`, response type, assistant text, any proposed records, and evidence. Use multipart endpoints for media; enforce MIME type and size limits. Configure CORS only for known local/frontend origins.

Exit criteria:

- Swagger at `/docs` can exercise the complete log-confirm-query flow.
- API errors use a consistent JSON shape and appropriate HTTP status.
- Streamlit calls the API instead of importing `app_brain` directly.
- API integration tests run with provider calls mocked.

### Phase 4: Dashboard and domain pages (Week 4)

**Goal:** make recorded data visible and correctable before a full UI migration.

Build Streamlit multipage navigation first:

- **Home/Chat:** central chat, today's completion state, and recent entries.
- **Wealth:** income, expenses, net total, category chart, date filters, searchable table, edit/delete, and CSV export.
- **Health:** sleep and calorie trends, workout frequency, consistency meter, filters, and editable table.
- **Learning:** learning minutes, streak, topic distribution, semantic search, source links, and editable table.
- **Weekly Review:** generated insights with the supporting data visible.
- **Settings:** goals, currency, model configuration status, data export, and backup.

For the proposed three-column home screen:

- Left: spending for the selected period, category breakdown, and budget progress.
- Center: chat and logging controls; this remains the primary interaction.
- Right: health consistency, learning minutes/streak, and today's completion.

Make side panels collapsible on small screens. A meter must represent a configured target, such as `learning_minutes / weekly_goal`; do not show an unexplained AI score.

Exit criteria:

- Every chart has a date range and empty state.
- Clicking a chart filter updates its table.
- Tables support pagination and record correction.
- The layout remains usable at desktop and mobile widths.

### Phase 5: Next.js frontend (Week 5, optional but recommended)

**Goal:** gain full UI control once API behavior is stable.

Use Next.js, TypeScript, a small component library, and a proven chart package. Generate a typed API client from FastAPI's OpenAPI schema. Implement:

1. Persistent responsive navigation.
2. Streaming chat responses using Server-Sent Events.
3. Audio recording and image upload with progress/error states.
4. Editable extraction preview before confirmation.
5. Dashboard and domain tables matching the Phase 4 behavior.
6. Accessible keyboard navigation, loading states, empty states, and form validation.
7. Local development configuration that points to FastAPI.

Do not remove Streamlit until the Next.js app reaches feature parity. Treat Streamlit as a debugging/admin client during migration.

Exit criteria:

- All core workflows work without Streamlit.
- Frontend unit tests cover forms and state handling.
- Browser tests cover text, media, correction, query, and navigation flows.

### Phase 6: Proactive copilot (Week 6)

**Goal:** create useful insights without waiting for a question.

Tasks:

1. Add APScheduler for a single local process; choose Celery/Redis only when deploying multiple workers.
2. Generate a deterministic weekly metrics payload first, then ask the LLM to summarize it.
3. Save insight text and evidence in `insights` so reports are reproducible.
4. Add configurable goals for spending, sleep, workouts, and learning time.
5. Create alert rules with cooldowns to avoid repeated warnings.
6. Show in-app notifications first. Add email or push delivery only after explicit opt-in.
7. Allow users to dismiss, mute, or change every alert.

Example weekly review:

- Income, expenses, net cash flow, and largest category.
- Average sleep, workout count, and health-data completeness.
- Learning minutes, topics, and recalled notes.
- Cross-domain observations only when enough paired days exist.
- Two small next actions backed by the week's data.

Exit criteria:

- Re-running a weekly job does not create duplicate reports.
- Every insight links to supporting records.
- Alerts are configurable and never sent externally without consent.

### Phase 7: Production readiness (after core features)

Tasks:

1. Add authentication before hosting the app publicly.
2. Encrypt transport with HTTPS and restrict database/file permissions.
3. Add export, backup, restore, and full data deletion workflows.
4. Add request IDs, latency metrics, token usage, provider error rates, and retrieval quality metrics without logging private content.
5. Containerize backend and frontend only after local workflows are stable.
6. Choose deployment with persistent encrypted storage; SQLite and local Chroma cannot live on an ephemeral filesystem.
7. Document recovery steps and verify backups by restoring them.

## 7. Testing Strategy

Use a testing pyramid:

- **Unit tests:** date parsing, validators, calculations, routing, prompt-output parsing, and goal rules.
- **Repository tests:** CRUD and migrations against temporary SQLite and Chroma directories.
- **Graph tests:** fixed state inputs with Gemini/Groq mocked; test every conditional route.
- **API tests:** FastAPI `TestClient` for success, validation, authorization, upload limits, and failures.
- **UI tests:** component tests plus Playwright for critical end-to-end flows.
- **AI evaluation set:** 30-50 anonymized messages with expected intent, extracted records, clarification behavior, and required evidence.

Minimum release scenarios:

1. Log one and multiple expenses from text.
2. Update the same day's health record.
3. Log learning from an image and retrieve it semantically.
4. Transcribe voice and correct the resulting draft.
5. Ask a date-filtered wealth question.
6. Ask a cross-domain health/wealth question.
7. Continue a multi-turn edit using "that" or "it."
8. Handle missing API keys, rate limits, malformed model JSON, and unavailable databases.
9. Prove that rejected or unconfirmed drafts are not saved.

Do not use the real personal database in automated tests. Aim first for strong coverage of repositories, calculations, validators, and routing rather than chasing a percentage. Add a regression test for every production bug.

## 8. Security and Privacy Checklist

- Keep `.env`, databases, vectors, uploads, backups, and logs out of Git.
- Validate file type by content and extension; cap upload size and duration.
- Use parameterized SQL for writes and allowlisted query functions for reads.
- Never expose raw stack traces through the API.
- Redact secrets and personal values from application logs.
- Include confirmation for destructive actions and provide export before deletion.
- Clearly state which content is sent to Gemini or Groq.
- Add authentication, rate limiting, and strict CORS before internet deployment.
- Defend prompts against instructions embedded in uploaded documents; extracted text is data, not system instruction.

## 9. Implementation Workflow for a Beginner

Complete one vertical slice at a time:

1. Read the relevant existing file and this plan.
2. Write a small acceptance test or list exact manual checks.
3. Change the schema/model first, repository second, service/graph third, and UI last.
4. Run focused tests, then the full suite.
5. Test once with mocked AI and once manually with a real provider.
6. Update documentation and commit one coherent change.

Keep AI-assisted coding requests narrow. Example:

```text
Implement health upsert by entry_date. First inspect schemas.py and db_utils.py.
Add a migration with a unique date constraint, preserve existing data, add repository
tests using a temporary database, and do not change the UI. Show the tests run.
```

Avoid prompts such as "build Phase 1" because they encourage large, unreviewable changes. Ask the coding assistant to name assumptions, preserve current behavior, add tests, and report changed files.

## 10. Prioritized Backlog

Work in this order:

1. Dependency file, settings, temporary test databases, and baseline tests.
2. SQL migrations and corrected daily data model.
3. Draft/validate/confirm logging flow with multiple entries.
4. Health upsert, record editing, and deletion.
5. Deterministic analytics and safe query routing.
6. LangGraph thread memory and reference resolution.
7. Cross-domain retrieval with evidence.
8. FastAPI and Swagger-tested contracts.
9. Streamlit dashboard and domain pages.
10. Next.js migration after API stabilization.
11. Weekly reviews, goals, schedules, and alerts.
12. Authentication, deployment, backup, and observability.

## 11. Definition of Done

A feature is complete only when:

- Its behavior and edge cases are described.
- Models and database changes are migrated safely.
- Automated tests cover core logic and failure paths.
- The UI includes loading, empty, validation, and error states.
- Personal information and secrets are not logged or committed.
- Documentation and API examples match the implementation.
- A beginner can reproduce the feature using documented commands.

The project is complete for its first major release when logging is correct across all three input types, records are editable, questions are evidence-based, dashboards expose all stored data, multi-turn context works, weekly insights are reproducible, and the application can be backed up and restored without data loss.
