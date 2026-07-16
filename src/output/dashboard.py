from __future__ import annotations
# Silent Patient Pool Finder — IQVIA Market Access Intelligence Platform
# ======================================================================
# Streamlit entry point. All substance lives in the sibling modules:
#   theme.py    — design tokens, CSS, presentation helpers
#   content.py  — tooltip copy (weights generated from config)
#   data.py     — parquet/Neon loaders + data-shape helpers
#   sidebar.py  — navigation + global filters
#   views/      — one module per dashboard view
#
# Run with: streamlit run src/output/dashboard.py

import os
import sys
from pathlib import Path

# ── Import bootstrap ──────────────────────────────────────────────────────────
# Streamlit runs this file with src/output/ on sys.path, not the repo root —
# on Streamlit Cloud that breaks every `from src....` import (ModuleNotFoundError
# in Data Provenance / weight sensitivity / campaign measurement). Put the repo
# root first, and pin the working directory so relative data/ paths resolve
# no matter where the app is launched from.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if not Path("data").exists() and (_REPO_ROOT / "data").exists():
    os.chdir(_REPO_ROOT)

import streamlit as st

# ── Page config — must be the first Streamlit call ───────────────────────────
st.set_page_config(
    page_title="SPPF — Market Access Intelligence",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.output.data import load_data, load_geojson, load_hcp_data, load_zip_data
from src.output.sidebar import render_sidebar
from src.output.theme import inject_css
from src.output.views import (
    view_7d_analysis,
    view_campaign_measurement,
    view_data_provenance,
    view_geographic,
    view_hcp_targeting,
    view_insights,
    view_investment_planner,
    view_market_overview,
    view_payer_landscape,
    view_state_drilldown,
    view_zip_territory,
)

inject_css()


def main():
    scores, scores_long = load_data()
    geojson    = load_geojson()
    zip_scores = load_zip_data()
    ctrl       = render_sidebar(scores)

    view        = ctrl["view"]
    condition   = ctrl["condition"]
    cond_label  = ctrl["cond_label"]
    state       = ctrl["state"]
    county      = ctrl.get("county", "All Counties")
    top_n       = ctrl["top_n"]
    tier_filter = ctrl["tier_filter"]

    if view == "Insights & Actions":
        view_insights(scores, scores_long, condition, cond_label, state, top_n)

    elif view == "Market Overview":
        view_market_overview(scores, scores_long, condition, cond_label)

    elif view == "7-Dimension Analysis":
        view_7d_analysis(scores, state, top_n, condition, cond_label)

    elif view == "Investment Planner":
        view_investment_planner(scores, scores_long, condition, state, top_n, tier_filter)

    elif view == "Geographic Intelligence":
        view_geographic(scores, scores_long, condition, state, geojson)

    elif view == "State Drill-Down":
        view_state_drilldown(scores, scores_long, condition, cond_label, state, county, top_n)

    elif view == "Payer Landscape":
        view_payer_landscape(scores, state, top_n)

    elif view == "ZIP & Territory":
        view_zip_territory(zip_scores, scores, state, condition)

    elif view == "HCP Targeting":
        view_hcp_targeting(load_hcp_data(), state)

    elif view == "Campaign Measurement":
        view_campaign_measurement(scores)

    elif view == "Data Provenance":
        view_data_provenance(scores)


if __name__ == "__main__":
    main()
