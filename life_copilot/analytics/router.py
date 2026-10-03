"""Natural-language routing into validated analytics requests."""

import json
import re
from datetime import date, timedelta

from pydantic import ValidationError

from life_copilot.agent.memory import _format_memory_context
from life_copilot.agent.provider import generate_gemini_content
from life_copilot.agent.state import DailyState
from life_copilot.analytics.models import (
    AnalyticsOperation,
    AnalyticsRequest,
    ComparisonOperator,
    DailyMetric,
    METRIC_DOMAINS,
)
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


_COMPARATOR_PATTERN = (
    r"more than|over|above|exceeded|exceeds|at least|"
    r"less than|under|below|at most"
)


def _comparison_operator(value: str) -> ComparisonOperator:
    normalized = value.casefold()
    if normalized in {"more than", "over", "above", "exceeded", "exceeds"}:
        return ComparisonOperator.GT
    if normalized == "at least":
        return ComparisonOperator.GTE
    if normalized in {"less than", "under", "below"}:
        return ComparisonOperator.LT
    return ComparisonOperator.LTE


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def _threshold_condition(
    message: str,
) -> tuple[DailyMetric, ComparisonOperator, float] | None:
    patterns = (
        (
            DailyMetric.EXPENSE_AMOUNT,
            rf"\b(?:spend|spent|spending|expense|expenses)\b.{{0,35}}?"
            rf"(?P<comparison>{_COMPARATOR_PATTERN})\s*"
            r"(?:inr|rs\.?|rupees?|usd|dollars?|eur|euros?)?\s*"
            r"(?P<value>\d[\d,]*(?:\.\d+)?)",
        ),
        (
            DailyMetric.SLEEP_HOURS,
            rf"\b(?:sleep|slept|sleeping)\b.{{0,20}}?"
            rf"(?P<comparison>{_COMPARATOR_PATTERN})\s*"
            r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?:hours?|hrs?)?",
        ),
        (
            DailyMetric.LEARNING_MINUTES,
            rf"\b(?:learn|learned|learning|study|studied|studying)\b.{{0,25}}?"
            rf"(?P<comparison>{_COMPARATOR_PATTERN})\s*"
            r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*"
            r"(?P<unit>hours?|hrs?|minutes?|mins?)?",
        ),
        (
            DailyMetric.CALORIES_CONSUMED,
            rf"\b(?:calories?|consume|consumed|eating|ate)\b.{{0,25}}?"
            rf"(?P<comparison>{_COMPARATOR_PATTERN})\s*"
            r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?:calories?)?",
        ),
    )
    for metric, pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if not match:
            continue
        threshold = _number(match.group("value"))
        if metric == DailyMetric.LEARNING_MINUTES:
            unit = match.groupdict().get("unit") or "minutes"
            if unit.casefold().startswith(("hour", "hr")):
                threshold *= 60
        return metric, _comparison_operator(match.group("comparison")), threshold

    if re.search(r"\b(?:on\s+)?(?:workout|exercise)\s+days?\b", message, re.IGNORECASE):
        return DailyMetric.WORKOUT_LOGGED, ComparisonOperator.GTE, 1.0
    return None


def _mentioned_metrics(message: str) -> list[DailyMetric]:
    patterns = (
        (DailyMetric.SLEEP_HOURS, r"\b(?:sleep|slept|sleeping)\b"),
        (DailyMetric.CALORIES_CONSUMED, r"\bcalories?\b"),
        (DailyMetric.EXPENSE_AMOUNT, r"\b(?:spend|spent|spending|expense|expenses)\b"),
        (
            DailyMetric.LEARNING_MINUTES,
            r"\b(?:learn|learned|learning|study|studied|studying)\b",
        ),
        (DailyMetric.WORKOUT_LOGGED, r"\b(?:workout|exercise)\b"),
    )
    return [
        metric
        for metric, pattern in patterns
        if re.search(pattern, message, re.IGNORECASE)
    ]


