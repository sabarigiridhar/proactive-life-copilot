"""Learning history, semantic search, and record maintenance page."""

from __future__ import annotations

from datetime import date, timedelta
from math import ceil
from typing import Any
from urllib.parse import urlparse

import streamlit as st

from life_copilot.ui.api_client import (
    ApiClientError,
    LearningSearchResult,
    get_api_client,
)


LEARNING_COLOR = "#5b8def"
TOPIC_COLOR = "#9b5de5"
FILTER_KEYS = (
    "learning_history_search",
    "learning_period",
    "learning_topic",
    "learning_start_date",
    "learning_end_date",
)


def _clean(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _record_date(record: dict) -> date:
    value = record["entry_date"]
    return value if isinstance(value, date) else date.fromisoformat(value)


def _clear_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state.learning_page = 1
    st.session_state.learning_action = None
    st.session_state.pop("learning_search_result", None)


def _render_filters() -> dict[str, Any]:
    with st.expander("History filters", expanded=True, icon=":material/filter_alt:"):
        search_column, topic_column = st.columns(2, gap="medium")
        with search_column:
            search = st.text_input(
                "Search history",
                key="learning_history_search",
                type="search",
                icon=":material/search:",
                placeholder="Topic, summary, or source URL",
            )
        with topic_column:
            topic = st.text_input(
                "Topic",
                key="learning_topic",
                placeholder="Exact topic or all topics",
            )

        period_column, clear_column = st.columns(
            [1, 0.28], gap="medium", vertical_alignment="bottom"
        )
        with period_column:
            period = st.selectbox(
                "Date range",
                ["All time", "Last 7 days", "Last 30 days", "Last 90 days", "Custom"],
                key="learning_period",
            )
        with clear_column:
            st.button(
                "Clear",
                icon=":material/filter_alt_off:",
                key="clear_learning_filters",
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
                    key="learning_start_date",
                    format="DD/MM/YYYY",
                )
            stored_end = st.session_state.get("learning_end_date", today)
            if stored_end < start_date:
                st.session_state.learning_end_date = start_date
            with end_column:
                end_date = st.date_input(
                    "To",
                    value=today,
                    min_value=start_date,
                    max_value=today,
                    key="learning_end_date",
                    format="DD/MM/YYYY",
                )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "search": _clean(search),
        "topic": _clean(topic),
    }


def _filter_signature(filters: dict[str, Any]) -> tuple:
    return tuple(
        (key, value.isoformat() if isinstance(value, date) else value)
        for key, value in sorted(filters.items())
    )


def _period_caption(records: list[dict], filters: dict[str, Any]) -> str:
    if filters["start_date"] and filters["end_date"]:
        start = filters["start_date"]
        end = filters["end_date"]
    elif records:
        dates = [_record_date(record) for record in records]
        start, end = min(dates), max(dates)
    else:
        return "No matching dates"
    return f"{start.strftime('%d %b %Y')} - {end.strftime('%d %b %Y')}"


def _streaks(records: list[dict], end_date: date) -> tuple[int, int]:
    days = sorted({_record_date(record) for record in records})
    longest = 0
    run = 0
    previous = None
    for current_day in days:
        run = run + 1 if previous == current_day - timedelta(days=1) else 1
        longest = max(longest, run)
        previous = current_day

    current = 0
    expected = end_date
    for current_day in reversed(days):
        if current_day != expected:
            break
        current += 1
        expected -= timedelta(days=1)
    return current, longest


