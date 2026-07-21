from __future__ import annotations
# View: Payer Landscape — payer-mix KPIs, MA/Medicaid scatter, and
# program-fit guidance.

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.data import _ensure_dims, _ensure_payer, _opp_score
from src.output.theme import (
    AMBER, BLUE, BORDER, DARK, G_DARK, G_LIGHT, G_MID, G_PALE, MUTED,
    PURPLE, _iicon, _stplot,
)


def view_payer_landscape(scores: pd.DataFrame, state: str, top_n: int):
    scores   = _ensure_dims(scores)
    scores, payer_synthetic = _ensure_payer(scores)
    opp_col  = _opp_score(scores)
    filtered = scores.copy()
    if state:
        filtered = filtered[filtered["state_name"].isin(state)]

    st.markdown('<div class="sec-head">Payer Landscape Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Understand who pays in each market — critical for screening program partnership decisions</div>', unsafe_allow_html=True)

    if payer_synthetic:
        st.info("📊 Showing **estimated** payer mix (SES-calibrated synthetic data). "
                "Run `python3 src/ingestion/ingest_real_data.py` to load real CMS "
                "county-level payer data.")
    else:
        st.caption("Medicare Advantage penetration: real CMS county data (3,108 of 3,128 "
                   "counties). Medicaid, commercial, and dual-eligible shares: modeled "
                   "estimates from SES signals and coverage arithmetic — directionally "
                   "sound planning figures, not sourced rates.")

    # KPI strip
    ma_avg  = filtered["ma_penetration_rate"].mean() * 100
    med_avg = filtered["medicaid_rate"].mean() * 100
    com_avg = filtered["commercial_rate"].mean() * 100
    ma_high = int((filtered["ma_penetration_rate"] >= 0.45).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-blue"><div class="label-w">Avg MA Penetration</div>{_iicon(METRIC_TOOLTIPS["avg_ma_penetration"])}<div class="big-num-w">{ma_avg:.0f}%</div><div class="sub-w">Medicare Advantage</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {PURPLE};"><div class="label">Avg Medicaid Rate</div>{_iicon(METRIC_TOOLTIPS["avg_medicaid"])}<div class="big-num">{med_avg:.0f}%</div><div class="sub-muted">of population</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Avg Commercial Rate</div>{_iicon(METRIC_TOOLTIPS["avg_commercial"])}<div class="big-num">{com_avg:.0f}%</div><div class="sub-muted">employer/individual</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-top:3px solid {BLUE};"><div class="label">High MA Counties</div>{_iicon(METRIC_TOOLTIPS["high_ma_counties"])}<div class="big-num">{ma_high}</div><div class="sub" style="color:{BLUE};">≥45% MA penetration</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    col_scatter, col_mix = st.columns([1.5, 1])

    with col_scatter:
        st.markdown(f'<div class="ch"><div class="sec-head">Payer Mix vs. Opportunity Score{_iicon(METRIC_TOOLTIPS["payer_mix"])}</div>'
                    f'<div class="sec-sub">Each dot = a county. Size = population. Color = opportunity score.</div></div>',
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
        _stplot(fig, use_container_width=True)

    with col_mix:
        st.markdown(f'<div class="ch"><div class="sec-head">National Payer Mix{_iicon(METRIC_TOOLTIPS["payer_mix"])}</div>'
                    f'<div class="sec-sub">Average payer distribution across all counties in view</div></div>',
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
        _stplot(fig2, use_container_width=True)

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
