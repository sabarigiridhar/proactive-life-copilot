"""Professional home-dashboard panels backed by the public API contract."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from life_copilot.ui.api_client import DashboardResult


WEALTH_COLOR = "#ef6351"
CATEGORY_COLOR = "#e9c46a"


def _period_label(dashboard: DashboardResult) -> str:
    start = dashboard.date_range.start_date.strftime("%d %b")
    end = dashboard.date_range.end_date.strftime("%d %b %Y")
    return f"{start} - {end}"


def _money(currency: str, value: float) -> str:
    decimals = 0 if float(value).is_integer() else 2
    return f"{currency} {value:,.{decimals}f}"


def _selected_currency(dashboard: DashboardResult) -> str | None:
    currencies = sorted(
        {
            item.currency
            for item in [
                *dashboard.wealth.income,
                *dashboard.wealth.expenses,
                *dashboard.wealth.net,
            ]
        }
    )
    if not currencies:
        return None
    if len(currencies) == 1:
        return currencies[0]
    return st.selectbox(
        "Currency",
        currencies,
        key="home_wealth_currency",
        label_visibility="collapsed",
    )


def render_wealth_panel(dashboard: DashboardResult) -> None:
    """Render seven-day spending totals, trend, and category distribution."""
    st.subheader("Wealth")
    st.caption(_period_label(dashboard))
    currency = _selected_currency(dashboard)
    if currency is None:
        st.info("No wealth activity in this period.", icon=":material/wallet:")
        return

    expense = next(
        (item for item in dashboard.wealth.expenses if item.currency == currency),
        None,
    )
    net = next(
        (item for item in dashboard.wealth.net if item.currency == currency),
        None,
    )
    daily = [
        item for item in dashboard.wealth.daily if item.currency == currency
    ]
    daily_values = [item.expense for item in daily]
    st.metric(
        "Spent",
        _money(currency, expense.total if expense else 0),
        delta=(f"Net {_money(currency, net.net)}" if net else None),
        delta_color="normal" if net and net.net >= 0 else "inverse",
        icon=":material/payments:",
        chart_data=daily_values or None,
        chart_type="area",
        border=True,
    )

    st.markdown("##### Spending trend")
    if daily:
        st.line_chart(
            [
                {"Date": item.entry_date, "Spent": item.expense}
                for item in daily
            ],
            x="Date",
            y="Spent",
            x_label=None,
            y_label=currency,
            color=WEALTH_COLOR,
            height=180,
        )
    else:
        st.info("No daily spending points for this currency.")

    st.markdown("##### Categories")
    categories = [
        item for item in dashboard.wealth.categories if item.currency == currency
    ][:5]
    if categories:
        st.bar_chart(
            [
                {"Category": item.category, "Amount": item.total}
                for item in categories
            ],
            x="Category",
            y="Amount",
            x_label=None,
            y_label=currency,
            color=CATEGORY_COLOR,
            horizontal=True,
            height=190,
        )
    else:
        st.info("No expense categories in this period.")


def _completion_badges(dashboard: DashboardResult) -> None:
    status = dashboard.daily_status
    items = (
        ("Health", status.health_complete),
        ("Wealth", status.wealth_reviewed),
        ("Learning", status.learning_complete),
    )
    with st.container(horizontal=True, gap="small"):
        for label, complete in items:
            st.badge(
                label,
                icon=":material/check:" if complete else ":material/schedule:",
                color="green" if complete else "gray",
            )


def render_life_panel(dashboard: DashboardResult) -> None:
    """Render completion, health, and learning summaries for the home screen."""
    period = _period_label(dashboard)
    status = dashboard.daily_status
    completed = sum(
        (status.health_complete, status.wealth_reviewed, status.learning_complete)
    )

    st.subheader("Today")
    st.caption(status.entry_date.strftime("%A, %d %B"))
    st.metric(
        "Daily check-in",
        f"{completed}/3",
        icon=":material/task_alt:",
        border=True,
    )
    st.progress(completed / 3, text="Daily completion")
    _completion_badges(dashboard)

    st.divider()
    st.subheader("Health")
    st.caption(period)
    health = dashboard.health
    sleep_values = [
        item.sleep_hours
        for item in health.daily
        if item.sleep_hours is not None
    ]
    health_left, health_right = st.columns(2, gap="small")
    with health_left:
        st.metric(
            "Avg sleep",
            (
                f"{health.average_sleep_hours:.1f} h"
                if health.average_sleep_hours is not None
                else "Not logged"
            ),
            icon=":material/bedtime:",
            chart_data=sleep_values or None,
            border=True,
        )
    with health_right:
        st.metric(
            "Workout days",
            health.workout_days,
            icon=":material/fitness_center:",
            border=True,
        )
    if not health.daily:
        st.info("No health entries in this period.", icon=":material/vital_signs:")
    elif health.average_calories is None:
        st.caption("Calories have not been logged for this period.")
    else:
        st.caption(f"Average calories: {health.average_calories:,.0f} per logged day")

    st.divider()
    st.subheader("Learning")
    st.caption(period)
    learning = dashboard.learning
    learning_values = [item.minutes for item in learning.daily]
    st.metric(
        "Focused time",
        f"{learning.total_minutes:,} min",
        delta=f"{learning.sessions} sessions",
        delta_color="off",
        icon=":material/menu_book:",
        chart_data=learning_values or None,
        chart_type="bar",
        border=True,
    )
    streak_col, days_col = st.columns(2, gap="small")
    with streak_col:
        st.metric("Current streak", f"{learning.current_streak_days} d")
    with days_col:
        st.metric("Active days", learning.learning_days)
    if not learning.daily:
        st.info("No learning sessions in this period.", icon=":material/school:")
    elif learning.topics:
        top_topic = learning.topics[0]
        st.caption(
            f"Top topic: {top_topic.topic} ({top_topic.minutes:,} min)"
        )


def dashboard_period(today: date) -> tuple[date, date]:
    """Return the inclusive seven-day home-dashboard period."""
    return today - timedelta(days=6), today
