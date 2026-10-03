"""Compact rendering for persisted analytics evidence."""

import streamlit as st


def render_message_evidence(metadata: dict | None) -> None:
    """Render analytics trust metadata when it is attached to a chat message."""
    if not metadata or "evidence" not in metadata:
        return
    evidence = metadata.get("evidence") or []
    date_range = metadata.get("date_range") or {}
    confidence = metadata.get("confidence")
    with st.expander("Evidence"):
        details = []
        if date_range.get("start_date") and date_range.get("end_date"):
            details.append(
                f"{date_range['start_date']} to {date_range['end_date']}"
            )
        if confidence is not None:
            details.append(f"Confidence: {float(confidence):.0%}")
        if details:
            st.caption(" | ".join(details))
        if evidence:
            st.dataframe(evidence, hide_index=True, width="stretch")
        else:
            st.caption("No matching records were found.")
