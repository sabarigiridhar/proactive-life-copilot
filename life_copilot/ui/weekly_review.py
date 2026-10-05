"""Weekly review page with visible supporting evidence."""

from __future__ import annotations

from datetime import date

import streamlit as st

from life_copilot.ui.api_client import ApiClientError, get_api_client


def run_weekly_review_page() -> None:
    """Render saved weekly reviews or the scheduled-insight empty state."""
    st.title("Weekly Review")
    st.caption(date.today().strftime("%A, %d %B %Y"))
    api = get_api_client()

    try:
        with st.spinner("Loading weekly reviews..."):
            result = api.list_weekly_reviews()
    except ApiClientError as exc:
        st.error(f"Weekly reviews could not be loaded: {exc}")
        return

    if not result.reviews:
        st.info(
            result.message or "No weekly reviews have been generated yet.",
            icon=":material/auto_awesome:",
        )
        st.caption(
            "Scheduled review generation is planned for the Proactive Copilot phase. "
            "When available, every review will show the records and metrics behind it."
        )
        return

    st.caption(f"{len(result.reviews)} saved review(s)")
    for review in result.reviews:
        with st.container(border=True):
            st.subheader(review.title)
            st.caption(
                f"{review.period_start.strftime('%d %b %Y')} - "
                f"{review.period_end.strftime('%d %b %Y')} · "
                f"created {review.created_at.strftime('%d %b %Y, %H:%M')}"
            )
            st.write(review.summary)
            with st.expander(
                "Supporting evidence",
                expanded=True,
                icon=":material/fact_check:",
            ):
                if review.evidence:
                    st.dataframe(
                        review.evidence,
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.info("No supporting evidence was stored for this review.")
