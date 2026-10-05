import io
import json
import unittest
import zipfile
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from life_copilot.ui import settings as settings_ui
from life_copilot.ui.api_client import (
    ApiClientError,
    BackupResult,
    SettingsResult,
)


def settings_result():
    return SettingsResult.model_validate(
        {
            "preferences": {
                "default_currency": "INR",
                "weekly_spending_limit": None,
                "weekly_learning_minutes": 300,
                "weekly_workouts": 3,
                "sleep_hours_target": 8,
                "updated_at": "2026-10-05T10:00:00Z",
            },
            "providers": [
                {
                    "provider": "Gemini",
                    "capability": "Chat and extraction",
                    "model": "gemini-test",
                    "configured": True,
                },
                {
                    "provider": "Groq",
                    "capability": "Voice transcription",
                    "model": "whisper-test",
                    "configured": False,
                },
            ],
        }
    )


class FakeSettingsApi:
    def __init__(self, error=None):
        self.error = error
        self.updates = []
        self.backups = 0
        self.listed_domains = []

    def get_settings(self):
        if self.error:
            raise self.error
        return settings_result()

    def update_settings(self, payload):
        self.updates.append(payload)
        result = settings_result()
        result.preferences.default_currency = payload["default_currency"]
        return result

    def list_all_records(self, domain):
        self.listed_domains.append(domain)
        common = {
            "id": 1,
            "entry_date": "2026-10-05",
            "source": "text",
            "created_at": "2026-10-05 10:00:00",
            "updated_at": "2026-10-05 10:00:00",
            "original_input": "private input",
        }
        if domain == "wealth":
            return [
                {
                    **common,
                    "transaction_type": "Expense",
                    "amount": 100,
                    "currency": "INR",
                    "category": "Food",
                    "merchant": "Cafe",
                    "notes": None,
                }
            ]
        if domain == "health":
            return [
                {
                    **common,
                    "sleep_hours": 8,
                    "workout_type": "Yoga",
                    "calories_consumed": 2000,
                    "notes": None,
                }
            ]
        return [
            {
                **common,
                "topic": "RAG",
                "summary_text": "Retrieval notes",
                "duration_minutes": 30,
                "url_reference": "https://example.com",
            }
        ]

    def create_backup(self):
        self.backups += 1
        return BackupResult.model_validate(
            {
                "backup_name": "snapshot_test",
                "created_at": "2026-10-05T10:00:00Z",
                "includes": ["SQLite database", "learning vector index"],
                "warnings": [],
            }
        )


class SettingsPageTests(unittest.TestCase):
    def _run(self, api):
        script = (
            "from life_copilot.ui.settings import run_settings_page\n"
            "run_settings_page()\n"
        )
        with patch.object(settings_ui, "get_api_client", return_value=api):
            return AppTest.from_string(script).run(timeout=20)

    def test_renders_preferences_provider_status_and_data_entry_points(self):
        app = self._run(FakeSettingsApi())

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(
            any(item.label == "Preferred currency" for item in app.text_input)
        )
        self.assertTrue(any(item.label == "Save settings" for item in app.button))
        self.assertTrue(any(item.label == "Prepare export" for item in app.button))
        self.assertTrue(
            any(item.label == "Create local snapshot" for item in app.button)
        )
        messages = {item.value for item in app.success}
        self.assertIn("Configured", messages)
        self.assertTrue(any(item.value == "Missing" for item in app.warning))
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertNotIn("private", rendered)

    def test_saves_validated_preferences(self):
        api = FakeSettingsApi()
        script = (
            "from life_copilot.ui.settings import run_settings_page\n"
            "run_settings_page()\n"
        )
        with patch.object(settings_ui, "get_api_client", return_value=api):
            app = AppTest.from_string(script).run(timeout=20)
            next(
                item for item in app.text_input if item.label == "Preferred currency"
            ).input("usd").run(timeout=20)
            next(item for item in app.button if item.label == "Save settings").click().run(
                timeout=20
            )

        self.assertEqual(api.updates[0]["default_currency"], "USD")
        self.assertEqual(api.updates[0]["weekly_learning_minutes"], 300)

    def test_prepares_public_export_and_creates_snapshot(self):
        api = FakeSettingsApi()
        script = (
            "from life_copilot.ui.settings import run_settings_page\n"
            "run_settings_page()\n"
        )
        with patch.object(settings_ui, "get_api_client", return_value=api):
            app = AppTest.from_string(script).run(timeout=20)
            next(item for item in app.button if item.label == "Prepare export").click().run(
                timeout=20
            )
            self.assertTrue(
                any(item.label == "Download records ZIP" for item in app.download_button)
            )
            next(
                item for item in app.button if item.label == "Create local snapshot"
            ).click().run(timeout=20)

        self.assertEqual(api.listed_domains, ["wealth", "health", "learning"])
        self.assertEqual(api.backups, 1)
        self.assertTrue(any("snapshot_test" in item.value for item in app.success))

    def test_export_contains_json_and_csv_without_private_input(self):
        api = FakeSettingsApi()
        payload = settings_ui._records_export(
            {domain: api.list_all_records(domain) for domain in ("wealth", "health", "learning")}
        )

        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    "life-copilot-records.json",
                    "wealth.csv",
                    "health.csv",
                    "learning.csv",
                },
            )
            exported = json.loads(archive.read("life-copilot-records.json"))
            self.assertEqual(exported["wealth"][0]["amount"], 100)
            self.assertNotIn("original_input", archive.read("wealth.csv").decode())

    def test_api_error_is_visible_without_rendering_controls(self):
        app = self._run(FakeSettingsApi(ApiClientError("API unavailable.")))

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(any("API unavailable" in item.value for item in app.error))


if __name__ == "__main__":
    unittest.main()