def _cross_category(message: str) -> str | None:
    amount_then_category = re.search(
        r"\d[\d,]*(?:\.\d+)?\s*"
        r"(?:rupees?|inr|rs\.?|dollars?|usd|euros?|eur)?\s*"
        r"(?:on|for)\s+(?P<category>[a-z][a-z &-]*?)"
        r"(?=\s+(?:today|yesterday|this|last|from|between)|[?.!,]|$)",
        message,
        re.IGNORECASE,
    )
    if amount_then_category:
        return amount_then_category.group("category").strip().title()
    category_then_spending = re.search(
        r"\b(?P<category>[a-z][a-z-]*)\s+(?:spending|expenses?)\b",
        message,
        re.IGNORECASE,
    )
    if category_then_spending:
        candidate = category_then_spending.group("category").strip().title()
        if candidate.casefold() not in {"my", "total", "daily"}:
            return candidate
    return None


def _currency(message: str) -> str:
    lowered = message.casefold()
    if any(value in lowered for value in ("usd", "dollar", "$")):
        return "USD"
    if any(value in lowered for value in ("eur", "euro")):
        return "EUR"
    return "INR"


def parse_cross_domain_question(
    message: str, *, today: date | None = None
) -> AnalyticsRequest | None:
    """Parse common threshold comparisons without asking a model to calculate."""
    condition = _threshold_condition(message)
    if condition is None:
        return None
    condition_metric, operator, threshold = condition
    outcome_metric = next(
        (
            metric
            for metric in _mentioned_metrics(message)
            if METRIC_DOMAINS[metric] != METRIC_DOMAINS[condition_metric]
        ),
        None,
    )
    if outcome_metric is None:
        return None

    current_day = today or date.today()
    has_date_scope = bool(
        re.search(
            r"\b(?:today|yesterday|this week|this month|last week|last month|"
            r"last \d+ days?|from|between|since|\d{4}-\d{2}-\d{2})\b",
            message,
            re.IGNORECASE,
        )
    )
    start_date, end_date = (
        _date_range(message, current_day)
        if has_date_scope
        else (current_day - timedelta(days=29), current_day)
    )
    return AnalyticsRequest(
        operation=AnalyticsOperation.CROSS_DOMAIN_COMPARISON,
        start_date=start_date,
        end_date=end_date,
        outcome_metric=outcome_metric,
        condition_metric=condition_metric,
        comparison_operator=operator,
        threshold=threshold,
        category=(
            _cross_category(message)
            if DailyMetric.EXPENSE_AMOUNT in {outcome_metric, condition_metric}
            else None
        ),
        currency=_currency(message),
    )


def parse_common_question(
    message: str, *, today: date | None = None
) -> AnalyticsRequest | None:
    """Route common questions without requiring a model call."""
    lowered = message.lower()
    start_date, end_date = _date_range(message, today or date.today())

    cross_domain = parse_cross_domain_question(message, today=today)
    if cross_domain is not None:
        return cross_domain

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
    - cross_domain_comparison

    JSON fields: operation, start_date, end_date, transaction_type, category,
    currency, limit, outcome_metric, condition_metric, comparison_operator, threshold.
    Cross-domain metrics: sleep_hours, calories_consumed, expense_amount,
    learning_minutes, learning_sessions, workout_logged. Comparison operators:
    gt, gte, lt, lte. Cross-domain metrics must come from different domains.
    Dates must use YYYY-MM-DD. The maximum range is 367 days and limit is at most 100.
    Use null for an unused category. Never return SQL or any additional field.
    Today is {today.isoformat()}.

    Conversation context:
    {_format_memory_context(state)}

    Latest question: {state.get('user_message', '')}
    """
    return generate_gemini_content(
        prompt,
        model_name=MODAL,
        generation_config={"response_mime_type": "application/json"},
        validator=lambda text: AnalyticsRequest.model_validate(json.loads(text)),
        operation="analytics_routing",
    )


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
            "health averages, workout frequency, a workout streak, or a "
            "cross-domain threshold comparison."
        ) from exc
