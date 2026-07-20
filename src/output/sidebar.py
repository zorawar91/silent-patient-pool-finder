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

        # ── Condition filter ──────────────────────────────────────────────────
        st.markdown(f"""
        <div class='label' style='margin-bottom:.2rem;'>Condition (Risk Score)</div>
        <div style='font-size:.64rem;color:{MUTED};margin-bottom:.4rem;line-height:1.5;'>
          Affects risk score column across all views.<br>
          Opportunity Score is always multi-condition.
        </div>""", unsafe_allow_html=True)

        cond_opts = {"All Conditions": "overall", "🩸 Type 2 Diabetes": "t2d",
                     "❤️ Hypertension": "htn", "🦋 Hypothyroidism": "hyperthyroidism"}
        cond_label = st.selectbox("Condition", list(cond_opts.keys()),
                                  label_visibility="collapsed")
        condition  = cond_opts[cond_label]

        # ── Geography filters ─────────────────────────────────────────────────
        st.markdown("<div class='label' style='margin-top:.7rem;margin-bottom:.3rem;'>Geography</div>",
                    unsafe_allow_html=True)

        state_list = sorted(scores["state_name"].unique().tolist())
        state = st.multiselect(
            "States", state_list,
            placeholder="All states (no filter)",
            label_visibility="collapsed",
        )

        # County dropdown only when exactly one state is selected
        county = "All Counties"
        if len(state) == 1:
            state_counties = ["All Counties"] + sorted(
                scores[scores["state_name"] == state[0]]["county_name"].unique().tolist()
            )
            county = st.selectbox("County", state_counties)
        elif len(state) > 1:
            st.caption(f"{len(state)} states selected")

        # ── Display options ───────────────────────────────────────────────────
        st.markdown("<div class='label' style='margin-top:.7rem;margin-bottom:.3rem;'>Display</div>",
                    unsafe_allow_html=True)

        top_n = st.slider("Top N counties", 10, 50, 20, step=5)

        tier_opts = ["All Tiers", "Priority", "Emerging", "Developing"]
        tier_filter = st.selectbox("Opportunity Tier", tier_opts)

        st.markdown("---")
        st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};line-height:1.6;">
          ⚠️ Population-level planning tool only.<br>
          Not a clinical diagnostic instrument.<br>
          Data: 7 public sources — see Data Provenance.<br>
          <span style="color:{G_LIGHT};font-weight:600;">v2.0 — 7-Dimension Framework</span>
        </div>""", unsafe_allow_html=True)

    return {
        "view": active.split("  ")[1],
        "condition": condition,
        "cond_label": cond_label,
        "state": state,
        "county": county,
        "top_n": top_n,
        "tier_filter": tier_filter,
    }