def _render_overview(records: list[dict], filters: dict[str, Any]) -> None:
    total_minutes = sum(int(record.get("duration_minutes") or 0) for record in records)
    active_days = len({_record_date(record) for record in records})
    streak_end = filters["end_date"] or date.today()
    current_streak, longest_streak = _streaks(records, streak_end)

    minutes_column, sessions_column, current_column, longest_column = st.columns(
        4, gap="medium"
    )
    with minutes_column:
        st.metric("Learning minutes", f"{total_minutes:,}", border=True)
    with sessions_column:
        st.metric("Sessions", f"{len(records):,}", delta=f"{active_days} active days", border=True)
    with current_column:
        st.metric("Current streak", f"{current_streak} days", border=True)
    with longest_column:
        st.metric("Longest streak", f"{longest_streak} days", border=True)

    period = _period_caption(records, filters)
    daily: dict[date, dict[str, int]] = {}
    topics: dict[str, dict[str, Any]] = {}
    for record in records:
        entry_date = _record_date(record)
        minutes = int(record.get("duration_minutes") or 0)
        daily_summary = daily.setdefault(entry_date, {"Minutes": 0, "Sessions": 0})
        daily_summary["Minutes"] += minutes
        daily_summary["Sessions"] += 1

        topic = str(record["topic"])
        topic_key = topic.casefold()
        topic_summary = topics.setdefault(
            topic_key, {"label": topic, "minutes": 0, "sessions": 0}
        )
        topic_summary["minutes"] += minutes
        topic_summary["sessions"] += 1

    trend_column, topic_column = st.columns(2, gap="large")
    with trend_column:
        st.subheader("Learning activity")
        st.caption(period)
        if daily:
            st.bar_chart(
                [
                    {"Date": day, **values}
                    for day, values in sorted(daily.items())
                ],
                x="Date",
                y="Minutes",
                y_label="Minutes",
                color=LEARNING_COLOR,
                height=280,
            )
        else:
            st.info("No learning activity matches these filters.")

    with topic_column:
        st.subheader("Topic distribution")
        st.caption(period)
        if topics:
            use_minutes = any(item["minutes"] for item in topics.values())
            value_key = "minutes" if use_minutes else "sessions"
            label = "Minutes" if use_minutes else "Sessions"
            topic_rows = [
                {"Topic": item["label"], label: item[value_key]}
                for item in sorted(
                    topics.values(),
                    key=lambda item: (item[value_key], item["sessions"]),
                    reverse=True,
                )[:10]
            ]
            st.bar_chart(
                topic_rows,
                x="Topic",
                y=label,
                y_label=label,
                color=TOPIC_COLOR,
                horizontal=True,
                height=280,
            )
        else:
            st.info("No topics match these filters.")


def _safe_source_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _render_search_results(result: LearningSearchResult) -> None:
    if result.warning:
        st.warning(result.warning)
    if not result.hits:
        st.info("No learning notes matched this search.")
        return

    st.caption(
        f"{len(result.hits)} verified result(s) · "
        f"{'Semantic index' if result.mode == 'vector' else 'Keyword fallback'}"
    )
    for hit in result.hits:
        with st.container(border=True):
            duration = (
                f" · {hit.duration_minutes} minutes"
                if hit.duration_minutes is not None
                else ""
            )
            st.markdown(f"**{hit.topic}** · {hit.entry_date.strftime('%d %b %Y')}{duration}")
            st.write(hit.summary_text)
            safe_url = _safe_source_url(hit.url_reference)
            if safe_url:
                st.link_button(
                    "Open source",
                    safe_url,
                    icon=":material/open_in_new:",
                )
            elif hit.url_reference:
                st.caption(f"Source reference: {hit.url_reference}")


def _render_semantic_search(api, filters: dict[str, Any]) -> None:
    st.subheader("Search your notes")
    st.caption("Semantic search finds related ideas, even when the wording differs.")
    query_column, button_column = st.columns(
        [1, 0.22], gap="medium", vertical_alignment="bottom"
    )
    with query_column:
        query = st.text_input(
            "Semantic search",
            key="learning_semantic_query",
            type="search",
            icon=":material/manage_search:",
            placeholder="What did I learn about retrieval quality?",
        )
    with button_column:
        search = st.button(
            "Search notes",
            icon=":material/search:",
            type="primary",
            disabled=not query.strip(),
            use_container_width=True,
        )

    if search:
        try:
            with st.spinner("Searching learning notes..."):
                result = api.search_learning(
                    query.strip(),
                    topic=filters["topic"],
                    start_date=filters["start_date"],
                    end_date=filters["end_date"],
                    limit=10,
                )
        except ApiClientError as exc:
            st.error(f"Learning notes could not be searched: {exc}")
        else:
            st.session_state.learning_search_result = result.model_dump(mode="json")

    stored = st.session_state.get("learning_search_result")
    if stored:
        _render_search_results(LearningSearchResult.model_validate(stored))


