from __future__ import annotations
# Silent Patient Pool Finder — IQVIA Market Access Intelligence Platform
# ======================================================================
# 5-view premium dashboard for pharma Market Access and Strategy teams.
# Answers: Where do we invest? Who pays? What program? How fast is it growing?
#
# Run with: streamlit run src/output/dashboard.py

import os
import json
import urllib.request
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SPPF — Market Access Intelligence",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens — IQVIA Blue Palette ───────────────────────────────────────
G_DARK   = "#003087"   # IQVIA deep navy
G_MID    = "#0077C8"   # IQVIA medium blue
G_LIGHT  = "#00A9E0"   # IQVIA light cyan-blue
G_PALE   = "#DEEEF9"   # IQVIA pale blue
WHITE    = "#FFFFFF"
BG       = "#F0F6FC"   # light blue-grey background
BORDER   = "#C8DDEF"   # blue-tinted border
MUTED    = "#5A7A9B"   # blue-grey muted text
DARK     = "#0A1F3C"   # near-black navy
AMBER    = "#F59E0B"
RED      = "#EF4444"
BLUE     = "#0077C8"   # alias
PURPLE   = "#8B5CF6"

# 7-Dimension color map
DIM_COLORS = {
    "disease_burden":       "#E76F51",
    "diagnosis_gap":        "#E63946",
    "access_to_care":       "#457B9D",
    "social_determinants":  "#8338EC",
    "payer_landscape":      "#2A9D8F",
    "commercial_readiness": "#F4A261",
    "trajectory":           "#60A5FA",
}
DIM_LABELS = {
    "disease_burden":       "Disease Burden",
    "diagnosis_gap":        "Diagnosis Gap",
    "access_to_care":       "Access to Care",
    "social_determinants":  "Social Determinants",
    "payer_landscape":      "Payer Landscape",
    "commercial_readiness": "Commercial Readiness",
    "trajectory":           "Trajectory",
}
DIM_ICONS = {
    "disease_burden":       "📊",
    "diagnosis_gap":        "🔍",
    "access_to_care":       "🏥",
    "social_determinants":  "🏘️",
    "payer_landscape":      "💳",
    "commercial_readiness": "🚀",
    "trajectory":           "📈",
}

DIM_SHORT = {
    "disease_burden":       "Disease Burden",
    "diagnosis_gap":        "Diagnosis Gap",
    "access_to_care":       "Access to Care",
    "social_determinants":  "Social Determinants",
    "payer_landscape":      "Payer Landscape",
    "commercial_readiness": "Commercial Readiness",
    "trajectory":           "Trajectory",
}

# Tooltip text shown on ℹ hover — used in the heatmap column headers
DIM_TOOLTIPS = {
    "disease_burden": (
        "How large is the total chronic disease burden? Combines diagnosed T2D prevalence, "
        "obesity rate, hypertension co-occurrence, and poor physical health days from CDC PLACES."
    ),
    "diagnosis_gap": (
        "What fraction of the disease burden remains undiagnosed? Driven by the gap between "
        "CDC-estimated true prevalence and Medicare-diagnosed rates, low annual checkup rates, "
        "and uninsured population — counties with low healthcare utilisation score highest."
    ),
    "access_to_care": (
        "Can an identified patient actually get diagnosed and treated? Reflects HRSA primary "
        "care shortage area (HPSA) designations, FQHC safety-net clinic presence, rural geography, "
        "and routine checkup utilisation as a proxy for primary care access."
    ),
    "social_determinants": (
        "What structural barriers drive the diagnosis gap? Combines poverty rate, median "
        "household income, uninsured rate, high school graduation rate, and a racial risk index "
        "weighted by elevated T2D risk in Black (1.6×) and Hispanic (1.5×) populations (Census ACS)."
    ),
    "payer_landscape": (
        "Who insures these patients, and what are their program funding incentives? High Medicare "
        "Advantage penetration = Stars quality metric incentives for payer partnerships. High "
        "Medicaid rate = HEDIS incentives via MCOs. Commercial coverage = employer wellness pathway."
    ),
    "commercial_readiness": (
        "How operationally feasible is it to launch and scale a screening program here? Reflects "
        "broadband internet access (digital health feasibility), urban vs. rural infrastructure, "
        "OTC purchasing proxies, and annual checkup rates (existing care relationships to recruit from)."
    ),
    "trajectory": (
        "Is the opportunity growing or shrinking? High score = widening gap. Driven by an ageing "
        "population (T2D risk increases sharply after 45), rising obesity rates as a leading T2D "
        "predictor, and rural + high-SDoH counties where investment lags behind need."
    ),
}

STATE_ABBREV = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
    "Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
    "Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA",
    "Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD",
    "Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS",
    "Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH",
    "New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC",
    "North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA",
    "Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN",
    "Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA",
    "West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY","District of Columbia":"DC",
}

INTERV_META = {
    "Payer Partnership Program":         {"color": BLUE,   "icon": "💳",
        "desc": "MA plan has Stars incentive — partner to fund screening & care management"},
    "Community Health Center Partnership":{"color": PURPLE,"icon": "🏘️",
        "desc": "High SDoH burden, low access — FQHCs are natural program delivery site"},
    "Employer Wellness Program":         {"color": AMBER,  "icon": "🏢",
        "desc": "High commercial coverage, urban — employer benefit integration"},
    "Digital Health Program":            {"color": G_LIGHT,"icon": "📱",
        "desc": "High broadband, commercial — telehealth screening & remote monitoring"},
    "Pharmacy-Based Screening":          {"color": G_MID,  "icon": "💊",
        "desc": "Broad accessibility — retail pharmacy A1C/BP screening events"},
}

