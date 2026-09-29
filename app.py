"""PUNARVAS - Streamlit wrapper.

The planning tool itself is a self-contained web app (index.html). This file
embeds it in a Streamlit page so it can be hosted on Streamlit Community Cloud.
"""
import os
from pathlib import Path

import streamlit as st
from PIL import Image

ROOT = Path(__file__).parent

st.set_page_config(
    page_title="PUNARVAS - Rehabilitation & Resettlement",
    page_icon=Image.open(ROOT / "assets" / "icon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Remove Streamlit's default padding and footer so the app fills the page.
st.markdown(
    """
    <style>
      .block-container {padding: 0 !important; max-width: 100% !important;}
      footer, [data-testid="stHeader"] {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)

# CARTO basemaps need a free API key (https://carto.com/basemaps/apikey).
# Put it in Streamlit secrets as CARTO_API_KEY. Without it the map uses plain OpenStreetMap tiles.
def get_carto_key() -> str:
    try:
        key = st.secrets.get("CARTO_API_KEY", "")
    except Exception:
        key = ""
    return str(key or os.environ.get("CARTO_API_KEY", "")).strip()


html = (ROOT / "index.html").read_text(encoding="utf-8")
key = get_carto_key()
if key:
    html = html.replace("__CARTO_KEY__", key)

# Small status note in the (collapsed) sidebar, handy for checking the secret was picked up.
st.sidebar.caption("Basemap: CARTO (API key found)" if key else "Basemap: Esri fallback (no CARTO_API_KEY secret found)")

# Height of the embedded app in pixels. Raise or lower to suit your screen.
APP_HEIGHT = 880

if hasattr(st, "iframe"):
    # Newer Streamlit versions
    st.iframe(html, height=APP_HEIGHT)
else:
    # Older Streamlit versions
    import streamlit.components.v1 as components

    components.html(html, height=APP_HEIGHT, scrolling=True)
