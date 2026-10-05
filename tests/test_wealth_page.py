import unittest
from datetime import date
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from life_copilot.ui import wealth as wealth_ui
from life_copilot.ui.api_client import (
    ApiClientError,
    RecordDeletionResult,
    RecordMutationResult,
)


def wealth_record(record_id: int, *, transaction_type="Expense", amount=100):
    return {
        "id": record_id,
        "entry_date": f"2026-10-{min(record_id, 9):02d}",
        "transaction_type": transaction_type,
        "amount": float(amount),
        "currency": "INR",
        "category": "Food" if transaction_type == "Expense" else "Salary",
        "merchant": "Market" if transaction_type == "Expense" else "Employer",
        "notes": f"Record {record_id}",
        "source": "text",
        "created_at": "2026-10-01 09:00:00",
        "updated_at": "2026-10-01 09:00:00",
    }


class FakeWealthApi:
    def __init__(self, records=None, error=None):
        self.records = records if records is not None else [
            wealth_record(1, transaction_type="Income", amount=1000),
            *[wealth_record(index, amount=index * 10) for index in range(2, 13)],
        ]
        self.error = error
        self.filters = []
        self.patches = []
        self.deletions = []

    def list_all_records(self, domain, **filters):
        self.filters.append((domain, filters))
        if self.error:
            raise self.error
        return self.records

    def patch_record(self, domain, record_id, payload):
        self.patches.append((domain, record_id, payload))
        record = next(item for item in self.records if item["id"] == record_id)
        return RecordMutationResult(
            domain=domain,
            record={**record, **payload},
        )

    def delete_record(self, domain, record_id):
        self.deletions.append((domain, record_id))
        return RecordDeletionResult(domain=domain, deleted_id=record_id)


class WealthPageTests(unittest.TestCase):
    def _run(self, api):
        script = (
            "from life_copilot.ui.wealth import run_wealth_page\n"
            "run_wealth_page()\n"
        )
        with patch.object(wealth_ui, "get_api_client", return_value=api):
            return AppTest.from_string(script).run(timeout=20)

    def test_renders_filters_totals_charts_table_pagination_and_export(self):
        api = FakeWealthApi()
        app = self._run(api)

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertEqual([str(item.value) for item in app.error], [])
        self.assertTrue(
            {"Income", "Expenses", "Net"}.issubset(
                {item.label for item in app.metric}
            )
        )
        self.assertEqual(len(app.dataframe), 1)
        self.assertTrue(any(item.label == "Download CSV" for item in app.download_button))
        self.assertTrue(any(item.label == "Search transactions" for item in app.text_input))
        self.assertTrue(any(item.label == "Date range" for item in app.selectbox))
        self.assertTrue(any(item.value == "Cash flow" for item in app.subheader))
        self.assertTrue(
            any(item.value == "Expense categories" for item in app.subheader)
        )
        self.assertTrue(any("Page 1 of 2" in item.value for item in app.markdown))

    def test_forwards_filters_and_pages_the_transaction_table(self):
        api = FakeWealthApi()
        script = (
            "from life_copilot.ui.wealth import run_wealth_page\n"
            "run_wealth_page()\n"
        )
        with patch.object(wealth_ui, "get_api_client", return_value=api):
            app = AppTest.from_string(script).run(timeout=20)
            next(item for item in app.selectbox if item.label == "Type").select(
                "Expense"
            ).run(timeout=20)
            next(item for item in app.text_input if item.label == "Category").input(
                "Food"
            ).run(timeout=20)
            next(item for item in app.button if item.label == "Next").click().run(
                timeout=20
            )

        self.assertEqual(api.filters[-1][0], "wealth")
        self.assertEqual(api.filters[-1][1]["transaction_type"], "Expense")
        self.assertEqual(api.filters[-1][1]["category"], "Food")
        self.assertTrue(any("Page 2 of 2" in item.value for item in app.markdown))

    def test_updates_and_deletes_only_after_explicit_actions(self):
        api = FakeWealthApi(records=[wealth_record(1)])
        script = (
            "from life_copilot.ui.wealth import run_wealth_page\n"
            "run_wealth_page()\n"
        )
        with patch.object(wealth_ui, "get_api_client", return_value=api):
            app = AppTest.from_string(script).run(timeout=20)
            next(
                item for item in app.button if item.label == "Edit transaction"
            ).click().run(timeout=20)
            app.number_input[0].set_value(125.0).run(timeout=20)
            next(
                item for item in app.button if item.label == "Save changes"
            ).click().run(timeout=20)

        self.assertEqual(api.patches[0][0:2], ("wealth", 1))
        self.assertEqual(api.patches[0][2]["amount"], 125.0)

        api = FakeWealthApi(records=[wealth_record(1)])
        with patch.object(wealth_ui, "get_api_client", return_value=api):
            app = AppTest.from_string(script).run(timeout=20)
            next(
                item for item in app.button if item.label == "Delete transaction"
            ).click().run(timeout=20)
            self.assertEqual(api.deletions, [])
            next(
                item for item in app.button if item.label == "Delete permanently"
            ).click().run(timeout=20)

        self.assertEqual(api.deletions, [("wealth", 1)])

    def test_empty_and_error_states_are_safe(self):
        empty_app = self._run(FakeWealthApi(records=[]))
        self.assertTrue(
            any("No wealth records" in item.value for item in empty_app.info)
        )

        error_app = self._run(
            FakeWealthApi(error=ApiClientError("The API is unavailable."))
        )
        self.assertEqual([str(item.value) for item in error_app.exception], [])
        self.assertTrue(any("API is unavailable" in item.value for item in error_app.error))

    def test_csv_contains_only_public_wealth_columns(self):
        content = wealth_ui._records_csv([wealth_record(1)])

        self.assertIn("id,entry_date,transaction_type,amount", content)
        self.assertIn("Record 1", content)
        self.assertNotIn("created_at", content)


if __name__ == "__main__":
    unittest.main()
