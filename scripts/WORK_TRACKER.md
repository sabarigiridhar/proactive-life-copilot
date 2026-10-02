# Life Copilot Work Tracker

This file is the execution tracker for the work defined in `DEVELOPMENT_PLAN.md`. It follows an Azure DevOps-style hierarchy:

```text
Phase (Epic) -> Feature -> User Story -> Task
```

Phase 0 is intentionally omitted. Update this file in the same pull request or commit as the related implementation.

## Tracking Rules

### Allowed states

| State | Meaning |
| --- | --- |
| `Not Started` | No implementation work has begun. |
| `Ready` | Requirements and dependencies are clear. |
| `In Progress` | Someone is actively implementing it. |
| `Blocked` | Work cannot continue; document the blocker. |
| `In Review` | Implementation is complete and being verified. |
| `Done` | Acceptance criteria pass and documentation is updated. |
| `Deferred` | Intentionally postponed with a recorded reason. |

### How to update an item

1. Change its `State` in the relevant table.
2. Change `[ ]` to `[x]` only when a task is `Done`.
3. Add the owner, branch/PR, or commit when available.
4. Record blockers in the Notes column and in the Blockers section.
5. Mark a story `Done` only after every required task and acceptance criterion passes.
6. Update the phase dashboard and change log before ending the work session.

## Phase Dashboard

| Phase | Epic | State | Depends on | Target result |
| --- | --- | --- | --- | --- |
| P1 | Reliable Capture and Daily Check-in | Done | None | Validated, editable multimodal logging |
| P2 | Memory and Trustworthy Retrieval | Not Started | P1 | Multi-turn, evidence-based answers |
| P3 | FastAPI Backend | Not Started | P1, P2 | Stable API usable by any frontend |
| P4 | Dashboard and Domain Pages | Not Started | P1, preferably P3 | Visible and editable personal data |
| P5 | Next.js Frontend | Not Started | P3, P4 UX validated | Full-control production frontend |
| P6 | Proactive Copilot | Not Started | P2, P3 | Weekly insights, goals, and alerts |
| P7 | Production Readiness | Not Started | P3-P6 as applicable | Secure, deployable, recoverable app |

---

# P1: Reliable Capture and Daily Check-in

**Epic state:** `Done`  
**Goal:** Ensure text, voice, and image inputs produce correct drafts that users can review before data is saved.

## P1-F1: Correct Daily Data Model

**Feature state:** `Done`

### P1-US1: Store the right number of records per day

**State:** `Done`  
**User story:** As a user, I want one health summary but multiple wealth and learning entries per day so no detail is overwritten or combined incorrectly.

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [x] | P1-T01 | Design the revised tables and document field constraints. | Done | None | See `DATA_MODEL.md`. |
| [x] | P1-T02 | Add a versioned migration mechanism. | Done | P1-T01 | Schema version 1 applied. |
| [x] | P1-T03 | Add `entry_date`, timestamps, and input `source` fields. | Done | P1-T02 | Existing rows marked `legacy`. |
| [x] | P1-T04 | Add a unique date rule and upsert behavior for health. | Done | P1-T03 | Eight rows consolidated into three dates. |
| [x] | P1-T05 | Store learning summary text in SQLite. | Done | P1-T03 | Four legacy summaries recovered. |
| [x] | P1-T06 | Use the SQLite learning row ID as the Chroma document ID. | Done | P1-T05 | New/rebuilt IDs use `learning_<id>`. |
| [x] | P1-T07 | Add a script to rebuild the learning vector index from SQLite. | Done | P1-T06 | Guarded, backup-first command added. |
| [x] | P1-T08 | Test migration repeatability and preservation of existing rows. | Done | P1-T02-P1-T07 | Eight tests passing. |

**Acceptance criteria:**

- A date can contain many wealth transactions and learning sessions.
- A date contains at most one health summary, which can be updated.
- Existing records remain readable after migration.
- Rebuilding ChromaDB does not duplicate learning records.

## P1-F2: Draft, Validate, and Confirm

**Feature state:** `Done`

