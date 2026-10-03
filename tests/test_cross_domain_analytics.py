import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from pydantic import ValidationError

from life_copilot import storage
from life_copilot.agent import nodes
from life_copilot.analytics import router
from life_copilot.analytics.models import (
    AnalyticsOperation,
    AnalyticsRequest,
    ComparisonOperator,
    DailyMetric,
)
from life_copilot.analytics.service import (
    GroundingError,
    build_analytics_answer,
    run_analytics,
)
from life_copilot.storage.cross_domain import load_daily_aggregates


class CrossDomainAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "cross-domain.db"
        storage.init_sqlite_db(self.db_path)
        self._seed_daily_records()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed_daily_records(self):
        start = date(2026, 9, 1)
        sleep_values = [6, 7, 6, 7, 8, 8, 8, 8]
        for index, sleep_hours in enumerate(sleep_values):
            entry_date = (start + timedelta(days=index)).isoformat()
            food_spend = 1500 if index < 4 else 500
            learning_minutes = 30 if index < 4 else 60
            storage.insert_health_log(
                entry_date,
                sleep_hours,
                "Running" if index % 2 == 0 else None,
                2000 + index,
                None,
                db_path=self.db_path,
            )
            storage.insert_wealth_log(
                entry_date,
                "Expense",
                food_spend,
                "INR",
                "Food",
                None,
                None,
                db_path=self.db_path,
            )
            storage.insert_wealth_log(
                entry_date,
                "Expense",
                5000,
                "INR",
                "Travel",
                None,
                None,
                db_path=self.db_path,
            )
            storage.insert_wealth_log(
                entry_date,
                "Expense",
                9000,
                "USD",
                "Food",
                None,
                None,
                db_path=self.db_path,
            )
            storage.insert_learning_log(
                entry_date,
                "Python",
                learning_minutes,
                None,
                summary_text="Practiced typed Python models.",
                db_path=self.db_path,
            )

    def _sleep_by_food_request(self, **overrides):
        values = {
            "operation": AnalyticsOperation.CROSS_DOMAIN_COMPARISON,
            "start_date": "2026-09-01",
            "end_date": "2026-09-08",
            "outcome_metric": DailyMetric.SLEEP_HOURS,
            "condition_metric": DailyMetric.EXPENSE_AMOUNT,
            "comparison_operator": ComparisonOperator.GT,
            "threshold": 1000,
            "category": "Food",
            "currency": "INR",
        }
        values.update(overrides)
        return AnalyticsRequest(**values)

    def test_daily_aggregates_join_health_wealth_and_learning_by_date(self):
        days = load_daily_aggregates(
            date(2026, 9, 1), date(2026, 9, 8), db_path=self.db_path
        )

        self.assertEqual(len(days), 8)
        first = days[0]
        self.assertEqual(first.health.sleep_hours, 6)
        self.assertEqual(first.learning.duration_minutes, 30)
        self.assertEqual(first.learning.sessions, 1)
        self.assertEqual(len(first.wealth.totals), 3)

    def test_threshold_comparison_is_currency_and_category_scoped(self):
        result = run_analytics(
            self._sleep_by_food_request(), db_path=self.db_path
        )
        answer = build_analytics_answer(result)

        self.assertEqual(result.data.condition_days, 4)
        self.assertEqual(result.data.comparison_days, 4)
        self.assertEqual(result.data.condition_average, 6.5)
        self.assertEqual(result.data.comparison_average, 8.0)
        self.assertEqual(result.data.difference, -1.5)
        self.assertEqual(result.data.observation, "lower")
        self.assertTrue(result.data.enough_data)
        self.assertEqual(len(answer.evidence), 8)
        self.assertGreaterEqual(answer.confidence, 0.7)
        self.assertIn("6.50 hours", answer.text)
        self.assertIn("8.00 hours", answer.text)
        self.assertIn("1.50 hours lower", answer.text)
        self.assertIn("observational comparison", answer.text)

    def test_learning_can_be_compared_with_health_thresholds(self):
        request = AnalyticsRequest(
            operation=AnalyticsOperation.CROSS_DOMAIN_COMPARISON,
            start_date="2026-09-01",
            end_date="2026-09-08",
            outcome_metric=DailyMetric.LEARNING_MINUTES,
            condition_metric=DailyMetric.SLEEP_HOURS,
            comparison_operator=ComparisonOperator.GTE,
            threshold=8,
        )

        result = run_analytics(request, db_path=self.db_path)

        self.assertEqual(result.data.condition_average, 60)
        self.assertEqual(result.data.comparison_average, 30)
        self.assertEqual(result.data.observation, "higher")

    def test_small_groups_do_not_produce_a_directional_claim(self):
        result = run_analytics(
            self._sleep_by_food_request(end_date="2026-09-06"),
            db_path=self.db_path,
        )
        answer = build_analytics_answer(result)

        self.assertFalse(result.data.enough_data)
        self.assertEqual(result.data.observation, "insufficient")
        self.assertLess(answer.confidence, 0.5)
        self.assertIn("At least 3 days in each group", answer.text)
        self.assertNotIn("average was lower", answer.text)

    def test_common_cross_domain_question_routes_to_typed_request(self):
        request = router.parse_common_question(
            "Did my sleep quality drop on days I spent more than 1,000 rupees "
            "on food from 2026-09-01 to 2026-09-08?",
            today=date(2026, 10, 3),
        )

        self.assertEqual(
            request.operation, AnalyticsOperation.CROSS_DOMAIN_COMPARISON
        )
        self.assertEqual(request.outcome_metric, DailyMetric.SLEEP_HOURS)
        self.assertEqual(request.condition_metric, DailyMetric.EXPENSE_AMOUNT)
        self.assertEqual(request.comparison_operator, ComparisonOperator.GT)
        self.assertEqual(request.threshold, 1000)
        self.assertEqual(request.category, "Food")
        self.assertEqual(request.currency, "INR")

    def test_graph_returns_text_evidence_date_range_and_confidence(self):
        response = nodes.answer_query_node(
            {
                "user_message": (
                    "Did my sleep quality drop on days I spent more than 1000 "
                    "rupees on food from 2026-09-01 to 2026-09-08?"
                ),
                "db_path": str(self.db_path),
            }
        )

        self.assertIn("6.50 hours", response["ai_response"])
        self.assertEqual(len(response["evidence"]), 8)
        self.assertEqual(
            response["date_range"],
            {"start_date": "2026-09-01", "end_date": "2026-09-08"},
        )
        self.assertGreaterEqual(response["confidence"], 0.7)

    def test_same_domain_and_missing_threshold_requests_are_rejected(self):
        with self.assertRaises(ValidationError):
            AnalyticsRequest(
                operation=AnalyticsOperation.CROSS_DOMAIN_COMPARISON,
                start_date="2026-09-01",
                end_date="2026-09-08",
                outcome_metric=DailyMetric.SLEEP_HOURS,
                condition_metric=DailyMetric.CALORIES_CONSUMED,
                comparison_operator=ComparisonOperator.GT,
                threshold=2000,
            )
        with self.assertRaises(ValidationError):
            AnalyticsRequest(
                operation=AnalyticsOperation.CROSS_DOMAIN_COMPARISON,
                start_date="2026-09-01",
                end_date="2026-09-08",
                outcome_metric=DailyMetric.SLEEP_HOURS,
                condition_metric=DailyMetric.EXPENSE_AMOUNT,
            )

    def test_numerical_claims_are_rejected_when_evidence_is_tampered(self):
        result = run_analytics(
            self._sleep_by_food_request(), db_path=self.db_path
        )
        result.data.condition_average = 99

        with self.assertRaises(GroundingError):
            build_analytics_answer(result)


if __name__ == "__main__":
    unittest.main()
