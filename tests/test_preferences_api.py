import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.core.settings import Settings
from backend.main import create_app
from life_copilot import storage


class PreferencesApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            environment="test",
            database_path=root / "preferences.db",
            chroma_path=root / "chroma",
            backup_path=root / "backups",
            cors_origins=[],
        )
        storage.init_sqlite_db(self.settings.database_path)
        self.client = TestClient(create_app(self.settings))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_openapi_documents_settings_backup_and_weekly_review_routes(self):
        paths = self.client.get("/openapi.json").json()["paths"]

        self.assertIn("/api/v1/settings", paths)
        self.assertIn("/api/v1/data/backups", paths)
        self.assertIn("/api/v1/insights/weekly", paths)

    def test_preferences_are_persistent_and_validated(self):
        initial = self.client.get("/api/v1/settings")
        updated = self.client.patch(
            "/api/v1/settings",
            json={
                "default_currency": "usd",
                "weekly_spending_limit": 500,
                "weekly_learning_minutes": 240,
                "weekly_workouts": 4,
                "sleep_hours_target": 7.5,
            },
        )
        reloaded = self.client.get("/api/v1/settings")
        partial = self.client.patch(
            "/api/v1/settings", json={"default_currency": "eur"}
        )
        invalid = self.client.patch(
            "/api/v1/settings",
            json={
                "default_currency": "I",
                "weekly_spending_limit": -1,
                "weekly_learning_minutes": 20000,
                "weekly_workouts": 20,
                "sleep_hours_target": 30,
            },
        )

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.json()["data"]["preferences"]["default_currency"], "INR")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["data"]["preferences"]["default_currency"], "USD")
        self.assertEqual(
            reloaded.json()["data"]["preferences"]["weekly_learning_minutes"],
            240,
        )
        self.assertEqual(partial.status_code, 200)
        self.assertEqual(partial.json()["data"]["preferences"]["default_currency"], "EUR")
        self.assertEqual(partial.json()["data"]["preferences"]["weekly_workouts"], 4)
        self.assertEqual(invalid.status_code, 422)

    def test_provider_status_never_exposes_api_keys(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "private-gemini", "GROQ_API_KEY": "private-groq"},
        ):
            response = self.client.get("/api/v1/settings")

        body = response.text
        providers = response.json()["data"]["providers"]
        self.assertTrue(all(item["configured"] for item in providers))
        self.assertNotIn("private-gemini", body)
        self.assertNotIn("private-groq", body)
        self.assertNotIn("api_key", body.casefold())

    def test_local_backup_uses_test_paths_and_writes_manifest(self):
        self.settings.chroma_path.mkdir()
        (self.settings.chroma_path / "index.bin").write_bytes(b"test-vector-data")

        response = self.client.post("/api/v1/data/backups")

        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        destination = self.settings.backup_path / data["backup_name"]
        self.assertTrue((destination / self.settings.database_path.name).exists())
        self.assertTrue((destination / self.settings.chroma_path.name / "index.bin").exists())
        manifest = json.loads((destination / "manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["backup_name"], data["backup_name"])
        self.assertNotIn(str(self.settings.database_path), response.text)

    def test_weekly_reviews_return_typed_empty_state_until_generation_exists(self):
        response = self.client.get("/api/v1/insights/weekly")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["reviews"], [])
        self.assertFalse(data["generation_available"])
        self.assertIn("No weekly reviews", data["message"])


if __name__ == "__main__":
    unittest.main()