### P1-US2: Review extracted information before saving

**State:** `Done`  
**User story:** As a user, I want the AI to show editable extracted records before saving so I can correct mistakes.

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [x] | P1-T09 | Replace untyped graph dictionaries with validated Pydantic models. | Done | P1-US1 | Added domain, extraction, and daily draft models. |
| [x] | P1-T10 | Support arrays of wealth and learning entries in extraction output. | Done | P1-T09 | Separate entries are never combined. |
| [x] | P1-T11 | Add date parsing for today, yesterday, and explicit dates. | Done | P1-T09 | Resolved date is editable before confirmation. |
| [x] | P1-T12 | Add domain validators and clear validation messages. | Done | P1-T09 | Numeric bounds and required content validated. |
| [x] | P1-T13 | Add a confidence/ambiguity result to extracted drafts. | Done | P1-T10 | Displayed in the review form. |
| [x] | P1-T14 | Build an editable Streamlit draft preview. | Done | P1-T10-P1-T13 | Health, wealth, learning, and date are editable. |
| [x] | P1-T15 | Add Confirm, Edit, and Cancel actions. | Done | P1-T14 | Fields are edited inline; Confirm saves current values and Cancel discards them. |
| [x] | P1-T16 | Save only confirmed records. | Done | P1-T15 | Extraction graph has no persistence node. |
| [x] | P1-T17 | Preserve original input and source as private metadata. | Done | P1-T16 | Added schema version 2. |

**Acceptance criteria:**

- Two expenses in one prompt appear as two editable draft rows.
- Missing values remain absent rather than silently becoming zero.
- No rejected or cancelled draft reaches either database.
- Relative dates are displayed as resolved dates before confirmation.

### P1-US3: Handle partial daily logs

**State:** `Done`  
**User story:** As a user, I want to save one domain without completing all three so a missing log does not block valid data.

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [x] | P1-T18 | Remove the requirement that all three domains exist before saving. | Done | P1-US2 | Any one validated domain can be confirmed independently. |
| [x] | P1-T19 | Add a `daily_status` record or equivalent completion query. | Done | P1-US1 | Schema version 3 includes backfilled persistent status. |
| [x] | P1-T20 | Show today's health, wealth-review, and learning status. | Done | P1-T19 | Three database-backed indicators appear above the input. |
| [x] | P1-T21 | Ask follow-up questions without discarding the current draft. | Done | P1-T18 | Missing domains are named while the extracted draft stays pending. |
| [x] | P1-T22 | Test partial, resumed, and completed daily check-ins. | Done | P1-T18-P1-T21 | Health, wealth, and learning progression is covered. |

**Acceptance criteria:**

- A wealth-only message can be confirmed and saved.
- Completion indicators reflect database state, not chat state.
- A later message can fill another domain for the same date.

## P1-F3: Record Maintenance

**Feature state:** `Done`

### P1-US4: Correct or remove saved records

**State:** `Done`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [x] | P1-T23 | Add repository methods to fetch records by ID. | Done | P1-US1 | Domain allowlist excludes private original input. |
| [x] | P1-T24 | Add validated update methods for each domain. | Done | P1-T23 | Edits reuse Pydantic domain validation. |
| [x] | P1-T25 | Add delete methods with explicit confirmation. | Done | P1-T23 | UI requires a separate permanent-delete click. |
| [x] | P1-T26 | Keep SQLite and Chroma learning records synchronized on edit/delete. | Done | P1-T24-P1-T25 | Stable and legacy vector IDs are handled. |
| [x] | P1-T27 | Add repository and UI tests for edit/delete behavior. | Done | P1-T24-P1-T26 | CRUD tests and Streamlit interaction smoke test pass. |

**Phase P1 exit criteria:** All P1 stories are `Done`; text, voice, and image use the same validated confirmation flow; health updates do not duplicate rows.

---

# P2: Memory and Trustworthy Retrieval

**Epic state:** `Not Started`  
**Goal:** Support multi-turn context and answer analytical questions only from retrieved evidence.

## P2-F1: Conversation Memory

