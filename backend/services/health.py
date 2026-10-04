"""Health service for backend dependency status."""

from __future__ import annotations

from backend.core.settings import Settings
from backend.models.responses import DependencyHealth, HealthData
from backend.repositories.health import check_database, check_vector_store


def get_health(settings: Settings) -> HealthData:
    database_ok, database_detail = check_database(settings.database_path)
    vector_ok, vector_detail = check_vector_store(settings.chroma_path)
    status = "ok" if database_ok and vector_ok else "degraded"
    return HealthData(
        status=status,
        environment=settings.environment,
        database=DependencyHealth(
            status="ok" if database_ok else "error",
            detail=database_detail,
        ),
        vector_store=DependencyHealth(
            status="ok" if vector_ok else "error",
            detail=vector_detail,
        ),
    )