def _render_edit_form(api, record: dict) -> None:
    with st.container(border=True):
        st.subheader(f"Edit learning session #{record['id']}")
        with st.form(f"learning_edit_{record['id']}"):
            date_column, topic_column, duration_column = st.columns(3, gap="medium")
            with date_column:
                entry_date = st.date_input(
                    "Entry date",
                    value=_record_date(record),
                    format="DD/MM/YYYY",
                )
            with topic_column:
                topic = st.text_input("Topic", value=record["topic"])
            with duration_column:
                duration = st.number_input(
                    "Duration (minutes)",
                    min_value=0,
                    max_value=1440,
                    value=int(record.get("duration_minutes") or 0),
                    help="Use 0 when no duration was recorded.",
                )
            source_url = st.text_input(
                "Source URL",
                value=record.get("url_reference") or "",
                placeholder="https://example.com/article",
            )
            summary = st.text_area(
                "Summary",
                value=record.get("summary_text") or "",
                height=140,
            )
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
            st.session_state.learning_action = None
            st.rerun()
        if not save:
            return
        if not topic.strip() or not summary.strip():
            st.error("Topic and summary are required.")
            return
        try:
            with st.spinner("Updating learning session..."):
                result = api.patch_record(
                    "learning",
                    record["id"],
                    {
                        "entry_date": entry_date.isoformat(),
                        "topic": topic.strip(),
                        "summary_text": summary.strip(),
                        "duration_minutes": duration,
                        "url_reference": _clean(source_url),
                    },
                )
        except ApiClientError as exc:
            st.error(f"The learning session could not be updated: {exc}")
            return
        st.session_state.learning_flash = ("success", "Learning session updated.")
        if result.warnings:
            st.session_state.learning_flash = ("warning", result.warnings[0])
        st.session_state.learning_action = None
        st.session_state.pop("learning_search_result", None)
        st.rerun()


def _render_delete_confirmation(api, record: dict) -> None:
    with st.container(border=True):
        st.warning(
            f"Delete learning session #{record['id']} permanently? This cannot be undone."
        )
        delete_column, cancel_column = st.columns(2, gap="medium")
        with delete_column:
            confirm = st.button(
                "Delete permanently",
                icon=":material/delete_forever:",
                type="primary",
                use_container_width=True,
                key=f"confirm_learning_delete_{record['id']}",
            )
        with cancel_column:
            cancel = st.button(
                "Keep learning session",
                icon=":material/close:",
                use_container_width=True,
                key=f"cancel_learning_delete_{record['id']}",
            )
        if cancel:
            st.session_state.learning_action = None
            st.rerun()
        if not confirm:
            return
        try:
            with st.spinner("Deleting learning session..."):
                result = api.delete_record("learning", record["id"])
        except ApiClientError as exc:
            st.error(f"The learning session could not be deleted: {exc}")
            return
        st.session_state.learning_flash = ("success", "Learning session deleted.")
        if result.warnings:
            st.session_state.learning_flash = ("warning", result.warnings[0])
        st.session_state.learning_action = None
        st.session_state.pop("learning_search_result", None)
        st.rerun()