### P2-US1: Continue a conversation using prior context

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P2-T01 | Define `chat_threads` and `chat_messages` tables. | Not Started | P1-US1 | |
| [ ] | P2-T02 | Add a LangGraph checkpointer keyed by `thread_id`. | Not Started | P2-T01 | |
| [ ] | P2-T03 | Implement a bounded recent-message window. | Not Started | P2-T02 | |
| [ ] | P2-T04 | Add conversation summarization for older messages. | Not Started | P2-T03 | |
| [ ] | P2-T05 | Track the last confirmed entities in graph state. | Not Started | P2-T02 | |
| [ ] | P2-T06 | Resolve references such as "that" and "it." | Not Started | P2-T05 | |
| [ ] | P2-T07 | Ask for clarification when multiple prior entities match. | Not Started | P2-T06 | |
| [ ] | P2-T08 | Test memory isolation between thread IDs. | Not Started | P2-T02-P2-T07 | |

**Acceptance criteria:**

- "Add 50 more to that" updates the intended recent draft or record.
- Ambiguous references trigger a clarification instead of a guess.
- Two chat threads never share memory.

## P2-F2: Safe Retrieval and Analytics

### P2-US2: Answer structured questions safely

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P2-T09 | Define typed analytics requests and result models. | Not Started | P1 | |
| [ ] | P2-T10 | Implement date-range and total calculations. | Not Started | P2-T09 | |
| [ ] | P2-T11 | Implement category breakdown and trend calculations. | Not Started | P2-T09 | |
| [ ] | P2-T12 | Implement health averages, workout frequency, and streaks. | Not Started | P2-T09 | |
| [ ] | P2-T13 | Route common questions to allowlisted analytics functions. | Not Started | P2-T10-P2-T12 | |
| [ ] | P2-T14 | If free-form SQL remains, add parser validation, table allowlists, limits, and timeout. | Not Started | P2-T13 | Prefer typed functions. |
| [ ] | P2-T15 | Add tests for invalid, destructive, and oversized queries. | Not Started | P2-T13-P2-T14 | |

### P2-US3: Search learning records accurately

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P2-T16 | Add topic and date metadata filters to vector retrieval. | Not Started | P1-T06 | |
| [ ] | P2-T17 | Combine semantic results with SQLite record details. | Not Started | P2-T16 | |
| [ ] | P2-T18 | Handle an empty or unavailable vector index gracefully. | Not Started | P2-T16 | |
| [ ] | P2-T19 | Create learning-retrieval evaluation examples. | Not Started | P2-T17 | |
| [ ] | P2-T20 | Measure whether expected notes appear in top results. | Not Started | P2-T19 | |

### P2-US4: Answer cross-domain questions with evidence

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P2-T21 | Create daily aggregate models for all domains. | Not Started | P2-US2 | |
| [ ] | P2-T22 | Join daily aggregates by date in Python or controlled SQL. | Not Started | P2-T21 | |
| [ ] | P2-T23 | Implement threshold and comparison questions. | Not Started | P2-T22 | Example: sleep versus food spending. |
| [ ] | P2-T24 | Return `text`, `evidence`, `date_range`, and `confidence`. | Not Started | P2-T23 | |
| [ ] | P2-T25 | Require a minimum sample size for correlation-style observations. | Not Started | P2-T23 | |
| [ ] | P2-T26 | Add regression tests for numeric grounding. | Not Started | P2-T24-P2-T25 | |

## P2-F3: Provider Reliability and Guardrails

### P2-US5: Recover cleanly from AI provider failures

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P2-T27 | Classify retryable and permanent provider errors. | Not Started | None | |
| [ ] | P2-T28 | Add exponential backoff with jitter and retry limits. | Not Started | P2-T27 | |
| [ ] | P2-T29 | Validate all model output before using it. | Not Started | P1-T09 | |
| [ ] | P2-T30 | Add grounded-answer verification for numerical claims. | Not Started | P2-T24 | |
| [ ] | P2-T31 | Add user-safe fallback messages. | Not Started | P2-T27 | |
| [ ] | P2-T32 | Test rate limits, timeouts, malformed JSON, and empty output. | Not Started | P2-T28-P2-T31 | |

