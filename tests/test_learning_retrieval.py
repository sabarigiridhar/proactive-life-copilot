import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from life_copilot import storage
from life_copilot.agent import nodes
from life_copilot.retrieval.evaluation import evaluate_learning_retrieval
from life_copilot.retrieval.learning import (
    create_learning_search_request,
    search_learning_records,
)
from life_copilot.retrieval.models import (
    LearningSearchHit,
    LearningSearchRequest,
    LearningSearchResult,
)


class FakeCollection:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {"ids": [[]], "metadatas": [[]], "distances": [[]]}
        self.error = error
        self.query_arguments = None

    def count(self):
        if self.error:
            raise self.error
        return len(self.payload.get("ids", [[]])[0])

    def query(self, **kwargs):
        if self.error:
            raise self.error
        self.query_arguments = kwargs
        return self.payload


class LearningRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "learning.db"
        storage.init_sqlite_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert(self, entry_date, topic, summary):
        return storage.insert_learning_log(
            entry_date,
            topic,
            45,
            "https://example.com/note",
            summary_text=summary,
            db_path=self.db_path,
        )

    def test_vector_filters_and_sqlite_enrichment(self):
        record_id = self._insert(
            "2026-10-01", "RAG", "SQLite is the source of truth for this summary."
        )
        collection = FakeCollection(
            {
                "ids": [[f"learning_{record_id}"]],
                "metadatas": [[{"sqlite_id": record_id, "topic": "Untrusted"}]],
                "distances": [[0.12]],
            }
        )
        request = LearningSearchRequest(
            query_text="semantic retrieval",
            topic="RAG",
            start_date="2026-10-01",
            end_date="2026-10-02",
        )

        result = search_learning_records(
            request, db_path=self.db_path, collection=collection
        )

        self.assertEqual(result.mode, "vector")
        self.assertEqual(result.hits[0].record_id, record_id)
        self.assertEqual(result.hits[0].topic, "RAG")
        self.assertIn("source of truth", result.hits[0].summary_text)
        self.assertEqual(
            collection.query_arguments["where"],
            {
                "$and": [
                    {"topic": {"$eq": "RAG"}},
                    {
                        "date_ordinal": {
                            "$gte": date(2026, 10, 1).toordinal()
                        }
                    },
                    {
                        "date_ordinal": {
                            "$lte": date(2026, 10, 2).toordinal()
                        }
                    },
                ]
            },
        )

    def test_unavailable_vector_index_uses_ranked_sqlite_fallback(self):
        expected_id = self._insert(
            "2026-09-24",
            "SQLite",
            "Parameterized queries prevent SQL injection attacks.",
        )
        self._insert("2026-09-25", "CSS", "Grid creates responsive page layouts.")

        result = search_learning_records(
            LearningSearchRequest(query_text="How did I prevent SQL injection?"),
            db_path=self.db_path,
            collection=FakeCollection(error=RuntimeError("offline")),
        )

        self.assertEqual(result.mode, "sqlite_fallback")
        self.assertEqual(result.hits[0].record_id, expected_id)
        self.assertIn("unavailable", result.warning)

    def test_empty_index_and_database_return_an_empty_result(self):
        result = search_learning_records(
            LearningSearchRequest(query_text="What did I learn about RAG?"),
            db_path=self.db_path,
            collection=FakeCollection(),
        )

        self.assertEqual(result.mode, "empty")
        self.assertEqual(result.hits, [])
        self.assertIn("No matching", result.warning)

    def test_known_topic_and_relative_date_are_extracted(self):
        self._insert("2026-09-23", "LangGraph", "Stateful graph notes.")

        request = create_learning_search_request(
            "What did I learn about LangGraph last week?",
            today=date(2026, 10, 2),
            db_path=self.db_path,
        )

        self.assertEqual(request.topic, "LangGraph")
        self.assertEqual(request.start_date, date(2026, 9, 21))
        self.assertEqual(request.end_date, date(2026, 9, 27))

    def test_learning_query_node_returns_only_verified_hit_details(self):
        request = LearningSearchRequest(query_text="What did I learn about RAG?")
        retrieval = LearningSearchResult(
            request=request,
            mode="vector",
            hits=[
                LearningSearchHit(
                    record_id=7,
                    entry_date="2026-10-01",
                    topic="RAG",
                    summary_text="Retrieval adds relevant context before generation.",
                    duration_minutes=40,
                )
            ],
        )

        with patch.object(nodes, "search_learning_records", return_value=retrieval):
            response = nodes.answer_query_node(
                {
                    "user_message": "What did I learn about RAG?",
                    "db_path": str(self.db_path),
                }
            )

        self.assertIn("Retrieval adds relevant context", response["ai_response"])
        self.assertIn("Learning #7", response["ai_response"])
        self.assertIsNone(response["draft"])

    def test_evaluation_reports_top_k_hit_rate(self):
        cases = [
            {
                "name": "found",
                "query": "state",
                "expected_summary_contains": "conversation state",
                "top_k": 2,
            },
            {
                "name": "missing",
                "query": "SQL",
                "expected_summary_contains": "parameterized SQL",
                "top_k": 1,
            },
        ]

        def fake_search(request):
            return LearningSearchResult(
                request=request,
                mode="vector",
                hits=[
                    LearningSearchHit(
                        record_id=1,
                        entry_date="2026-10-01",
                        topic="LangGraph",
                        summary_text="Checkpoints preserve conversation state.",
                    )
                ],
            )

        report = evaluate_learning_retrieval(cases, fake_search)

        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["top_k_hit_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
