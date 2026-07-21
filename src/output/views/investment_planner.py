from __future__ import annotations
# View: Investment Planner — filtered county plan with program mix,
# screening-yield benchmarks, and a CSV export.

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.data import (
    _ensure_dims, _get_intervention, _has_dims, _opp_score,
    condition_score, condition_tier,
)
from src.output.theme import (
    BORDER, COND_META, DARK, DIM_COLORS, DIM_LABELS, G_DARK, G_MID,
    INTERV_META, MUTED, _iicon, _score_bar, _stplot, _tier_pill,
)


def view_investment_planner(scores: pd.DataFrame, scores_long: pd.DataFrame,
                             condition: str, state: str, top_n: int, tier_filter: str):
    scores = _ensure_dims(scores)
    opp_col = _opp_score(scores)
    scores, score_col = condition_score(scores, condition)
    scores = scores.copy()
    scores["_tier"] = condition_tier(scores, condition, score_col)

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
    if state:
        scored = scored[scored["state_name"].isin(state)]
    if "_tier" in scored.columns and tier_filter != "All Tiers":
        scored = scored[scored["_tier"] == tier_filter]

    top = scored.nlargest(min(top_n, len(scored)), opp_col).copy()

    # Summary KPIs
    total_pool = int(top["total_estimated_pool"].sum()) if "total_estimated_pool" in top.columns else 0
    lead_interv = top["recommended_intervention"].value_counts().idxmax() if len(top) > 0 else "—"
    lead_meta   = INTERV_META.get(str(lead_interv), {"color": G_MID, "icon": "•"})

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties in Plan</div>{_iicon(METRIC_TOOLTIPS["counties_in_plan"], tip_cls="tip-r")}<div class="big-num-w">{len(top)}</div><div class="sub-w">filtered selection</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><div class="label">Est. Undiagnosed Pool</div>{_iicon(METRIC_TOOLTIPS["est_pool"])}<div class="big-num">{total_pool:,}</div><div class="sub">within selected counties</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card"><div class="label">Avg Opportunity Score</div>{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}<div class="big-num">{top[opp_col].mean():.0f}</div><div class="sub-muted">out of 100</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-left:3px solid {lead_meta["color"]};"><div class="label">Lead Program Type</div>{_iicon(METRIC_TOOLTIPS["lead_program_type"])}<div style="font-size:1rem;font-weight:800;color:{DARK};margin:.2rem 0;">{lead_meta["icon"]} {lead_interv}</div><div class="sub-muted">most common</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Intervention breakdown + return estimate
    col_prog, col_roi = st.columns([1, 1])

    with col_prog:
        st.markdown(f'<div class="ch"><div class="sec-head">Program Mix Recommendation{_iicon(METRIC_TOOLTIPS["program_mix"])}</div>'
                    f'<div class="sec-sub">Which program type to deploy in each priority county</div></div>',
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
        _stplot(fig, use_container_width=True)

        for _, prow in prog_counts.iterrows():
            meta = INTERV_META.get(str(prow["program"]), {"color":G_MID,"icon":"•","desc":""})
            st.markdown(f"""
            <div style="border-left:3px solid {meta['color']};padding-left:.7rem;margin-bottom:.6rem;">
              <div style="font-size:.75rem;font-weight:700;color:{DARK};">{meta['icon']} {prow['program']}</div>
              <div style="font-size:.7rem;color:{MUTED};margin-top:2px;">{meta['desc']}</div>
            </div>""", unsafe_allow_html=True)

    with col_roi:
        st.markdown(f'<div class="ch"><div class="sec-head">Estimated Screening Yield{_iicon(METRIC_TOOLTIPS["screening_yield"])}</div>'
                    f'<div class="sec-sub">Patients newly diagnosed per 1,000 screened by program type (literature benchmarks)</div></div>',
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
        _stplot(fig2, use_container_width=True)
        st.markdown(f'<div style="font-size:.7rem;color:{MUTED};margin-top:.5rem;">⚠️ Yield figures based on published screening program literature. Actual results vary by market.</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Priority county table
    st.markdown(f'<div class="ch"><div class="sec-head">Priority County Investment List{_iicon(METRIC_TOOLTIPS["priority_county_list"])}</div>'
                f'<div class="sec-sub">Ranked by composite opportunity score. Use this to brief market access teams and payer strategy leads.</div></div>',
                unsafe_allow_html=True)

    rows_html = ""
    for i, (_, row) in enumerate(top.iterrows()):
        opp_val  = row[opp_col]
        risk_val = row.get(score_col, opp_val)
        pool_str = f"{int(row['total_estimated_pool']):,}" if pd.notna(row.get('total_estimated_pool')) else "—"
        rural    = "🌾" if row.get("is_rural") else "🏙️"
        interv   = str(row.get("recommended_intervention", "—"))
        imeta    = INTERV_META.get(interv, {"color": G_MID, "icon": "•"})
        tier_val = row.get("_tier", "—")

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
                                "opportunity_percentile","confidence_grade",
                                score_col,"_tier","recommended_intervention",
                                "total_estimated_pool"] if c in top.columns]
    csv = top[export_cols].to_csv(index=False)
    st.download_button("⬇️  Export investment list (CSV)", csv,
                       file_name="sppf_investment_plan.csv", mime="text/csv")
