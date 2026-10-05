import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from life_copilot.ui import weekly_review as weekly_review_ui
from life_copilot.ui.api_client import ApiClientError, WeeklyReviewsResult


class FakeWeeklyReviewApi:
    def __init__(self, result=None, error=None):
        self.result = result or WeeklyReviewsResult(
            reviews=[],
            generation_available=False,
            message="No weekly reviews have been generated yet.",
        )
        self.error = error

    def list_weekly_reviews(self):
        if self.error:
            raise self.error
        return self.result


class WeeklyReviewPageTests(unittest.TestCase):
    def _run(self, api):
        script = (
            "from life_copilot.ui.weekly_review import run_weekly_review_page\n"
            "run_weekly_review_page()\n"
        )
        with patch.object(weekly_review_ui, "get_api_client", return_value=api):
            return AppTest.from_string(script).run(timeout=20)

    def test_empty_state_explains_scheduled_review_dependency(self):
        app = self._run(FakeWeeklyReviewApi())

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(any("No weekly reviews" in item.value for item in app.info))
        self.assertTrue(
            any("Proactive Copilot" in item.value for item in app.caption)
        )

    def test_review_displays_summary_period_and_visible_evidence(self):
        result = WeeklyReviewsResult.model_validate(
            {
                "reviews": [
                    {
                        "id": 1,
                        "period_start": "2026-09-28",
                        "period_end": "2026-10-04",
                        "title": "Week of 28 September",
                        "summary": "You studied consistently this week.",
                        "evidence": [
                            {"metric": "learning_minutes", "value": 180}
                        ],
                        "created_at": "2026-10-05T08:00:00Z",
                    }
                ],
                "generation_available": True,
            }
        )
        app = self._run(FakeWeeklyReviewApi(result=result))

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(
            any(item.value == "Week of 28 September" for item in app.subheader)
        )
        self.assertTrue(
            any("studied consistently" in str(item.value) for item in app.markdown)
        )
        self.assertEqual(len(app.dataframe), 1)

    def test_api_error_is_visible(self):
        app = self._run(
            FakeWeeklyReviewApi(error=ApiClientError("API unavailable."))
        )

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(any("API unavailable" in item.value for item in app.error))


if __name__ == "__main__":
    unittest.main()
