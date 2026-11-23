"""Small shared CSS tweaks. Works in both light and dark themes."""
import streamlit as st

_CSS = """
<style>
span[data-baseweb="tag"] { background-color: #F2A33A !important; }
span[data-baseweb="tag"], span[data-baseweb="tag"] span { color: #0B1623 !important; }
[data-testid="stMetric"] { background: rgba(128, 128, 128, 0.10);
                           border: 1px solid rgba(128, 128, 128, 0.35);
                           border-radius: 10px; padding: 12px 16px; }
.block-container { padding-top: 2rem; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
