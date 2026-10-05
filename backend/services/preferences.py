"""Services for local preferences, provider readiness, and data snapshots."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from backend.core.settings import Settings
from backend.models.preferences import (
    AppPreferencesPatch,
    BackupData,
    ProviderConfiguration,
    SettingsData,
)
from life_copilot import storage
from life_copilot.config import MODAL


def _provider_configurations() -> list[ProviderConfiguration]:
    return [
        ProviderConfiguration(
            provider="Gemini",
            capability="Chat, extraction, and summaries",
            model=MODAL,
            configured=bool(os.getenv("GEMINI_API_KEY", "").strip()),
        ),
        ProviderConfiguration(
            provider="Gemini",
            capability="Image extraction",
            model="gemini-3.6-flash",
            configured=bool(os.getenv("GEMINI_API_KEY", "").strip()),
        ),
        ProviderConfiguration(
            provider="Groq",
            capability="Voice transcription",
            model="whisper-large-v3",
            configured=bool(os.getenv("GROQ_API_KEY", "").strip()),
        ),
    ]


def get_settings_data(settings: Settings) -> SettingsData:
    return SettingsData(
        preferences=storage.get_app_preferences(settings.database_path),
        providers=_provider_configurations(),
    )


def save_preferences(
    patch: AppPreferencesPatch,
    settings: Settings,
) -> SettingsData:
    current = storage.get_app_preferences(settings.database_path)
    changes = patch.model_dump(exclude_unset=True)
    merged = {
        key: changes.get(key, current[key])
        for key in (
            "default_currency",
            "weekly_spending_limit",
            "weekly_learning_minutes",
            "weekly_workouts",
            "sleep_hours_target",
        )
    }
    preferences = storage.update_app_preferences(
        **merged,
        db_path=settings.database_path,
    )
    return SettingsData(
        preferences=preferences,
        providers=_provider_configurations(),
    )


def create_local_backup(settings: Settings) -> BackupData:
    """Create a local SQLite snapshot and a best-effort vector-store copy."""
    storage.init_sqlite_db(settings.database_path)
    created_at = datetime.now(timezone.utc)
    backup_name = f"snapshot_{created_at.strftime('%Y%m%d_%H%M%S_%f')}"
    backup_root = settings.backup_path.resolve()
    destination = backup_root / backup_name
    destination.mkdir(parents=True, exist_ok=False)

    includes = []
    warnings = []
    database_destination = destination / settings.database_path.name
    with closing(sqlite3.connect(settings.database_path)) as source:
        with closing(sqlite3.connect(database_destination)) as target:
            source.backup(target)
    includes.append("SQLite database")

    if settings.chroma_path.exists():
        try:
            shutil.copytree(
                settings.chroma_path,
                destination / settings.chroma_path.name,
            )
            includes.append("learning vector index")
        except Exception:
            warnings.append(
                "The database was backed up, but the vector index could not be copied."
            )
    else:
        warnings.append("No learning vector index was present to copy.")

    manifest = {
        "backup_name": backup_name,
        "created_at": created_at.isoformat(),
        "includes": includes,
        "warnings": warnings,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return BackupData(**manifest)
