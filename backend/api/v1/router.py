"""Version 1 API router."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.v1.conversations import router as conversation_router
from backend.api.v1.health import router as health_router
from backend.api.v1.insights import router as insights_router
from backend.api.v1.learning import router as learning_router
from backend.api.v1.media import router as media_router
from backend.api.v1.preferences import router as preferences_router
from backend.api.v1.records import router as records_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(insights_router)
api_router.include_router(learning_router)
api_router.include_router(conversation_router)
api_router.include_router(media_router)
api_router.include_router(records_router)
api_router.include_router(preferences_router)