def _render_sessions(api, records: list[dict]) -> None:
    st.subheader("Learning sessions")
    if not records:
        st.info("No learning sessions match the current filters.")
        return

    page_size = st.selectbox(
        "Rows per page",
        [10, 25, 50],
        key="learning_page_size",
        width=180,
    )
    total_pages = max(1, ceil(len(records) / page_size))
    page_number = min(st.session_state.get("learning_page", 1), total_pages)
    st.session_state.learning_page = page_number
    start = (page_number - 1) * page_size
    page_records = records[start : start + page_size]

    st.dataframe(
        page_records,
        hide_index=True,
        column_order=[
            "entry_date",
            "topic",
            "duration_minutes",
            "summary_text",
            "url_reference",
            "source",
        ],
        column_config={
            "entry_date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "topic": st.column_config.TextColumn("Topic"),
            "duration_minutes": st.column_config.NumberColumn("Minutes", format="%d"),
            "summary_text": st.column_config.TextColumn("Summary", width="large"),
            "url_reference": st.column_config.LinkColumn("Source", display_text="Open"),
            "source": st.column_config.TextColumn("Captured via"),
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
            key="previous_learning_page",
        )
    with page_column:
        st.markdown(
            f"<div class='page-count'>Page {page_number} of {total_pages} "
            f"&middot; {len(records):,} sessions</div>",
            unsafe_allow_html=True,
        )
    with next_column:
        following = st.button(
            "Next",
            icon=":material/chevron_right:",
            disabled=page_number >= total_pages,
            use_container_width=True,
            key="next_learning_page",
        )
    if previous:
        st.session_state.learning_page = page_number - 1
        st.session_state.learning_action = None
        st.rerun()
    if following:
        st.session_state.learning_page = page_number + 1
        st.session_state.learning_action = None
        st.rerun()

    record_by_id = {record["id"]: record for record in page_records}
    selection_key = f"learning_selected_{page_number}_{page_size}"
    if st.session_state.get(selection_key) not in record_by_id:
        st.session_state[selection_key] = next(iter(record_by_id))
    selected_id = st.selectbox(
        "Learning session",
        list(record_by_id),
        format_func=lambda record_id: (
            f"#{record_id} | {record_by_id[record_id]['entry_date']} | "
            f"{record_by_id[record_id]['topic']}"
        ),
        key=selection_key,
    )
    edit_column, delete_column = st.columns(2, gap="medium")
    with edit_column:
        edit = st.button(
            "Edit learning session",
            icon=":material/edit:",
            use_container_width=True,
        )
    with delete_column:
        delete = st.button(
            "Delete learning session",
            icon=":material/delete:",
            use_container_width=True,
        )
    if edit:
        st.session_state.learning_action = ("edit", selected_id)
    elif delete:
        st.session_state.learning_action = ("delete", selected_id)

    action = st.session_state.get("learning_action")
    if not action:
        return
    action_name, record_id = action
    record = next((item for item in records if item["id"] == record_id), None)
    if record is None:
        st.session_state.learning_action = None
        st.warning("That learning session is no longer available.")
        return
    if action_name == "edit":
        _render_edit_form(api, record)
    else:
        _render_delete_confirmation(api, record)


def run_learning_page() -> None:
    """Render filtered learning analytics, search, and maintenance."""
    st.title("Learning")
    st.caption(date.today().strftime("%A, %d %B %Y"))
    api = get_api_client()

    flash = st.session_state.pop("learning_flash", None)
    if flash:
        level, message = flash
        getattr(st, level)(message)

    filters = _render_filters()
    signature = _filter_signature(filters)
    if st.session_state.get("learning_filter_signature") != signature:
        st.session_state.learning_filter_signature = signature
        st.session_state.learning_page = 1
        st.session_state.learning_action = None
        st.session_state.pop("learning_search_result", None)

    try:
        with st.spinner("Loading learning history..."):
            records = api.list_all_records("learning", **filters)
    except ApiClientError as exc:
        st.error(f"Learning records could not be loaded: {exc}")
        return

    _render_overview(records, filters)
    st.divider()
    _render_semantic_search(api, filters)
    st.divider()
    _render_sessions(api, records)
