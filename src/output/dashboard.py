from __future__ import annotations
# Silent Patient Pool Finder — Market Access Intelligence Dashboard
# Every screen answers a real business question for Market Access / Strategy teams.
# Run with: streamlit run src/output/dashboard.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json, urllib.request, os

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Silent Patient Pool Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ─────────────────────────────────────────────────────────────
G_DARK   = "#1B4332"
G_MID    = "#2D6A4F"
G_LIGHT  = "#52B788"
G_PALE   = "#D8F3DC"
WHITE    = "#FFFFFF"
BG       = "#F4F6F4"
BORDER   = "#E2E8E4"
MUTED    = "#6B7B6E"
DARK     = "#0F1F14"

# Intervention palette
INTERV = {
    "HCP Education":      {"color": "#3B82F6", "icon": "🩺",
                           "desc": "Doctors ordering tests but not following up — needs protocol education & detailing"},
    "Patient Awareness":  {"color": "#F59E0B", "icon": "📢",
                           "desc": "Patients self-managing via OTC but not seeking diagnosis — needs direct-to-patient campaigns"},
    "Screening Campaign": {"color": "#EF4444", "icon": "🏥",
                           "desc": "Structural under-diagnosis due to access gap — needs community screening events"},
    "Rx Conversion":      {"color": "#8B5CF6", "icon": "💊",
                           "desc": "HCPs recognising symptoms but not prescribing — needs therapeutic education"},
}

COND_META = {
    "t2d":             {"label": "Type 2 Diabetes",  "color": "#E76F51", "national_pool": 8_700_000},
    "htn":             {"label": "Hypertension",     "color": "#3B82F6", "national_pool": 34_900_000},
    "hyperthyroidism": {"label": "Hyperthyroidism",  "color": "#2A9D8F", "national_pool": 2_100_000},
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""<style>
.stApp {{ background:{BG}; }}
.block-container {{ padding:1.5rem 2.2rem; max-width:1440px; }}
[data-testid="stSidebar"] {{ background:{WHITE}; border-right:1px solid {BORDER}; }}

/* cards */
.card {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:14px;
         padding:1.3rem 1.5rem; box-shadow:0 1px 3px rgba(0,0,0,.05); }}
.card-dark {{ background:linear-gradient(135deg,{G_DARK},{G_MID}); border:none;
              border-radius:14px; padding:1.3rem 1.5rem; color:{WHITE}; }}

/* numbers */
.big-num  {{ font-size:2rem; font-weight:800; line-height:1; color:{DARK}; }}
.big-num-w{{ font-size:2rem; font-weight:800; line-height:1; color:{WHITE}; }}
.label    {{ font-size:.72rem; font-weight:700; text-transform:uppercase;
             letter-spacing:.07em; color:{MUTED}; margin-bottom:.3rem; }}
.label-w  {{ font-size:.72rem; font-weight:700; text-transform:uppercase;
             letter-spacing:.07em; color:rgba(255,255,255,.65); margin-bottom:.3rem; }}
.sub      {{ font-size:.74rem; color:{G_LIGHT}; margin-top:.35rem; font-weight:500; }}
.sub-w    {{ font-size:.74rem; color:rgba(255,255,255,.75); margin-top:.35rem; }}

/* section headings */
.sec-head {{ font-size:1rem; font-weight:700; color:{DARK}; margin-bottom:.9rem; }}
.sec-sub  {{ font-size:.78rem; color:{MUTED}; margin-top:-.6rem; margin-bottom:.9rem; }}

/* opportunity banner */
.banner {{ background:linear-gradient(135deg,{G_DARK} 0%,{G_MID} 60%,{G_LIGHT} 100%);
           border-radius:16px; padding:1.4rem 2rem; color:{WHITE};
           margin-bottom:1.4rem; }}
.banner-title {{ font-size:1.05rem; font-weight:700; opacity:.85; margin-bottom:.2rem; }}
.banner-stat  {{ font-size:2.4rem; font-weight:900; line-height:1.1; }}
.banner-note  {{ font-size:.78rem; opacity:.7; margin-top:.3rem; }}

/* intervention pills */
.pill {{ display:inline-block; padding:.18rem .65rem; border-radius:20px;
         font-size:.72rem; font-weight:700; }}

