from __future__ import annotations
# View: Geographic Intelligence — county choropleth, top states, and
# per-condition breakdowns.

import pandas as pd
import plotly.express as px
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.data import (
    _cond_proxy, _ensure_dims, _get_intervention, _opp_score,
)
from src.output.theme import (
    AMBER, BG, BORDER, COND_META, DARK, G_DARK, G_LIGHT, G_PALE, MUTED,
    RED, _iicon, _stplot,
)


def view_geographic(scores: pd.DataFrame, scores_long: pd.DataFrame,
                    condition: str, state: str, geojson):
    scores    = _ensure_dims(scores)
    opp_col   = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    if score_col not in scores.columns:
        score_col = opp_col
    filtered  = scores.copy()
    if state:
        filtered = filtered[filtered["state_name"].isin(state)]

    cond_label = "All Conditions" if condition == "overall" else COND_META[condition]["label"]
    priority_n = int((filtered[opp_col] >= 55).sum())
    emerging_n = int(((filtered[opp_col] >= 40) & (filtered[opp_col] < 55)).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties Mapped</div>{_iicon(METRIC_TOOLTIPS["counties_mapped"], tip_cls="tip-r")}<div class="big-num-w">{len(filtered):,}</div><div class="sub-w">{filtered["state_name"].nunique()} states</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority ≥55</div>{_iicon(METRIC_TOOLTIPS["priority_tier"])}<div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Act now</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging 40–55</div>{_iicon(METRIC_TOOLTIPS["emerging_tier"])}<div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Plan &amp; monitor</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card"><div class="label">Avg Score ({cond_label})</div>{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}<div class="big-num">{filtered[score_col].mean():.0f}</div><div class="sub-muted">this view</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    col_map, col_right = st.columns([2.8, 1])

    with col_map:
        st.markdown(f'<div class="card"><div class="sec-head">Opportunity Map — {cond_label}{_iicon(METRIC_TOOLTIPS["opp_map"])}</div><div class="sec-sub">Shading = composite opportunity score. Hover for county profile.</div>', unsafe_allow_html=True)

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

            # Color scale anchored to actual score range (~25–65).
            # Matches tier thresholds: grey = Developing, amber = Emerging, red = Priority.
            fig = px.choropleth(
                map_data,
                geojson=geojson,
                locations="county_fips",
                color=opp_col,
                color_continuous_scale=[
                    [0.00, "#EEF2F7"],   # Developing low end
                    [0.50, "#F4A261"],   # Emerging (score ≈ 45)
                    [0.85, "#E63946"],   # Priority threshold (score ≈ 55)
                    [1.00, "#8B0000"],   # Top priority counties
                ],
                range_color=(25, 65),
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
                    title="Opp.<br>Score",
                    tickvals=[25, 40, 55, 65],
                    ticktext=["25<br><i>Developing</i>", "40<br><i>Emerging</i>",
                              "55<br><i>Priority</i>", "65"],
                    thickness=12, len=0.65, bgcolor="white",
                    bordercolor=BORDER, borderwidth=1,
                ),
                height=480,
            )
            _stplot(fig, width="stretch")
        else:
            st.info("County boundary map unavailable (GeoJSON download failed) — "
                    "showing state averages instead. It will retry on the next reload.")
            state_avg = (filtered.groupby("state_name")[opp_col].mean()
                         .reset_index().sort_values(opp_col, ascending=False).head(20))
            fig = px.bar(state_avg, x="state_name", y=opp_col,
                         color=opp_col, color_continuous_scale=[[0,G_PALE],[1,G_DARK]],
                         labels={"state_name":"","opportunity_score":"Avg Opportunity Score"})
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                               margin=dict(l=0,r=0,t=10,b=0), height=480, coloraxis_showscale=False)
            _stplot(fig, width="stretch")

        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        # Top states
        st.markdown(f'<div class="card"><div class="sec-head">Top States{_iicon(METRIC_TOOLTIPS["top_states"])}</div>', unsafe_allow_html=True)
        state_avgs = (filtered.groupby("state_name")[opp_col].mean()
                      .reset_index().sort_values(opp_col, ascending=False).head(10))
        for _, srow in state_avgs.iterrows():
            pct = min(float(srow[opp_col]), 100)
            color = RED if pct >= 55 else (AMBER if pct >= 40 else G_LIGHT)
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
        st.markdown(f'<div class="card"><div class="sec-head">By Condition{_iicon(METRIC_TOOLTIPS["by_condition"])}</div>', unsafe_allow_html=True)
        for ckey, cmeta in COND_META.items():
            proxy_s = _cond_proxy(filtered, ckey)
            avg = proxy_s.mean()
            hi  = (proxy_s >= 55).sum()
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
