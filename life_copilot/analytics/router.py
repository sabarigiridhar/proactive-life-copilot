"""Natural-language routing into validated analytics requests."""

import json
import re
from datetime import date, timedelta

from pydantic import ValidationError

from life_copilot.agent.memory import _format_memory_context
from life_copilot.agent.provider import genai
from life_copilot.agent.state import DailyState
from life_copilot.analytics.models import AnalyticsOperation, AnalyticsRequest
from life_copilot.config import MODAL


def _date_range(message: str, today: date) -> tuple[date, date]:
    lowered = message.lower()
    explicit = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if explicit:
        parsed = [date.fromisoformat(value) for value in explicit[:2]]
        if len(parsed) == 1 and (
            "since" in lowered or re.search(r"\bfrom\s+\d{4}-\d{2}-\d{2}\b", lowered)
        ):
            return parsed[0], today
        return (parsed[0], parsed[-1])
    if "yesterday" in lowered:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if "this week" in lowered:
        return today - timedelta(days=today.weekday()), today
    if "this month" in lowered:
        return today.replace(day=1), today
    if "last week" in lowered:
        this_monday = today - timedelta(days=today.weekday())
        return this_monday - timedelta(days=7), this_monday - timedelta(days=1)
    if "last month" in lowered:
        last_day = today.replace(day=1) - timedelta(days=1)
        return last_day.replace(day=1), last_day
    recent = re.search(r"\blast\s+(\d+)\s+days?\b", lowered)
    if recent:
        days = int(recent.group(1))
        return today - timedelta(days=max(days - 1, 0)), today
    return today, today


def parse_common_question(
    message: str, *, today: date | None = None
) -> AnalyticsRequest | None:
    """Route common questions without requiring a model call."""
    lowered = message.lower()
    start_date, end_date = _date_range(message, today or date.today())

    if "workout" in lowered and "streak" in lowered:
        operation = AnalyticsOperation.WORKOUT_STREAK
    elif "workout" in lowered and any(
        term in lowered for term in ("frequency", "count", "how many")
    ):
        operation = AnalyticsOperation.WORKOUT_FREQUENCY
    elif any(term in lowered for term in ("sleep", "calorie", "health")) and any(
        term in lowered for term in ("average", "avg", "mean")
    ):
        operation = AnalyticsOperation.HEALTH_AVERAGES
    elif any(
        term in lowered
        for term in (
            "expense",
            "spend",
            "spent",
            "spending",
            "income",
            "earned",
            "wealth",
        )
    ):
        if any(term in lowered for term in ("category", "categories", "breakdown")):
            operation = AnalyticsOperation.WEALTH_CATEGORY_BREAKDOWN
        elif any(term in lowered for term in ("trend", "daily", "over time")):
            operation = AnalyticsOperation.WEALTH_DAILY_TREND
        else:
            operation = AnalyticsOperation.WEALTH_TOTAL
    else:
        return None

    transaction_type = (
        "Income"
        if any(term in lowered for term in ("income", "earned", "salary"))
        else "Expense"
    )
    category = None
    category_match = re.search(
        r"\b(?:spend|spent|spending|expenses?)\s+(?:money\s+)?(?:on|for)\s+"
        r"(?P<category>[a-z][a-z &-]*?)"
        r"(?=\s+(?:today|yesterday|this week|this month|last week|last month|"
        r"last \d+ days?|from|between)|[?.!,]|$)",
        lowered,
    )
    if category_match and operation == AnalyticsOperation.WEALTH_TOTAL:
        category = category_match.group("category").strip().title()
    return AnalyticsRequest(
        operation=operation,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        category=category,
    )


def _model_request(state: DailyState) -> AnalyticsRequest:
    today = date.today()
    prompt = f"""
    Route the latest question to one analytics operation. Return JSON only.

    Allowed operations:
    - wealth_total
    - wealth_category_breakdown
    - wealth_daily_trend
    - health_averages
    - workout_frequency
    - workout_streak

    JSON fields: operation, start_date, end_date, transaction_type, category, limit.
    Dates must use YYYY-MM-DD. The maximum range is 367 days and limit is at most 100.
    Use null for an unused category. Never return SQL or any additional field.
    Today is {today.isoformat()}.

    Conversation context:
    {_format_memory_context(state)}

    Latest question: {state.get('user_message', '')}
    """
    response = genai.GenerativeModel(MODAL).generate_content(
        prompt, generation_config={"response_mime_type": "application/json"}
    )
    return AnalyticsRequest.model_validate(json.loads(response.text))


def route_analytics_request(state: DailyState) -> AnalyticsRequest:
    """Return a validated request or raise a safe validation error."""
    try:
        common = parse_common_question(state.get("user_message", ""))
        if common is not None:
            return common
        return _model_request(state)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError(
            "I could not map that question to a supported calculation. "
            "Try asking for spending totals, category breakdowns, trends, "
            "health averages, workout frequency, or a workout streak."
        ) from exc