**Phase P2 exit criteria:** Multi-turn tests pass, all numerical responses expose evidence, unsafe queries are rejected, and provider failures do not corrupt state.

---

# P3: FastAPI Backend

**Epic state:** `Not Started`  
**Goal:** Expose a documented, versioned API and remove direct UI-to-graph coupling.

## P3-F1: API Foundation

### P3-US1: Run the Life Copilot as an API service

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P3-T01 | Create the `backend/api`, `services`, `repositories`, `models`, and `core` packages. | Not Started | P1, P2 | Move incrementally. |
| [ ] | P3-T02 | Create the FastAPI application and `/api/v1` router. | Not Started | P3-T01 | |
| [ ] | P3-T03 | Add typed settings and dependency injection. | Not Started | P3-T01 | |
| [ ] | P3-T04 | Add `/health` with database and vector-store checks. | Not Started | P3-T02 | |
| [ ] | P3-T05 | Define a consistent success/error response format. | Not Started | P3-T02 | |
| [ ] | P3-T06 | Configure local CORS from settings. | Not Started | P3-T03 | |
| [ ] | P3-T07 | Add request IDs and safe request logging. | Not Started | P3-T02 | |

## P3-F2: Conversation and Media API

### P3-US2: Send messages through the API

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P3-T08 | Implement `POST /api/v1/messages`. | Not Started | P3-F1, P2 | |
| [ ] | P3-T09 | Return stable thread ID, response type, drafts, and evidence. | Not Started | P3-T08 | |
| [ ] | P3-T10 | Implement `POST /api/v1/logs/confirm`. | Not Started | P3-T08, P1-US2 | |
| [ ] | P3-T11 | Add API tests for log, query, clarify, and confirm paths. | Not Started | P3-T08-P3-T10 | Mock providers. |

### P3-US3: Process audio and images safely

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P3-T12 | Implement multipart audio transcription endpoint. | Not Started | P3-F1 | |
| [ ] | P3-T13 | Implement multipart image extraction endpoint. | Not Started | P3-F1 | |
| [ ] | P3-T14 | Enforce MIME type, file size, and duration/dimension limits. | Not Started | P3-T12-P3-T13 | |
| [ ] | P3-T15 | Use unique temporary files and guaranteed cleanup. | Not Started | P3-T12 | |
| [ ] | P3-T16 | Test invalid files, provider errors, and cleanup. | Not Started | P3-T12-P3-T15 | |

## P3-F3: Records and Dashboard API

### P3-US4: Manage domain records through REST

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P3-T17 | Implement paginated `GET /logs/{domain}` with filters. | Not Started | P1-F3 | |
| [ ] | P3-T18 | Implement `PATCH /logs/{domain}/{id}`. | Not Started | P3-T17 | |
| [ ] | P3-T19 | Implement `DELETE /logs/{domain}/{id}`. | Not Started | P3-T17 | |
| [ ] | P3-T20 | Implement `GET /dashboard/summary`. | Not Started | P2-US2 | |
| [ ] | P3-T21 | Add API integration tests for pagination, filters, CRUD, and summaries. | Not Started | P3-T17-P3-T20 | |

### P3-US5: Use the API from Streamlit

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P3-T22 | Create a small typed Streamlit API client. | Not Started | P3-F2, P3-F3 | |
| [ ] | P3-T23 | Replace direct `app_brain` imports with API calls. | Not Started | P3-T22 | |
| [ ] | P3-T24 | Display API loading and error states. | Not Started | P3-T23 | |
| [ ] | P3-T25 | Verify the full workflow in Swagger and Streamlit. | Not Started | P3-T23-P3-T24 | |

**Phase P3 exit criteria:** Swagger exercises all core workflows, API tests mock external providers, and Streamlit uses only public API contracts.

---

# P4: Dashboard and Domain Pages

**Epic state:** `Not Started`  
**Goal:** Make every stored record visible, understandable, filterable, and correctable.

