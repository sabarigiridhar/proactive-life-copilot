"""Streamlit entry point and application navigation for Life Copilot."""

import streamlit as st

from life_copilot.ui.main import run_app, run_records_page
from life_copilot.ui.learning import run_learning_page
from life_copilot.ui.settings import run_settings_page
from life_copilot.ui.theme import apply_app_styles
from life_copilot.ui.wealth import run_wealth_page
from life_copilot.ui.weekly_review import run_weekly_review_page


st.set_page_config(
    page_title="Life Copilot",
    page_icon=":material/track_changes:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_app_styles()

navigation = st.navigation(
    [
        st.Page(
            run_app,
            title="Home",
            icon=":material/home:",
            default=True,
        ),
        st.Page(
            run_wealth_page,
            title="Wealth",
            icon=":material/account_balance_wallet:",
            url_path="wealth",
        ),
        st.Page(
            run_learning_page,
            title="Learning",
            icon=":material/school:",
            url_path="learning",
        ),
        st.Page(
            run_weekly_review_page,
            title="Weekly Review",
            icon=":material/auto_awesome:",
            url_path="weekly-review",
        ),
        st.Page(
            run_settings_page,
            title="Settings",
            icon=":material/settings:",
            url_path="settings",
        ),
        st.Page(
            run_records_page,
            title="Records",
            icon=":material/table_view:",
            url_path="records",
        ),
    ],
    position="top",
)
navigation.run()
