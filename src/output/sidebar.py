from __future__ import annotations
# Sidebar navigation + global filters for the SPPF dashboard.

import pandas as pd
import streamlit as st

from src.output.theme import BORDER, DARK, G_DARK, G_LIGHT, MUTED


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

        st.markdown("<div class='label' style='margin-bottom:.4rem;'>View</div>", unsafe_allow_html=True)
        view = st.radio("Navigation", [
            "⚡  Insights & Actions",
            "📊  Market Overview",
            "🔭  7-Dimension Analysis",
            "💡  Investment Planner",
            "🗺️  Geographic Intelligence",
            "💳  Payer Landscape",
            "📍  State Drill-Down",
            "🗂️  ZIP & Territory",
            "🎯  HCP Targeting",
            "📐  Campaign Measurement",
            "📋  Data Provenance",
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
        "view": view.split("  ")[1],
        "condition": condition,
        "cond_label": cond_label,
        "state": state,
        "county": county,
        "top_n": top_n,
        "tier_filter": tier_filter,
    }