## P4-F1: Navigation and Home Dashboard

### P4-US1: See the important daily information around chat

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P4-T01 | Add Streamlit multipage navigation. | Not Started | P3 preferred | |
| [ ] | P4-T02 | Build desktop three-column home layout. | Not Started | P4-T01 | |
| [ ] | P4-T03 | Add spending trend and category breakdown on the left. | Not Started | P3-T20 | |
| [ ] | P4-T04 | Keep chat and multimodal logging in the center. | Not Started | P4-T02 | |
| [ ] | P4-T05 | Add health, learning, and daily completion metrics on the right. | Not Started | P3-T20 | |
| [ ] | P4-T06 | Collapse side panels appropriately on narrow screens. | Not Started | P4-T02 | |
| [ ] | P4-T07 | Add loading, empty, partial-data, and error states. | Not Started | P4-T03-P4-T05 | |

## P4-F2: Wealth Page

### P4-US2: Inspect and maintain wealth records

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P4-T08 | Add date, type, category, and merchant filters. | Not Started | P3-T17 | |
| [ ] | P4-T09 | Show income, expense, and net totals. | Not Started | P2-US2 | |
| [ ] | P4-T10 | Add category and time-series charts. | Not Started | P4-T08 | |
| [ ] | P4-T11 | Add paginated searchable transaction table. | Not Started | P3-T17 | |
| [ ] | P4-T12 | Add edit and confirmed-delete actions. | Not Started | P3-T18-P3-T19 | |
| [ ] | P4-T13 | Add filtered CSV export. | Not Started | P4-T08 | |

## P4-F3: Health Page

### P4-US3: Understand health consistency

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P4-T14 | Show sleep and calorie trends. | Not Started | P3-T17 | |
| [ ] | P4-T15 | Show workout count, minutes, and frequency. | Not Started | P2-US2 | |
| [ ] | P4-T16 | Define target-backed health meters. | Not Started | P6 goal model or temporary settings | No unexplained AI score. |
| [ ] | P4-T17 | Add filtered editable health table. | Not Started | P3-T17-P3-T19 | |
| [ ] | P4-T18 | Add clear missing-data indicators. | Not Started | P4-T14-P4-T17 | |

## P4-F4: Learning and Review Pages

### P4-US4: Browse and search learning history

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P4-T19 | Show learning minutes, streak, and topic distribution. | Not Started | P2-US2 | |
| [ ] | P4-T20 | Add semantic search with topic/date filters. | Not Started | P2-US3 | |
| [ ] | P4-T21 | Show source links and retrieved summary text. | Not Started | P4-T20 | |
| [ ] | P4-T22 | Add editable learning table with synchronized vector updates. | Not Started | P3-F3 | |

### P4-US5: Read weekly reviews and manage settings

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P4-T23 | Add Weekly Review page with visible evidence. | Not Started | P6-F1 | Can initially show empty state. |
| [ ] | P4-T24 | Add Settings page for currency and goal values. | Not Started | P6-F2 | |
| [ ] | P4-T25 | Add model configuration status without exposing keys. | Not Started | P3-T03 | |
| [ ] | P4-T26 | Add backup/export entry points. | Not Started | P7-F2 | |

**Phase P4 exit criteria:** Every chart has a date range and empty state; all records are reachable from tables; editing updates charts; desktop and mobile layouts are usable.

---

# P5: Next.js Frontend

**Epic state:** `Not Started`  
**Decision gate:** Start only after P3 API contracts are stable and P4 validates the desired workflows.

## P5-F1: Frontend Foundation

### P5-US1: Run a typed web client against FastAPI

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P5-T01 | Create Next.js project with TypeScript and linting. | Not Started | P3 | |
| [ ] | P5-T02 | Select accessible UI and chart libraries. | Not Started | P5-T01 | Record decision. |
| [ ] | P5-T03 | Generate a typed client from FastAPI OpenAPI. | Not Started | P3 stable | |
| [ ] | P5-T04 | Add environment-specific API configuration. | Not Started | P5-T01 | |
| [ ] | P5-T05 | Build responsive navigation and page shell. | Not Started | P5-T02 | |
| [ ] | P5-T06 | Add shared loading, error, empty, and notification components. | Not Started | P5-T02 | |

