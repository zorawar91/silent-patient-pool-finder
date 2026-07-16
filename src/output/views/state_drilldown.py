from __future__ import annotations
# View: State Drill-Down — single-state intelligence with optional county
# deep-dive scorecard.

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.data import _ensure_dims, _opp_score
from src.output.theme import (
    AMBER, BORDER, COND_META, DARK, DIM_COLORS, DIM_ICONS, DIM_LABELS,
    G_DARK, G_LIGHT, G_MID, G_PALE, INTERV_META, MUTED, RED,
    _iicon, _score_bar, _stplot, _tier_pill,
)


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
    pctl  = row.get("opportunity_percentile")
    pctl_str = f"{pctl:.0f}th percentile of 3,144 counties" if pd.notna(pctl) else "out of 100"
    conf  = str(row.get("confidence_grade", "")) or ""
    conf_str = f" · data confidence {conf}" if conf in ("A", "B", "C") else ""
    c1.markdown(f"""<div class="card-dark">
      <div class="label-w">Opportunity Score{_iicon(METRIC_TOOLTIPS["opportunity_percentile"], tip_cls="tip-r")}</div>
      <div class="big-num-w">{opp_val:.0f}</div>
      <div class="sub-w">{pctl_str}{conf_str}</div></div>""", unsafe_allow_html=True)
    c2.markdown(f"""<div class="card" style="border-top:3px solid {DIM_COLORS['diagnosis_gap']};">
      <div class="label">Risk Score ({cond_label}){_iicon(METRIC_TOOLTIPS["risk_score_cond"])}</div>
      <div class="big-num">{risk_val:.0f}</div>
      <div class="sub-muted">out of 100</div></div>""", unsafe_allow_html=True)
    c3.markdown(f"""<div class="card" style="border-top:3px solid {imeta['color']};">
      <div class="label">Recommended Program{_iicon(METRIC_TOOLTIPS["recommended_intervention"])}</div>
      <div style="font-size:.9rem;font-weight:700;color:{imeta['color']};margin-top:.3rem;">
        {imeta['icon']} {interv}</div></div>""", unsafe_allow_html=True)
    c4.markdown(f"""<div class="card">
      <div class="label">Opportunity Tier{_iicon(METRIC_TOOLTIPS["priority_tier"])}</div>
      <div style="margin-top:.4rem;">{_tier_pill(row.get('opportunity_tier','Developing'))}</div>
      <div class="sub-muted" style="margin-top:.4rem;">Est. pool: {pool_str}
        {_iicon(METRIC_TOOLTIPS["est_pool"], pos="")}</div></div>""",
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


def view_state_drilldown(scores: pd.DataFrame, scores_long: pd.DataFrame,
                          condition: str, cond_label: str,
                          state: list, county: str, top_n: int):
    scores    = _ensure_dims(scores)
    opp_col   = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    if score_col not in scores.columns:
        score_col = opp_col

    # ── Prompt if no state selected ───────────────────────────────────────────
    if not state:
        st.markdown("""
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

    # ── Multiple states selected — drill-down requires exactly one ────────────
    if len(state) > 1:
        st.info(
            f"State Drill-Down shows a single state at a time. "
            f"Narrow your selection to one state in the sidebar ({len(state)} currently selected).",
            icon="📍",
        )
        return

    # ── Exactly one state selected ────────────────────────────────────────────
    state_name = state[0]
    state_df = scores[scores["state_name"] == state_name].copy()

    # ── County deep-dive (if county selected) ─────────────────────────────────
    if county and county != "All Counties":
        county_rows = state_df[state_df["county_name"] == county]
        if not county_rows.empty:
            _render_county_scorecard(county_rows.iloc[0], opp_col, score_col, cond_label)
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── State KPI banner ──────────────────────────────────────────────────────
    total_pool = int(state_df["total_estimated_pool"].sum()) if "total_estimated_pool" in state_df.columns else 0
    priority_n = int((state_df[opp_col] >= 55).sum())
    emerging_n = int(((state_df[opp_col] >= 40) & (state_df[opp_col] < 55)).sum())
    avg_score  = state_df[opp_col].mean()
    top_prog   = (state_df["recommended_intervention"].value_counts().idxmax()
                  if "recommended_intervention" in state_df.columns else "—")

    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">State Intelligence — {state_name}</div>
      <div class="banner-stat">{len(state_df)} Counties</div>
      <div class="banner-note">
        Est. pool: {total_pool:,} &nbsp;·&nbsp;
        {priority_n} Priority · {emerging_n} Emerging &nbsp;·&nbsp;
        Avg score: {avg_score:.0f} &nbsp;·&nbsp; Lead program: {top_prog}
      </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Total Counties</div>{_iicon(METRIC_TOOLTIPS["counties_scored"], tip_cls="tip-r")}<div class="big-num-w">{len(state_df)}</div><div class="sub-w">{state_name}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority ≥55</div>{_iicon(METRIC_TOOLTIPS["priority_tier"])}<div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Act now</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging 40–55</div>{_iicon(METRIC_TOOLTIPS["emerging_tier"])}<div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Plan &amp; monitor</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-top:3px solid {G_LIGHT};"><div class="label">Avg Opp. Score</div>{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}<div class="big-num" style="color:{G_DARK};">{avg_score:.0f}</div><div class="sub-muted">out of 100</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="card"><div class="label">Est. Pool</div><div style="font-size:1.2rem;font-weight:800;color:{DARK};">{total_pool:,}</div><div class="sub-muted">undiagnosed</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # ── County ranking chart + right-side panels ──────────────────────────────
    col_chart, col_right = st.columns([2.5, 1])

    with col_chart:
        st.markdown(f'<div class="ch"><div class="sec-head">County Rankings — {state_name}</div>'
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
        fig.add_vline(x=55, line_dash="dot", line_color=RED,   line_width=1.5,
                      annotation_text="Priority", annotation_position="top")
        fig.update_layout(
            margin=dict(l=0, r=50, t=30, b=20),
            height=max(350, len(ranked) * 26 + 80),
            paper_bgcolor="white", plot_bgcolor="white",
            xaxis=dict(range=[0, 115], showgrid=True, gridcolor=BORDER,
                       title="Opportunity Score"),
            yaxis=dict(tickfont=dict(size=10)),
        )
        _stplot(fig, width="stretch")

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
            _stplot(fig2, width="stretch")

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
    st.markdown(f'<div class="ch"><div class="sec-head">All Counties — {state_name} ({len(state_df)} total)</div>'
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
        highlight = "background:#EBF5FF;" if (county and county == row["county_name"]) else ""

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

    export_cols = [c for c in ["county_name", "population", opp_col,
                                "opportunity_percentile", "confidence_grade",
                                score_col, "opportunity_tier", "recommended_intervention",
                                "total_estimated_pool"] if c in top.columns]
    csv = top[export_cols].to_csv(index=False)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    st.download_button(
        f"⬇ Download {state_name} county data (CSV)", csv,
        f"sppf_{state_name.lower().replace(' ', '_')}.csv", "text/csv",
    )
