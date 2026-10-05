"""Shared visual treatment for the Streamlit application shell."""

import streamlit as st


def apply_app_styles() -> None:
    st.markdown(
        """
        <style>
        .stAppViewContainer .main .block-container {
            max-width: 1600px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3, h4, h5, h6 {
            letter-spacing: 0 !important;
        }

        h1 {
            font-size: 2rem !important;
            line-height: 1.15 !important;
        }

        h2, [data-testid="stHeadingWithActionElements"] h2 {
            font-size: 1.15rem !important;
        }

        [data-testid="stMetric"] {
            border-radius: 6px;
            background: color-mix(in srgb, var(--secondary-background-color) 82%, transparent);
        }

        [data-testid="stMetricValue"] {
            font-size: 1.35rem;
        }

        [data-testid="stChatMessage"],
        [data-testid="stAlert"],
        [data-testid="stFileUploaderDropzone"] {
            border-radius: 6px;
        }

        .st-key-conversation_history {
            background: color-mix(in srgb, var(--secondary-background-color) 45%, transparent);
            border-radius: 6px;
        }

        .st-key-home_grid > div > [data-testid="stHorizontalBlock"] {
            align-items: flex-start;
        }

        .page-count {
            min-height: 2.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            color: color-mix(in srgb, var(--text-color) 72%, transparent);
            font-size: 0.9rem;
            text-align: center;
        }

        @media (max-width: 900px) {
            .stAppViewContainer .main .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .st-key-home_grid > div > [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }

            .st-key-home_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width: 100%;
                flex: 1 1 100%;
            }

            .st-key-home_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {
                order: 1;
            }

            .st-key-home_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) {
                order: 2;
            }

            .st-key-home_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) {
                order: 3;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
