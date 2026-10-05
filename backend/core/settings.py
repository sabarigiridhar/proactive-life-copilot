"""Typed settings for the FastAPI backend."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from life_copilot.storage import DEFAULT_CHROMA_PATH, DEFAULT_DB_PATH


class Settings(BaseModel):
    """Runtime settings loaded from environment variables."""

    app_name: str = "Life Copilot API"
    environment: str = Field(default="local")
    api_prefix: str = "/api/v1"
    database_path: Path = DEFAULT_DB_PATH
    chroma_path: Path = DEFAULT_CHROMA_PATH
    backup_path: Path = Path("backups")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    log_level: str = "INFO"
    max_audio_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    max_audio_duration_seconds: float = Field(default=300.0, gt=0)
    max_image_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_image_dimension: int = Field(default=8192, gt=0)
    max_image_pixels: int = Field(default=25_000_000, gt=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached settings built from environment variables."""
    return Settings(
        environment=os.getenv("LIFE_COPILOT_ENV", "local"),
        database_path=Path(os.getenv("LIFE_COPILOT_DB_PATH", str(DEFAULT_DB_PATH))),
        chroma_path=Path(os.getenv("LIFE_COPILOT_CHROMA_PATH", str(DEFAULT_CHROMA_PATH))),
        backup_path=Path(os.getenv("LIFE_COPILOT_BACKUP_PATH", "backups")),
        cors_origins=os.getenv("LIFE_COPILOT_CORS_ORIGINS", "http://localhost:3000"),
        log_level=os.getenv("LIFE_COPILOT_LOG_LEVEL", "INFO"),
        max_audio_bytes=os.getenv(
            "LIFE_COPILOT_MAX_AUDIO_BYTES", str(25 * 1024 * 1024)
        ),
        max_audio_duration_seconds=os.getenv(
            "LIFE_COPILOT_MAX_AUDIO_DURATION_SECONDS", "300"
        ),
        max_image_bytes=os.getenv(
            "LIFE_COPILOT_MAX_IMAGE_BYTES", str(10 * 1024 * 1024)
        ),
        max_image_dimension=os.getenv("LIFE_COPILOT_MAX_IMAGE_DIMENSION", "8192"),
        max_image_pixels=os.getenv("LIFE_COPILOT_MAX_IMAGE_PIXELS", "25000000"),
    )