## P5-F2: Chat and Capture Experience

### P5-US2: Use all chat and logging features from the web client

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P5-T07 | Build conversation list and message view. | Not Started | P5-F1 | |
| [ ] | P5-T08 | Add text composer and thread persistence. | Not Started | P5-T07 | |
| [ ] | P5-T09 | Add audio recording with upload progress. | Not Started | P3-US3 | |
| [ ] | P5-T10 | Add image upload and preview. | Not Started | P3-US3 | |
| [ ] | P5-T11 | Build editable extraction confirmation UI. | Not Started | P3-US2 | |
| [ ] | P5-T12 | Add response streaming through Server-Sent Events. | Not Started | New backend streaming route | |
| [ ] | P5-T13 | Cover keyboard and screen-reader interactions. | Not Started | P5-T07-P5-T12 | |

## P5-F3: Dashboard Feature Parity

### P5-US3: Replace Streamlit without losing functionality

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P5-T14 | Rebuild Home dashboard behavior from P4. | Not Started | P4 | |
| [ ] | P5-T15 | Rebuild Wealth page and CRUD flows. | Not Started | P4-F2 | |
| [ ] | P5-T16 | Rebuild Health page and CRUD flows. | Not Started | P4-F3 | |
| [ ] | P5-T17 | Rebuild Learning and Weekly Review pages. | Not Started | P4-F4 | |
| [ ] | P5-T18 | Add frontend unit tests for forms and state. | Not Started | P5-T14-P5-T17 | |
| [ ] | P5-T19 | Add Playwright tests for critical workflows. | Not Started | P5-T07-P5-T17 | |
| [ ] | P5-T20 | Verify feature parity before deprecating Streamlit. | Not Started | P5-T18-P5-T19 | Keep Streamlit as admin/debug client initially. |

**Phase P5 exit criteria:** Text/media logging, confirmation, querying, record maintenance, dashboards, and navigation work without Streamlit; accessibility and browser tests pass.

---

# P6: Proactive Copilot

**Epic state:** `Not Started`  
**Goal:** Generate reproducible weekly insights and configurable alerts.

## P6-F1: Scheduled Weekly Reviews

### P6-US1: Receive an evidence-backed weekly summary

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P6-T01 | Define the `insights` table and evidence format. | Not Started | P1 data model | |
| [ ] | P6-T02 | Build deterministic weekly wealth metrics. | Not Started | P2-US2 | |
| [ ] | P6-T03 | Build deterministic weekly health metrics. | Not Started | P2-US2 | |
| [ ] | P6-T04 | Build deterministic weekly learning metrics. | Not Started | P2-US2 | |
| [ ] | P6-T05 | Add cross-domain observations with sample-size checks. | Not Started | P2-US4 | |
| [ ] | P6-T06 | Generate a natural-language summary from the metrics payload. | Not Started | P6-T02-P6-T05 | |
| [ ] | P6-T07 | Store the report and supporting evidence. | Not Started | P6-T01, P6-T06 | |
| [ ] | P6-T08 | Make report generation idempotent by date range. | Not Started | P6-T07 | |
| [ ] | P6-T09 | Add a manual regenerate action. | Not Started | P6-T08 | |

## P6-F2: Goals and Alerts

### P6-US2: Configure personal targets

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P6-T10 | Define goals for metric, target, period, and active state. | Not Started | P1 data model | |
| [ ] | P6-T11 | Add goal CRUD service and API routes. | Not Started | P3 | |
| [ ] | P6-T12 | Add goal controls to Settings. | Not Started | P4 or P5 UI | |
| [ ] | P6-T13 | Drive dashboard meters from configured goals. | Not Started | P6-T10-P6-T12 | |