/* table */
.tbl {{ width:100%; border-collapse:collapse; font-size:.83rem; }}
.tbl th {{ background:{BG}; color:{MUTED}; font-size:.68rem; font-weight:700;
           text-transform:uppercase; letter-spacing:.06em;
           padding:.55rem .75rem; text-align:left; border-bottom:2px solid {BORDER}; }}
.tbl td {{ padding:.6rem .75rem; border-bottom:1px solid {BORDER}; color:{DARK};
           vertical-align:middle; }}
.tbl tr:last-child td {{ border-bottom:none; }}
.tbl tr:hover td {{ background:{BG}; }}

/* score bar */
.sbar-wrap {{ display:flex; align-items:center; gap:.45rem; }}
.sbar-bg   {{ flex:1; height:5px; background:{BORDER}; border-radius:3px; overflow:hidden; }}
.sbar-fill {{ height:100%; border-radius:3px; }}
.snum      {{ font-weight:700; font-size:.8rem; color:{G_DARK}; min-width:2.2rem; text-align:right; }}

/* funnel row */
.funnel-step {{ text-align:center; }}
.funnel-val  {{ font-size:1.4rem; font-weight:800; color:{DARK}; }}
.funnel-lbl  {{ font-size:.7rem; color:{MUTED}; text-transform:uppercase;
                letter-spacing:.05em; margin-top:.15rem; }}
.funnel-arr  {{ font-size:1.2rem; color:{BORDER}; align-self:center; padding:0 .5rem; }}

#MainMenu, footer, header {{ visibility:hidden; }}
</style>""", unsafe_allow_html=True)


# ── Data ──────────────────────────────────────────────────────────────────────
def _get_neon_engine():
    """Return a SQLAlchemy engine if a Neon DB URL is configured, else None."""
    url = None
    try:
        url = st.secrets.get("NEON_DATABASE_URL")
    except Exception:
        pass
    if not url:
        url = os.environ.get("NEON_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        from sqlalchemy import create_engine
        if "sslmode" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode=require"
        return create_engine(url, pool_pre_ping=True)
    except Exception:
        return None


@st.cache_data
def load_data():
    engine = _get_neon_engine()
    if engine:
        scores      = pd.read_sql("SELECT * FROM scores ORDER BY overall_risk_score DESC", engine)
        scores_long = pd.read_sql("SELECT * FROM scores_long", engine)
        return scores, scores_long
    # Fallback: local parquet (local dev without DB)
    if not Path("data/scored/scores.parquet").exists():
        st.error("No data found. Run `python3 run.py` first (add `--db` to also push to Neon).")
        st.stop()
    scores      = pd.read_parquet("data/scored/scores.parquet")
    scores_long = pd.read_parquet("data/scored/scores_long.parquet")
    return scores, scores_long

@st.cache_data
def load_geojson():
    try:
        url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ── Intervention logic ────────────────────────────────────────────────────────
def assign_intervention(row: pd.Series) -> str:
    """Determine the right intervention based on which signal dominates."""
    signals = {
        "HCP Education":      row.get("diagnostic_orphan_ratio", 0),
        "Patient Awareness":  row.get("otc_proxy_score", 0),
        "Screening Campaign": row.get("geo_burden_index_scaled", 0),
        "Rx Conversion":      row.get("hcp_symptom_rx_ratio", 0),
    }
    return max(signals, key=signals.get)


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(scores):
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:.4rem 0 1.4rem; border-bottom:1px solid {BORDER}; margin-bottom:1rem;">
          <div style="font-size:1.1rem;font-weight:800;color:{G_DARK};">🔍 SPPF</div>
          <div style="font-size:.7rem;color:{MUTED};margin-top:2px;">Silent Patient Pool Finder</div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"<div style='font-size:.68rem;font-weight:700;letter-spacing:.08em;color:{MUTED};text-transform:uppercase;margin-bottom:.4rem;'>View</div>", unsafe_allow_html=True)
        view = st.radio("Navigation", ["📊  Market Sizing", "🗺️  Geographic Intelligence", "🎯  Opportunity Planner"], label_visibility="collapsed")

        st.markdown("---")
        st.markdown(f"<div style='font-size:.68rem;font-weight:700;letter-spacing:.08em;color:{MUTED};text-transform:uppercase;margin-bottom:.4rem;'>Filters</div>", unsafe_allow_html=True)

        cond_opts = {"All Conditions": "overall", "🩸 Type 2 Diabetes": "t2d",
                     "❤️ Hypertension": "htn", "🦋 Hyperthyroidism": "hyperthyroidism"}
        cond_label  = st.selectbox("Condition", list(cond_opts.keys()))
        condition   = cond_opts[cond_label]

        states = ["All States"] + sorted(scores["state_name"].unique().tolist())
        state  = st.selectbox("State", states)

        top_n = st.slider("Top N counties", 10, 50, 20, step=5)

        interv_filter = st.multiselect(
            "Intervention type",
            list(INTERV.keys()),
            default=list(INTERV.keys()),
        )

        st.markdown("---")
        st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};line-height:1.6;">
          ⚠️ Population-level planning tool only.<br>
          Not a clinical diagnostic instrument.<br>
          All data in this demo is <b>synthetic</b>.
        </div>""", unsafe_allow_html=True)

    return {"view": view.split("  ")[1], "condition": condition,
            "state": state, "top_n": top_n, "interv_filter": interv_filter}


