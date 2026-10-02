import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from life_copilot import storage as db_utils
from life_copilot.agent import memory, workflow
from life_copilot.services.drafts import save_confirmed_draft


class ConversationRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "memory.db"
        db_utils.init_sqlite_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_threads_are_isolated_and_recent_window_is_bounded(self):
        for index in range(10):
            db_utils.add_chat_message(
                "thread-a", "user", f"message a {index}", db_path=self.db_path
            )
        db_utils.add_chat_message(
            "thread-b", "user", "message b", db_path=self.db_path
        )

        window = db_utils.get_memory_window(
            "thread-a", recent_limit=8, db_path=self.db_path
        )

        self.assertEqual(len(window["recent_messages"]), 8)
        self.assertEqual(len(window["unsummarized_messages"]), 2)
        self.assertTrue(
            all("message a" in item["content"] for item in window["recent_messages"])
        )
        self.assertEqual(
            [item["content"] for item in db_utils.get_chat_messages(
                "thread-b", db_path=self.db_path
            )],
            ["message b"],
        )

    def test_summary_cursor_prevents_messages_from_being_summarized_twice(self):
        for index in range(5):
            db_utils.add_chat_message(
                "thread-a", "user", f"message {index}", db_path=self.db_path
            )
        first_window = db_utils.get_memory_window(
            "thread-a", recent_limit=2, db_path=self.db_path
        )
        older = first_window["unsummarized_messages"]
        db_utils.update_chat_summary(
            "thread-a", "Stored summary", older[-1]["id"], db_path=self.db_path
        )

        second_window = db_utils.get_memory_window(
            "thread-a", recent_limit=2, db_path=self.db_path
        )

        self.assertEqual(second_window["summary"], "Stored summary")
        self.assertEqual(second_window["unsummarized_messages"], [])

    def test_graph_rolls_older_messages_into_persisted_summary(self):
        for index in range(10):
            db_utils.add_chat_message(
                "thread-a", "user", f"message {index}", db_path=self.db_path
            )

        with patch.object(
            memory, "_summarize_messages", return_value="Compact conversation summary"
        ):
            state = memory.load_memory_node(
                {"thread_id": "thread-a", "db_path": str(self.db_path)}
            )

        window = db_utils.get_memory_window(
            "thread-a", recent_limit=8, db_path=self.db_path
        )
        self.assertEqual(state["conversation_summary"], "Compact conversation summary")
        self.assertEqual(window["summary"], "Compact conversation summary")
        self.assertEqual(window["unsummarized_messages"], [])

    def test_confirmed_entities_can_be_recovered_from_message_metadata(self):
        entities = [{"domain": "wealth", "record_id": 42, "merchant": "Cafe"}]
        db_utils.add_chat_message(
            "thread-a",
            "assistant",
            "Saved one record.",
            metadata={"event": "confirmed_records", "entities": entities},
            db_path=self.db_path,
        )

        self.assertEqual(
            db_utils.get_last_confirmed_entities(
                "thread-a", db_path=self.db_path
            ),
            entities,
        )


class ConversationGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "graph-memory.db"
        db_utils.init_sqlite_db(self.db_path)
        self.thread_a = f"test-a-{uuid.uuid4().hex}"
        self.thread_b = f"test-b-{uuid.uuid4().hex}"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _initialize_thread(self, thread_id):
        return workflow.app_brain.invoke(
            {
                "thread_id": thread_id,
                "db_path": str(self.db_path),
                "user_message": "Add 1 more to that",
                "source": "text",
                "draft": None,
            },
            config=workflow.thread_config(thread_id),
        )

    def _insert_wealth(self, amount, merchant):
        return db_utils.insert_wealth_log(
            "2026-10-02",
            "Expense",
            amount,
            "INR",
            "Food",
            merchant,
            None,
            db_path=self.db_path,
        )

    def test_reference_creates_confirmable_update_and_threads_do_not_share_it(self):
        record_id = self._insert_wealth(100, "Cafe")
        self._initialize_thread(self.thread_a)
        self._initialize_thread(self.thread_b)
        workflow.remember_confirmed_draft(
            self.thread_a,
            {
                "record_ids": {
                    "wealth": [record_id],
                    "health": [],
                    "learning": [],
                }
            },
            db_path=self.db_path,
        )

        state_a = workflow.app_brain.invoke(
            {
                "thread_id": self.thread_a,
                "db_path": str(self.db_path),
                "user_message": "Add 50 more to that",
                "source": "text",
                "draft": None,
            },
            config=workflow.thread_config(self.thread_a),
        )
        state_b = workflow.app_brain.invoke(
            {
                "thread_id": self.thread_b,
                "db_path": str(self.db_path),
                "user_message": "Add 50 more to that",
                "source": "text",
                "draft": None,
            },
            config=workflow.thread_config(self.thread_b),
        )

        self.assertEqual(state_a["draft"]["operation"], "update")
        self.assertEqual(state_a["draft"]["target_record_id"], record_id)
        self.assertEqual(state_a["draft"]["wealth"][0]["amount"], 150)
        self.assertIsNone(state_b["draft"])
        self.assertIn("cannot tell", state_b["ai_response"])

        result = save_confirmed_draft(
            state_a["draft"], db_path=self.db_path
        )
        self.assertEqual(result["record_ids"]["wealth"], [record_id])
        self.assertEqual(
            db_utils.get_domain_log("wealth", record_id, db_path=self.db_path)[
                "amount"
            ],
            150,
        )
        self.assertEqual(
            len(db_utils.list_domain_logs("wealth", db_path=self.db_path)), 1
        )

    def test_ambiguous_reference_requires_and_resolves_clarification(self):
        cafe_id = self._insert_wealth(100, "Cafe")
        coffee_id = self._insert_wealth(80, "Coffee shop")
        self._initialize_thread(self.thread_a)
        workflow.remember_confirmed_draft(
            self.thread_a,
            {
                "record_ids": {
                    "wealth": [cafe_id, coffee_id],
                    "health": [],
                    "learning": [],
                }
            },
            db_path=self.db_path,
        )

        ambiguous = workflow.app_brain.invoke(
            {
                "thread_id": self.thread_a,
                "db_path": str(self.db_path),
                "user_message": "Add 50 more to that",
                "source": "text",
                "draft": None,
            },
            config=workflow.thread_config(self.thread_a),
        )

        self.assertIsNone(ambiguous["draft"])
        self.assertIn("Which transaction", ambiguous["ai_response"])
        self.assertIsNotNone(ambiguous["awaiting_clarification"])

        resolved = workflow.app_brain.invoke(
            {
                "thread_id": self.thread_a,
                "db_path": str(self.db_path),
                "user_message": "the coffee shop one",
                "source": "text",
                "draft": None,
            },
            config=workflow.thread_config(self.thread_a),
        )

        self.assertEqual(resolved["draft"]["target_record_id"], coffee_id)
        self.assertEqual(resolved["draft"]["wealth"][0]["amount"], 130)
        self.assertIsNone(resolved["awaiting_clarification"])


if __name__ == "__main__":
    unittest.main()
