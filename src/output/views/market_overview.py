from __future__ import annotations
# View: Market Overview — national KPIs, condition cards, score distribution,
# intervention mix, and the illustrative patient funnel.

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.data import (
    condition_score,
    _cond_proxy, _ensure_dims, _get_intervention, _opp_score, condition_tier,
)
from src.output.theme import (
    AMBER, BLUE, BORDER, COND_META, DARK, G_DARK, G_LIGHT, G_MID,
    INTERV_META, MUTED, RED, _iicon, _stplot,
)


def view_market_overview(scores: pd.DataFrame, scores_long: pd.DataFrame,
                          condition: str = "overall", cond_label: str = "All Conditions"):
    scores  = _ensure_dims(scores)
    opp_col = _opp_score(scores)
    scores, score_col = condition_score(scores, condition)
    scores = scores.copy()
    scores["_tier"] = condition_tier(scores, condition, score_col)
    total_pool = int(scores["total_estimated_pool"].sum()) if "total_estimated_pool" in scores.columns else 45_700_000
    priority_n = int((scores["_tier"] == "Priority").sum())
    emerging_n = int((scores["_tier"] == "Emerging").sum())

    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">Total Estimated Undiagnosed Patient Pool — United States</div>
      <div class="banner-stat">{total_pool/1_000_000:.1f}M</div>
      <div class="banner-note">
        Across Type 2 Diabetes, Hypertension &amp; Hypothyroidism · summed from
        all {len(scores):,} counties (adult population × prevalence × NHANES
        age-weighted undiagnosis rate) ·
        {priority_n:,} Priority + {emerging_n:,} Emerging counties identified
      </div>
    </div>""", unsafe_allow_html=True)

    # KPI strip
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties Scored{_iicon(METRIC_TOOLTIPS["counties_scored"], tip_cls="tip-r")}</div><div class="big-num-w">{len(scores):,}</div><div class="sub-w">US county coverage</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority Markets{_iicon(METRIC_TOOLTIPS["priority_tier"])}</div><div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Opportunity Score ≥55</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging Markets{_iicon(METRIC_TOOLTIPS["emerging_tier"])}</div><div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Score 40–55</div></div>', unsafe_allow_html=True)
    avg_opp = scores[opp_col].mean()
    c4.markdown(f'<div class="card" style="border-top:3px solid {G_LIGHT};"><div class="label">Avg Opportunity Score{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}</div><div class="big-num" style="color:{G_DARK};">{avg_opp:.0f}</div><div class="sub-muted">national baseline</div></div>', unsafe_allow_html=True)
    top_state = scores.groupby("state_name")[opp_col].mean().idxmax()
    c5.markdown(f'<div class="card" style="border-top:3px solid {BLUE};"><div class="label">Top State{_iicon(METRIC_TOOLTIPS["top_state"])}</div><div style="font-size:1.3rem;font-weight:800;color:{DARK};">{top_state}</div><div class="sub-muted">by avg opp. score</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Condition cards.
    # The headline is OUR computed pool for that condition, so the three cards
    # sum exactly to the banner total. Previously these showed published
    # national estimates (8.7M/34.9M/2.1M = 45.7M) beside a computed banner
    # (33.7M) — two different measurement systems on one screen, with
    # hypertension alone appearing to exceed the stated total. The published
    # figure is kept as labelled context, since it is a broader definition
    # (HTN counts "undiagnosed OR uncontrolled") and is useful comparison.
    _POOL_COL = {"t2d": "est_pool_t2d", "htn": "est_pool_htn",
                 "hyperthyroidism": "est_pool_hypo"}
    col1, col2, col3 = st.columns(3)
    _cond_tip_keys = {"t2d": "condition_t2d", "htn": "condition_htn", "hyperthyroidism": "condition_hypo"}
    for col, (ckey, meta) in zip([col1, col2, col3], COND_META.items()):
        proxy     = _cond_proxy(scores, ckey)
        high_risk = int((proxy >= 55).sum())
        avg_risk  = proxy.mean()
        peak_risk = f"{proxy.max():.0f}"
        pool_col  = _POOL_COL[ckey]
        computed  = int(scores[pool_col].sum()) if pool_col in scores.columns else None
        est_pool  = (f"{computed/1_000_000:.1f}M" if computed
                     else f"{meta['national_pool']/1_000_000:.1f}M")
        published = f"{meta['national_pool']/1_000_000:.1f}M"
        col.markdown(f"""
        <div class="card" style="border-top:3px solid {meta['color']};">
          <div class="label">{meta['label']}</div>
          {_iicon(METRIC_TOOLTIPS[_cond_tip_keys[ckey]])}
          <div class="big-num">{est_pool}</div>
          <div class="sub" style="color:{meta['color']};">our estimate, summed from counties</div>
          <div style="font-size:.67rem;color:{MUTED};margin-top:.15rem;">
            published national estimate: {published}</div>
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
        st.markdown(f'<div class="ch"><div class="sec-head">Opportunity Score Distribution{_iicon(METRIC_TOOLTIPS["opp_score_dist"])}</div>'
                    f'<div class="sec-sub">How the 3,000+ US counties distribute across the 0–100 opportunity scale</div></div>',
                    unsafe_allow_html=True)
        # Manual binning so we can colour each bar by tier
        _vals = scores[opp_col].dropna().values
        _bins = np.arange(0, 101, 2.5)          # 40 bins of width 2.5
        _counts, _edges = np.histogram(_vals, bins=_bins)
        _mids   = (_edges[:-1] + _edges[1:]) / 2
        _colors = [RED if m >= 55 else AMBER if m >= 40 else G_LIGHT for m in _mids]
        _labels = [
            f"{'Priority' if m>=55 else 'Emerging' if m>=40 else 'Developing'} · {m:.0f}: {c} counties"
            for m, c in zip(_mids, _counts)
        ]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=_mids, y=_counts,
            width=2.3,
            marker=dict(color=_colors, opacity=0.85, line=dict(width=0)),
            customdata=_labels,
            hovertemplate="%{customdata}<extra></extra>",
        ))
        fig.add_vline(x=40, line=dict(dash="dot", color=AMBER, width=1.5),
                      annotation_text="Emerging", annotation_position="top right",
                      annotation_font_size=10, annotation_font_color=AMBER)
        fig.add_vline(x=55, line=dict(dash="dot", color=RED, width=1.5),
                      annotation_text="Priority", annotation_position="top right",
                      annotation_font_size=10, annotation_font_color=RED)
        fig.update_layout(
            xaxis=dict(title="Opportunity Score", range=[0, 100]),
            yaxis=dict(title="Number of Counties"),
            plot_bgcolor="white", paper_bgcolor="white",
            bargap=0.05,
            margin=dict(l=0, r=0, t=20, b=30), height=260,
        )
        _stplot(fig, use_container_width=True)

    with col_interv:
        st.markdown(f'<div class="ch"><div class="sec-head">Recommended Interventions{_iicon(METRIC_TOOLTIPS["recommended_intervention"])}</div>'
                    f'<div class="sec-sub">What program type does each county need?</div></div>',
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
        _stplot(fig2, use_container_width=True)

        for iname, cnt in mix.items():
            meta = INTERV_META.get(str(iname), {"color": G_MID, "icon": "•"})
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:.45rem;margin-bottom:.3rem;">
              <div style="width:8px;height:8px;border-radius:50%;background:{meta['color']};flex-shrink:0;"></div>
              <div style="font-size:.73rem;color:{DARK};">{meta['icon']} {iname}</div>
              <div style="margin-left:auto;font-size:.73rem;font-weight:700;color:{DARK};">{cnt}</div>
            </div>""", unsafe_allow_html=True)

    # Patient funnel
    st.markdown(f'<div class="ch"><div class="sec-head">Patient Identification Funnel{_iicon(METRIC_TOOLTIPS["patient_funnel"])}</div>'
                f'<div class="sec-sub">From total adult population to actionable screening opportunity</div></div>',
                unsafe_allow_html=True)

    funnel_labels = ["US Adult Population", "Estimated Prevalence\n(T2D+HTN+Hypo)",
                     "Estimated Undiagnosed", "Observable via Proxy Signals", "Actionable via Programs"]
    funnel_vals   = [258, 84, 45.7, 18, 8]
    fig3 = go.Figure(go.Funnel(
        y=[lbl.replace("\n", " ") for lbl in funnel_labels],
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
    _stplot(fig3, use_container_width=True)