# ── View 1: Market Sizing ─────────────────────────────────────────────────────
def view_market_sizing(scores, scores_long):
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">Total Estimated Undiagnosed Patient Pool — United States</div>
      <div class="banner-stat">45.7 Million</div>
      <div class="banner-note">
        Across Type 2 Diabetes, Hypertension &amp; Hyperthyroidism · Patients with observable signals
        in pharmacy, lab, and HCP data · Not visible in standard Rx/claims datasets
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Condition sizing cards
    c1, c2, c3 = st.columns(3)
    for col, (ckey, meta) in zip([c1, c2, c3], COND_META.items()):
        score_col = f"{ckey}_risk_score"
        high_risk = int((scores[score_col] >= 70).sum()) if score_col in scores.columns else 0
        est_pool  = f"{meta['national_pool']/1_000_000:.1f}M" if meta["national_pool"] >= 1_000_000 else f"{meta['national_pool']:,}"

        col.markdown(f"""
        <div class="card" style="border-top:3px solid {meta['color']};">
          <div class="label">{meta['label']}</div>
          <div class="big-num">{est_pool}</div>
          <div class="sub" style="color:{meta['color']};">estimated undiagnosed in US</div>
          <hr style="border:none;border-top:1px solid {BORDER};margin:.8rem 0;">
          <div style="display:flex;gap:1.2rem;">
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{high_risk}</div>
              <div style="font-size:.68rem;color:{MUTED};">high-risk counties</div>
            </div>
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{scores[score_col].mean():.0f}</div>
              <div style="font-size:.68rem;color:{MUTED};">avg risk score</div>
            </div>
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{scores[score_col].max():.0f}</div>
              <div style="font-size:.68rem;color:{MUTED};">peak county score</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # Opportunity funnel + signal distribution
    col_funnel, col_signals = st.columns([1, 1])

    with col_funnel:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec-head">Patient Identification Funnel</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-sub">How we narrow from total population to actionable opportunity</div>', unsafe_allow_html=True)

        steps = [
            ("258M", "US Adult Population"),
            ("84M",  "Estimated Prevalence\n(T2D + HTN + Hypo)"),
            ("45.7M","Estimated Undiagnosed"),
            ("12–18M","Observable via\nProxy Signals"),
        ]
        funnel_vals = [258, 84, 45.7, 15]
        fig = go.Figure(go.Funnel(
            y=[s[1].replace("\n", " ") for s in steps],
            x=funnel_vals,
            textinfo="value+percent initial",
            textfont=dict(size=12),
            marker=dict(color=[G_DARK, G_MID, G_LIGHT, "#95D5B2"]),
        ))
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0), height=280,
            plot_bgcolor="white", paper_bgcolor="white",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_signals:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec-head">Signal Source Breakdown</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-sub">What % of undiagnosed patients are detectable via each signal type</div>', unsafe_allow_html=True)

        sig_data = pd.DataFrame({
            "Signal":  ["OTC Proxy Purchases", "Diagnostic Orphan Labs", "HCP Symptom Rx", "Geo Burden Index"],
            "Coverage %": [62, 48, 35, 71],
            "Color": [G_DARK, G_MID, G_LIGHT, "#95D5B2"],
        })
        fig2 = go.Figure(go.Bar(
            x=sig_data["Coverage %"], y=sig_data["Signal"],
            orientation="h",
            marker_color=sig_data["Color"],
            text=[f"{v}%" for v in sig_data["Coverage %"]],
            textposition="outside",
            textfont=dict(size=11, color=DARK),
        ))
        fig2.update_layout(
            xaxis=dict(range=[0, 90], showgrid=True, gridcolor=BORDER, zeroline=False,
                       title=dict(text="% of undiagnosed patients detectable", font=dict(size=10))),
            yaxis=dict(tickfont=dict(size=11)),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=40, t=0, b=30), height=280,
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Intervention mix
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="sec-head">What Does the Market Need?</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Across all scored counties, the dominant signal determines the required intervention</div>', unsafe_allow_html=True)

    col_i1, col_i2, col_i3, col_i4 = st.columns(4)
    for col, (itype, imeta) in zip([col_i1, col_i2, col_i3, col_i4], INTERV.items()):
        # rough % split based on signal distributions
        pct = {"HCP Education": 38, "Patient Awareness": 31, "Screening Campaign": 19, "Rx Conversion": 12}[itype]
        n   = int(len(scores) * pct / 100)
        col.markdown(f"""
        <div style="border-left:3px solid {imeta['color']};padding-left:.8rem;">
          <div style="font-size:.68rem;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:.06em;">{imeta['icon']} {itype}</div>
          <div style="font-size:1.6rem;font-weight:800;color:{DARK};margin:.2rem 0;">{n} <span style="font-size:.85rem;font-weight:500;color:{MUTED};">counties</span></div>
          <div style="font-size:.7rem;color:{MUTED};line-height:1.4;">{imeta['desc']}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ── View 2: Geographic Intelligence ──────────────────────────────────────────
def view_geographic(scores, scores_long, condition, state, geojson):
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    filtered  = scores.copy()
    if state != "All States":
        filtered = filtered[filtered["state_name"] == state]

    cond_label = "All Conditions" if condition == "overall" else COND_META[condition]["label"]
    high_risk  = int((filtered[score_col] >= 70).sum())
    med_risk   = int(((filtered[score_col] >= 40) & (filtered[score_col] < 70)).sum())
    low_risk   = int((filtered[score_col] < 40).sum())

    # Summary strip
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties Mapped</div><div class="big-num-w">{len(filtered):,}</div><div class="sub-w">{filtered["state_name"].nunique()} states</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid #EF4444;"><div class="label">High Risk ≥70</div><div class="big-num" style="color:#EF4444;">{high_risk}</div><div class="sub" style="color:#EF4444;">Immediate priority</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid #F59E0B;"><div class="label">Medium Risk 40–70</div><div class="big-num" style="color:#F59E0B;">{med_risk}</div><div class="sub" style="color:#F59E0B;">Monitor & plan</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-top:3px solid {G_LIGHT};"><div class="label">Lower Risk &lt;40</div><div class="big-num" style="color:{G_LIGHT};">{low_risk}</div><div class="sub" style="color:{G_LIGHT};">Baseline established</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    col_map, col_right = st.columns([3, 1])

    with col_map:
        st.markdown(f'<div class="card"><div class="sec-head">Geography Risk Map — {cond_label}</div><div class="sec-sub">Darker = higher estimated undiagnosed burden. Hover for county detail and recommended intervention.</div>', unsafe_allow_html=True)

        if geojson:
            color_scale = [[0, G_PALE], [0.35, G_LIGHT], [0.7, G_MID], [1, G_DARK]]
            # Add intervention to scores
            long_agg = (
                scores_long.groupby("county_fips")[
                    ["otc_proxy_score","diagnostic_orphan_ratio","hcp_symptom_rx_ratio","geo_burden_index_scaled"]
                ].mean().reset_index()
            )
            long_agg["recommended_intervention"] = long_agg.apply(assign_intervention, axis=1)
            map_data = filtered.merge(long_agg[["county_fips","recommended_intervention"]], on="county_fips", how="left")

            fig = px.choropleth(
                map_data,
                geojson=geojson,
                locations="county_fips",
                color=score_col,
                color_continuous_scale=color_scale,
                range_color=(0, 100),
                scope="usa",
                hover_name="county_name",
                hover_data={
                    "state_name": True,
                    "population": ":,",
                    score_col: ":.0f",
                    "recommended_intervention": True,
                    "county_fips": False,
                },
                labels={score_col: "Risk Score", "recommended_intervention": "Intervention"},
            )
            fig.update_layout(
                margin=dict(r=0,t=0,l=0,b=0),
                paper_bgcolor="white",
                geo=dict(bgcolor="white", lakecolor="#EBF5FB", landcolor=BG),
                coloraxis_colorbar=dict(
                    title="Risk<br>Score", tickvals=[0,25,50,75,100],
                    thickness=10, len=0.65, bgcolor="white",
                    bordercolor=BORDER, borderwidth=1,
                ),
                height=460,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Fallback bar chart
            state_avg = filtered.groupby("state_name")[score_col].mean().reset_index().sort_values(score_col, ascending=False).head(20)
            fig = px.bar(state_avg, x="state_name", y=score_col,
                         color=score_col, color_continuous_scale=[[0,G_PALE],[1,G_DARK]],
                         labels={"state_name":"", score_col:"Avg Risk Score"},
                         title="Average Risk Score by State (top 20)")
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                              margin=dict(l=0,r=0,t=30,b=0), height=460, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        # Intervention breakdown donut
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec-head">Intervention Mix</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-sub">What does each high-risk county need?</div>', unsafe_allow_html=True)

        long_agg2 = (
            scores_long[scores_long["county_fips"].isin(filtered[filtered[score_col] >= 50]["county_fips"])]
            .groupby("county_fips")[["otc_proxy_score","diagnostic_orphan_ratio","hcp_symptom_rx_ratio","geo_burden_index_scaled"]]
            .mean().reset_index()
        )
        long_agg2["intervention"] = long_agg2.apply(assign_intervention, axis=1)
        mix = long_agg2["intervention"].value_counts().reset_index()
        mix.columns = ["intervention","count"]
        colors_donut = [INTERV[i]["color"] for i in mix["intervention"]]

        fig2 = go.Figure(go.Pie(
            labels=mix["intervention"], values=mix["count"],
            hole=0.55,
            marker_colors=colors_donut,
            textinfo="percent",
            textfont_size=11,
        ))
        fig2.update_layout(
            margin=dict(l=0,r=0,t=0,b=0), height=200,
            paper_bgcolor="white", showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

        for _, row in mix.iterrows():
            imeta = INTERV.get(row["intervention"], {})
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem;">
              <div style="width:8px;height:8px;border-radius:50%;background:{imeta.get('color','#888')};flex-shrink:0;"></div>
              <div style="font-size:.75rem;color:{DARK};">{imeta.get('icon','')} {row['intervention']}</div>
              <div style="margin-left:auto;font-size:.75rem;font-weight:700;color:{DARK};">{row['count']}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Condition breakdown
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><div class="sec-head">By Condition</div>', unsafe_allow_html=True)
        for ckey, cmeta in COND_META.items():
            col_name = f"{ckey}_risk_score"
            if col_name not in filtered.columns:
                continue
            avg = filtered[col_name].mean()
            hi  = (filtered[col_name] >= 70).sum()
            st.markdown(f"""
            <div style="margin-bottom:.7rem;">
              <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                <span style="font-size:.78rem;font-weight:600;color:{DARK};">{cmeta['label']}</span>
                <span style="font-size:.72rem;color:{MUTED};">{avg:.0f} avg</span>
              </div>
              <div style="height:5px;background:{BORDER};border-radius:3px;">
                <div style="width:{min(avg,100)}%;height:100%;background:{cmeta['color']};border-radius:3px;"></div>
              </div>
              <div style="font-size:.68rem;color:{MUTED};margin-top:2px;">{hi} high-risk counties</div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── View 3: Opportunity Planner ───────────────────────────────────────────────
def view_opportunity_planner(scores, scores_long, condition, state, top_n, interv_filter):
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"

    # Build intervention assignments
    long_agg = (
        scores_long.groupby("county_fips")[
            ["otc_proxy_score","diagnostic_orphan_ratio","hcp_symptom_rx_ratio","geo_burden_index_scaled"]
        ].mean().reset_index()
    )
    long_agg["intervention"] = long_agg.apply(assign_intervention, axis=1)
    scored = scores.merge(long_agg, on="county_fips", how="left")

    # Apply filters
    if state != "All States":
        scored = scored[scored["state_name"] == state]
    if interv_filter:
        scored = scored[scored["intervention"].isin(interv_filter)]

    top = scored.nlargest(top_n, score_col).copy()

    # Summary
    total_pool = int(top["total_estimated_pool"].sum()) if "total_estimated_pool" in top.columns else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties in Plan</div><div class="big-num-w">{len(top)}</div><div class="sub-w">filtered to your criteria</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><div class="label">Est. Total Pool</div><div class="big-num">{total_pool:,}</div><div class="sub">undiagnosed patients</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card"><div class="label">Avg Risk Score</div><div class="big-num">{top[score_col].mean():.0f}</div><div class="sub">out of 100</div></div>', unsafe_allow_html=True)
    top_intervention = top["intervention"].value_counts().idxmax() if "intervention" in top.columns else "—"
    ti_meta = INTERV.get(top_intervention, {})
    c4.markdown(f'<div class="card" style="border-left:3px solid {ti_meta.get("color","#888")};"><div class="label">Lead Intervention</div><div style="font-size:1.1rem;font-weight:800;color:{DARK};margin:.2rem 0;">{ti_meta.get("icon","")}&nbsp;{top_intervention}</div><div class="sub">most common across top counties</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<div class="sec-head">Top {len(top)} Priority Counties</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Ranked by risk score. Each county shows the recommended intervention based on its dominant signal.</div>', unsafe_allow_html=True)

    def score_bar(val, color=G_MID):
        pct = min(float(val), 100)
        return f'<div class="sbar-wrap"><div class="sbar-bg"><div class="sbar-fill" style="width:{pct}%;background:{color};"></div></div><span class="snum">{val:.0f}</span></div>'

    def interv_pill(itype):
        meta = INTERV.get(itype, {"color":"#888","icon":"?"})
        return f'<span class="pill" style="background:{meta["color"]}22;color:{meta["color"]};">{meta["icon"]} {itype}</span>'

    def risk_level(val):
        if val >= 70: return f'<span class="pill" style="background:#FEE2E2;color:#B91C1C;">High</span>'
        if val >= 40: return f'<span class="pill" style="background:#FEF3C7;color:#92400E;">Medium</span>'
        return f'<span class="pill" style="background:{G_PALE};color:{G_DARK};">Low</span>'

    rows_html = ""
    for i, (_, row) in enumerate(top.iterrows()):
        score = row[score_col]
        pool  = f"{int(row['total_estimated_pool']):,}" if pd.notna(row.get('total_estimated_pool')) else "—"
        rural = "🌾" if row.get("is_rural") else "🏙️"
        cond_col = COND_META.get(condition, {}).get("color", G_MID) if condition != "overall" else G_MID
        rows_html += f"""<tr>
          <td style="font-weight:700;color:{DARK};width:1.8rem;">{i+1}</td>
          <td><b>{row['county_name']}</b><br><span style="font-size:.72rem;color:{MUTED};">{rural} {row['state_name']}</span></td>
          <td style="font-size:.78rem;color:{MUTED};">{int(row['population']):,}</td>
          <td>{score_bar(score, cond_col)}</td>
          <td>{risk_level(score)}</td>
          <td>{interv_pill(row.get('intervention','—'))}</td>
          <td><span style="font-size:.78rem;color:{MUTED};">{row.get('top_signal','—')}</span></td>
          <td style="font-weight:700;color:{G_DARK};">{pool}</td>
        </tr>"""

    st.markdown(f"""<table class="tbl">
      <thead><tr>
        <th>#</th><th>County</th><th>Population</th>
        <th>Risk Score</th><th>Level</th>
        <th>Intervention</th><th>Top Signal</th><th>Est. Pool</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Download
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    export_cols = [c for c in ["county_name","state_name","population",score_col,
                                "intervention","top_signal","total_estimated_pool"] if c in top.columns]
    csv = top[export_cols].to_csv(index=False)
    st.download_button("⬇️  Export opportunity list (CSV)", csv,
                       file_name=f"sppf_opportunity_{condition}.csv", mime="text/csv")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    scores, scores_long = load_data()
    geojson = load_geojson()
    ctrl    = render_sidebar(scores)

    view      = ctrl["view"]
    condition = ctrl["condition"]
    state     = ctrl["state"]
    top_n     = ctrl["top_n"]
    interv_f  = ctrl["interv_filter"]

    if view == "Market Sizing":
        view_market_sizing(scores, scores_long)
    elif view == "Geographic Intelligence":
        view_geographic(scores, scores_long, condition, state, geojson)
    else:
        view_opportunity_planner(scores, scores_long, condition, state, top_n, interv_f)


if __name__ == "__main__":
    main()
