import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from life_copilot import storage
from life_copilot.agent import workflow
from streamlit.testing.v1 import AppTest


class FakeBrain:
    def invoke(self, *_args, **_kwargs):
        return {
            "ai_response": "Your total expenses are 350.",
            "draft": None,
            "evidence": [{"currency": "INR", "total": 350.0}],
            "date_range": {
                "start_date": "2026-10-02",
                "end_date": "2026-10-02",
            },
            "confidence": 1.0,
        }


class StreamlitInteractionTests(unittest.TestCase):
    def setUp(self):
        self.original_directory = Path.cwd()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        os.chdir(self.original_directory)
        self.temp_dir.cleanup()

    def test_query_uses_neutral_status_and_clears_input_after_reply(self):
        app_path = self.original_directory / "app.py"
        source = (
            self.original_directory / "life_copilot" / "ui" / "main.py"
        ).read_text(encoding="utf-8")
        self.assertIn('st.spinner("Processing your message...")', source)
        self.assertNotIn('st.spinner("Preparing a draft...")', source)

        with patch.object(workflow, "app_brain", FakeBrain()):
            app = AppTest.from_file(str(app_path)).run(timeout=20)
            app.text_area[0].input("What is my today expense").run(timeout=20)
            send_button = next(button for button in app.button if button.label == "Send")
            send_button.click().run(timeout=20)

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertEqual(app.text_area[0].value, "")
        self.assertTrue(any("350" in item.value for item in app.markdown))
        self.assertTrue(any(item.label == "Evidence" for item in app.expander))
        self.assertEqual(len(app.dataframe), 1)

    def test_maintenance_renders_a_legacy_zero_wealth_amount(self):
        storage.init_sqlite_db()
        storage.insert_wealth_log(
            "2026-10-02",
            "Expense",
            0.0,
            "INR",
            "General",
            None,
            "Legacy zero-value record",
        )

        app_path = self.original_directory / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=20)

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
