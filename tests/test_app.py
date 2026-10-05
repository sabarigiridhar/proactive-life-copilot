import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from life_copilot.ui import main as ui_main
from life_copilot.ui.api_client import (
    ApiClientError,
    ConfirmationResult,
    DailyStatusResult,
    DashboardResult,
    MessageResult,
    RecordPageResult,
)


class FakeApi:
    def __init__(self, records=None):
        self.records = records or []
        self.messages = []
        self.confirmed_drafts = []
        self.dashboard_queries = []

    def get_dashboard_summary(self, *, status_date, start_date=None, end_date=None):
        self.dashboard_queries.append((status_date, start_date, end_date))
        start_date = start_date or status_date
        end_date = end_date or status_date
        return DashboardResult.model_validate(
            {
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "status_date": status_date,
                "daily_status": {
                    "entry_date": status_date,
                    "health_complete": False,
                    "wealth_reviewed": False,
                    "learning_complete": False,
                    "is_complete": False,
                },
                "wealth": {
                    "income": [],
                    "expenses": [
                        {
                            "currency": "INR",
                            "total": 350,
                            "records": 2,
                        }
                    ],
                    "net": [
                        {
                            "currency": "INR",
                            "income": 0,
                            "expense": 350,
                            "net": -350,
                        }
                    ],
                    "categories": [
                        {
                            "category": "Food",
                            "currency": "INR",
                            "total": 350,
                            "records": 2,
                        }
                    ],
                    "daily": [
                        {
                            "entry_date": end_date,
                            "currency": "INR",
                            "income": 0,
                            "expense": 350,
                            "net": -350,
                        }
                    ],
                },
                "health": {
                    "average_sleep_hours": 7.5,
                    "average_calories": None,
                    "sleep_records": 1,
                    "calorie_records": 0,
                    "workout_days": 1,
                    "daily": [
                        {
                            "entry_date": end_date,
                            "sleep_hours": 7.5,
                            "calories_consumed": None,
                            "workout_type": "Gym",
                        }
                    ],
                },
                "learning": {
                    "total_minutes": 45,
                    "sessions": 1,
                    "learning_days": 1,
                    "current_streak_days": 1,
                    "longest_streak_days": 1,
                    "topics": [
                        {"topic": "FastAPI", "minutes": 45, "sessions": 1}
                    ],
                    "daily": [
                        {"entry_date": end_date, "minutes": 45, "sessions": 1}
                    ],
                },
            }
        )

    def list_records(self, domain, *, page=1, page_size=50):
        items = self.records if domain == "wealth" else []
        return RecordPageResult(
            domain=domain,
            items=items,
            page=page,
            page_size=page_size,
            total=len(items),
            total_pages=1 if items else 0,
        )

    def send_message(self, *, thread_id, message, source="text"):
        self.messages.append((thread_id, message, source))
        if "spent" in message.lower():
            return MessageResult(
                thread_id=thread_id,
                response_type="log_draft",
                assistant_text="I prepared 1 record(s). Review the draft before saving.",
                draft={
                    "entry_date": "2026-10-04",
                    "source": source,
                    "original_input": message,
                    "health": None,
                    "wealth": [
                        {
                            "transaction_type": "Expense",
                            "amount": 120,
                            "currency": "INR",
                            "category": "Food",
                            "merchant": "Cafe",
                            "notes": None,
                        }
                    ],
                    "learning": [],
                    "confidence": 0.95,
                    "ambiguities": [],
                    "operation": "create",
                    "target_domain": None,
                    "target_record_id": None,
                },
            )
        return MessageResult(
            thread_id=thread_id,
            response_type="query_answer",
            assistant_text="Your total expenses are 350.",
            evidence=[{"currency": "INR", "total": 350.0}],
            date_range={
                "start_date": "2026-10-04",
                "end_date": "2026-10-04",
            },
            confidence=1.0,
        )

    def confirm_log(self, *, thread_id, draft):
        self.confirmed_drafts.append(draft)
        return ConfirmationResult(
            thread_id=thread_id,
            assistant_text="Saved 1 confirmed record(s).",
            daily_status=DailyStatusResult(
                entry_date=date(2026, 10, 4),
                health_complete=False,
                wealth_reviewed=True,
                learning_complete=False,
                is_complete=False,
            ),
        )


class UnavailableApi:
    def get_dashboard_summary(
        self, *, status_date, start_date=None, end_date=None
    ):
        raise ApiClientError(
            "The Life Copilot API is unavailable. Check that the backend is running."
        )


class MessageFailureApi(FakeApi):
    def send_message(self, *, thread_id, message, source="text"):
        raise ApiClientError("The message could not be processed safely.")


class EmptyDashboardApi(FakeApi):
    def get_dashboard_summary(self, *, status_date, start_date=None, end_date=None):
        dashboard = super().get_dashboard_summary(
            status_date=status_date,
            start_date=start_date,
            end_date=end_date,
        )
        dashboard.wealth.income = []
        dashboard.wealth.expenses = []
        dashboard.wealth.net = []
        dashboard.wealth.categories = []
        dashboard.wealth.daily = []
        dashboard.health.average_sleep_hours = None
        dashboard.health.average_calories = None
        dashboard.health.sleep_records = 0
        dashboard.health.calorie_records = 0
        dashboard.health.workout_days = 0
        dashboard.health.daily = []
        dashboard.learning.total_minutes = 0
        dashboard.learning.sessions = 0
        dashboard.learning.learning_days = 0
        dashboard.learning.current_streak_days = 0
        dashboard.learning.longest_streak_days = 0
        dashboard.learning.topics = []
        dashboard.learning.daily = []
        return dashboard


class StreamlitInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.app_path = cls.root / "app.py"

    def _run(self, api):
        with patch.object(ui_main, "get_api_client", return_value=api):
            return AppTest.from_file(str(self.app_path)).run(timeout=20)

    def test_query_uses_api_neutral_status_and_clears_input_after_reply(self):
        source = (self.root / "life_copilot" / "ui" / "main.py").read_text(
            encoding="utf-8"
        )
        app_source = (self.root / "app.py").read_text(encoding="utf-8")
        self.assertIn('st.spinner("Processing your message...")', source)
        self.assertIn("st.navigation", app_source)
        self.assertIn('position="top"', app_source)
        self.assertNotIn("app_brain", source)
        self.assertNotIn("life_copilot.agent", source)
        api = FakeApi()

        with patch.object(ui_main, "get_api_client", return_value=api):
            app = AppTest.from_file(str(self.app_path)).run(timeout=20)
            app.text_area[0].input("What is my today expense").run(timeout=20)
            send_button = next(button for button in app.button if button.label == "Send")
            send_button.click().run(timeout=20)

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertEqual(app.text_area[0].value, "")
        self.assertTrue(any("350" in item.value for item in app.markdown))
        self.assertTrue(any(item.label == "Evidence" for item in app.expander))
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(api.messages[0][1], "What is my today expense")
        self.assertGreaterEqual(len(api.dashboard_queries), 3)
        self.assertEqual(
            (api.dashboard_queries[0][2] - api.dashboard_queries[0][1]).days,
            6,
        )

    def test_home_renders_wealth_health_learning_and_completion_metrics(self):
        api = FakeApi()
        app = self._run(api)

        self.assertEqual([str(item.value) for item in app.exception], [])
        labels = {item.label for item in app.metric}
        self.assertTrue(
            {
                "Spent",
                "Daily check-in",
                "Avg sleep",
                "Workout days",
                "Focused time",
                "Current streak",
                "Active days",
            }.issubset(labels)
        )
        self.assertTrue(any(item.value == "Wealth" for item in app.subheader))
        self.assertTrue(any(item.value == "Copilot" for item in app.subheader))
        self.assertTrue(any(item.value == "Health" for item in app.subheader))
        self.assertTrue(any(item.value == "Learning" for item in app.subheader))

    def test_home_has_clear_empty_states_for_each_domain(self):
        app = self._run(EmptyDashboardApi())

        self.assertEqual([str(item.value) for item in app.exception], [])
        messages = {item.value for item in app.info}
        self.assertIn("No wealth activity in this period.", messages)
        self.assertIn("No health entries in this period.", messages)
        self.assertIn("No learning sessions in this period.", messages)

    def test_log_draft_is_confirmed_through_api(self):
        api = FakeApi()
        with patch.object(ui_main, "get_api_client", return_value=api):
            app = AppTest.from_file(str(self.app_path)).run(timeout=20)
            app.text_area[0].input("I spent 120 at Cafe").run(timeout=20)
            next(button for button in app.button if button.label == "Send").click().run(
                timeout=20
            )
            confirm = next(
                button for button in app.button if button.label == "Confirm and save"
            )
            confirm.click().run(timeout=20)

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertEqual(len(api.confirmed_drafts), 1)
        self.assertEqual(api.confirmed_drafts[0]["wealth"][0]["amount"], 120)
        self.assertTrue(
            any("Saved 1 confirmed" in item.value for item in app.markdown)
        )

    def test_api_unavailable_state_is_visible_without_crashing(self):
        app = self._run(UnavailableApi())

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(any("API is unavailable" in item.value for item in app.error))
        self.assertTrue(any("Start the FastAPI backend" in item.value for item in app.info))

    def test_message_api_failure_is_rendered_as_an_error(self):
        api = MessageFailureApi()
        with patch.object(ui_main, "get_api_client", return_value=api):
            app = AppTest.from_file(str(self.app_path)).run(timeout=20)
            app.text_area[0].input("Log something").run(timeout=20)
            next(button for button in app.button if button.label == "Send").click().run(
                timeout=20
            )

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(
            any("could not be processed safely" in item.value for item in app.error)
        )

    def test_maintenance_renders_a_legacy_zero_wealth_amount_from_api(self):
        api = FakeApi(
            records=[
                {
                    "id": 1,
                    "entry_date": "2026-10-02",
                    "transaction_type": "Expense",
                    "amount": 0.0,
                    "currency": "INR",
                    "category": "General",
                    "merchant": None,
                    "notes": "Legacy zero-value record",
                    "source": "legacy",
                    "created_at": "2026-10-02 00:00:00",
                    "updated_at": "2026-10-02 00:00:00",
                }
            ]
        )
        with patch.object(ui_main, "get_api_client", return_value=api):
            app = AppTest.from_string(
                "from life_copilot.ui.main import run_records_page\n"
                "run_records_page()\n"
            ).run(timeout=20)

        self.assertEqual([str(item.value) for item in app.exception], [])
        amount_input = next(
            field for field in app.number_input if field.label == "Amount"
        )
        self.assertEqual(amount_input.value, 0.0)
        self.assertTrue(
            any("greater than zero" in item.value for item in app.warning)
        )


if __name__ == "__main__":
    unittest.main()