### P6-US3: Receive useful alerts without repetition

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P6-T14 | Define alert rules for spending, sleep, workouts, and learning. | Not Started | P6-US2 | |
| [ ] | P6-T15 | Add cooldown, dismiss, mute, and re-enable behavior. | Not Started | P6-T14 | |
| [ ] | P6-T16 | Show in-app notifications with linked evidence. | Not Started | P6-T14 | |
| [ ] | P6-T17 | Require explicit opt-in before any external delivery. | Not Started | P6-T16 | |
| [ ] | P6-T18 | Test threshold boundaries and duplicate suppression. | Not Started | P6-T14-P6-T17 | |

## P6-F3: Scheduler

### P6-US4: Run proactive jobs reliably

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P6-T19 | Add APScheduler for the single-process local deployment. | Not Started | P6-F1 | |
| [ ] | P6-T20 | Configure timezone and weekly schedule. | Not Started | P6-T19 | |
| [ ] | P6-T21 | Add job locking and idempotency checks. | Not Started | P6-T19 | |
| [ ] | P6-T22 | Record job start, completion, and failure without private content. | Not Started | P6-T19 | |
| [ ] | P6-T23 | Document when migration to a distributed job queue is necessary. | Not Started | P6-T19 | |

**Phase P6 exit criteria:** Weekly jobs are idempotent, reports link to evidence, targets drive meters, and alerts are configurable and cannot spam the user.

---

# P7: Production Readiness

**Epic state:** `Not Started`  
**Goal:** Make the application secure, observable, deployable, and recoverable.

## P7-F1: Authentication and Application Security

### P7-US1: Protect personal data before internet deployment

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P7-T01 | Select and document the authentication approach. | Not Started | P3 | Single user is acceptable initially. |
| [ ] | P7-T02 | Protect API routes and verify resource ownership. | Not Started | P7-T01 | |
| [ ] | P7-T03 | Add rate limiting and strict production CORS. | Not Started | P7-T01 | |
| [ ] | P7-T04 | Validate uploads by content and extension. | Not Started | P3-US3 | |
| [ ] | P7-T05 | Treat uploaded/extracted instructions as untrusted data. | Not Started | P3-US3 | Prompt injection defense. |
| [ ] | P7-T06 | Redact secrets and personal values from logs and errors. | Not Started | P3-T07 | |
| [ ] | P7-T07 | Add dependency and secret scanning to CI. | Not Started | CI available | |
| [ ] | P7-T08 | Complete a security review before public deployment. | Not Started | P7-T01-P7-T07 | |

## P7-F2: Backup, Restore, Export, and Deletion

### P7-US2: Control and recover personal data

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P7-T09 | Create a consistent backup of SQLite and vector data. | Not Started | P1 | |
| [ ] | P7-T10 | Add full JSON/CSV data export. | Not Started | P3-F3 | |
| [ ] | P7-T11 | Add restore validation and a dry-run report. | Not Started | P7-T09 | |
| [ ] | P7-T12 | Test restoration into an empty environment. | Not Started | P7-T11 | |
| [ ] | P7-T13 | Add full account/data deletion with typed confirmation. | Not Started | P7-T10 | |
| [ ] | P7-T14 | Document backup retention and recovery steps. | Not Started | P7-T09-P7-T13 | |

## P7-F3: Observability and Quality

### P7-US3: Diagnose failures without exposing private content

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P7-T15 | Measure request latency and error rates. | Not Started | P3 | |
| [ ] | P7-T16 | Measure provider latency, retries, and token usage. | Not Started | P2-F3 | |
| [ ] | P7-T17 | Measure retrieval quality using the evaluation set. | Not Started | P2-US3 | |
| [ ] | P7-T18 | Add health/readiness checks for deployed dependencies. | Not Started | P3-T04 | |
| [ ] | P7-T19 | Define alerts for service failures and job failures. | Not Started | P7-T15-P7-T18 | |
| [ ] | P7-T20 | Verify telemetry contains no prompts or personal records by default. | Not Started | P7-T15-P7-T19 | |

## P7-F4: Packaging and Deployment

### P7-US4: Deploy with persistent storage and reproducible builds

