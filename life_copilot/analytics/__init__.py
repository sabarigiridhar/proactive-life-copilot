"""Typed, allowlisted analytics for natural-language questions."""

from life_copilot.analytics.models import (
    AnalyticsAnswer,
    AnalyticsOperation,
    AnalyticsRequest,
    AnalyticsResult,
)

__all__ = [
    "AnalyticsAnswer",
    "AnalyticsOperation",
    "AnalyticsRequest",
    "AnalyticsResult",
    "answer_analytics_request",
    "build_analytics_answer",
    "route_analytics_request",
    "run_analytics",
]


def __getattr__(name):
    """Preserve package-level imports without eagerly creating import cycles."""
    if name == "route_analytics_request":
        from life_copilot.analytics.router import route_analytics_request

        return route_analytics_request
    if name in {"answer_analytics_request", "build_analytics_answer", "run_analytics"}:
        from life_copilot.analytics import service

        return getattr(service, name)
    raise AttributeError(name)
