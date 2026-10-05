import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from life_copilot.ui import learning as learning_ui
from life_copilot.ui.api_client import (
    ApiClientError,
    LearningSearchResult,
    RecordDeletionResult,
    RecordMutationResult,
)


def learning_record(record_id: int):
    return {
        "id": record_id,
        "entry_date": f"2026-10-{min(record_id, 9):02d}",
        "topic": "RAG" if record_id % 2 else "Python",
        "summary_text": f"Learning summary {record_id}",
        "duration_minutes": record_id * 10,
        "url_reference": f"https://example.com/notes/{record_id}",
        "source": "text",
        "created_at": "2026-10-01 09:00:00",
        "updated_at": "2026-10-01 09:00:00",
    }


class FakeLearningApi:
    def __init__(self, records=None, error=None):
        self.records = records if records is not None else [
            learning_record(index) for index in range(1, 13)
        ]
        self.error = error
        self.filters = []
        self.searches = []
        self.patches = []
        self.deletions = []

    def list_all_records(self, domain, **filters):
        self.filters.append((domain, filters))
        if self.error:
            raise self.error
        return self.records

    def search_learning(self, query, **filters):
        self.searches.append((query, filters))
        return LearningSearchResult.model_validate(
            {
                "request": {
                    "query_text": query,
                    "topic": filters.get("topic"),
                    "start_date": filters.get("start_date"),
                    "end_date": filters.get("end_date"),
                    "limit": filters.get("limit", 10),
                },
                "hits": [
                    {
                        "record_id": 1,
                        "entry_date": "2026-10-01",
                        "topic": "RAG",
                        "summary_text": "A verified semantic result.",
                        "duration_minutes": 10,
                        "url_reference": "https://example.com/source",
                        "distance": 0.1,
                    }
                ],
                "mode": "vector",
            }
        )

    def patch_record(self, domain, record_id, payload):
        self.patches.append((domain, record_id, payload))
        record = next(item for item in self.records if item["id"] == record_id)
        return RecordMutationResult(domain=domain, record={**record, **payload})

    def delete_record(self, domain, record_id):
        self.deletions.append((domain, record_id))
        return RecordDeletionResult(domain=domain, deleted_id=record_id)


class LearningPageTests(unittest.TestCase):
    def _run(self, api):
        script = (
            "from life_copilot.ui.learning import run_learning_page\n"
            "run_learning_page()\n"
        )
        with patch.object(learning_ui, "get_api_client", return_value=api):
            return AppTest.from_string(script).run(timeout=20)

    def test_renders_metrics_charts_filters_and_paginated_table(self):
        app = self._run(FakeLearningApi())

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertEqual([str(item.value) for item in app.error], [])
        labels = {item.label for item in app.metric}
        self.assertTrue(
            {"Learning minutes", "Sessions", "Current streak", "Longest streak"}
            .issubset(labels)
        )
        self.assertTrue(any(item.value == "Learning activity" for item in app.subheader))
        self.assertTrue(any(item.value == "Topic distribution" for item in app.subheader))
        self.assertTrue(any(item.label == "Semantic search" for item in app.text_input))
        self.assertEqual(len(app.dataframe), 1)
        self.assertTrue(any("Page 1 of 2" in item.value for item in app.markdown))

    def test_semantic_search_forwards_topic_and_shows_summary_and_source(self):
        api = FakeLearningApi()
        script = (
            "from life_copilot.ui.learning import run_learning_page\n"
            "run_learning_page()\n"
        )
        with patch.object(learning_ui, "get_api_client", return_value=api):
            app = AppTest.from_string(script).run(timeout=20)
            next(item for item in app.text_input if item.label == "Topic").input(
                "RAG"
            ).run(timeout=20)
            next(
                item for item in app.text_input if item.label == "Semantic search"
            ).input("grounded retrieval").run(timeout=20)
            next(item for item in app.button if item.label == "Search notes").click().run(
                timeout=20
            )

        self.assertEqual(api.searches[0][0], "grounded retrieval")
        self.assertEqual(api.searches[0][1]["topic"], "RAG")
        self.assertTrue(any("verified semantic result" in str(item.value).lower() for item in app.markdown))
        self.assertTrue(
            any(item.label == "Open source" for item in app.get("link_button"))
        )

    def test_updates_and_deletes_through_learning_contract(self):
        api = FakeLearningApi(records=[learning_record(1)])
        script = (
            "from life_copilot.ui.learning import run_learning_page\n"
            "run_learning_page()\n"
        )
        with patch.object(learning_ui, "get_api_client", return_value=api):
            app = AppTest.from_string(script).run(timeout=20)
            next(
                item for item in app.button if item.label == "Edit learning session"
            ).click().run(timeout=20)
            next(item for item in app.text_area if item.label == "Summary").input(
                "Updated learning summary"
            ).run(timeout=20)
            next(item for item in app.button if item.label == "Save changes").click().run(
                timeout=20
            )

        self.assertEqual(api.patches[0][0:2], ("learning", 1))
        self.assertEqual(api.patches[0][2]["summary_text"], "Updated learning summary")

        api = FakeLearningApi(records=[learning_record(1)])
        with patch.object(learning_ui, "get_api_client", return_value=api):
            app = AppTest.from_string(script).run(timeout=20)
            next(
                item for item in app.button if item.label == "Delete learning session"
            ).click().run(timeout=20)
            self.assertEqual(api.deletions, [])
            next(
                item for item in app.button if item.label == "Delete permanently"
            ).click().run(timeout=20)

        self.assertEqual(api.deletions, [("learning", 1)])

    def test_empty_and_api_error_states_are_safe(self):
        empty_app = self._run(FakeLearningApi(records=[]))
        self.assertEqual([str(item.value) for item in empty_app.exception], [])
        self.assertTrue(
            any("No learning sessions" in item.value for item in empty_app.info)
        )

        error_app = self._run(
            FakeLearningApi(error=ApiClientError("The API is unavailable."))
        )
        self.assertEqual([str(item.value) for item in error_app.exception], [])
        self.assertTrue(any("API is unavailable" in item.value for item in error_app.error))


if __name__ == "__main__":
    unittest.main()
