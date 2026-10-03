"""Small, repeatable top-k evaluation for learning retrieval."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

from life_copilot.retrieval.models import LearningSearchRequest, LearningSearchResult


class LearningEvaluationCase(BaseModel):
    name: str
    query: str
    expected_summary_contains: str
    topic: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    top_k: int = Field(default=3, ge=1, le=20)


def load_learning_evaluation(path: str | Path) -> dict:
    """Load the self-contained records and retrieval cases in an evaluation file."""
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    payload["cases"] = [
        LearningEvaluationCase.model_validate(item) for item in payload["cases"]
    ]
    return payload


def evaluate_learning_retrieval(
    cases: list[LearningEvaluationCase | dict],
    search: Callable[[LearningSearchRequest], LearningSearchResult],
) -> dict:
    """Measure whether each expected note occurs within its requested top-k."""
    details = []
    for raw_case in cases:
        case = LearningEvaluationCase.model_validate(raw_case)
        request = LearningSearchRequest(
            query_text=case.query,
            topic=case.topic,
            start_date=case.start_date,
            end_date=case.end_date,
            limit=case.top_k,
        )
        result = search(request)
        expected = case.expected_summary_contains.casefold()
        rank = next(
            (
                index
                for index, hit in enumerate(result.hits[: case.top_k], start=1)
                if expected in hit.summary_text.casefold()
            ),
            None,
        )
        details.append(
            {
                "name": case.name,
                "passed": rank is not None,
                "rank": rank,
                "mode": result.mode,
            }
        )
    passed = sum(item["passed"] for item in details)
    total = len(details)
    return {
        "passed": passed,
        "total": total,
        "top_k_hit_rate": passed / total if total else 0.0,
        "cases": details,
    }
