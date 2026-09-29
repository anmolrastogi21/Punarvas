"""PUNARVAS: Rehabilitation & Resettlement.

Tab 1 embeds the planning map (index.html). Tab 2 explains the priority score with SHAP.
"""
from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from PIL import Image

import core

ROOT = Path(__file__).parent

st.set_page_config(
    page_title="PUNARVAS - Rehabilitation & Resettlement",
    page_icon=Image.open(ROOT / "assets" / "icon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .block-container {padding: 0.5rem 1rem 1rem !important; max-width: 100% !important;}
      footer, [data-testid="stHeader"] {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)


def show_chart(chart) -> None:
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:  # older Streamlit
        st.altair_chart(chart, use_container_width=True)


def show_table(df: pd.DataFrame) -> None:
    try:
        st.dataframe(df, hide_index=True, width="stretch")
    except TypeError:
        st.dataframe(df, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------- map tab
def carto_key() -> str:
    try:
        value = st.secrets.get("CARTO_API_KEY", "")
    except Exception:
        value = ""
    return str(value or os.environ.get("CARTO_API_KEY", "")).strip()


def render_map() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    key = carto_key()
    if key:
        html = html.replace("__CARTO_KEY__", key)
    height = 880
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        import streamlit.components.v1 as components

        components.html(html, height=height, scrolling=True)


# ------------------------------------------------------------ analyst tab
def render_analyst() -> None:
    st.markdown("### SHAP analysis: why villages rank the way they do")
    st.caption(
        "Set a scenario below. The ranking and SHAP explanations use these settings. "
        "This tab has its own controls and is not linked to the sliders on the map. "
        "Data is indicative and not for operational use."
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        rain = st.slider("Forecast rainfall (mm in 24 h)", 0, 300, 30, key="a_rain")
        budget = st.slider("Villages funded", 1, 7, 4, key="a_budget")
    with c2:
        with st.expander("Priority weights", expanded=False):
            w1, w2, w3, w4 = st.columns(4)
            weights = {
                "h": w1.slider("Hazard", 0, 100, core.DEFAULT_WEIGHTS["h"], key="a_wh"),
                "e": w2.slider("Exposure", 0, 100, core.DEFAULT_WEIGHTS["e"], key="a_we"),
                "v": w3.slider("Vulnerability", 0, 100, core.DEFAULT_WEIGHTS["v"], key="a_wv"),
                "d": w4.slider("History", 0, 100, core.DEFAULT_WEIGHTS["d"], key="a_wd"),
            }
        if not any(weights.values()):
            st.warning("All weights are zero, so every village scores 0. Raise at least one weight.")

    res = core.compute(rain, weights, budget)
    villages = res["villages"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Alert level", res["alert"])
    m2.metric("Villages in Red Zone", sum(1 for v in villages if v["red"]))
    m3.metric("Households in Red Zone", sum(v["hh"] for v in villages if v["red"]))
    m4.metric("Average RPI", f"{res['base_value']:.1f}")

    df = pd.DataFrame([{
        "Rank": v["rank"], "Village": v["name"], "Households": v["hh"], "RPI": v["rpi"], "Tier": v["tier"],
        "Red Zone": "Yes" if v["red"] else "No",
        "Site": (v["site"]["name"].split(" (")[0] if v["site"] else ("none has room" if v["funded"] else "-")),
    } for v in villages])
    show_table(df)

    # ---- SHAP for one village
    st.markdown("#### What drives a village's score (SHAP)")
    names = [v["name"] for v in villages]
    pick = st.selectbox("Village", names, key="a_pick")
    v = next(x for x in villages if x["name"] == pick)
    sdf = pd.DataFrame({
        "Factor": list(v["shap"].keys()),
        "RPI points vs average village": list(v["shap"].values()),
    })
    sdf["Effect"] = sdf["RPI points vs average village"].apply(lambda s: "Raises RPI" if s >= 0 else "Lowers RPI")
    bars = alt.Chart(sdf).mark_bar().encode(
        x=alt.X("RPI points vs average village:Q", title="RPI points vs the average village"),
        y=alt.Y("Factor:N", sort=list(core.FEATURES), title=None),
        color=alt.Color("Effect:N", legend=None,
                        scale=alt.Scale(domain=["Raises RPI", "Lowers RPI"], range=["#c8402f", "#2a6fbb"])),
        tooltip=["Factor", alt.Tooltip("RPI points vs average village:Q", format="+.1f")],
    ).properties(height=170)
    show_chart(bars)
    st.markdown(core.explain_village(res, v["id"]))
    total = res["base_value"] + sum(v["shap"].values())
    st.caption(
        f"Average village {res['base_value']:.1f} + the four bars = {total:.1f}, shown as RPI {v['rpi']}. "
        f"Method: {res['shap_method']}, with the seven villages as the background data."
    )

    with st.expander("All villages at a glance"):
        rows = [{"Village": x["name"], "Factor": f, "SHAP": s} for x in villages for f, s in x["shap"].items()]
        long = pd.DataFrame(rows)
        base = alt.Chart(long).encode(
            x=alt.X("Factor:N", sort=list(core.FEATURES), title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Village:N", sort=names, title=None),
        )
        heat = base.mark_rect().encode(
            color=alt.Color("SHAP:Q", title="RPI points",
                            scale=alt.Scale(scheme="redblue", domainMid=0, reverse=True)))
        text = base.mark_text(fontSize=12).encode(
            text=alt.Text("SHAP:Q", format="+.1f"),
            color=alt.condition("abs(datum.SHAP) > 7", alt.value("white"), alt.value("black")))
        show_chart((heat + text).properties(height=260))
        st.caption("Red cells push a village up the priority list, blue cells pull it down, relative to the average village.")

    with st.expander("Setup status"):
        st.write(f"Basemap: {'CARTO (API key found)' if carto_key() else 'Esri fallback (no CARTO_API_KEY secret found)'}")
        st.write(f"SHAP method: {res['shap_method']}")


tab_map, tab_shap = st.tabs(["Planning map", "SHAP analysis"])
with tab_map:
    render_map()
with tab_shap:
    render_analyst()
