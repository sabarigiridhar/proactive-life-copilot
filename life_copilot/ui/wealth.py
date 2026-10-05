"""Wealth inspection and maintenance page using public REST contracts."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from math import ceil
from typing import Any

import streamlit as st

from life_copilot.ui.api_client import ApiClientError, get_api_client


INCOME_COLOR = "#2a9d8f"
EXPENSE_COLOR = "#ef6351"
CATEGORY_COLOR = "#e9c46a"
FILTER_KEYS = (
    "wealth_search",
    "wealth_period",
    "wealth_type",
    "wealth_currency",
    "wealth_category",
    "wealth_merchant",
    "wealth_start_date",
    "wealth_end_date",
)


def _clean(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _clear_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state.wealth_page = 1
    st.session_state.wealth_action = None


def _render_filters() -> dict[str, Any]:
    with st.expander("Filters", expanded=True, icon=":material/filter_alt:"):
        search = st.text_input(
            "Search transactions",
            key="wealth_search",
            type="search",
            icon=":material/search:",
            placeholder="Category, merchant, or notes",
        )
        period_column, type_column, currency_column = st.columns(
            [1.2, 1, 1], gap="medium"
        )
        with period_column:
            period = st.selectbox(
                "Date range",
                ["All time", "Last 7 days", "Last 30 days", "Last 90 days", "Custom"],
                key="wealth_period",
            )
        with type_column:
            transaction_type = st.selectbox(
                "Type",
                ["All", "Expense", "Income"],
                key="wealth_type",
            )
        with currency_column:
            currency = st.text_input(
                "Currency",
                key="wealth_currency",
                placeholder="All currencies",
            )

        category_column, merchant_column, clear_column = st.columns(
            [1, 1, 0.55], gap="medium", vertical_alignment="bottom"
        )
        with category_column:
            category = st.text_input(
                "Category",
                key="wealth_category",
                placeholder="All categories",
            )
        with merchant_column:
            merchant = st.text_input(
                "Merchant",
                key="wealth_merchant",
                placeholder="All merchants",
            )
        with clear_column:
            st.button(
                "Clear",
                icon=":material/filter_alt_off:",
                key="clear_wealth_filters",
                on_click=_clear_filters,
                use_container_width=True,
            )

        today = date.today()
        start_date = None
        end_date = None
        if period == "Last 7 days":
            start_date, end_date = today - timedelta(days=6), today
        elif period == "Last 30 days":
            start_date, end_date = today - timedelta(days=29), today
        elif period == "Last 90 days":
            start_date, end_date = today - timedelta(days=89), today
        elif period == "Custom":
            start_column, end_column = st.columns(2, gap="medium")
            with start_column:
                start_date = st.date_input(
                    "From",
                    value=today - timedelta(days=29),
                    max_value=today,
                    key="wealth_start_date",
                    format="DD/MM/YYYY",
                )
            stored_end = st.session_state.get("wealth_end_date", today)
            if stored_end < start_date:
                st.session_state.wealth_end_date = start_date
            with end_column:
                end_date = st.date_input(
                    "To",
                    value=today,
                    min_value=start_date,
                    max_value=today,
                    key="wealth_end_date",
                    format="DD/MM/YYYY",
                )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "search": _clean(search),
        "transaction_type": (
            transaction_type if transaction_type != "All" else None
        ),
        "currency": _clean(currency),
        "category": _clean(category),
        "merchant": _clean(merchant),
    }


def _filter_signature(filters: dict[str, Any]) -> tuple:
    return tuple(
        (key, value.isoformat() if isinstance(value, date) else value)
        for key, value in sorted(filters.items())
    )


def _currency_options(records: list[dict]) -> list[str]:
    return sorted({str(record["currency"]).upper() for record in records})


def _format_money(currency: str, amount: float) -> str:
    decimals = 0 if float(amount).is_integer() else 2
    return f"{currency} {amount:,.{decimals}f}"


def _record_date(record: dict) -> date:
    value = record["entry_date"]
    return value if isinstance(value, date) else date.fromisoformat(value)


def _period_caption(records: list[dict], filters: dict[str, Any]) -> str:
    if filters["start_date"] and filters["end_date"]:
        start = filters["start_date"]
        end = filters["end_date"]
    else:
        dates = [_record_date(record) for record in records]
        start, end = min(dates), max(dates)
    return f"{start.strftime('%d %b %Y')} - {end.strftime('%d %b %Y')}"


def _render_summary_and_charts(records: list[dict], filters: dict[str, Any]) -> None:
    currencies = _currency_options(records)
    if st.session_state.get("wealth_summary_currency") not in currencies:
        st.session_state.wealth_summary_currency = currencies[0]
    selected_currency = st.selectbox(
        "Summary currency",
        currencies,
        key="wealth_summary_currency",
    )
    currency_records = [
        record
        for record in records
        if str(record["currency"]).upper() == selected_currency
    ]
    income = sum(
        float(record["amount"])
        for record in currency_records
        if str(record["transaction_type"]).casefold() == "income"
    )
    expense = sum(
        float(record["amount"])
        for record in currency_records
        if str(record["transaction_type"]).casefold() == "expense"
    )
    net = income - expense

    income_column, expense_column, net_column = st.columns(3, gap="medium")
    with income_column:
        st.metric(
            "Income",
            _format_money(selected_currency, income),
            icon=":material/trending_up:",
            border=True,
        )
    with expense_column:
        st.metric(
            "Expenses",
            _format_money(selected_currency, expense),
            icon=":material/trending_down:",
            border=True,
        )
    with net_column:
        st.metric(
            "Net",
            _format_money(selected_currency, net),
            delta="Positive" if net >= 0 else "Negative",
            delta_color="normal" if net >= 0 else "inverse",
            icon=":material/account_balance_wallet:",
            border=True,
        )

    period = _period_caption(currency_records, filters)
    daily: dict[date, dict[str, float]] = {}
    categories: dict[str, dict[str, Any]] = {}
    for record in currency_records:
        entry_date = _record_date(record)
        values = daily.setdefault(entry_date, {"Income": 0.0, "Expense": 0.0})
        transaction_type = str(record["transaction_type"]).title()
        values[transaction_type] += float(record["amount"])
        if transaction_type == "Expense":
            category = str(record.get("category") or "Uncategorized")
            category_key = category.casefold()
            category_summary = categories.setdefault(
                category_key,
                {"label": category.title(), "amount": 0.0},
            )
            category_summary["amount"] += float(record["amount"])

    trend_column, category_column = st.columns(2, gap="large")
    with trend_column:
        st.subheader("Cash flow")
        st.caption(period)
        trend_rows = [
            {"Date": day, **values}
            for day, values in sorted(daily.items())
        ]
        st.line_chart(
            trend_rows,
            x="Date",
            y=["Income", "Expense"],
            y_label=selected_currency,
            color=[INCOME_COLOR, EXPENSE_COLOR],
            height=280,
        )
    with category_column:
        st.subheader("Expense categories")
        st.caption(period)
        category_rows = [
            {"Category": summary["label"], "Amount": summary["amount"]}
            for summary in sorted(
                categories.values(),
                key=lambda item: item["amount"],
                reverse=True,
            )[:8]
        ]
        if category_rows:
            st.bar_chart(
                category_rows,
                x="Category",
                y="Amount",
                x_label=None,
                y_label=selected_currency,
                color=CATEGORY_COLOR,
                horizontal=True,
                height=280,
            )
        else:
            st.info("No expenses match these filters.")

    if len(currencies) > 1:
        st.caption(
            f"Summary shows {selected_currency}; the transaction table includes "
            f"{len(currencies)} currencies."
        )


def _records_csv(records: list[dict]) -> str:
    fields = [
        "id",
        "entry_date",
        "transaction_type",
        "amount",
        "currency",
        "category",
        "merchant",
        "notes",
        "source",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue()


def _render_edit_form(api, record: dict) -> None:
    with st.container(border=True):
        st.subheader(f"Edit transaction #{record['id']}")
        with st.form(f"wealth_edit_{record['id']}"):
            date_column, type_column, amount_column = st.columns(3, gap="medium")
            with date_column:
                entry_date = st.date_input(
                    "Entry date",
                    value=_record_date(record),
                    format="DD/MM/YYYY",
                )
            with type_column:
                transaction_type = st.selectbox(
                    "Type",
                    ["Expense", "Income"],
                    index=(
                        0
                        if str(record["transaction_type"]).casefold() == "expense"
                        else 1
                    ),
                )
            with amount_column:
                amount = st.number_input(
                    "Amount",
                    value=float(record["amount"]),
                    step=0.01,
                    format="%.2f",
                )
            currency_column, category_column, merchant_column = st.columns(
                3, gap="medium"
            )
            with currency_column:
                currency = st.text_input("Currency", value=record["currency"])
            with category_column:
                category = st.text_input("Category", value=record["category"])
            with merchant_column:
                merchant = st.text_input(
                    "Merchant", value=record.get("merchant") or ""
                )
            notes = st.text_area("Notes", value=record.get("notes") or "")
            save_column, cancel_column = st.columns(2, gap="medium")
            with save_column:
                save = st.form_submit_button(
                    "Save changes",
                    icon=":material/save:",
                    type="primary",
                    use_container_width=True,
                )
            with cancel_column:
                cancel = st.form_submit_button(
                    "Cancel",
                    icon=":material/close:",
                    use_container_width=True,
                )

        if cancel:
            st.session_state.wealth_action = None
            st.rerun()
        if not save:
            return
        if amount <= 0 or not currency.strip() or not category.strip():
            st.error("Amount, currency, and category must contain valid values.")
            return
        try:
            with st.spinner("Updating transaction..."):
                api.patch_record(
                    "wealth",
                    record["id"],
                    {
                        "entry_date": entry_date.isoformat(),
                        "transaction_type": transaction_type,
                        "amount": amount,
                        "currency": currency.strip(),
                        "category": category.strip(),
                        "merchant": _clean(merchant),
                        "notes": _clean(notes),
                    },
                )
        except ApiClientError as exc:
            st.error(f"The transaction could not be updated: {exc}")
            return
        st.session_state.wealth_flash = ("success", "Transaction updated.")
        st.session_state.wealth_action = None
        st.rerun()


def _render_delete_confirmation(api, record: dict) -> None:
    with st.container(border=True):
        st.warning(
            f"Delete transaction #{record['id']} permanently? This cannot be undone."
        )
        delete_column, cancel_column = st.columns(2, gap="medium")
        with delete_column:
            confirm = st.button(
                "Delete permanently",
                icon=":material/delete_forever:",
                type="primary",
                use_container_width=True,
                key=f"confirm_wealth_delete_{record['id']}",
            )
        with cancel_column:
            cancel = st.button(
                "Keep transaction",
                icon=":material/close:",
                use_container_width=True,
                key=f"cancel_wealth_delete_{record['id']}",
            )
        if cancel:
            st.session_state.wealth_action = None
            st.rerun()
        if not confirm:
            return
        try:
            with st.spinner("Deleting transaction..."):
                api.delete_record("wealth", record["id"])
        except ApiClientError as exc:
            st.error(f"The transaction could not be deleted: {exc}")
            return
        st.session_state.wealth_flash = ("success", "Transaction deleted.")
        st.session_state.wealth_action = None
        st.rerun()


def _render_transactions(api, records: list[dict]) -> None:
    st.subheader("Transactions")
    table_header, export_column = st.columns(
        [1, 0.28], gap="medium", vertical_alignment="bottom"
    )
    with table_header:
        page_size = st.selectbox(
            "Rows per page",
            [10, 25, 50],
            key="wealth_page_size",
            width=180,
        )
    with export_column:
        st.download_button(
            "Download CSV",
            data=_records_csv(records),
            file_name=f"wealth-records-{date.today().isoformat()}.csv",
            mime="text/csv",
            icon=":material/download:",
            on_click="ignore",
            use_container_width=True,
        )

    total_pages = max(1, ceil(len(records) / page_size))
    page_number = min(st.session_state.get("wealth_page", 1), total_pages)
    st.session_state.wealth_page = page_number
    start = (page_number - 1) * page_size
    page_records = records[start : start + page_size]

    st.dataframe(
        page_records,
        hide_index=True,
        column_order=[
            "entry_date",
            "transaction_type",
            "amount",
            "currency",
            "category",
            "merchant",
            "notes",
        ],
        column_config={
            "entry_date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "transaction_type": st.column_config.TextColumn("Type"),
            "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
            "currency": st.column_config.TextColumn("Currency"),
            "category": st.column_config.TextColumn("Category"),
            "merchant": st.column_config.TextColumn("Merchant"),
            "notes": st.column_config.TextColumn("Notes", width="large"),
        },
        width="stretch",
        height=min(520, 82 + (len(page_records) * 36)),
    )

    previous_column, page_column, next_column = st.columns(
        [0.25, 0.5, 0.25], gap="medium", vertical_alignment="center"
    )
    with previous_column:
        previous = st.button(
            "Previous",
            icon=":material/chevron_left:",
            disabled=page_number <= 1,
            use_container_width=True,
        )
    with page_column:
        st.markdown(
            f"<div class='page-count'>Page {page_number} of {total_pages} "
            f"&middot; {len(records):,} transactions</div>",
            unsafe_allow_html=True,
        )
    with next_column:
        following = st.button(
            "Next",
            icon=":material/chevron_right:",
            disabled=page_number >= total_pages,
            use_container_width=True,
        )
    if previous:
        st.session_state.wealth_page = page_number - 1
        st.session_state.wealth_action = None
        st.rerun()
    if following:
        st.session_state.wealth_page = page_number + 1
        st.session_state.wealth_action = None
        st.rerun()

    record_by_id = {record["id"]: record for record in page_records}
    selection_key = f"wealth_selected_{page_number}_{page_size}"
    if st.session_state.get(selection_key) not in record_by_id:
        st.session_state[selection_key] = next(iter(record_by_id))
    selected_id = st.selectbox(
        "Transaction",
        list(record_by_id),
        format_func=lambda record_id: (
            f"#{record_id} | {record_by_id[record_id]['entry_date']} | "
            f"{record_by_id[record_id]['transaction_type']} "
            f"{record_by_id[record_id]['currency']} "
            f"{record_by_id[record_id]['amount']:.2f}"
        ),
        key=selection_key,
    )
    edit_column, delete_column = st.columns(2, gap="medium")
    with edit_column:
        edit = st.button(
            "Edit transaction",
            icon=":material/edit:",
            use_container_width=True,
        )
    with delete_column:
        delete = st.button(
            "Delete transaction",
            icon=":material/delete:",
            use_container_width=True,
        )
    if edit:
        st.session_state.wealth_action = ("edit", selected_id)
    elif delete:
        st.session_state.wealth_action = ("delete", selected_id)

    action = st.session_state.get("wealth_action")
    if not action:
        return
    action_name, record_id = action
    record = next((item for item in records if item["id"] == record_id), None)
    if record is None:
        st.session_state.wealth_action = None
        st.warning("That transaction is no longer available.")
        return
    if action_name == "edit":
        _render_edit_form(api, record)
    else:
        _render_delete_confirmation(api, record)


def run_wealth_page() -> None:
    """Render filtered wealth analytics and record maintenance."""
    st.title("Wealth")
    st.caption(date.today().strftime("%A, %d %B %Y"))
    api = get_api_client()

    flash = st.session_state.pop("wealth_flash", None)
    if flash:
        level, message = flash
        getattr(st, level)(message)

    filters = _render_filters()
    signature = _filter_signature(filters)
    if st.session_state.get("wealth_filter_signature") != signature:
        st.session_state.wealth_filter_signature = signature
        st.session_state.wealth_page = 1
        st.session_state.wealth_action = None

    try:
        with st.spinner("Loading wealth records..."):
            records = api.list_all_records("wealth", **filters)
    except ApiClientError as exc:
        st.error(f"Wealth records could not be loaded: {exc}")
        return

    if not records:
        st.info(
            "No wealth records match the current filters.",
            icon=":material/account_balance_wallet:",
        )
        return

    _render_summary_and_charts(records, filters)
    st.divider()
    _render_transactions(api, records)
