"""REST routes for weekly reviews."""

from fastapi import APIRouter

from backend.core.dependencies import RequestIdDep
from backend.models.insights import WeeklyReviewsData
from backend.models.responses import ApiResponse, success_response
from backend.services.insights import list_weekly_reviews


router = APIRouter(tags=["insights"])


@router.get("/insights/weekly", response_model=ApiResponse[WeeklyReviewsData])
def weekly_reviews(request_id: RequestIdDep) -> ApiResponse[WeeklyReviewsData]:
    return success_response(list_weekly_reviews(), request_id)
