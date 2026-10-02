import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from life_copilot import storage
from life_copilot.agent import nodes
from life_copilot.analytics import router
from life_copilot.analytics.models import AnalyticsOperation, AnalyticsRequest
from life_copilot.analytics.service import answer_analytics_request, run_analytics


class FakeResponse:
    def __init__(self, payload):
        self.text = json.dumps(payload)


class FakeModel:
    def __init__(self, payload):
        self.payload = payload

    def generate_content(self, *_args, **_kwargs):
        return FakeResponse(self.payload)


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "analytics.db"
        storage.init_sqlite_db(self.db_path)
        self._seed_records()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed_records(self):
        transactions = [
            ("2026-10-01", "Expense", 100, "Food"),
            ("2026-10-01", "expense", 50, "Travel"),
            ("2026-10-02", "Expense", 250, "Food"),
            ("2026-10-02", "Income", 1000, "Salary"),
        ]
        for entry_date, transaction_type, amount, category in transactions:
            storage.insert_wealth_log(
                entry_date,
                transaction_type,
                amount,
                "INR",
                category,
                None,
                None,
                db_path=self.db_path,
            )
        storage.insert_health_log(
            "2026-10-01", 7, "Running", 2000, None, db_path=self.db_path
        )
        storage.insert_health_log(
            "2026-10-02", 9, "Yoga", 2200, None, db_path=self.db_path
        )

    def _request(self, operation, **overrides):
        return AnalyticsRequest(
            operation=operation,
            start_date=overrides.pop("start_date", "2026-10-01"),
            end_date=overrides.pop("end_date", "2026-10-02"),
            **overrides,
        )

    def test_wealth_total_uses_date_type_and_category_filters(self):
        result = run_analytics(
            self._request(AnalyticsOperation.WEALTH_TOTAL, category="Food"),
            db_path=self.db_path,
        )

        self.assertEqual(result.matched_records, 2)
        self.assertEqual(result.data.totals[0].total, 350)
        self.assertIn("INR 350.00", answer_analytics_request(result))

    def test_category_breakdown_and_daily_trend_are_deterministic(self):
        breakdown = run_analytics(
            self._request(AnalyticsOperation.WEALTH_CATEGORY_BREAKDOWN),
            db_path=self.db_path,
        )
        trend = run_analytics(
            self._request(AnalyticsOperation.WEALTH_DAILY_TREND),
            db_path=self.db_path,
        )

        self.assertEqual(
            [(row.label, row.total) for row in breakdown.data.groups],
            [("Food", 350), ("Travel", 50)],
        )
        self.assertEqual(
            [(row.label, row.total) for row in trend.data.groups],
            [("2026-10-01", 150), ("2026-10-02", 250)],
        )

    def test_health_averages_frequency_and_streak(self):
        averages = run_analytics(
            self._request(AnalyticsOperation.HEALTH_AVERAGES),
            db_path=self.db_path,
        )
        frequency = run_analytics(
            self._request(AnalyticsOperation.WORKOUT_FREQUENCY),
            db_path=self.db_path,
        )
        streak = run_analytics(
            self._request(AnalyticsOperation.WORKOUT_STREAK),
            db_path=self.db_path,
        )

        self.assertEqual(averages.data.average_sleep_hours, 8)
        self.assertEqual(averages.data.average_calories, 2100)
        self.assertEqual(frequency.data.workout_days, 2)
        self.assertEqual(streak.data.current_streak_days, 2)
        self.assertEqual(streak.data.longest_streak_days, 2)

    def test_common_question_routes_without_model_generated_sql(self):
        request = router.parse_common_question(
            "What is my total expense today?", today=date(2026, 10, 2)
        )

        self.assertEqual(request.operation, AnalyticsOperation.WEALTH_TOTAL)
        self.assertEqual(request.start_date, date(2026, 10, 2))
        self.assertEqual(request.transaction_type, "Expense")

        filtered = router.parse_common_question(
            "How much did I spend on food this month?", today=date(2026, 10, 2)
        )
        self.assertEqual(filtered.start_date, date(2026, 10, 1))
        self.assertEqual(filtered.category, "Food")

        last_week = router.parse_common_question(
            "Show my spending last week", today=date(2026, 10, 2)
        )
        self.assertEqual(last_week.start_date, date(2026, 9, 21))
        self.assertEqual(last_week.end_date, date(2026, 9, 27))

    def test_query_node_returns_calculated_answer(self):
        result = nodes.answer_query_node(
            {
                "user_message": "What is my expense on 2026-10-02?",
                "db_path": str(self.db_path),
            }
        )

        self.assertIn("INR 250.00", result["ai_response"])
        self.assertIsNone(result["draft"])

    def test_invalid_destructive_and_oversized_requests_are_rejected(self):
        with self.assertRaises(ValidationError):
            AnalyticsRequest.model_validate(
                {
                    "operation": "DROP TABLE wealth_logs",
                    "start_date": "2026-10-01",
                    "end_date": "2026-10-02",
                }
            )
        with self.assertRaises(ValidationError):
            self._request(
                AnalyticsOperation.WEALTH_TOTAL,
                start_date="2020-01-01",
                end_date="2026-10-02",
            )
        with self.assertRaises(ValidationError):
            self._request(AnalyticsOperation.WEALTH_DAILY_TREND, limit=1000)

        disabled = storage.query_sqlite(
            "DROP TABLE wealth_logs", db_path=self.db_path
        )
        self.assertIn("disabled", disabled)
        self.assertIn(
            "disabled",
            storage.query_sqlite(
                "SELECT * FROM wealth_logs", db_path=self.db_path
            ),
        )
        self.assertEqual(
            len(storage.list_domain_logs("wealth", db_path=self.db_path)), 4
        )

    def test_malicious_model_output_cannot_be_executed(self):
        payload = {
            "operation": "DELETE FROM wealth_logs",
            "start_date": "2026-10-01",
            "end_date": "2026-10-02",
            "transaction_type": "Expense",
            "category": None,
            "limit": 10,
        }
        with patch.object(
            router.genai, "GenerativeModel", return_value=FakeModel(payload)
        ):
            with self.assertRaises(ValueError):
                router.route_analytics_request(
                    {"user_message": "Run my custom database command"}
                )

        self.assertEqual(
            len(storage.list_domain_logs("wealth", db_path=self.db_path)), 4
        )


if __name__ == "__main__":
    unittest.main()
