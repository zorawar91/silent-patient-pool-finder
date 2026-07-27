# Layouts — SPPF Dashboard

Streamlit app. There is no router and no layout component tree: the **app shell**
is `src/output/dashboard.py` (page config → CSS injection → sidebar → one view
function), and the only persistent chrome is the **sidebar** in
`src/output/sidebar.py`. Streamlit's own header/footer/menu are hidden by CSS
(`#MainMenu, footer, header { visibility:hidden; }`), so there is no top nav,
no breadcrumb, and no footer — every page instead opens with its own full-width
`.banner` block.

Shell structure on every screen:

```
.stApp                          background #F0F6FC
├── [data-testid="stSidebar"]   white, 1px #C8DDEF right border, 17rem desktop
│   ├── brand block             🔬 SPPF / Silent Patient Pool Finder / IQVIA…
│   ├── radio "Decision Views"  3 items
│   ├── expander "🔎 Analyst & Audit"  radio, 8 items
│   ├── hr
│   ├── filters                 Condition · Geography (state, county) · Display (top_n, tier)
│   └── hr + disclaimer footnote
└── .block-container            max-width 1600px, padding 1.5rem 2.2rem
    └── <one view module>       .banner → KPI card row (st.columns) → charts/tables
```

---

## `src/output/dashboard.py` — app shell / entry point

Renders: page config (`layout="wide"`, sidebar expanded, title
"SPPF — Market Access Intelligence", icon 🔬), injects the global stylesheet,
renders the sidebar, then dispatches to exactly one view function.

```python
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
```

---

## `src/output/sidebar.py` — persistent navigation + global filters

Renders: brand block, two mutually-exclusive radio groups (3 decision views
always visible; 8 analyst/audit views inside a collapsed expander that
auto-opens when one is active), then the global filters. Filters that don't
apply to the active view are rendered **disabled** rather than hidden, and their
values are forced back to defaults so a dead control can't leak into view logic.
Returns a dict of control state consumed by `dashboard.main()`.

