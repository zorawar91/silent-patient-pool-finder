from __future__ import annotations
# Design tokens, shared metadata dicts, CSS, and small presentation helpers
# for the SPPF dashboard. No data logic lives here.

import pandas as pd
import streamlit as st

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
    "disease_burden":       "Burden",
    "diagnosis_gap":        "Dx Gap",
    "access_to_care":       "Access",
    "social_determinants":  "SDoH",
    "payer_landscape":      "Payer",
    "commercial_readiness": "Readiness",
    "trajectory":           "Trend",
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
    "hyperthyroidism": {"label": "Hypothyroidism",   "color": "#2A9D8F", "national_pool": 2_100_000},
}


# ── Presentation helpers ──────────────────────────────────────────────────────

def _iicon(tip: str, pos: str = "position:absolute;top:8px;right:10px;", tip_cls: str = "") -> str:
    """Return a classy circular info badge with a CSS hover tooltip.
    Default positioning: absolute top-right corner of the nearest relative container.
    Pass pos='' to render inline.
    tip_cls='tip-r' → tooltip extends RIGHT (for leftmost column icons).
    tip_cls='tip-l' → tooltip appears LEFT of icon at mid-height (for banner/inline icons).
    """
    safe = tip.replace('"', "&quot;").replace("'", "&#39;")
    style = f' style="{pos}"' if pos else ""
    cls = f"info-tip {tip_cls}".strip() if tip_cls else "info-tip"
    return f'<span class="{cls}" data-tip="{safe}"{style}>i</span>'


def _stplot(fig, **kwargs):
    """Wrapper around st.plotly_chart — applies consistent dark axis colours first."""
    fig.update_layout(font=dict(color=DARK, family="sans-serif", size=11))
    fig.update_xaxes(
        tickfont=dict(color=DARK, size=10),
        title_font=dict(color=MUTED, size=11),
        linecolor="#CACFD6",
        gridcolor="#EAEDF0",
        zerolinecolor="#CACFD6",
    )
    fig.update_yaxes(
        tickfont=dict(color=DARK, size=10),
        title_font=dict(color=MUTED, size=11),
        linecolor="#CACFD6",
        gridcolor="#EAEDF0",
        zerolinecolor="#CACFD6",
    )
    st.plotly_chart(fig, **kwargs)


def _score_bar(val, color=G_MID) -> str:
    pct = min(float(val or 0), 100)
    return (f'<div class="sbar-wrap"><div class="sbar-bg">'
            f'<div class="sbar-fill" style="width:{pct:.0f}%;background:{color};"></div>'
            f'</div><span class="snum">{pct:.0f}</span></div>')


def _tier_pill(tier) -> str:
    tier = str(tier) if pd.notna(tier) else "Developing"
    cls  = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
    return f'<span class="pill {cls}">{tier}</span>'


