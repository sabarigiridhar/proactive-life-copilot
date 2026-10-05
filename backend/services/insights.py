"""Weekly review service boundary pending scheduled insight generation."""

from backend.models.insights import WeeklyReviewsData


def list_weekly_reviews() -> WeeklyReviewsData:
    return WeeklyReviewsData(
        reviews=[],
        generation_available=False,
        message=(
            "No weekly reviews have been generated yet. Scheduled, evidence-backed "
            "reviews will become available with the proactive copilot phase."
        ),
    )
