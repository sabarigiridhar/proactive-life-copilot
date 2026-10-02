"""Backward-compatible imports for persistence helpers."""

from life_copilot.storage import *  # noqa: F401,F403
from life_copilot.storage.base import _persistent_chroma_client


if __name__ == "__main__":
    applied = init_sqlite_db()
    init_chroma_db()
    print(f"Database ready. Applied migrations: {applied or 'none'}")
