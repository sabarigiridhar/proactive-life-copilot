"""REST routes for semantic learning-history search."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from backend.core.dependencies import RequestIdDep, SettingsDep
from backend.models.responses import ApiResponse, success_response
from backend.services.learning import search_learning_history
from life_copilot.retrieval.models import LearningSearchRequest, LearningSearchResult


router = APIRouter(tags=["learning"])


@router.get(
    "/learning/search",
    response_model=ApiResponse[LearningSearchResult],
)
def search_learning(
    query: Annotated[str, Query(min_length=1, max_length=2000)],
    settings: SettingsDep,
    request_id: RequestIdDep,
    topic: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> ApiResponse[LearningSearchResult]:
    try:
        request = LearningSearchRequest(
            query_text=query,
            topic=topic,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except ValidationError:
        raise HTTPException(
            status_code=422,
            detail="Invalid learning search parameters.",
        ) from None
    return success_response(search_learning_history(request, settings), request_id)
