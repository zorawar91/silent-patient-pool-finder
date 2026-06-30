"""
Streamlit Dashboard — Silent Patient Pool Finder
=================================================
Interactive dashboard showing Geography Risk Scores across US counties.

Run with:
    streamlit run src/output/dashboard.py

Reads from: data/scored/scores.parquet
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json
import urllib.request

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Silent Patient Pool Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

CONDITION_LABELS = {
    "t2d": "Type 2 Diabetes",
    "htn": "Hypertension",
    "hyperthyroidism": "Hyperthyroidism",
}

CONDITION_COLORS = {
    "t2d": "#E86C3A",
    "htn": "#3A7FE8",
    "hyperthyroidism": "#3AE89F",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_scores(scores_path: str = "data/scored/scores.parquet") -> pd.DataFrame:
    return pd.read_parquet(scores_path)


@st.cache_data
def load_scores_long(path: str = "data/scored/scores_long.parquet") -> pd.DataFrame:
    return pd.read_parquet(path)


@st.cache_data
def load_us_counties_geojson() -> dict:
    """Load US county GeoJSON. Uses a reliable public source."""
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
def render_sidebar(scores: pd.DataFrame) -> dict:
    st.sidebar.image("https://img.icons8.com/ios/100/000000/find-user-male.png", width=60)
    st.sidebar.title("Silent Patient\nPool Finder")
    st.sidebar.caption("Identifying undiagnosed chronic-disease burden by geography")
    st.sidebar.divider()

    # Condition selector
    condition_options = {"Overall (All Conditions)": "overall"} | {
        CONDITION_LABELS[c]: c for c in ["t2d", "htn", "hyperthyroidism"]
        if f"{c}_risk_score" in scores.columns
    }
    selected_label = st.sidebar.selectbox(
        "Condition", list(condition_options.keys()), index=0
    )
    selected_condition = condition_options[selected_label]

    # State filter
    states = ["All States"] + sorted(scores["state_name"].unique().tolist())
    selected_state = st.sidebar.selectbox("Filter by State", states)

    # Top N
    top_n = st.sidebar.slider("Top N opportunity counties", 10, 100, 25, step=5)

    # Rural filter
    show_rural_only = st.sidebar.checkbox("Rural counties only", value=False)

    st.sidebar.divider()
    st.sidebar.caption(
        "⚠️ Population-level planning tool only. "
        "Not a clinical diagnostic instrument."
    )

    return {
        "condition": selected_condition,
        "state": selected_state,
        "top_n": top_n,
        "rural_only": show_rural_only,
    }


# ---------------------------------------------------------------------------
# Metrics row
# ---------------------------------------------------------------------------
def render_metrics(filtered: pd.DataFrame, condition: str):
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Counties Analyzed", f"{len(filtered):,}")
    with col2:
        st.metric("Avg Risk Score", f"{filtered[score_col].mean():.1f}")
    with col3:
        high_risk = (filtered[score_col] >= 70).sum()
        st.metric("High-Risk Counties (≥70)", f"{high_risk:,}")
    with col4:
        total_pool = filtered["total_estimated_pool"].sum() if "total_estimated_pool" in filtered.columns else 0
        st.metric("Est. Undiagnosed Pool", f"{int(total_pool):,}")


# ---------------------------------------------------------------------------
# Choropleth map
# ---------------------------------------------------------------------------
def render_map(scores: pd.DataFrame, geojson: dict | None, condition: str):
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    label = "Overall Risk Score" if condition == "overall" else f"{CONDITION_LABELS.get(condition, condition)} Risk Score"

    if geojson is None:
        st.warning("GeoJSON unavailable (offline?). Showing scatter plot fallback.")
        # Fallback: scatter by state
        state_agg = scores.groupby("state_name")[score_col].mean().reset_index()
        fig = px.bar(
            state_agg.sort_values(score_col, ascending=False),
            x="state_name", y=score_col,
            color=score_col, color_continuous_scale="Reds",
            labels={"state_name": "State", score_col: label},
            title=f"{label} by State (County-level GeoJSON unavailable)",
        )
        st.plotly_chart(fig, use_container_width=True)
        return

    fig = px.choropleth(
        scores,
        geojson=geojson,
        locations="county_fips",
        color=score_col,
        color_continuous_scale="Reds",
        range_color=(0, 100),
        scope="usa",
        labels={score_col: label},
        hover_name="county_name",
        hover_data={
            "state_name": True,
            "population": ":,",
            score_col: ":.1f",
            "top_signal": True,
        },
        title=f"{label} — US Counties",
    )
    fig.update_layout(
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        coloraxis_colorbar={"title": "Risk Score", "tickvals": [0, 25, 50, 75, 100]},
        height=520,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Top counties table
# ---------------------------------------------------------------------------
def render_opportunity_table(filtered: pd.DataFrame, condition: str, top_n: int):
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    top = filtered.nlargest(top_n, score_col).copy()

    display_cols = {
        "county_name": "County",
        "state_name": "State",
        "population": "Population",
        score_col: "Risk Score",
        "top_signal": "Top Signal",
        "total_estimated_pool": "Est. Undiagnosed Pool",
        "is_rural": "Rural",
    }
    available = {k: v for k, v in display_cols.items() if k in top.columns}
    top_display = top[list(available.keys())].rename(columns=available)

    if "Risk Score" in top_display.columns:
        top_display["Risk Score"] = top_display["Risk Score"].round(1)
    if "Population" in top_display.columns:
        top_display["Population"] = top_display["Population"].apply(lambda x: f"{int(x):,}")
    if "Est. Undiagnosed Pool" in top_display.columns:
        top_display["Est. Undiagnosed Pool"] = top_display["Est. Undiagnosed Pool"].apply(
            lambda x: f"{int(x):,}" if pd.notna(x) else "—"
        )

    st.dataframe(
        top_display,
        use_container_width=True,
        hide_index=True,
    )

    # Download button
    csv = top[list(available.keys())].to_csv(index=False)
    st.download_button(
        "⬇️ Download opportunity table (CSV)",
        csv,
        file_name=f"opportunity_{condition}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Signal breakdown chart
# ---------------------------------------------------------------------------
def render_signal_breakdown(scores_long: pd.DataFrame, county_fips: str, condition: str):
    if condition == "overall":
        cond_data = scores_long[scores_long["county_fips"] == county_fips]
    else:
        cond_data = scores_long[
            (scores_long["county_fips"] == county_fips) &
            (scores_long["condition"] == condition)
        ]

    if cond_data.empty:
        st.info("Select a county from the table to see signal breakdown.")
        return

    signal_cols = {
        "otc_proxy_score": "OTC Proxy Score",
        "diagnostic_orphan_ratio": "Diagnostic Orphan Ratio",
        "hcp_symptom_rx_ratio": "HCP Symptom Rx Ratio",
        "geo_burden_index_scaled": "Geo Burden Index",
    }

    rows = []
    for cond_row in cond_data.itertuples():
        for col, label in signal_cols.items():
            if hasattr(cond_row, col):
                rows.append({
                    "Signal": label,
                    "Value": getattr(cond_row, col),
                    "Condition": CONDITION_LABELS.get(cond_row.condition, cond_row.condition),
                })

    if not rows:
        return

    chart_data = pd.DataFrame(rows)
    fig = px.bar(
        chart_data,
        x="Signal", y="Value", color="Condition",
        barmode="group",
        title="Signal Breakdown",
        range_y=[0, 1],
        color_discrete_map={v: CONDITION_COLORS.get(k, "#888") for k, v in CONDITION_LABELS.items()},
    )
    fig.update_layout(height=350, margin={"t": 40, "b": 20})
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
def main():
    scores_path = Path("data/scored/scores.parquet")
    if not scores_path.exists():
        st.error(
            "No scored data found. Run the pipeline first:\n\n"
            "```bash\npython run.py --country us\n```"
        )
        st.stop()

    scores = load_scores(str(scores_path))
    scores_long = load_scores_long()
    geojson = load_us_counties_geojson()

    controls = render_sidebar(scores)

    # Apply filters
    filtered = scores.copy()
    if controls["state"] != "All States":
        filtered = filtered[filtered["state_name"] == controls["state"]]
    if controls["rural_only"] and "is_rural" in filtered.columns:
        filtered = filtered[filtered["is_rural"]]

    # Header
    st.title("🔍 Silent Patient Pool Finder")
    condition_label = (
        "All Conditions (Overall)"
        if controls["condition"] == "overall"
        else CONDITION_LABELS.get(controls["condition"], controls["condition"])
    )
    st.caption(
        f"Identifying undiagnosed **{condition_label}** burden across US counties "
        f"using OTC, diagnostic, HCP, and geographic signals."
    )

    # Metrics
    render_metrics(filtered, controls["condition"])
    st.divider()

    # Map + Table
    col_map, col_table = st.columns([3, 2])

    with col_map:
        render_map(filtered, geojson, controls["condition"])

    with col_table:
        st.subheader(f"Top {controls['top_n']} Opportunity Counties")
        render_opportunity_table(filtered, controls["condition"], controls["top_n"])

    st.divider()

    # Signal breakdown (for a selected county)
    st.subheader("Signal Breakdown")
    county_options = ["— Select a county —"] + filtered["county_name"].tolist()
    selected_county_name = st.selectbox("County", county_options)
    if selected_county_name != "— Select a county —":
        fips = filtered[filtered["county_name"] == selected_county_name]["county_fips"].iloc[0]
        render_signal_breakdown(scores_long, fips, controls["condition"])


if __name__ == "__main__":
    main()