```python
from __future__ import annotations
# Sidebar navigation + global filters for the SPPF dashboard.
#
# Navigation is grouped by audience, not by feature count. The three decision
# views a leader actually acts on are always visible; the eight analyst/audit
# views live in a collapsed "Analyst & Audit" group — depth on demand. The two
# radios are coordinated so exactly one view is ever selected (picking in one
# group clears the other), which keeps a single source of truth for `view`.

import pandas as pd
import streamlit as st

from src.output.theme import BORDER, DARK, G_DARK, G_LIGHT, MUTED

# Decision views — where a leader looks: the opportunity, the plan, the map.
DECISION_VIEWS = [
    "⚡  Insights & Actions",
    "💡  Investment Planner",
    "🗺️  Geographic Intelligence",
]
# Analyst & Audit — depth an analyst opens to interrogate or defend the above.
AUDIT_VIEWS = [
    "📊  Market Overview",
    "🔭  7-Dimension Analysis",
    "📍  State Drill-Down",
    "💳  Payer Landscape",
    "🗂️  ZIP & Territory",
    "🎯  HCP Targeting",
    "📐  Campaign Measurement",
    "📋  Data Provenance",
]
_DECISION_KEY = "_nav_decision"
_AUDIT_KEY = "_nav_audit"

# Which sidebar filters each view actually consumes. Anything not listed is
# greyed out for that view rather than silently ignored — a control that looks
# live but changes nothing is worse than no control at all.
VIEW_FILTERS: dict[str, set[str]] = {
    "Insights & Actions":      {"condition", "state"},
    "Investment Planner":      {"condition", "state", "top_n", "tier"},
    "Geographic Intelligence": {"condition", "state"},
    "Market Overview":         {"condition"},
    "7-Dimension Analysis":    {"condition", "state", "top_n"},
    "State Drill-Down":        {"condition", "state", "county"},
    "Payer Landscape":         {"state", "top_n"},
    "ZIP & Territory":         {"state"},
    "HCP Targeting":           {"state"},
    "Campaign Measurement":    set(),   # has its own in-view county pickers
    "Data Provenance":         set(),   # nothing to filter
}


def _pick_decision():
    # Picking a decision view clears the audit selection (mutual exclusion).
    st.session_state[_AUDIT_KEY] = None


def _pick_audit():
    st.session_state[_DECISION_KEY] = None


def render_sidebar(scores: pd.DataFrame) -> dict:
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

        # Default landing view = Insights & Actions (seed before the widgets
        # so the decision radio opens on it and the audit group stays empty).
        if _DECISION_KEY not in st.session_state and _AUDIT_KEY not in st.session_state:
            st.session_state[_DECISION_KEY] = DECISION_VIEWS[0]

        st.markdown("<div class='label' style='margin-bottom:.4rem;'>Decision Views</div>",
                    unsafe_allow_html=True)
        st.radio("Decision navigation", DECISION_VIEWS, index=None,
                 key=_DECISION_KEY, on_change=_pick_decision,
                 label_visibility="collapsed")

        # The eight analyst/audit views — collapsed by default, auto-expanded
        # only when the active view is one of them (so the selection stays visible).
        audit_active = st.session_state.get(_AUDIT_KEY) in AUDIT_VIEWS
        with st.expander("🔎  Analyst & Audit", expanded=audit_active):
            st.radio("Analyst navigation", AUDIT_VIEWS, index=None,
                     key=_AUDIT_KEY, on_change=_pick_audit,
                     label_visibility="collapsed")

        active = (st.session_state.get(_DECISION_KEY)
                  or st.session_state.get(_AUDIT_KEY)
                  or DECISION_VIEWS[0])

        st.markdown("---")

        view_name = active.split("  ")[1]
        applies = VIEW_FILTERS.get(view_name, set())

        def _off(name: str) -> bool:
            """True when this filter has no effect on the current view."""
            return name not in applies

        if not applies:
            st.caption("This view has no sidebar filters — its controls are in the page.")
        else:
            st.caption("Greyed-out filters don't apply to this view.")

        # ── Condition filter ──────────────────────────────────────────────────
        st.markdown(f"""
        <div class='label' style='margin-bottom:.2rem;'>Condition (Risk Score)</div>
        <div style='font-size:.64rem;color:{MUTED};margin-bottom:.4rem;line-height:1.5;'>
          Ranks and shades by the selected condition.<br>
          Opportunity Score is always multi-condition.
        </div>""", unsafe_allow_html=True)

        cond_opts = {"All Conditions": "overall", "🩸 Type 2 Diabetes": "t2d",
                     "❤️ Hypertension": "htn", "🦋 Hypothyroidism": "hyperthyroidism"}
        cond_label = st.selectbox("Condition", list(cond_opts.keys()),
                                  label_visibility="collapsed",
                                  disabled=_off("condition"))
        condition  = cond_opts[cond_label]
        # A disabled filter must not leak into the view's logic.
        if _off("condition"):
            condition, cond_label = "overall", "All Conditions"

        # ── Geography filters ─────────────────────────────────────────────────
        st.markdown("<div class='label' style='margin-top:.7rem;margin-bottom:.3rem;'>Geography</div>",
                    unsafe_allow_html=True)

        state_list = sorted(scores["state_name"].unique().tolist())
        state = st.multiselect(
            "States", state_list,
            placeholder="All states (no filter)",
            label_visibility="collapsed",
            disabled=_off("state"),
        )
        if _off("state"):
            state = []

        # County dropdown only when exactly one state is selected
        county = "All Counties"
        if "county" in applies and len(state) == 1:
            state_counties = ["All Counties"] + sorted(
                scores[scores["state_name"] == state[0]]["county_name"].unique().tolist()
            )
            county = st.selectbox("County", state_counties)
        elif len(state) > 1:
            st.caption(f"{len(state)} states selected")

        # ── Display options ───────────────────────────────────────────────────
        st.markdown("<div class='label' style='margin-top:.7rem;margin-bottom:.3rem;'>Display</div>",
                    unsafe_allow_html=True)

        top_n = st.slider("Top N counties", 10, 50, 20, step=5,
                          disabled=_off("top_n"))

        tier_opts = ["All Tiers", "Priority", "Emerging", "Developing"]
        tier_filter = st.selectbox("Opportunity Tier", tier_opts,
                                   disabled=_off("tier"))
        if _off("tier"):
            tier_filter = "All Tiers"

        st.markdown("---")
        st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};line-height:1.6;">
          ⚠️ Population-level planning tool only.<br>
          Not a clinical diagnostic instrument.<br>
          Data: 7 public sources — see Data Provenance.<br>
          <span style="color:{G_LIGHT};font-weight:600;">v2.0 — 7-Dimension Framework</span>
        </div>""", unsafe_allow_html=True)

    return {
        "view": view_name,
        "condition": condition,
        "cond_label": cond_label,
        "state": state,
        "county": county,
        "top_n": top_n,
        "tier_filter": tier_filter,
    }
```

---

## Sidebar chrome CSS (in `theme.py`, matters for any layout redesign)

- Streamlit's collapse toggle is explicitly kept visible and given a real
  affordance: 34×34px, `#DEEEF9` fill, 1px `#0077C8` border, 8px radius,
  hover fills `#0077C8` with white icon. The expand control when collapsed sits
  at `z-index: 999999`.
- Expander summaries pin **both** background and text colour (`#FFFFFF` /
  `#0A1F3C`; in the sidebar `#DEEEF9` / `#003087`) so they never inherit an
  unreadable pair from the ambient theme.
- Sidebar text colour is forced (`label`, `p`, `span`, radio/selectbox/slider
  labels all → `#0A1F3C`) for the same reason.
- Desktop ≥768px: `min-width: 17rem` when expanded. Mobile ≤767px: `min-width: 0`,
  never forced open.