COND_META = {
    "t2d":             {"label": "Type 2 Diabetes",  "color": "#E76F51", "national_pool": 8_700_000},
    "htn":             {"label": "Hypertension",     "color": "#3B82F6", "national_pool": 34_900_000},
    "hyperthyroidism": {"label": "Hyperthyroidism",  "color": "#2A9D8F", "national_pool": 2_100_000},
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""<style>
.stApp {{ background:{BG}; }}
.block-container {{ padding:1.5rem 2.2rem; max-width:1600px; }}
[data-testid="stSidebar"] {{ background:{WHITE}; border-right:1px solid {BORDER}; }}

.card {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:10px;
         padding:0.8rem 1rem; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
.card-dark {{ background:linear-gradient(135deg,{G_DARK},{G_MID}); border:none;
              border-radius:10px; padding:0.8rem 1rem; color:{WHITE}; }}
.card-blue {{ background:linear-gradient(135deg,#1E3A5F,#2D6A9F); border:none;
              border-radius:10px; padding:0.8rem 1rem; color:{WHITE}; }}
/* chart-head: lightweight section label above a chart — no white box */
.ch {{ border-left:3px solid {G_LIGHT}; padding:.35rem .75rem; margin-bottom:.4rem;
       background:rgba(0,169,224,.04); border-radius:0 6px 6px 0; }}
.ch .sec-head {{ margin-bottom:.15rem; }}
.ch .sec-sub  {{ margin-bottom:0; }}

.big-num   {{ font-size:2rem; font-weight:800; line-height:1; color:{DARK}; }}
.big-num-w {{ font-size:2rem; font-weight:800; line-height:1; color:{WHITE}; }}
.label     {{ font-size:.7rem; font-weight:700; text-transform:uppercase;
              letter-spacing:.07em; color:{MUTED}; margin-bottom:.25rem; }}
.label-w   {{ font-size:.7rem; font-weight:700; text-transform:uppercase;
              letter-spacing:.07em; color:rgba(255,255,255,.6); margin-bottom:.25rem; }}
.sub       {{ font-size:.74rem; color:{G_LIGHT}; margin-top:.3rem; font-weight:500; }}
.sub-w     {{ font-size:.74rem; color:rgba(255,255,255,.7); margin-top:.3rem; }}
.sub-muted {{ font-size:.74rem; color:{MUTED}; margin-top:.3rem; }}

.sec-head {{ font-size:1rem; font-weight:700; color:{DARK}; margin-bottom:.6rem; }}
.sec-sub  {{ font-size:.76rem; color:{MUTED}; margin-top:-.4rem; margin-bottom:.8rem; }}

.banner {{ background:linear-gradient(135deg,{G_DARK} 0%,{G_MID} 55%,{G_LIGHT} 100%);
           border-radius:16px; padding:1.4rem 2rem; color:{WHITE}; margin-bottom:1.2rem; }}
.banner-title {{ font-size:1rem; font-weight:700; opacity:.8; margin-bottom:.2rem; }}
.banner-stat  {{ font-size:2.4rem; font-weight:900; line-height:1.1; }}
.banner-note  {{ font-size:.75rem; opacity:.65; margin-top:.25rem; }}

.pill {{ display:inline-block; padding:.18rem .65rem; border-radius:20px;
         font-size:.72rem; font-weight:700; }}

.tbl {{ width:100%; border-collapse:collapse; font-size:.83rem; }}
.tbl th {{ background:{BG}; color:{MUTED}; font-size:.67rem; font-weight:700;
           text-transform:uppercase; letter-spacing:.06em;
           padding:.55rem .75rem; text-align:left; border-bottom:2px solid {BORDER}; }}
.tbl td {{ padding:.55rem .75rem; border-bottom:1px solid {BORDER}; color:{DARK};
           vertical-align:middle; }}
.tbl tr:last-child td {{ border-bottom:none; }}
.tbl tr:hover td {{ background:{BG}; }}

.sbar-wrap {{ display:flex; align-items:center; gap:.4rem; }}
.sbar-bg   {{ flex:1; height:5px; background:{BORDER}; border-radius:3px; overflow:hidden; }}
.sbar-fill {{ height:100%; border-radius:3px; }}
.snum      {{ font-weight:700; font-size:.79rem; color:{G_DARK}; min-width:2rem; text-align:right; }}

.dim-bar  {{ display:flex; align-items:center; gap:.5rem; margin-bottom:.45rem; }}
.dim-icon {{ font-size:.95rem; width:1.4rem; }}
.dim-name {{ font-size:.73rem; font-weight:600; color:{DARK}; width:7.5rem; flex-shrink:0; }}
.dim-bg   {{ flex:1; height:7px; background:{BORDER}; border-radius:4px; overflow:hidden; }}
.dim-fill {{ height:100%; border-radius:4px; }}
.dim-num  {{ font-size:.73rem; font-weight:700; color:{DARK}; width:2rem; text-align:right; }}

.tier-priority  {{ background:#FEE2E2; color:#991B1B; }}
.tier-emerging  {{ background:#FEF3C7; color:#92400E; }}
.tier-developing{{ background:{G_PALE}; color:{G_DARK}; }}

#MainMenu, footer, header {{ visibility:hidden; }}

/* ── Sidebar: always visible, non-collapsible ── */
[data-testid="stSidebar"] {{
    min-width: 17rem !important;
    transform: none !important;
    visibility: visible !important;
    display: block !important;
    margin-left: 0 !important;
}}
[data-testid="stSidebar"][aria-expanded="false"] {{
    min-width: 17rem !important;
    transform: none !important;
    margin-left: 0 !important;
}}
/* Hide ALL sidebar control buttons — collapse arrow, header buttons, etc. */
[data-testid="stSidebar"] button,
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}

/* ── Fix: force sidebar text visible regardless of Streamlit theme ── */
[data-testid="stSidebar"] {{ color:{DARK}; }}
[data-testid="stSidebar"] label {{ color:{DARK} !important; }}
[data-testid="stSidebar"] label p {{ color:{DARK} !important; }}
[data-testid="stSidebar"] p {{ color:{DARK} !important; }}
[data-testid="stSidebar"] span {{ color:{DARK}; }}
[data-testid="stSidebar"] .stRadio label {{ color:{DARK} !important; }}
[data-testid="stSidebar"] div[role="radiogroup"] label p {{ color:{DARK} !important; }}
[data-testid="stSidebar"] .stSelectbox label {{ color:{DARK} !important; }}
[data-testid="stSidebar"] .stSlider label {{ color:{DARK} !important; }}
[data-testid="stSidebar"] hr {{ border-color:{BORDER}; }}
</style>""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────
def _get_neon_engine():
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


def _opp_score(df: pd.DataFrame) -> str:
    """Return column to use as composite opportunity score."""
    return "opportunity_score" if "opportunity_score" in df.columns else "overall_risk_score"


def _has_dims(df: pd.DataFrame) -> bool:
    return "dim_disease_burden" in df.columns


def _get_intervention(row: pd.Series) -> str:
    if "recommended_intervention" in row.index and pd.notna(row.get("recommended_intervention")):
        return str(row["recommended_intervention"])
    # Fallback from signals
    signals = {
        "Payer Partnership Program":          row.get("diagnostic_orphan_ratio", 0),
        "Pharmacy-Based Screening":           row.get("otc_proxy_score", 0),
        "Community Health Center Partnership":row.get("geo_burden_index_scaled", 0),
        "Digital Health Program":             row.get("hcp_symptom_rx_ratio", 0),
    }
    return max(signals, key=signals.get)


def _tier_pill(tier) -> str:
    tier = str(tier) if pd.notna(tier) else "Developing"
    cls  = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
    return f'<span class="pill {cls}">{tier}</span>'


def _compute_fallback_dims(df: pd.DataFrame) -> pd.DataFrame:
    """Estimate 7 dimension scores from XGBoost signals when open-data pipeline hasn't run.
    Uses whatever signal columns exist in scores.parquet to produce reasonable proxies."""
    out = df.copy()

    def _norm(s: pd.Series) -> pd.Series:
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series(50.0, index=s.index)
        return (100.0 * (s - mn) / (mx - mn)).clip(0, 100)

    base    = _norm(out.get("overall_risk_score",  pd.Series(50.0, index=out.index)))
    otc     = _norm(out["otc_proxy_score"])           if "otc_proxy_score"           in out.columns else base.copy()
    orphan  = _norm(out["diagnostic_orphan_ratio"])   if "diagnostic_orphan_ratio"   in out.columns else base.copy()
    hcp     = _norm(out["hcp_symptom_rx_ratio"])      if "hcp_symptom_rx_ratio"      in out.columns else base.copy()
    geo     = _norm(out["geo_burden_index_scaled"])   if "geo_burden_index_scaled"   in out.columns else base.copy()
    ses     = _norm(out["ses_disadvantage_index"])    if "ses_disadvantage_index"    in out.columns else base.copy()

    out["dim_disease_burden"]       = (0.55 * base   + 0.30 * otc    + 0.15 * geo).clip(0, 100)
    out["dim_diagnosis_gap"]        = (0.45 * orphan + 0.35 * base   + 0.20 * otc).clip(0, 100)
    out["dim_access_to_care"]       = (100 - 0.50 * geo - 0.30 * ses + 0.20 * base).clip(0, 100)
    out["dim_social_determinants"]  = (0.60 * ses    + 0.40 * geo).clip(0, 100)
    out["dim_payer_landscape"]      = (0.50 * otc    + 0.50 * hcp).clip(0, 100)
    out["dim_commercial_readiness"] = (0.45 * hcp    + 0.35 * otc    + 0.20 * (100 - ses)).clip(0, 100)
    out["dim_trajectory"]           = (0.50 * base   + 0.30 * orphan + 0.20 * geo).clip(0, 100)

    weights  = [0.20, 0.25, 0.15, 0.15, 0.10, 0.10, 0.05]
    dim_cols = ["dim_disease_burden", "dim_diagnosis_gap", "dim_access_to_care",
                "dim_social_determinants", "dim_payer_landscape",
                "dim_commercial_readiness", "dim_trajectory"]
    out["opportunity_score"] = sum(w * out[c] for w, c in zip(weights, dim_cols))
    out["opportunity_tier"]  = pd.cut(
        out["opportunity_score"], bins=[0, 40, 70, 100],
        labels=["Developing", "Emerging", "Priority"], include_lowest=True,
    ).astype(str)
    out["recommended_intervention"] = out.apply(
        lambda r: (
            "Payer Partnership Program"          if r.get("dim_payer_landscape", 0)   >= 65 else
            "Community Health Center Partnership" if r.get("dim_social_determinants", 0) >= 60 else
            "Employer Wellness Program"           if r.get("dim_commercial_readiness", 0) >= 60 else
            "Digital Health Program"              if r.get("dim_commercial_readiness", 0) >= 50 else
            "Pharmacy-Based Screening"
        ), axis=1,
    )
    out["priority_rank"] = out["opportunity_score"].rank(ascending=False).astype(int)
    return out


def _ensure_dims(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with dimension columns guaranteed — real if available, fallback otherwise."""
    if _has_dims(df):
        return df
    return _compute_fallback_dims(df)


def _ensure_payer(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Return (df_with_payer_cols, is_synthetic).
    Synthesises realistic county-level payer mix when CMS data hasn't been ingested.
    Rates are seeded from SES signals so high-deprivation counties skew Medicaid-heavy,
    consistent with published CMS county benchmarks."""
    payer_cols = ["ma_penetration_rate", "medicaid_rate", "commercial_rate"]
    if all(c in df.columns for c in payer_cols):
        return df, False

    out = df.copy()
    rng = np.random.default_rng(42)
    n   = len(out)

    # Normalise SES disadvantage if available; else flat mid-point
    if "ses_disadvantage_index" in out.columns:
        s = out["ses_disadvantage_index"]
        ses_n = ((s - s.min()) / (s.max() - s.min() + 1e-6)).values
    else:
        ses_n = np.full(n, 0.5)

    # MA penetration: national avg ~38 %, higher in high-SES (older, Medicare pop)
    out["ma_penetration_rate"] = np.clip(
        0.38 + 0.06 * (1 - ses_n) + 0.08 * rng.standard_normal(n), 0.10, 0.72
    )
    # Medicaid: national avg ~18 %, higher in high-SES-disadvantage counties
    out["medicaid_rate"] = np.clip(
        0.18 + 0.16 * ses_n + 0.04 * rng.standard_normal(n), 0.05, 0.60
    )
    # Commercial: residual, inversely correlated with SES disadvantage
    out["commercial_rate"] = np.clip(
        0.50 - 0.22 * ses_n + 0.04 * rng.standard_normal(n), 0.10, 0.70
    )
    return out, True


def _score_bar(val, color=G_MID) -> str:
    pct = min(float(val or 0), 100)
    return (f'<div class="sbar-wrap"><div class="sbar-bg">'
            f'<div class="sbar-fill" style="width:{pct:.0f}%;background:{color};"></div>'
            f'</div><span class="snum">{pct:.0f}</span></div>')


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(scores: pd.DataFrame):
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:.4rem 0 1.3rem;border-bottom:1px solid {BORDER};margin-bottom:1rem;">
          <div style="font-size:1.55rem;font-weight:900;color:{G_DARK};letter-spacing:-.01em;">🔬 SPPF</div>
          <div style="font-size:.82rem;color:{DARK};font-weight:600;margin-top:3px;line-height:1.4;">
            Silent Patient Pool Finder
          </div>
          <div style="font-size:.72rem;color:{G_LIGHT};font-weight:700;margin-top:1px;">
            IQVIA Market Access Intelligence
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"<div class='label' style='margin-bottom:.4rem;'>View</div>", unsafe_allow_html=True)
        view = st.radio("Navigation", [
            "📊  Market Overview",
            "🔭  7-Dimension Analysis",
            "💡  Investment Planner",
            "🗺️  Geographic Intelligence",
            "💳  Payer Landscape",
            "📍  State Drill-Down",
        ], label_visibility="collapsed")

        st.markdown("---")

        # ── Condition filter ──────────────────────────────────────────────────
        st.markdown(f"""
        <div class='label' style='margin-bottom:.2rem;'>Condition (Risk Score)</div>
        <div style='font-size:.64rem;color:{MUTED};margin-bottom:.4rem;line-height:1.5;'>
          Affects risk score column across all views.<br>
          Opportunity Score is always multi-condition.
        </div>""", unsafe_allow_html=True)

        cond_opts = {"All Conditions": "overall", "🩸 Type 2 Diabetes": "t2d",
                     "❤️ Hypertension": "htn", "🦋 Hyperthyroidism": "hyperthyroidism"}
        cond_label = st.selectbox("Condition", list(cond_opts.keys()),
                                  label_visibility="collapsed")
        condition  = cond_opts[cond_label]

        # ── Geography filters ─────────────────────────────────────────────────
        st.markdown(f"<div class='label' style='margin-top:.7rem;margin-bottom:.3rem;'>Geography</div>",
                    unsafe_allow_html=True)

        states = ["All States"] + sorted(scores["state_name"].unique().tolist())
        state  = st.selectbox("State", states)

        # Cascading county dropdown — only appears when a state is selected
        county = "All Counties"
        if state != "All States":
            state_counties = ["All Counties"] + sorted(
                scores[scores["state_name"] == state]["county_name"].unique().tolist()
            )
            county = st.selectbox("County", state_counties)

        # ── Display options ───────────────────────────────────────────────────
        st.markdown(f"<div class='label' style='margin-top:.7rem;margin-bottom:.3rem;'>Display</div>",
                    unsafe_allow_html=True)

        top_n = st.slider("Top N counties", 10, 50, 20, step=5)

        tier_opts = ["All Tiers", "Priority", "Emerging", "Developing"]
        tier_filter = st.selectbox("Opportunity Tier", tier_opts)

        st.markdown("---")
        st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};line-height:1.6;">
          ⚠️ Population-level planning tool only.<br>
          Not a clinical diagnostic instrument.<br>
          All scoring uses synthetic &amp; open data.<br>
          <span style="color:{G_LIGHT};font-weight:600;">v2.0 — 7-Dimension Framework</span>
        </div>""", unsafe_allow_html=True)

    return {
        "view": view.split("  ")[1],
        "condition": condition,
        "cond_label": cond_label,
        "state": state,
        "county": county,
        "top_n": top_n,
        "tier_filter": tier_filter,
    }


# ── View 1: Market Overview ───────────────────────────────────────────────────
def view_market_overview(scores: pd.DataFrame, scores_long: pd.DataFrame,
                          condition: str = "overall", cond_label: str = "All Conditions"):
    scores  = _ensure_dims(scores)
    opp_col = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    total_pool = int(scores["total_estimated_pool"].sum()) if "total_estimated_pool" in scores.columns else 45_700_000
    priority_n = int((scores[opp_col] >= 70).sum())
    emerging_n = int(((scores[opp_col] >= 40) & (scores[opp_col] < 70)).sum())

    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">Total Estimated Undiagnosed Patient Pool — United States</div>
      <div class="banner-stat">{total_pool/1_000_000:.1f}M</div>
      <div class="banner-note">
        Across Type 2 Diabetes, Hypertension &amp; Hyperthyroidism ·
        Scored via 7-Dimension framework ·
        {priority_n:,} Priority + {emerging_n:,} Emerging counties identified
      </div>
    </div>""", unsafe_allow_html=True)

    # KPI strip
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties Scored</div><div class="big-num-w">{len(scores):,}</div><div class="sub-w">US county coverage</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority Markets</div><div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Opportunity Score ≥70</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging Markets</div><div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Score 40–70</div></div>', unsafe_allow_html=True)
    avg_opp = scores[opp_col].mean()
    c4.markdown(f'<div class="card" style="border-top:3px solid {G_LIGHT};"><div class="label">Avg Opportunity Score</div><div class="big-num" style="color:{G_DARK};">{avg_opp:.0f}</div><div class="sub-muted">national baseline</div></div>', unsafe_allow_html=True)
    top_state = scores.groupby("state_name")[opp_col].mean().idxmax()
    c5.markdown(f'<div class="card" style="border-top:3px solid {BLUE};"><div class="label">Top State</div><div style="font-size:1.3rem;font-weight:800;color:{DARK};">{top_state}</div><div class="sub-muted">by avg opp. score</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Condition cards
    col1, col2, col3 = st.columns(3)
    for col, (ckey, meta) in zip([col1, col2, col3], COND_META.items()):
        score_col = f"{ckey}_risk_score"
        high_risk = int((scores[score_col] >= 70).sum()) if score_col in scores.columns else 0
        avg_risk  = scores[score_col].mean() if score_col in scores.columns else 0
        peak_risk = f"{scores[score_col].max():.0f}" if score_col in scores.columns else "—"
        est_pool  = f"{meta['national_pool']/1_000_000:.1f}M"
        col.markdown(f"""
        <div class="card" style="border-top:3px solid {meta['color']};">
          <div class="label">{meta['label']}</div>
          <div class="big-num">{est_pool}</div>
          <div class="sub" style="color:{meta['color']};">estimated undiagnosed nationally</div>
          <hr style="border:none;border-top:1px solid {BORDER};margin:.7rem 0;">
          <div style="display:flex;gap:1rem;">
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{high_risk}</div>
              <div style="font-size:.67rem;color:{MUTED};">priority counties</div>
            </div>
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{avg_risk:.0f}</div>
              <div style="font-size:.67rem;color:{MUTED};">avg risk score</div>
            </div>
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{peak_risk}</div>
              <div style="font-size:.67rem;color:{MUTED};">peak score</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Opportunity distribution + intervention mix
    col_hist, col_interv = st.columns([1.4, 1])

    with col_hist:
        st.markdown('<div class="ch"><div class="sec-head">Opportunity Score Distribution</div>'
                    '<div class="sec-sub">How the 3,000+ US counties distribute across the 0–100 opportunity scale</div></div>',
                    unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=scores[opp_col],
            nbinsx=40,
            marker=dict(
                color=scores[opp_col],
                colorscale=[[0, G_PALE], [0.4, G_LIGHT], [0.7, G_MID], [1, G_DARK]],
                showscale=False,
            ),
            hovertemplate="Score %{x:.0f}: %{y} counties<extra></extra>",
        ))
        fig.add_vline(x=40, line=dict(dash="dot", color=AMBER, width=1.5),
                      annotation_text="Emerging", annotation_position="top right",
                      annotation_font_size=10, annotation_font_color=AMBER)
        fig.add_vline(x=70, line=dict(dash="dot", color=RED, width=1.5),
                      annotation_text="Priority", annotation_position="top right",
                      annotation_font_size=10, annotation_font_color=RED)
        fig.update_layout(
            xaxis=dict(title="Opportunity Score", range=[0, 100]),
            yaxis=dict(title="Number of Counties"),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=0, t=20, b=30), height=260,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_interv:
        st.markdown('<div class="ch"><div class="sec-head">Recommended Interventions</div>'
                    '<div class="sec-sub">What program type does each county need?</div></div>',
                    unsafe_allow_html=True)

        if "recommended_intervention" in scores.columns:
            mix = scores["recommended_intervention"].value_counts()
        else:
            # Fallback: derive from long signals
            long_agg = (
                scores_long.groupby("county_fips")[
                    ["otc_proxy_score","diagnostic_orphan_ratio",
                     "hcp_symptom_rx_ratio","geo_burden_index_scaled"]
                ].mean().reset_index()
            )
            long_agg["recommended_intervention"] = long_agg.apply(_get_intervention, axis=1)
            merged = scores[["county_fips"]].merge(long_agg[["county_fips","recommended_intervention"]], on="county_fips", how="left")
            mix = merged["recommended_intervention"].value_counts()

        colors_pie = [INTERV_META.get(i, {}).get("color", G_MID) for i in mix.index]
        fig2 = go.Figure(go.Pie(
            labels=mix.index, values=mix.values,
            hole=0.55, marker_colors=colors_pie,
            textinfo="percent", textfont_size=11,
        ))
        fig2.update_layout(
            margin=dict(l=0,r=0,t=0,b=0), height=180,
            paper_bgcolor="white", showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

        for iname, cnt in mix.items():
            meta = INTERV_META.get(str(iname), {"color": G_MID, "icon": "•"})
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:.45rem;margin-bottom:.3rem;">
              <div style="width:8px;height:8px;border-radius:50%;background:{meta['color']};flex-shrink:0;"></div>
              <div style="font-size:.73rem;color:{DARK};">{meta['icon']} {iname}</div>
              <div style="margin-left:auto;font-size:.73rem;font-weight:700;color:{DARK};">{cnt}</div>
            </div>""", unsafe_allow_html=True)

    # Patient funnel
    st.markdown('<div class="ch"><div class="sec-head">Patient Identification Funnel</div>'
                '<div class="sec-sub">From total adult population to actionable screening opportunity</div></div>',
                unsafe_allow_html=True)

    funnel_labels = ["US Adult Population", "Estimated Prevalence\n(T2D+HTN+Hypo)",
                     "Estimated Undiagnosed", "Observable via Proxy Signals", "Actionable via Programs"]
    funnel_vals   = [258, 84, 45.7, 18, 8]
    fig3 = go.Figure(go.Funnel(
        y=[l.replace("\n"," ") for l in funnel_labels],
        x=funnel_vals,
        textinfo="value+percent initial",
        texttemplate="%{value}M (%{percentInitial})",
        textfont=dict(size=12),
        marker=dict(color=[G_DARK, G_MID, G_LIGHT, "#7EBBEE", "#B3D9F0"]),
    ))
    fig3.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=240,
        plot_bgcolor="white", paper_bgcolor="white", showlegend=False,
    )
    st.plotly_chart(fig3, use_container_width=True)


# ── View 2: 7-Dimension Analysis ─────────────────────────────────────────────
def view_7d_analysis(scores: pd.DataFrame, state: str, top_n: int,
                      condition: str = "overall", cond_label: str = "All Conditions"):
    using_fallback = not _has_dims(scores)
    scores = _ensure_dims(scores)
    if using_fallback:
        st.info("📊 Showing **estimated** dimension scores (derived from model signals). "
                "Run `python3 run.py --skip-data --skip-train` to load full open-data scores "
                "(CDC PLACES, Census ACS, HRSA, CMS).")

    opp_col   = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    sort_col  = score_col if score_col in scores.columns else opp_col

    filtered = scores.copy()
    if state != "All States":
        filtered = filtered[filtered["state_name"] == state]

    top = filtered.nlargest(min(top_n, len(filtered)), sort_col)

    dim_cols = [f"dim_{k}" for k in DIM_LABELS]

    # National dimension averages
    st.markdown('<div class="sec-head">National Dimension Profile</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Average score across all US counties for each of the 7 dimensions</div>', unsafe_allow_html=True)

    col_radar, col_bars = st.columns([1, 1])

    with col_radar:
        st.markdown('<div class="ch"><div class="sec-head">National Radar</div>'
                    '<div class="sec-sub">All counties vs. top opportunity counties</div></div>',
                    unsafe_allow_html=True)
        dim_avgs_national = scores[dim_cols].mean()
        dim_avgs_top      = top[dim_cols].mean()

        labels = [DIM_LABELS[k] for k in DIM_LABELS]
        r_nat  = [dim_avgs_national[f"dim_{k}"] for k in DIM_LABELS]
        r_top  = [dim_avgs_top[f"dim_{k}"] for k in DIM_LABELS]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=r_nat + [r_nat[0]], theta=labels + [labels[0]],
            fill='toself', name='All Counties',
            line=dict(color=BORDER, width=1.5),
            fillcolor=f"rgba(0,169,224,0.1)",
        ))
        fig.add_trace(go.Scatterpolar(
            r=r_top + [r_top[0]], theta=labels + [labels[0]],
            fill='toself', name=f'Top {len(top)}',
            line=dict(color=G_DARK, width=2),
            fillcolor=f"rgba(0,48,135,0.2)",
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], tickfont_size=9),
                angularaxis=dict(tickfont_size=10),
            ),
            showlegend=True,
            legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center", font_size=11),
            margin=dict(l=30,r=30,t=30,b=50), height=360,
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_bars:
        # Build all bars in ONE markdown call so the card wrapper encloses its content
        bars_html = (
            f'<div class="card"><div class="sec-head">Dimension Breakdown</div>'
            f'<div style="font-size:.67rem;color:{MUTED};margin-bottom:.65rem;margin-top:.15rem;">'
            f'  <span style="border-left:2px solid {MUTED};padding-left:4px;margin-right:.7rem;">national avg</span>'
            f'  <span style="font-weight:600;color:{DARK};">● top {len(top)} score &nbsp; +/− vs national</span>'
            f'</div>'
        )
        for k in DIM_LABELS:
            col_key  = f"dim_{k}"
            nat_val  = dim_avgs_national[col_key]
            top_val  = dim_avgs_top[col_key]
            color    = DIM_COLORS[k]
            icon     = DIM_ICONS[k]
            delta    = top_val - nat_val
            delta_str   = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
            delta_color = "#16a34a" if delta >= 0 else "#dc2626"
            bars_html += f"""
            <div class="dim-bar">
              <div class="dim-icon">{icon}</div>
              <div class="dim-name">{DIM_LABELS[k]}</div>
              <div style="flex:1;display:flex;align-items:center;gap:.35rem;">
                <div class="dim-bg" style="flex:1;position:relative;">
                  <div class="dim-fill" style="width:{top_val:.0f}%;background:{color};"></div>
                  <div style="position:absolute;top:-4px;bottom:-4px;left:{nat_val:.0f}%;width:3px;background:#000000;border-radius:1px;"></div>
                </div>
                <div class="dim-num">{top_val:.0f}</div>
                <div style="font-size:.67rem;width:2.4rem;text-align:right;color:{delta_color};font-weight:700;">{delta_str}</div>
              </div>
            </div>"""
        bars_html += '</div>'
        st.markdown(bars_html, unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # County-level dimension heatmap
    st.markdown(
        f'<div class="ch"><div class="sec-head">Top {len(top)} Counties — Dimension Heatmap</div>'
        f'<div class="sec-sub">Each row = a county · Each column = one of the 7 dimensions · Darker = stronger signal</div></div>',
        unsafe_allow_html=True)

    hm_data = top[["county_name", "state_name"] + dim_cols].head(25).copy()
    hm_data["state_abbr"]   = hm_data["state_name"].map(STATE_ABBREV).fillna(hm_data["state_name"].str[:2].str.upper())
    hm_data["county_label"] = hm_data["county_name"] + ", " + hm_data["state_abbr"]

    hm_raw = hm_data[dim_cols].values.astype(float)

    # Per-column normalise for colour (so every column uses the full warm→navy range)
    hm_norm = hm_raw.copy()
    for j in range(hm_norm.shape[1]):
        col = hm_norm[:, j]
        mn, mx = col.min(), col.max()
        hm_norm[:, j] = 100 * (col - mn) / (mx - mn) if mx > mn else np.full_like(col, 50.0)

    def _cell_color(norm_v: float):
        """Diverging cell bg + text color. norm_v = 0–100 (relative rank in column)."""
        v = max(0.0, min(1.0, norm_v / 100.0))
        if v < 0.5:
            t = v * 2
            r = int(0xF5 + (0xDE - 0xF5) * t)
            g = int(0xC6 + (0xEE - 0xC6) * t)
            b = int(0xA0 + (0xF9 - 0xA0) * t)
            txt = "#7A2A0A" if v < 0.25 else "#5A7A9B"
        else:
            t = (v - 0.5) * 2
            r = int(0xDE + (0x00 - 0xDE) * t)
            g = int(0xEE + (0x30 - 0xEE) * t)
            b = int(0xF9 + (0x87 - 0xF9) * t)
            txt = "#003087" if t < 0.4 else "#FFFFFF"
        return f"#{r:02X}{g:02X}{b:02X}", txt

    # Build HTML table
    dim_keys = list(DIM_LABELS.keys())
    th_style = (f"padding:7px 10px;font-size:.7rem;font-weight:600;color:{MUTED};"
                f"text-align:center;border-bottom:2px solid {BORDER};white-space:nowrap;")
    td_county = (f"padding:6px 10px;font-size:.76rem;color:{DARK};font-weight:500;"
                 f"border-bottom:1px solid {BORDER};white-space:nowrap;")
    html = (
        f'<div style="overflow-x:auto;">'
        f'<table style="width:100%;border-collapse:collapse;font-family:sans-serif;">'
        f'<thead><tr>'
        f'<th style="{th_style}text-align:left;"></th>'
    )
    for k in dim_keys:
        tip = DIM_TOOLTIPS[k].replace('"', '&quot;')
        html += (
            f'<th style="{th_style}">'
            f'{DIM_ICONS[k]} {DIM_SHORT[k]}&nbsp;'
            f'<span title="{tip}" style="cursor:help;color:{G_LIGHT};'
            f'font-size:.72rem;font-weight:400;vertical-align:middle;">ℹ</span>'
            f'</th>'
        )
    html += '</tr></thead><tbody>'

    for row_i, row in enumerate(hm_data.itertuples()):
        html += f'<tr><td style="{td_county}">{row.county_label}</td>'
        for col_j, k in enumerate(dim_keys):
            raw_val  = hm_raw[row_i, col_j]
            norm_val = hm_norm[row_i, col_j]
            bg, txt  = _cell_color(norm_val)
            html += (f'<td style="padding:6px 8px;text-align:center;font-size:.78rem;'
                     f'font-weight:700;background:{bg};color:{txt};'
                     f'border-bottom:1px solid {BORDER};">'
                     f'{raw_val:.0f}</td>')
        html += '</tr>'

    html += (
        '</tbody></table></div>'
        f'<div style="font-size:.67rem;color:{MUTED};margin-top:.4rem;">'
        f'  Color = relative rank within shown counties per dimension &nbsp;·&nbsp;'
        f'  Navy = strongest &nbsp;·&nbsp; Warm = weakest'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ── View 3: Investment Planner ────────────────────────────────────────────────
def view_investment_planner(scores: pd.DataFrame, scores_long: pd.DataFrame,
                             condition: str, state: str, top_n: int, tier_filter: str):
    scores = _ensure_dims(scores)
    opp_col = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"

    # Build intervention column
    if "recommended_intervention" not in scores.columns:
        long_agg = (
            scores_long.groupby("county_fips")[
                ["otc_proxy_score","diagnostic_orphan_ratio","hcp_symptom_rx_ratio","geo_burden_index_scaled"]
            ].mean().reset_index()
        )
        long_agg["recommended_intervention"] = long_agg.apply(_get_intervention, axis=1)
        scored = scores.merge(long_agg[["county_fips","recommended_intervention"]], on="county_fips", how="left")
    else:
        scored = scores.copy()

    # Filters
    if state != "All States":
        scored = scored[scored["state_name"] == state]
    if "opportunity_tier" in scored.columns and tier_filter != "All Tiers":
        scored = scored[scored["opportunity_tier"] == tier_filter]

    top = scored.nlargest(min(top_n, len(scored)), opp_col).copy()

    # Summary KPIs
    total_pool = int(top["total_estimated_pool"].sum()) if "total_estimated_pool" in top.columns else 0
    lead_interv = top["recommended_intervention"].value_counts().idxmax() if len(top) > 0 else "—"
    lead_meta   = INTERV_META.get(str(lead_interv), {"color": G_MID, "icon": "•"})

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties in Plan</div><div class="big-num-w">{len(top)}</div><div class="sub-w">filtered selection</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><div class="label">Est. Undiagnosed Pool</div><div class="big-num">{total_pool:,}</div><div class="sub">within selected counties</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card"><div class="label">Avg Opportunity Score</div><div class="big-num">{top[opp_col].mean():.0f}</div><div class="sub-muted">out of 100</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-left:3px solid {lead_meta["color"]};"><div class="label">Lead Program Type</div><div style="font-size:1rem;font-weight:800;color:{DARK};margin:.2rem 0;">{lead_meta["icon"]} {lead_interv}</div><div class="sub-muted">most common</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Intervention breakdown + return estimate
    col_prog, col_roi = st.columns([1, 1])

    with col_prog:
        st.markdown('<div class="ch"><div class="sec-head">Program Mix Recommendation</div>'
                    '<div class="sec-sub">Which program type to deploy in each priority county</div></div>',
                    unsafe_allow_html=True)

        prog_counts = top["recommended_intervention"].value_counts().reset_index()
        prog_counts.columns = ["program", "counties"]
        prog_counts["color"] = prog_counts["program"].map(lambda x: INTERV_META.get(x, {}).get("color", G_MID))

        fig = go.Figure(go.Bar(
            x=prog_counts["counties"],
            y=prog_counts["program"],
            orientation="h",
            marker_color=prog_counts["color"],
            text=prog_counts["counties"],
            textposition="outside",
            textfont=dict(size=12),
        ))
        fig.update_layout(
            xaxis=dict(title="Number of Counties", showgrid=True, gridcolor=BORDER),
            yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=40, t=10, b=30), height=280,
        )
        st.plotly_chart(fig, use_container_width=True)

        for _, prow in prog_counts.iterrows():
            meta = INTERV_META.get(str(prow["program"]), {"color":G_MID,"icon":"•","desc":""})
            st.markdown(f"""
            <div style="border-left:3px solid {meta['color']};padding-left:.7rem;margin-bottom:.6rem;">
              <div style="font-size:.75rem;font-weight:700;color:{DARK};">{meta['icon']} {prow['program']}</div>
              <div style="font-size:.7rem;color:{MUTED};margin-top:2px;">{meta['desc']}</div>
            </div>""", unsafe_allow_html=True)

    with col_roi:
        st.markdown('<div class="ch"><div class="sec-head">Estimated Screening Yield</div>'
                    '<div class="sec-sub">Patients newly diagnosed per 1,000 screened by program type (literature benchmarks)</div></div>',
                    unsafe_allow_html=True)

        roi_data = pd.DataFrame({
            "Program": ["Payer Partnership Program", "Community Health Center Partnership",
                         "Pharmacy-Based Screening", "Employer Wellness Program", "Digital Health Program"],
            "Yield per 1k": [142, 98, 76, 54, 38],
            "Cost per dx ($)": [280, 350, 220, 480, 390],
            "Scalability": [4, 3, 5, 3, 4],
        })
        roi_data["color"] = roi_data["Program"].map(lambda x: INTERV_META.get(x, {}).get("color", G_MID))

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            name="Yield / 1k screened",
            x=roi_data["Program"],
            y=roi_data["Yield per 1k"],
            marker_color=roi_data["color"],
            yaxis="y1",
        ))
        fig2.add_trace(go.Scatter(
            name="Cost per dx ($)",
            x=roi_data["Program"],
            y=roi_data["Cost per dx ($)"],
            mode="lines+markers",
            line=dict(color=DARK, width=2, dash="dot"),
            marker=dict(size=8, color=DARK),
            yaxis="y2",
        ))
        fig2.update_layout(
            xaxis=dict(tickangle=-20, tickfont_size=10),
            yaxis=dict(title="Yield per 1,000", showgrid=True, gridcolor=BORDER),
            yaxis2=dict(title="Cost per dx ($)", overlaying="y", side="right",
                        showgrid=False, range=[0, 700]),
            legend=dict(orientation="h", y=1.1, font_size=10),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=40, t=20, b=80), height=280,
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('<div style="font-size:.7rem;color:{MUTED};margin-top:.5rem;">⚠️ Yield figures based on published screening program literature. Actual results vary by market.</div>'.format(MUTED=MUTED), unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Priority county table
    st.markdown('<div class="ch"><div class="sec-head">Priority County Investment List</div>'
                '<div class="sec-sub">Ranked by composite opportunity score. Use this to brief market access teams and payer strategy leads.</div></div>',
                unsafe_allow_html=True)

    rows_html = ""
    for i, (_, row) in enumerate(top.iterrows()):
        opp_val  = row[opp_col]
        risk_val = row.get(score_col, opp_val)
        pool_str = f"{int(row['total_estimated_pool']):,}" if pd.notna(row.get('total_estimated_pool')) else "—"
        rural    = "🌾" if row.get("is_rural") else "🏙️"
        interv   = str(row.get("recommended_intervention", "—"))
        imeta    = INTERV_META.get(interv, {"color": G_MID, "icon": "•"})
        tier_val = row.get("opportunity_tier", "—")

        # Dimension mini-bars (if available)
        dim_mini = ""
        if _has_dims(top):
            dim_mini = '<div style="display:flex;gap:2px;margin-top:3px;">'
            for k in DIM_LABELS:
                v = row.get(f"dim_{k}", 50)
                c = DIM_COLORS[k]
                h = max(3, int((v / 100) * 16))
                dim_mini += f'<div title="{DIM_LABELS[k]}: {v:.0f}" style="width:5px;height:{h}px;background:{c};border-radius:1px;align-self:flex-end;"></div>'
            dim_mini += '</div>'

        rows_html += f"""<tr>
          <td style="font-weight:700;color:{MUTED};">{i+1}</td>
          <td>
            <div style="font-weight:700;color:{DARK};">{row['county_name']}</div>
            <div style="font-size:.7rem;color:{MUTED};">{rural} {row['state_name']}</div>
            {dim_mini}
          </td>
          <td style="font-size:.78rem;color:{MUTED};">{int(row['population']):,}</td>
          <td>{_score_bar(opp_val, G_DARK)}</td>
          <td>{_score_bar(risk_val, COND_META.get(condition,{}).get('color',G_MID))}</td>
          <td>{_tier_pill(tier_val)}</td>
          <td><span style="font-size:.75rem;">{imeta['icon']} {interv}</span></td>
          <td style="font-weight:700;color:{G_DARK};font-size:.82rem;">{pool_str}</td>
        </tr>"""

    st.markdown(f"""<table class="tbl">
      <thead><tr>
        <th>#</th><th>County</th><th>Population</th>
        <th>Opp. Score</th><th>Risk Score</th><th>Tier</th>
        <th>Program</th><th>Est. Pool</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    export_cols = [c for c in ["county_name","state_name","population",opp_col,
                                score_col,"opportunity_tier","recommended_intervention",
                                "total_estimated_pool"] if c in top.columns]
    csv = top[export_cols].to_csv(index=False)
    st.download_button("⬇️  Export investment list (CSV)", csv,
                       file_name=f"sppf_investment_plan.csv", mime="text/csv")


# ── View 4: Geographic Intelligence ──────────────────────────────────────────
def view_geographic(scores: pd.DataFrame, scores_long: pd.DataFrame,
                    condition: str, state: str, geojson):
    scores    = _ensure_dims(scores)
    opp_col   = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    filtered  = scores.copy()
    if state != "All States":
        filtered = filtered[filtered["state_name"] == state]

    cond_label = "All Conditions" if condition == "overall" else COND_META[condition]["label"]
    priority_n = int((filtered[opp_col] >= 70).sum())
    emerging_n = int(((filtered[opp_col] >= 40) & (filtered[opp_col] < 70)).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties Mapped</div><div class="big-num-w">{len(filtered):,}</div><div class="sub-w">{filtered["state_name"].nunique()} states</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority ≥70</div><div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Act now</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging 40–70</div><div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Plan &amp; monitor</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card"><div class="label">Avg Score ({cond_label})</div><div class="big-num">{filtered[score_col].mean():.0f}</div><div class="sub-muted">this view</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    col_map, col_right = st.columns([2.8, 1])

    with col_map:
        st.markdown(f'<div class="card"><div class="sec-head">Opportunity Map — {cond_label}</div><div class="sec-sub">Shading = composite opportunity score. Hover for county profile.</div>', unsafe_allow_html=True)

        # Build intervention mapping
        if "recommended_intervention" not in filtered.columns:
            long_agg = (
                scores_long.groupby("county_fips")[
                    ["otc_proxy_score","diagnostic_orphan_ratio","hcp_symptom_rx_ratio","geo_burden_index_scaled"]
                ].mean().reset_index()
            )
            long_agg["recommended_intervention"] = long_agg.apply(_get_intervention, axis=1)
            map_data = filtered.merge(long_agg[["county_fips","recommended_intervention"]], on="county_fips", how="left")
        else:
            map_data = filtered.copy()

        if geojson:
            hover_extra = {opp_col: ":.0f", score_col: ":.0f",
                           "recommended_intervention": True, "county_fips": False}
            if "opportunity_tier" in map_data.columns:
                hover_extra["opportunity_tier"] = True

            fig = px.choropleth(
                map_data,
                geojson=geojson,
                locations="county_fips",
                color=opp_col,
                color_continuous_scale=[[0, G_PALE],[0.35, G_LIGHT],[0.7, G_MID],[1, G_DARK]],
                range_color=(0, 100),
                scope="usa",
                hover_name="county_name",
                hover_data={"state_name": True, "population": ":,", **hover_extra},
                labels={opp_col: "Opp. Score", score_col: "Risk Score",
                        "recommended_intervention": "Program", "opportunity_tier": "Tier"},
            )
            fig.update_layout(
                margin=dict(r=0,t=0,l=0,b=0),
                paper_bgcolor="white",
                geo=dict(bgcolor="white", lakecolor="#EBF5FB", landcolor=BG),
                coloraxis_colorbar=dict(
                    title="Opp.<br>Score", tickvals=[0,25,50,75,100],
                    thickness=10, len=0.65, bgcolor="white",
                    bordercolor=BORDER, borderwidth=1,
                ),
                height=480,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            state_avg = (filtered.groupby("state_name")[opp_col].mean()
                         .reset_index().sort_values(opp_col, ascending=False).head(20))
            fig = px.bar(state_avg, x="state_name", y=opp_col,
                         color=opp_col, color_continuous_scale=[[0,G_PALE],[1,G_DARK]],
                         labels={"state_name":"","opportunity_score":"Avg Opportunity Score"})
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                               margin=dict(l=0,r=0,t=10,b=0), height=480, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        # Top states
        st.markdown('<div class="card"><div class="sec-head">Top States</div>', unsafe_allow_html=True)
        state_avgs = (filtered.groupby("state_name")[opp_col].mean()
                      .reset_index().sort_values(opp_col, ascending=False).head(10))
        for _, srow in state_avgs.iterrows():
            pct = min(float(srow[opp_col]), 100)
            color = RED if pct >= 70 else (AMBER if pct >= 40 else G_LIGHT)
            st.markdown(f"""
            <div style="margin-bottom:.55rem;">
              <div style="display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:2px;">
                <span style="font-weight:600;color:{DARK};">{srow['state_name']}</span>
                <span style="color:{color};font-weight:700;">{pct:.0f}</span>
              </div>
              <div style="height:5px;background:{BORDER};border-radius:3px;">
                <div style="width:{pct}%;height:100%;background:{color};border-radius:3px;"></div>
              </div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Condition breakdown
        st.markdown('<div class="card"><div class="sec-head">By Condition</div>', unsafe_allow_html=True)
        for ckey, cmeta in COND_META.items():
            col_name = f"{ckey}_risk_score"
            if col_name not in filtered.columns:
                continue
            avg = filtered[col_name].mean()
            hi  = (filtered[col_name] >= 70).sum()
            st.markdown(f"""
            <div style="margin-bottom:.6rem;">
              <div style="display:flex;justify-content:space-between;font-size:.76rem;margin-bottom:2px;">
                <span style="font-weight:600;color:{DARK};">{cmeta['label']}</span>
                <span style="font-size:.7rem;color:{MUTED};">{avg:.0f} avg</span>
              </div>
              <div style="height:5px;background:{BORDER};border-radius:3px;">
                <div style="width:{min(avg,100):.0f}%;height:100%;background:{cmeta['color']};border-radius:3px;"></div>
              </div>
              <div style="font-size:.67rem;color:{MUTED};margin-top:2px;">{hi} high-risk</div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── View 5: Payer Landscape ───────────────────────────────────────────────────
def view_payer_landscape(scores: pd.DataFrame, state: str, top_n: int):
    scores   = _ensure_dims(scores)
    scores, payer_synthetic = _ensure_payer(scores)
    opp_col  = _opp_score(scores)
    filtered = scores.copy()
    if state != "All States":
        filtered = filtered[filtered["state_name"] == state]

    st.markdown('<div class="sec-head">Payer Landscape Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Understand who pays in each market — critical for screening program partnership decisions</div>', unsafe_allow_html=True)

    if payer_synthetic:
        st.info("📊 Showing **estimated** payer mix (SES-calibrated synthetic data). "
                "Run `python3 run.py` to load real CMS county-level payer data.")

    # KPI strip
    ma_avg  = filtered["ma_penetration_rate"].mean() * 100
    med_avg = filtered["medicaid_rate"].mean() * 100
    com_avg = filtered["commercial_rate"].mean() * 100
    ma_high = int((filtered["ma_penetration_rate"] >= 0.45).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-blue"><div class="label-w">Avg MA Penetration</div><div class="big-num-w">{ma_avg:.0f}%</div><div class="sub-w">Medicare Advantage</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {PURPLE};"><div class="label">Avg Medicaid Rate</div><div class="big-num">{med_avg:.0f}%</div><div class="sub-muted">of population</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Avg Commercial Rate</div><div class="big-num">{com_avg:.0f}%</div><div class="sub-muted">employer/individual</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-top:3px solid {BLUE};"><div class="label">High MA Counties</div><div class="big-num">{ma_high}</div><div class="sub" style="color:{BLUE};">≥45% MA penetration</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    col_scatter, col_mix = st.columns([1.5, 1])

    with col_scatter:
        st.markdown('<div class="ch"><div class="sec-head">Payer Mix vs. Opportunity Score</div>'
                    '<div class="sec-sub">Each dot = a county. Size = population. Color = opportunity score.</div></div>',
                    unsafe_allow_html=True)

        plot_data = filtered.nlargest(min(500, len(filtered)), opp_col).copy()
        plot_data["ma_pct"]  = plot_data["ma_penetration_rate"] * 100
        plot_data["med_pct"] = plot_data["medicaid_rate"] * 100

        fig = px.scatter(
            plot_data,
            x="ma_pct", y="med_pct",
            color=opp_col,
            color_continuous_scale=[[0,G_PALE],[0.35,G_LIGHT],[0.7,G_MID],[1,G_DARK]],
            size="population",
            size_max=20,
            hover_name="county_name",
            hover_data={"state_name": True, opp_col: ":.0f", "ma_pct":":.0f", "med_pct":":.0f", "population":":,"},
            labels={"ma_pct":"Medicare Advantage %","med_pct":"Medicaid %", opp_col:"Opp. Score"},
        )
        # Quadrant lines
        fig.add_hline(y=med_avg, line=dict(dash="dot", color=MUTED, width=1))
        fig.add_vline(x=ma_avg,  line=dict(dash="dot", color=MUTED, width=1))

        # Quadrant labels
        fig.add_annotation(x=ma_avg+15, y=med_avg+8, text="High MA + High Medicaid<br>(Dual incentive)", showarrow=False, font=dict(size=9, color=DARK))
        fig.add_annotation(x=ma_avg+15, y=med_avg-8, text="High MA + Commercial<br>(Employer + payer)", showarrow=False, font=dict(size=9, color=DARK))

        fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0,r=0,t=10,b=30), height=380,
            coloraxis_colorbar=dict(title="Opp.", thickness=10, len=0.6,
                                    bgcolor="white", bordercolor=BORDER, borderwidth=1),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_mix:
        st.markdown('<div class="ch"><div class="sec-head">National Payer Mix</div>'
                    '<div class="sec-sub">Average payer distribution across all counties in view</div></div>',
                    unsafe_allow_html=True)

        fig2 = go.Figure(go.Pie(
            labels=["Medicare Advantage", "Medicaid", "Commercial", "Other/Uninsured"],
            values=[ma_avg, med_avg, com_avg, max(0, 100-ma_avg-med_avg-com_avg)],
            hole=0.55,
            marker=dict(colors=[BLUE, PURPLE, AMBER, BORDER]),
            textinfo="percent+label",
            textfont=dict(size=11),
        ))
        fig2.update_layout(
            margin=dict(l=0,r=0,t=0,b=0), height=260,
            paper_bgcolor="white", showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown(f"""
        <div style="margin-top:.5rem;">
          <div style="font-size:.78rem;font-weight:700;color:{DARK};margin-bottom:.5rem;">Program Fit by Payer Mix</div>
          <div style="border-left:3px solid {BLUE};padding-left:.7rem;margin-bottom:.5rem;">
            <div style="font-size:.73rem;font-weight:700;color:{DARK};">💳 MA Penetration ≥40%</div>
            <div style="font-size:.7rem;color:{MUTED};">→ Payer Partnership Program (Stars bonus)</div>
          </div>
          <div style="border-left:3px solid {PURPLE};padding-left:.7rem;margin-bottom:.5rem;">
            <div style="font-size:.73rem;font-weight:700;color:{DARK};">🏘️ Medicaid Rate ≥25%</div>
            <div style="font-size:.7rem;color:{MUTED};">→ FQHC / Community Health Partnership</div>
          </div>
          <div style="border-left:3px solid {AMBER};padding-left:.7rem;">
            <div style="font-size:.73rem;font-weight:700;color:{DARK};">🏢 Commercial Rate ≥40%</div>
            <div style="font-size:.7rem;color:{MUTED};">→ Employer Wellness or Digital Health</div>
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Top MA penetration counties
        st.markdown('<div class="ch"><div class="sec-head">Top MA Counties</div></div>', unsafe_allow_html=True)
        top_ma = (filtered.nlargest(min(top_n//2, 8), "ma_penetration_rate")
                  [["county_name","state_name","ma_penetration_rate",opp_col]].copy())
        for _, mrow in top_ma.iterrows():
            ma_val  = mrow["ma_penetration_rate"] * 100
            opp_val = mrow[opp_col]
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        margin-bottom:.4rem;padding-bottom:.4rem;border-bottom:1px solid {BORDER};">
              <div>
                <div style="font-size:.78rem;font-weight:600;color:{DARK};">{mrow['county_name']}</div>
                <div style="font-size:.68rem;color:{MUTED};">{mrow['state_name']}</div>
              </div>
              <div style="text-align:right;">
                <div style="font-size:.83rem;font-weight:700;color:{BLUE};">{ma_val:.0f}% MA</div>
                <div style="font-size:.68rem;color:{MUTED};">Opp: {opp_val:.0f}</div>
              </div>
            </div>""", unsafe_allow_html=True)


# ── County Scorecard Helper ───────────────────────────────────────────────────
def _render_county_scorecard(row: pd.Series, opp_col: str,
                              score_col: str, cond_label: str):
    """Full-width deep-dive card for one county."""
    opp_val  = row[opp_col]
    risk_val = row.get(score_col, opp_val)
    pool_str = f"{int(row['total_estimated_pool']):,}" if pd.notna(row.get("total_estimated_pool")) else "—"
    interv   = str(row.get("recommended_intervention", "Pharmacy-Based Screening"))
    imeta    = INTERV_META.get(interv, {"color": G_MID, "icon": "•", "desc": ""})

    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">County Deep Dive</div>
      <div class="banner-stat">{row['county_name']}, {row.get('state_name','')}</div>
      <div class="banner-note">
        {'🌾 Rural' if row.get('is_rural') else '🏙️ Urban / Suburban'} &nbsp;·&nbsp;
        Population: {row['population']:,} &nbsp;·&nbsp; Est. Undiagnosed Pool: {pool_str}
      </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"""<div class="card-dark">
      <div class="label-w">Opportunity Score</div>
      <div class="big-num-w">{opp_val:.0f}</div>
      <div class="sub-w">out of 100</div></div>""", unsafe_allow_html=True)
    c2.markdown(f"""<div class="card" style="border-top:3px solid {DIM_COLORS['diagnosis_gap']};">
      <div class="label">Risk Score ({cond_label})</div>
      <div class="big-num">{risk_val:.0f}</div>
      <div class="sub-muted">out of 100</div></div>""", unsafe_allow_html=True)
    c3.markdown(f"""<div class="card" style="border-top:3px solid {imeta['color']};">
      <div class="label">Recommended Program</div>
      <div style="font-size:.9rem;font-weight:700;color:{imeta['color']};margin-top:.3rem;">
        {imeta['icon']} {interv}</div></div>""", unsafe_allow_html=True)
    c4.markdown(f"""<div class="card">
      <div class="label">Opportunity Tier</div>
      <div style="margin-top:.4rem;">{_tier_pill(row.get('opportunity_tier','Developing'))}</div>
      <div class="sub-muted" style="margin-top:.4rem;">Est. pool: {pool_str}</div></div>""",
      unsafe_allow_html=True)

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    # 7-Dimension bars (2 columns)
    dim_cols_keys = list(DIM_LABELS.keys())
    if any(f"dim_{k}" in row.index for k in dim_cols_keys):
        col_a, col_b = st.columns(2)
        mid = 4
        left, right = dim_cols_keys[:mid], dim_cols_keys[mid:]

        def _dim_section(keys, container):
            with container:
                st.markdown('<div class="ch"><div class="sec-head">7-Dimension Profile</div></div>',
                            unsafe_allow_html=True)
                for k in keys:
                    val   = float(row.get(f"dim_{k}", 0))
                    color = DIM_COLORS[k]
                    st.markdown(f"""
                    <div class="dim-bar">
                      <div class="dim-icon">{DIM_ICONS[k]}</div>
                      <div class="dim-name">{DIM_LABELS[k]}</div>
                      <div class="dim-bg" style="flex:1;">
                        <div class="dim-fill" style="width:{val:.0f}%;background:{color};"></div>
                      </div>
                      <div class="dim-num">{val:.0f}</div>
                    </div>""", unsafe_allow_html=True)

        _dim_section(left, col_a)
        _dim_section(right, col_b)

    # Program rationale
    st.markdown(f"""
    <div style="margin-top:.5rem;padding:.8rem 1.1rem;background:{G_PALE};border-radius:10px;
                border-left:4px solid {imeta['color']};">
      <div style="font-size:.78rem;font-weight:700;color:{DARK};">
        {imeta['icon']} Why {interv}?</div>
      <div style="font-size:.73rem;color:{MUTED};margin-top:.3rem;">{imeta.get('desc','')}</div>
    </div>""", unsafe_allow_html=True)


# ── View 6: State Drill-Down ──────────────────────────────────────────────────
def view_state_drilldown(scores: pd.DataFrame, scores_long: pd.DataFrame,
                          condition: str, cond_label: str,
                          state: str, county: str, top_n: int):
    scores    = _ensure_dims(scores)
    opp_col   = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    if score_col not in scores.columns:
        score_col = opp_col

    # ── Prompt if no state selected ───────────────────────────────────────────
    if state == "All States":
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:3rem 2rem;margin-top:1rem;">
          <div style="font-size:3.5rem;">📍</div>
          <div class="sec-head" style="margin-top:1rem;font-size:1.1rem;">Select a State to Begin</div>
          <div class="sec-sub" style="max-width:420px;margin:0 auto;">
            Choose a state from the <strong>Geography</strong> filter in the sidebar.
            A county dropdown will appear automatically.
          </div>
        </div>""", unsafe_allow_html=True)

        # Teaser: top 5 states
        state_ranks = (scores.groupby("state_name")[opp_col].mean()
                       .sort_values(ascending=False).head(5).reset_index())
        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
        st.markdown('<div class="ch"><div class="sec-head">Top 5 States by Avg Opportunity Score</div>'
                    '<div class="sec-sub">Select one in the sidebar to drill in</div></div>',
                    unsafe_allow_html=True)
        for i, r in state_ranks.iterrows():
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem;">
              <div style="font-weight:800;color:{MUTED};font-size:.8rem;width:1.2rem;">{i+1}</div>
              <div style="flex:1;">
                <div style="font-size:.83rem;font-weight:600;color:{DARK};">{r['state_name']}</div>
                <div style="height:5px;background:{BORDER};border-radius:3px;margin-top:3px;">
                  <div style="width:{r[opp_col]:.0f}%;height:100%;background:{G_MID};border-radius:3px;"></div>
                </div>
              </div>
              <div style="font-size:.83rem;font-weight:700;color:{G_DARK};min-width:2.5rem;text-align:right;">
                {r[opp_col]:.0f}</div>
            </div>""", unsafe_allow_html=True)
        return

    # ── State selected ────────────────────────────────────────────────────────
    state_df = scores[scores["state_name"] == state].copy()

    # ── County deep-dive (if county selected) ─────────────────────────────────
    if county and county != "All Counties":
        county_rows = state_df[state_df["county_name"] == county]
        if not county_rows.empty:
            _render_county_scorecard(county_rows.iloc[0], opp_col, score_col, cond_label)
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── State KPI banner ──────────────────────────────────────────────────────
    total_pool = int(state_df["total_estimated_pool"].sum()) if "total_estimated_pool" in state_df.columns else 0
    priority_n = int((state_df[opp_col] >= 70).sum())
    emerging_n = int(((state_df[opp_col] >= 40) & (state_df[opp_col] < 70)).sum())
    avg_score  = state_df[opp_col].mean()
    top_prog   = (state_df["recommended_intervention"].value_counts().idxmax()
                  if "recommended_intervention" in state_df.columns else "—")

    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">State Intelligence — {state}</div>
      <div class="banner-stat">{len(state_df)} Counties</div>
      <div class="banner-note">
        Est. pool: {total_pool:,} &nbsp;·&nbsp;
        {priority_n} Priority · {emerging_n} Emerging &nbsp;·&nbsp;
        Avg score: {avg_score:.0f} &nbsp;·&nbsp; Lead program: {top_prog}
      </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Total Counties</div><div class="big-num-w">{len(state_df)}</div><div class="sub-w">{state}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority ≥70</div><div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Act now</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging 40–70</div><div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Plan &amp; monitor</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-top:3px solid {G_LIGHT};"><div class="label">Avg Opp. Score</div><div class="big-num" style="color:{G_DARK};">{avg_score:.0f}</div><div class="sub-muted">out of 100</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="card"><div class="label">Est. Pool</div><div style="font-size:1.2rem;font-weight:800;color:{DARK};">{total_pool:,}</div><div class="sub-muted">undiagnosed</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # ── County ranking chart + right-side panels ──────────────────────────────
    col_chart, col_right = st.columns([2.5, 1])

    with col_chart:
        st.markdown(f'<div class="ch"><div class="sec-head">County Rankings — {state}</div>'
                    f'<div class="sec-sub">Sorted by Opportunity Score · Risk column: {cond_label} · Dotted lines = tier thresholds</div></div>',
                    unsafe_allow_html=True)

        ranked = state_df.sort_values(opp_col, ascending=True).copy()
        tier_colors = {"Priority": RED, "Emerging": AMBER, "Developing": G_LIGHT}
        bar_colors  = [tier_colors.get(str(r.get("opportunity_tier", "Developing")), G_MID)
                       for _, r in ranked.iterrows()]

        fig = go.Figure(go.Bar(
            x=ranked[opp_col], y=ranked["county_name"],
            orientation="h",
            marker=dict(color=bar_colors),
            text=ranked[opp_col].apply(lambda v: f"{v:.0f}"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Opp. Score: %{x:.0f}<extra></extra>",
        ))
        fig.add_vline(x=40, line_dash="dot", line_color=AMBER, line_width=1.5,
                      annotation_text="Emerging", annotation_position="top")
        fig.add_vline(x=70, line_dash="dot", line_color=RED,   line_width=1.5,
                      annotation_text="Priority", annotation_position="top")
        fig.update_layout(
            margin=dict(l=0, r=50, t=30, b=20),
            height=max(350, len(ranked) * 26 + 80),
            paper_bgcolor="white", plot_bgcolor="white",
            xaxis=dict(range=[0, 115], showgrid=True, gridcolor=BORDER,
                       title="Opportunity Score"),
            yaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        # Tier donut
        st.markdown('<div class="ch"><div class="sec-head">Tier Split</div></div>',
                    unsafe_allow_html=True)
        if "opportunity_tier" in state_df.columns:
            tc = state_df["opportunity_tier"].astype(str).value_counts()
            fig2 = go.Figure(go.Pie(
                labels=tc.index, values=tc.values, hole=0.55,
                marker_colors=[{"Priority": RED, "Emerging": AMBER, "Developing": G_LIGHT}.get(t, G_MID)
                               for t in tc.index],
                textinfo="percent+label", textfont_size=10,
            ))
            fig2.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=190,
                               paper_bgcolor="white", showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Program mix
        st.markdown('<div class="ch"><div class="sec-head">Program Mix</div></div>',
                    unsafe_allow_html=True)
        if "recommended_intervention" in state_df.columns:
            prog_counts = state_df["recommended_intervention"].value_counts()
            for prog, cnt in prog_counts.items():
                meta = INTERV_META.get(str(prog), {"color": G_MID, "icon": "•"})
                pct  = 100 * cnt / len(state_df)
                st.markdown(f"""
                <div style="margin-bottom:.5rem;">
                  <div style="display:flex;justify-content:space-between;font-size:.72rem;
                              color:{DARK};">
                    <span>{meta['icon']} {prog}</span>
                    <span style="font-weight:700;">{cnt}</span>
                  </div>
                  <div style="height:4px;background:{BORDER};border-radius:2px;margin-top:2px;">
                    <div style="width:{pct:.0f}%;height:100%;background:{meta['color']};
                                border-radius:2px;"></div>
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Condition breakdown
        st.markdown('<div class="ch"><div class="sec-head">By Condition</div></div>',
                    unsafe_allow_html=True)
        for ckey, cmeta in COND_META.items():
            col_name = f"{ckey}_risk_score"
            if col_name not in state_df.columns:
                continue
            avg = state_df[col_name].mean()
            hi  = (state_df[col_name] >= 70).sum()
            selected = "★ " if condition == ckey else ""
            st.markdown(f"""
            <div style="margin-bottom:.5rem;">
              <div style="display:flex;justify-content:space-between;font-size:.73rem;">
                <span style="font-weight:{'700' if condition==ckey else '500'};
                             color:{cmeta['color']};">{selected}{cmeta['label']}</span>
                <span style="color:{MUTED};">{avg:.0f}</span>
              </div>
              <div style="height:4px;background:{BORDER};border-radius:2px;margin-top:2px;">
                <div style="width:{min(avg,100):.0f}%;height:100%;background:{cmeta['color']};
                            border-radius:2px;"></div>
              </div>
              <div style="font-size:.67rem;color:{MUTED};">{hi} high-risk</div>
            </div>""", unsafe_allow_html=True)

    # ── Full county table ─────────────────────────────────────────────────────
    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    st.markdown(f'<div class="ch"><div class="sec-head">All Counties — {state} ({len(state_df)} total)</div>'
                f'<div class="sec-sub">Sorted by Opportunity Score · Select a county in the sidebar for full deep-dive</div></div>',
                unsafe_allow_html=True)

    top = state_df.sort_values(opp_col, ascending=False).copy()
    dim_cols_list = [f"dim_{k}" for k in DIM_LABELS]

    rows_html = ""
    for i, (_, row) in enumerate(top.iterrows()):
        opp_val  = row[opp_col]
        risk_val = row.get(score_col, opp_val)
        pool_str = f"{int(row['total_estimated_pool']):,}" if pd.notna(row.get("total_estimated_pool")) else "—"
        rural    = "🌾" if row.get("is_rural") else "🏙️"
        interv   = str(row.get("recommended_intervention", "—"))
        imeta    = INTERV_META.get(interv, {"color": G_MID, "icon": "•"})
        highlight = f"background:#EBF5FF;" if (county and county == row["county_name"]) else ""

        mini_bars = ""
        if all(c in row.index for c in dim_cols_list):
            for k in DIM_LABELS:
                v = float(row.get(f"dim_{k}", 0))
                mini_bars += (f'<div style="height:3px;width:{v:.0f}%;'
                              f'background:{DIM_COLORS[k]};border-radius:1px;margin-bottom:1px;"></div>')

        rows_html += f"""
        <tr style="{highlight}">
          <td style="font-weight:700;color:{MUTED};font-size:.75rem;">{i+1}</td>
          <td>
            <div style="font-weight:600;font-size:.82rem;color:{DARK};">{rural} {row['county_name']}</div>
            <div style="width:55px;margin-top:3px;">{mini_bars}</div>
          </td>
          <td style="font-size:.8rem;">{int(row['population']):,}</td>
          <td>{_score_bar(opp_val, G_MID)}</td>
          <td>{_score_bar(risk_val, DIM_COLORS.get('diagnosis_gap', G_MID))}</td>
          <td>{_tier_pill(row.get('opportunity_tier','Developing'))}</td>
          <td><span style="color:{imeta['color']};font-size:.75rem;font-weight:600;">
            {imeta['icon']} {interv}</span></td>
          <td style="font-size:.8rem;">{pool_str}</td>
        </tr>"""

    st.markdown(f"""
    <table class="tbl">
      <thead><tr>
        <th>#</th><th>County</th><th>Population</th>
        <th>Opp. Score</th><th>Risk ({cond_label})</th>
        <th>Tier</th><th>Program</th><th>Est. Pool</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>""", unsafe_allow_html=True)

    export_cols = [c for c in ["county_name", "population", opp_col, score_col,
                                "opportunity_tier", "recommended_intervention",
                                "total_estimated_pool"] if c in top.columns]
    csv = top[export_cols].to_csv(index=False)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    st.download_button(
        f"⬇ Download {state} county data (CSV)", csv,
        f"sppf_{state.lower().replace(' ', '_')}.csv", "text/csv",
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    scores, scores_long = load_data()
    geojson = load_geojson()
    ctrl    = render_sidebar(scores)

    view        = ctrl["view"]
    condition   = ctrl["condition"]
    cond_label  = ctrl["cond_label"]
    state       = ctrl["state"]
    county      = ctrl.get("county", "All Counties")
    top_n       = ctrl["top_n"]
    tier_filter = ctrl["tier_filter"]

    if view == "Market Overview":
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


if __name__ == "__main__":
    main()