**State:** `Not Started`

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P7-T21 | Containerize the FastAPI backend. | Not Started | P3 stable | |
| [ ] | P7-T22 | Containerize the Next.js frontend if P5 is adopted. | Not Started | P5 | Optional. |
| [ ] | P7-T23 | Add reproducible environment and startup configuration. | Not Started | P7-T21 | |
| [ ] | P7-T24 | Select encrypted persistent storage for SQLite/Chroma or migrate stores. | Not Started | Deployment target known | Never use ephemeral disk. |
| [ ] | P7-T25 | Configure HTTPS and production secrets. | Not Started | P7-T24 | |
| [ ] | P7-T26 | Run smoke tests after deployment. | Not Started | P7-T21-P7-T25 | |
| [ ] | P7-T27 | Document deploy, rollback, and recovery procedures. | Not Started | P7-T26 | |

**Phase P7 exit criteria:** Authentication protects private data, backups restore successfully, telemetry is privacy-safe, storage persists across deployments, and deploy/rollback procedures have been tested.

---

## Cross-Phase Quality Work

These tasks apply whenever their related feature is changed.

| Done | Task ID | Task | State | Notes |
| --- | --- | --- | --- | --- |
| [ ] | Q-T01 | Maintain an anonymized AI evaluation set of at least 30 representative messages. | Not Started | Cover intent, extraction, clarification, and evidence. |
| [ ] | Q-T02 | Add a regression test for every confirmed bug. | Not Started | Ongoing task. |
| [ ] | Q-T03 | Keep API examples and setup documentation synchronized with code. | Not Started | Ongoing task. |
| [ ] | Q-T04 | Verify tests never access the personal production database. | Not Started | Ongoing task. |
| [ ] | Q-T05 | Run formatting, linting, unit tests, and relevant integration tests before review. | Not Started | Ongoing task. |

## Active Work

Use this section as a short sprint board. Keep only current work here; canonical state remains in the phase tables.

| Item ID | Description | Owner | State | Branch/PR | Next action |
| --- | --- | --- | --- | --- | --- |
| - | No active tracked work | - | Not Started | - | Select the first P1 story. |

## Blockers and Decisions

| ID | Type | Related item | Description | Owner | State | Resolution/date |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | No blockers or pending decisions recorded. | - | - | - |

Use `BLK-###` for blockers and `DEC-###` for decisions. Important architecture decisions should also be summarized in `DEVELOPMENT_PLAN.md`.

## Change Log

| Date | Item IDs | Update | Author |
| --- | --- | --- | --- |
| 2026-10-02 | P1-US4, P1-T23-P1-T27 | Added validated record maintenance, explicit deletion confirmation, status recalculation, and learning-vector synchronization. | Codex |
| 2026-10-02 | P1-US3, P1-T18-P1-T22 | Added persistent daily completion, partial/resumed check-ins, status indicators, and missing-domain follow-ups. | Codex |
| 2026-10-02 | P1-T15 | Simplified draft review to Confirm and Cancel; inline edits are saved directly on confirmation. | Codex |
| 2026-10-02 | P1-US2, P1-T09-P1-T17 | Added validated editable drafts, date resolution, explicit confirmation, and private source metadata. | Codex |
| 2026-10-02 | P1-T04 | Fixed daily health merging so later workouts preserve earlier meal notes and omitted values no longer become zero. | Codex |
| 2026-10-02 | P1-US1, P1-T01-P1-T08 | Completed schema v1, migrated personal data after backup, and added migration/persistence tests. | Codex |
| 2026-09-27 | P1-P7 | Initial tracker created; all implementation work starts as `Not Started`. | Codex |

## Story Completion Template

Copy this block when adding a new story:

```markdown
### P#-US#: Short user-focused title

**State:** `Not Started`
**User story:** As a [user], I want [capability] so that [benefit].

| Done | Task ID | Task | State | Depends on | Notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | P#-T## | Concrete implementation step. | Not Started | None | |

**Acceptance criteria:**

- Observable result one.
- Observable result two.
```