def inject_css() -> None:
    """Inject the global dashboard stylesheet. Call once, right after page config."""
    st.markdown(f"""<style>
.stApp {{ background:{BG}; }}
.block-container {{ padding:1.5rem 2.2rem; max-width:1600px; }}
[data-testid="stSidebar"] {{ background:{WHITE}; border-right:1px solid {BORDER}; }}

.card {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:10px;
         padding:0.8rem 1rem; box-shadow:0 1px 2px rgba(0,0,0,.04);
         position:relative; }}
.card-dark {{ background:linear-gradient(135deg,{G_DARK},{G_MID}); border:none;
              border-radius:10px; padding:0.8rem 1rem; color:{WHITE};
              position:relative; }}
.card-blue {{ background:linear-gradient(135deg,#1E3A5F,#2D6A9F); border:none;
              border-radius:10px; padding:0.8rem 1rem; color:{WHITE};
              position:relative; }}
/* chart-head: lightweight section label above a chart — no white box */
.ch {{ border-left:3px solid {G_LIGHT}; padding:.35rem .75rem; margin-bottom:.4rem;
       background:rgba(0,169,224,.04); border-radius:0 6px 6px 0;
       position:relative; }}
.ch .sec-head {{ margin-bottom:.15rem; }}
.ch .sec-sub  {{ margin-bottom:0; }}

.big-num   {{ font-size:2rem; font-weight:800; line-height:1; color:{DARK}; }}
.big-num-w {{ font-size:2rem; font-weight:800; line-height:1; color:{WHITE}; }}
.label     {{ font-size:.7rem; font-weight:700; color:{MUTED}; margin-bottom:.25rem; }}
.label-w   {{ font-size:.7rem; font-weight:700; color:rgba(255,255,255,.6); margin-bottom:.25rem; }}
.sub       {{ font-size:.74rem; color:{G_LIGHT}; margin-top:.3rem; font-weight:500; }}
.sub-w     {{ font-size:.74rem; color:rgba(255,255,255,.7); margin-top:.3rem; }}
.sub-muted {{ font-size:.74rem; color:{MUTED}; margin-top:.3rem; }}

.sec-head {{ font-size:1rem; font-weight:700; color:{DARK}; margin-bottom:.6rem; }}
.sec-sub  {{ font-size:.76rem; color:{MUTED}; margin-top:-.4rem; margin-bottom:.8rem; }}

.banner {{ background:linear-gradient(135deg,{G_DARK} 0%,{G_MID} 55%,{G_LIGHT} 100%);
           border-radius:16px; padding:1.4rem 2rem; color:{WHITE}; margin-bottom:1.2rem;
           position:relative; }}
.banner-title {{ font-size:1rem; font-weight:700; opacity:.8; margin-bottom:.2rem; }}
.banner-stat  {{ font-size:2.4rem; font-weight:900; line-height:1.1; }}
.banner-note  {{ font-size:.75rem; opacity:.65; margin-top:.25rem; }}

.pill {{ display:inline-block; padding:.18rem .65rem; border-radius:20px;
         font-size:.72rem; font-weight:700; }}

.tbl {{ width:100%; border-collapse:collapse; font-size:.83rem; }}
.tbl th {{ background:{BG}; color:{MUTED}; font-size:.67rem; font-weight:700;
           padding:.55rem .75rem; text-align:left; border-bottom:2px solid {BORDER}; }}
.tbl td {{ padding:.55rem .75rem; border-bottom:1px solid {BORDER}; color:{DARK};
           vertical-align:middle; }}
.tbl tr:last-child td {{ border-bottom:none; }}
.tbl tr:hover td {{ background:{BG}; }}

.sbar-wrap {{ display:flex; align-items:center; gap:.4rem; }}
.sbar-bg   {{ flex:1; height:5px; background:{BORDER}; border-radius:3px; overflow:hidden; }}
.sbar-fill {{ height:100%; border-radius:3px; }}
.snum      {{ font-weight:700; font-size:.79rem; color:{G_DARK}; min-width:2rem; text-align:right; }}

.dim-bar  {{ display:flex; align-items:center; gap:.5rem; margin-bottom:.45rem;
             position:relative; padding-right:1.4rem; }}
.dim-icon {{ font-size:.95rem; width:1.4rem; }}
.dim-name {{ font-size:.73rem; font-weight:600; color:{DARK}; width:7.5rem; flex-shrink:0; }}
.dim-bg   {{ flex:1; height:7px; background:{BORDER}; border-radius:4px; overflow:hidden; }}
.dim-fill {{ height:100%; border-radius:4px; }}
.dim-num  {{ font-size:.73rem; font-weight:700; color:{DARK}; width:2rem; text-align:right; }}

.tier-priority  {{ background:#FEE2E2; color:#991B1B; }}
.tier-emerging  {{ background:#FEF3C7; color:#92400E; }}
.tier-developing{{ background:{G_PALE}; color:{G_DARK}; }}

#MainMenu, footer, header {{ visibility:hidden; }}

/* ── Tab styling — ensure inactive tabs are legible ── */
button[data-baseweb="tab"] {{
    color: {MUTED} !important;
    font-size: .85rem !important;
    font-weight: 600 !important;
}}
button[data-baseweb="tab"]:hover {{
    color: {G_DARK} !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {G_DARK} !important;
    font-weight: 700 !important;
}}

/* ── Allow tooltips to escape Streamlit column/block clip zones ── */
[data-testid="stColumn"],
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stMarkdownContainer"],
[data-testid="stElementContainer"] {{
    overflow: visible !important;
}}

/* ── Info icon with CSS tooltip ──────────────────────────── */
.info-tip {{
    display:inline-flex; align-items:center; justify-content:center;
    width:15px; height:15px; border-radius:50%;
    background:linear-gradient(135deg,{G_MID},{G_LIGHT});
    color:#fff; font-size:.6rem; font-style:italic; font-weight:800;
    font-family:Georgia,serif; cursor:help; position:relative;
    vertical-align:middle; margin-left:4px; flex-shrink:0;
    box-shadow:0 1px 5px rgba(0,119,200,.35);
    transition:transform .15s,box-shadow .15s;
    line-height:1; user-select:none;
    z-index:9999;
}}
.info-tip:hover {{
    transform:scale(1.2);
    box-shadow:0 3px 10px rgba(0,119,200,.55);
    z-index:99999;
}}
/* Tooltip bubble — appears BELOW-LEFT of icon so it never hides behind right-edge cards */
.info-tip::after {{
    content:attr(data-tip);
    position:absolute;
    top:calc(100% + 8px);
    right:0; left:auto;
    background:{DARK};
    color:#fff;
    padding:10px 14px;
    border-radius:10px;
    font-size:.72rem; font-weight:400; font-style:normal;
    line-height:1.55; width:240px; white-space:normal;
    z-index:99999; opacity:0; pointer-events:none;
    transition:opacity .18s ease;
    box-shadow:0 8px 28px rgba(0,0,0,.35);
    border:1px solid rgba(255,255,255,.10);
    letter-spacing:.01em; text-align:left;
}}
/* Small caret above the bubble */
.info-tip::before {{
    content:'';
    position:absolute;
    top:calc(100% + 2px);
    right:4px; left:auto;
    border:6px solid transparent;
    border-bottom-color:{DARK};
    z-index:99999; opacity:0; pointer-events:none;
    transition:opacity .18s ease;
}}
/* ── Enable tooltip on hover ── */
.info-tip:hover::after,
.info-tip:hover::before {{ opacity:1; }}

/* tip-r: tooltip extends RIGHT from icon (leftmost column — avoids sidebar overlap) */
.info-tip.tip-r::after {{
    left:0; right:auto; transform:none;
}}
.info-tip.tip-r::before {{
    left:4px; right:auto;
}}

/* tip-l: tooltip appears LEFT of icon at mid-height (banner inline icons) */
.info-tip.tip-l::after {{
    top:50%; bottom:auto;
    right:calc(100% + 12px); left:auto;
    transform:translateY(-50%);
}}
.info-tip.tip-l::before {{
    top:50%; bottom:auto;
    right:calc(100% + 0px); left:auto;
    transform:translateY(-50%);
    border:6px solid transparent;
    border-left-color:{DARK};
    border-bottom-color:transparent;
}}

/* ── Sidebar: expanded by default, collapsible on every screen size ──────────
   Previously pinned open: forced min-width/transform plus a blanket
   `[data-testid="stSidebar"] button {{ display:none }}` that killed the collapse
   control. On a phone Streamlit had already set aria-expanded="false" — it
   wanted to collapse — but those overrides kept the panel rendered at 272px of
   a 375px viewport with no way to dismiss it. Streamlit's native collapse /
   expand is now left intact; we only style it. */

/* Streamlit's own collapse toggle must stay visible and clickable. */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] > button,
[data-testid="stSidebar"] [data-testid="stBaseButton-headerNoPadding"],
[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {{
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    width: auto !important;
}}

/* Give the toggle a real affordance. Streamlit renders a bare ~28px chevron
   with no border or background, floating in whitespace — present but easy to
   miss, which reads to users as "there is no collapse button". */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"] {{
    background: {G_PALE} !important;
    border: 1px solid {G_MID} !important;
    border-radius: 8px !important;
    width: 34px !important;
    height: 34px !important;
    color: {G_DARK} !important;
    box-shadow: 0 1px 4px rgba(0,48,135,.18) !important;
    transition: background .15s, color .15s;
}}
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="stExpandSidebarButton"]:hover {{
    background: {G_MID} !important;
    color: {WHITE} !important;
}}
[data-testid="stSidebarCollapseButton"] button svg,
[data-testid="stExpandSidebarButton"] svg {{
    width: 20px !important;
    height: 20px !important;
}}
/* When collapsed, the re-open control sits over the page — keep it above
   content and clear of the top edge. */
[data-testid="stExpandSidebarButton"] {{
    z-index: 999999 !important;
}}

/* The "Analyst & Audit" expander toggle inside the sidebar. */
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] details > summary,
[data-testid="stSidebar"] [data-testid="stExpander"] button {{
    display: flex !important;
    visibility: visible !important;
}}

/* ── Expander headers: pin background AND text colour ────────────────────────
   Expander summaries inherited their colours from the ambient Streamlit theme,
   so the open state could land on dark-text-on-dark-fill (sidebar "Analyst &
   Audit") or light-text-on-light-fill (the QA Gate Report rows) — unreadable
   either way. Both halves of the contrast pair are now set explicitly, in the
   open and closed states, so they never depend on the viewer's theme. */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] details > summary,
[data-testid="stExpander"] details[open] > summary {{
    background: {WHITE} !important;
    color: {DARK} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    font-weight: 600;
}}
/* Children inherit their own colours from the theme — force them too. */
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary div,
[data-testid="stExpander"] summary label {{
    color: {DARK} !important;
}}
[data-testid="stExpander"] summary svg {{ fill: {G_DARK} !important; }}
[data-testid="stExpander"] summary:hover {{ background: {G_PALE} !important; }}

/* Expander body: keep it on the light card surface with readable text. */
[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stExpander"] [data-testid="stExpanderDetails"] p,
[data-testid="stExpander"] [data-testid="stExpanderDetails"] span,
[data-testid="stExpander"] [data-testid="stExpanderDetails"] div {{
    color: {DARK} !important;
}}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    background: {WHITE} !important;
}}

/* Sidebar expander sits on the white sidebar — tint it so it reads as a group
   header rather than a floating card. */
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] details[open] > summary {{
    background: {G_PALE} !important;
    color: {G_DARK} !important;
}}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
[data-testid="stSidebar"] [data-testid="stExpander"] summary div {{
    color: {G_DARK} !important;
}}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    background: transparent !important;
}}

/* Desktop: comfortable fixed width while open (nav is always in reach). */
@media (min-width: 768px) {{
    [data-testid="stSidebar"][aria-expanded="true"] {{
        min-width: 17rem !important;
    }}
}}

/* Mobile: never force the panel open, and tighten page padding so the
   dashboard uses the full width once the sidebar is dismissed. */
@media (max-width: 767px) {{
    [data-testid="stSidebar"] {{ min-width: 0 !important; }}
    .block-container {{ padding: 1rem 0.9rem !important; }}
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
