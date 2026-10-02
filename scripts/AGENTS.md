# Repository Guidelines

## Project Structure & Module Organization

- `app.py` contains the Streamlit UI, audio/image extraction flow, and chat session state.
- `graph.py` defines the LangGraph workflow for intent classification, extraction, retrieval, saving, and follow-up responses.
- `db_utils.py` owns SQLite table setup, inserts, SELECT-only querying, and ChromaDB vector storage.
- `schemas.py` defines Pydantic models for structured daily logs.
- `Constants.py` stores shared model configuration.
- `life_copilot.db` and `chroma_data/` are local runtime data stores. Avoid committing generated or private data.

There is no dedicated `tests/` directory yet; add one with automated tests.

## Build, Test, and Development Commands

Create and activate a virtual environment before installing dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the packages used by the app:

```powershell
pip install streamlit pillow groq google-generativeai langgraph python-dotenv chromadb pydantic
```

Initialize local databases:

```powershell
python db_utils.py
```

Run the app locally:

```powershell
streamlit run app.py
```

There is no formal test command yet. Use focused manual checks through the Streamlit UI and add automated tests for new business logic.

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation. Keep module names lowercase unless preserving existing files such as `Constants.py`. Use `snake_case` for functions and variables, `PascalCase` for Pydantic models, and LangGraph node names ending in `_node`.

Keep database access inside `db_utils.py`, workflow behavior inside `graph.py`, and UI behavior inside `app.py`. Prefer typed models or dictionaries matching `schemas.py` over loosely shaped payloads.

## Testing Guidelines

When adding tests, place them under `tests/` and name files `test_<module>.py`. Prefer unit tests for pure extraction/routing helpers and database tests against temporary SQLite or Chroma paths, not the checked-in local data files.

Recommended future command:

```powershell
pytest
```

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries, for example `Add Voice and image Extraction`. Keep messages concise and focused on the user-visible change.

Pull requests should include a brief description, manual test steps, database/schema impact, and screenshots or short screen recordings for UI changes. Link related issues and note required environment variables.

## Security & Configuration Tips

Store secrets in `.env`, including `GROQ_API_KEY` and `GEMINI_API_KEY`; never hard-code or commit API keys. Treat `life_copilot.db`, `chroma_data/`, uploaded media, and temporary audio files as private user data. Keep generated files and caches out of commits unless they are intentionally shared fixtures.
