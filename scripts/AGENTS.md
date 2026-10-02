# Repository Guidelines

## Project Structure & Module Organization

Application code lives under `life_copilot/`:

- `agent/` contains LangGraph state, memory, parsing, reference resolution, AI nodes, and workflow assembly.
- `analytics/` contains typed requests, natural-language routing, execution, and grounded answer formatting.
- `storage/` contains SQLite migrations and separate repositories for domain logs, daily status, conversations, retrieval, and ChromaDB vectors.
- `services/` coordinates validated record and draft persistence.
- `ui/` contains the Streamlit screen, session helpers, draft review, and record-maintenance components.
- `models.py` defines Pydantic domain and draft models; `config.py` holds shared configuration.

Root modules such as `graph.py`, `db_utils.py`, and `schemas.py` are compatibility imports. Add new logic to `life_copilot/`, not to these wrappers. Tests live in `tests/`; operational commands and planning documents live in `scripts/`.

## Build, Test, and Development Commands

Create an environment and install the current dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install streamlit pillow groq google-generativeai langgraph python-dotenv chromadb pydantic
```

Run the complete test suite with `python -m unittest discover -s tests -v`. Run the UI with `python -m streamlit run app.py`. Apply guarded database migrations with `python scripts/migrate_database.py`; this command creates a backup first.

## Coding Style & Naming Conventions

Use Python 3, four-space indentation, type hints, and `snake_case` functions. Use `PascalCase` for Pydantic models and suffix graph functions with `_node`. Keep Streamlit calls in `ui/`, SQL in `storage/`, and cross-repository workflows in `services/`. Prefer imports from `life_copilot.*` over compatibility modules.

## Testing Guidelines

Name tests `test_<area>.py` and use `unittest`. Database tests must use temporary SQLite paths and fake vector collections. Mock Gemini, Groq, and Chroma boundaries; tests must never access the personal production database. Add a regression test for every fixed bug.

## Commit & Pull Request Guidelines

Use short imperative commit subjects, such as `Refactor conversation workflow`. Pull requests should describe behavior changes, schema impact, test commands, and manual UI checks. Include screenshots for visible UI changes and identify any new environment variables.

## Security & Configuration

Keep API keys in `.env`. Treat `life_copilot.db`, `chroma_data/`, backups, prompts, and uploads as private data. Never include their contents in tests, logs, commits, or screenshots.
