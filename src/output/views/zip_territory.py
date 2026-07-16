from __future__ import annotations
# View: ZIP & Territory — ZCTA-level opportunity map, paste-your-ZIPs
# territory builder, and ZIP rankings.

import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.theme import (
    AMBER, BG, BORDER, G_DARK, G_LIGHT, G_MID, INTERV_META, MUTED,
    RED, _iicon, _score_bar, _stplot,
)


def view_zip_territory(zip_scores: pd.DataFrame, county_scores: pd.DataFrame,
                       state: list = None, condition: str = "overall"):
    """ZIP/ZCTA-level opportunity scoring and territory builder."""

    # ── Empty state ───────────────────────────────────────────────────────────
    if zip_scores.empty:
        st.markdown(f"""
        <div class="card" style="padding:2rem;text-align:center;">
          <div style="font-size:2.5rem;margin-bottom:1rem;">🗂️</div>
          <div class="sec-head">ZIP & Territory data not yet generated</div>
          <div class="sec-sub" style="max-width:560px;margin:0 auto 1.2rem;">
            Run the ZCTA ingestion pipeline to score ~33,000 US ZIP codes using
            CDC PLACES, Census ACS, and county-level dimension signals.
          </div>
          <code style="background:{BG};padding:.5rem 1rem;border-radius:6px;font-size:.82rem;">
            python3 src/ingestion/ingest_zcta_data.py
          </code>
          <div style="font-size:.72rem;color:{MUTED};margin-top:1rem;">
            Runtime: ~3 minutes on first run. Requires dimension_scores.parquet
            from src/ingestion/ingest_real_data.py.
          </div>
        </div>""", unsafe_allow_html=True)
        return

    df = zip_scores.copy()
    score_col = "zip_opportunity_score"

    # Ensure score col exists
    if score_col not in df.columns:
        st.error("zip_scores.parquet is missing zip_opportunity_score — "
                 "re-run src/ingestion/ingest_zcta_data.py")
        return

    # State filter
    if state and "state_name" in df.columns:
        df = df[df["state_name"].isin(state)]

    n_total   = len(df)
    n_pri     = int((df[score_col] >= 55).sum())
    n_eme     = int(((df[score_col] >= 40) & (df[score_col] < 55)).sum())
    total_pool = int(df["zip_total_pool"].sum()) if "zip_total_pool" in df.columns else 0
    avg_score  = df[score_col].mean()

    # Banner
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">ZIP Code Territory Intelligence — {", ".join(state[:2]) + (f" +{len(state)-2} more" if len(state) > 2 else "") if state else "United States"}</div>
      <div class="banner-stat">{n_total:,} ZIPs {_iicon(METRIC_TOOLTIPS["zip_count"], pos="", tip_cls="tip-l")}</div>
      <div class="banner-note">
        {n_pri:,} Priority · {n_eme:,} Emerging · Avg score {avg_score:.0f} {_iicon(METRIC_TOOLTIPS["zip_score"], pos="", tip_cls="tip-l")} ·
        {total_pool/1_000_000:.1f}M estimated undiagnosed patients {_iicon(METRIC_TOOLTIPS["zip_pool"], pos="", tip_cls="tip-l")}
      </div>
    </div>""", unsafe_allow_html=True)

    # Sub-tabs
    tab_map, tab_builder, tab_rank = st.tabs(["🌎 ZIP Map", "Territory Builder", "ZIP Rankings"])

    with tab_map:
        _render_zip_map(df, score_col)

    with tab_builder:
        _render_territory_builder(df, score_col, county_scores)

    with tab_rank:
        _render_zip_rankings(df, score_col)


def _render_zip_map(df: pd.DataFrame, score_col: str):
    """Scatter-geo map of ZCTA centroids colored by opportunity score."""
    has_geo = "lat" in df.columns and "lon" in df.columns and df["lat"].notna().sum() > 500

    if not has_geo:
        st.info("📍 Centroid data not available — run src/ingestion/ingest_zcta_data.py "
                "to add lat/lon to ZIP scores.")
        # Fallback: show county choropleth note
        st.markdown("""<div class="card">
          <div class="sec-sub">The ZIP map uses Census Gazetteer centroids (lat/lon per ZCTA).
          These are downloaded automatically by <code>src/ingestion/ingest_zcta_data.py</code>.
          Once available, the map shows ~33,000 ZIP centroids sized by estimated patient pool
          and colored by Opportunity Score.</div></div>""", unsafe_allow_html=True)
        return

    plot_df = df.dropna(subset=["lat", "lon", score_col]).copy()

    plot_df["tier"] = "Developing"
    if "zip_opportunity_tier" in plot_df.columns:
        plot_df["tier"] = plot_df["zip_opportunity_tier"].fillna("Developing")

    plot_df["color_val"] = plot_df[score_col]
    plot_df["pool_disp"] = (
        plot_df["zip_total_pool"].fillna(0).astype(int)
        if "zip_total_pool" in plot_df.columns else 0
    )
    plot_df["hover"] = (
        "ZIP: " + plot_df["zcta5"].astype(str) +
        ("<br>State: " + plot_df["state_name"] if "state_name" in plot_df.columns else "") +
        "<br>Score: " + plot_df[score_col].round(1).astype(str) +
        "<br>Tier: " + plot_df["tier"] +
        "<br>Est. Pool: " + plot_df["pool_disp"].apply(lambda x: f"{x:,}")
    )

    # scatter_geo handles 33k points fine — no subsampling needed

    fig = px.scatter_geo(
        plot_df,
        lat="lat", lon="lon",
        color=score_col,
        color_continuous_scale=[[0, G_LIGHT], [0.4, G_MID], [0.55, AMBER], [1, RED]],
        range_color=[0, 100],
        size="pool_disp" if "zip_total_pool" in plot_df.columns else None,
        size_max=10,
        scope="usa",
        projection="albers usa",
        hover_name="zcta5",
        custom_data=["hover"],
        opacity=0.7,
        labels={score_col: "Opportunity Score"},
    )
    fig.update_traces(
        hovertemplate="%{customdata[0]}<extra></extra>",
        marker=dict(line=dict(width=0)),
    )
    fig.update_layout(
        coloraxis_colorbar=dict(
            title="Opp. Score",
            tickvals=[0, 40, 55, 100],
            ticktext=["0", "40<br>Emerging", "55<br>Priority", "100"],
            len=0.6,
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=500,
        paper_bgcolor="white",
        geo=dict(
            showland=True, landcolor="#F8F9FA",
            showlakes=True, lakecolor="#EAF4FB",
            showcoastlines=True, coastlinecolor=BORDER,
            showsubunits=True, subunitcolor=BORDER,
            bgcolor="white",
        ),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown(f"""<div style="font-size:.71rem;color:{MUTED};margin-top:-.5rem;">
      {len(plot_df):,} ZCTAs shown · sized by estimated undiagnosed pool · colored by Opportunity Score
    </div>""", unsafe_allow_html=True)


def _render_territory_builder(df: pd.DataFrame, score_col: str, county_scores: pd.DataFrame):
    """Paste ZIP codes → aggregate scorecard for that territory."""
    st.markdown('<div class="sec-head">Territory Builder</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Paste ZIP codes to define a field territory and instantly get its aggregate opportunity scorecard.</div>', unsafe_allow_html=True)

    zip_input = st.text_area(
        "Paste ZIP codes (comma, space, or newline separated):",
        height=100,
        placeholder="e.g.  90210, 10001, 60601\nor one per line: 90210\n10001\n60601",
        key="territory_zip_input",
    )

    if not zip_input.strip():
        st.markdown(f"""<div class="card" style="text-align:center;padding:2rem;color:{MUTED};">
          Enter ZIP codes above to see the territory scorecard.
        </div>""", unsafe_allow_html=True)
        return

    # Parse ZIPs
    raw_zips = re.split(r"[\s,;]+", zip_input.strip())
    zips_entered = [z.strip().zfill(5) for z in raw_zips if z.strip().isdigit() and len(z.strip()) <= 5]

    if not zips_entered:
        st.warning("No valid 5-digit ZIP codes found. Please enter numeric ZIPs.")
        return

    territory = df[df["zcta5"].isin(zips_entered)].copy()
    n_found   = len(territory)
    n_missing = len(zips_entered) - n_found

    if n_found == 0:
        st.warning(f"None of the {len(zips_entered)} entered ZIPs are in the scored dataset. "
                   "Verify the ZIPs are valid US ZCTAs.")
        return

    if n_missing > 0:
        st.caption(f"ℹ️ {n_found} ZIPs matched · {n_missing} not found in dataset "
                   "(may be P.O. Box ZIPs or outside ZCTA coverage)")

    # ── KPI strip ─────────────────────────────────────────────────────────────
    avg_score  = territory[score_col].mean()
    pri_count  = int((territory[score_col] >= 55).sum())
    total_pool = int(territory["zip_total_pool"].sum()) if "zip_total_pool" in territory.columns else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f'<div class="card-dark"><div class="label-w">Territory ZIPs{_iicon(METRIC_TOOLTIPS["zip_count"], tip_cls="tip-r")}</div>'
                f'<div class="big-num-w">{n_found}</div>'
                f'<div class="sub-w">matched in database</div></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="card" style="border-top:3px solid {G_MID};"><div class="label">Avg Opportunity{_iicon(METRIC_TOOLTIPS["zip_score"])}</div>'
                f'<div class="big-num" style="color:{G_DARK};">{avg_score:.0f}</div>'
                f'<div class="sub-muted">out of 100</div></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority ZIPs{_iicon(METRIC_TOOLTIPS["priority_tier"])}</div>'
                f'<div class="big-num" style="color:{RED};">{pri_count}</div>'
                f'<div class="sub" style="color:{RED};">Score ≥55</div></div>', unsafe_allow_html=True)
    k4.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Est. Undiagnosed Pool{_iicon(METRIC_TOOLTIPS["zip_pool"])}</div>'
                f'<div class="big-num" style="color:{AMBER};">{total_pool:,}</div>'
                f'<div class="sub" style="color:{AMBER};">T2D + HTN + Hypo</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # ── Dimension radar + intervention breakdown ───────────────────────────────
    dim_col_map = {
        "zip_dim_disease_burden":       "Burden",
        "zip_dim_diagnosis_gap":        "Gap",
        "zip_dim_access_to_care":       "Access",
        "zip_dim_social_determinants":  "SDoH",
        "zip_dim_payer_landscape":      "Payer",
        "zip_dim_commercial_readiness": "Readiness",
        "zip_dim_trajectory":           "Trend",
    }
    avail_dims = {k: v for k, v in dim_col_map.items() if k in territory.columns}

    col_radar, col_interv = st.columns([1, 1])

    if avail_dims:
        with col_radar:
            st.markdown(f'<div class="ch"><div class="sec-head">Territory Dimension Profile</div>'
                        f'<div class="sec-sub">Average across {n_found} ZIPs vs. US national</div></div>',
                        unsafe_allow_html=True)
            terr_avgs = [territory[col].mean() for col in avail_dims]
            natl_avgs = [df[col].mean() for col in avail_dims]
            labels    = list(avail_dims.values())
            fig_r = go.Figure()
            fig_r.add_trace(go.Scatterpolar(
                r=natl_avgs + [natl_avgs[0]], theta=labels + [labels[0]],
                fill="toself", name="US National",
                line=dict(color=BORDER, width=1.5),
                fillcolor="rgba(0,169,224,0.08)",
            ))
            fig_r.add_trace(go.Scatterpolar(
                r=terr_avgs + [terr_avgs[0]], theta=labels + [labels[0]],
                fill="toself", name="Your Territory",
                line=dict(color=G_DARK, width=2.5),
                fillcolor="rgba(0,48,135,0.2)",
            ))
            fig_r.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont_size=9)),
                showlegend=True, legend=dict(font_size=10),
                margin=dict(l=20, r=20, t=30, b=20), height=260,
                paper_bgcolor="white",
            )
            _stplot(fig_r, width="stretch")

    if "zip_recommended_intervention" in territory.columns:
        with col_interv:
            st.markdown('<div class="ch"><div class="sec-head">Recommended Programs</div>'
                        '<div class="sec-sub">Distribution across territory ZIPs</div></div>',
                        unsafe_allow_html=True)
            interv_counts = territory["zip_recommended_intervention"].value_counts()
            for prog, cnt in interv_counts.items():
                meta  = INTERV_META.get(prog, {"color": G_LIGHT, "icon": "•"})
                pct   = cnt / n_found * 100
                st.markdown(
                    f'<div class="dim-bar">'
                    f'<span class="dim-icon">{meta["icon"]}</span>'
                    f'<span class="dim-name" style="width:12rem;">{prog[:28]}</span>'
                    f'<div class="dim-bg"><div class="dim-fill" style="width:{pct:.0f}%;background:{meta["color"]};"></div></div>'
                    f'<span class="dim-num">{cnt}</span>'
                    f'</div>', unsafe_allow_html=True
                )

    # ── Per-ZIP table ─────────────────────────────────────────────────────────
    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sec-head">ZIP-Level Detail</div>', unsafe_allow_html=True)

    display_cols = ["zcta5", score_col, "zip_opportunity_tier"]
    for c in ["state_name", "zip_total_pool", "zip_recommended_intervention"]:
        if c in territory.columns:
            display_cols.append(c)

    tbl = territory[display_cols].sort_values(score_col, ascending=False).copy()
    tbl = tbl.rename(columns={
        "zcta5": "ZIP", score_col: "Score", "zip_opportunity_tier": "Tier",
        "state_name": "State", "zip_total_pool": "Est. Pool",
        "zip_recommended_intervention": "Program",
    })

    # Render as HTML table
    rows_html = ""
    for _, row in tbl.iterrows():
        tier = str(row.get("Tier", "Developing"))
        tier_cls = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
        score_val = row.get("Score", 0)
        pool_val  = f"{int(row['Est. Pool']):,}" if "Est. Pool" in row and pd.notna(row.get("Est. Pool")) else "—"
        prog_val  = str(row.get("Program", ""))[:30] if "Program" in row else "—"
        state_val = str(row.get("State", "")) if "State" in row else "—"
        rows_html += (
            f"<tr>"
            f"<td><strong>{row['ZIP']}</strong></td>"
            f"<td>{state_val}</td>"
            f"<td>{_score_bar(score_val, G_DARK if score_val >= 55 else G_MID)}</td>"
            f"<td><span class='pill {tier_cls}'>{tier}</span></td>"
            f"<td>{pool_val}</td>"
            f"<td style='font-size:.75rem;'>{prog_val}</td>"
            f"</tr>"
        )

    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>ZIP</th><th>State</th><th>Score</th><th>Tier</th><th>Est. Pool</th><th>Program</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    # CSV download
    csv_bytes = tbl.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Download Territory CSV",
        data=csv_bytes,
        file_name="territory_zips.csv",
        mime="text/csv",
        key="terr_dl",
    )


def _render_zip_rankings(df: pd.DataFrame, score_col: str):
    """Top ZIP rankings table with CSV export."""
    st.markdown('<div class="sec-head">ZIP Code Rankings</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Top opportunity ZCTAs by composite score</div>', unsafe_allow_html=True)

    col_top_n, col_tier = st.columns([1, 1])
    with col_top_n:
        top_n = st.slider("Show top N ZIPs", 20, 200, 50, step=10, key="zip_rank_n")
    with col_tier:
        tier_f = st.selectbox("Tier filter", ["All Tiers", "Priority", "Emerging", "Developing"],
                              key="zip_rank_tier")

    ranked = df.copy()
    if tier_f != "All Tiers" and "zip_opportunity_tier" in ranked.columns:
        ranked = ranked[ranked["zip_opportunity_tier"] == tier_f]

    ranked = ranked.nlargest(top_n, score_col)

    if ranked.empty:
        st.info("No ZIPs match the current filters.")
        return

    display_cols = ["zcta5", score_col]
    for c in ["zip_opportunity_percentile", "zip_confidence_grade",
              "zip_opportunity_tier", "state_name", "zip_total_pool",
              "diabetes_prevalence_pct", "poverty_rate", "zip_recommended_intervention"]:
        if c in ranked.columns:
            display_cols.append(c)

    tbl = ranked[display_cols].copy().reset_index(drop=True)
    tbl.insert(0, "Rank", range(1, len(tbl) + 1))

    rows_html = ""
    for _, row in tbl.iterrows():
        tier = str(row.get("zip_opportunity_tier", "Developing"))
        tier_cls = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
        score_val  = row[score_col]
        pool_val   = f"{int(row['zip_total_pool']):,}" if "zip_total_pool" in row and pd.notna(row.get("zip_total_pool")) else "—"
        diab_val   = f"{row['diabetes_prevalence_pct']*100:.1f}%" if "diabetes_prevalence_pct" in row and pd.notna(row.get("diabetes_prevalence_pct")) else "—"
        pov_val    = f"{row['poverty_rate']*100:.1f}%" if "poverty_rate" in row and pd.notna(row.get("poverty_rate")) else "—"
        state_val  = str(row.get("state_name", ""))[:2] if "state_name" in row else "—"
        prog_val   = str(row.get("zip_recommended_intervention", ""))[:22] if "zip_recommended_intervention" in row else "—"
        pctl_val   = f"{row['zip_opportunity_percentile']:.0f}" if pd.notna(row.get("zip_opportunity_percentile")) else "—"
        grade_val  = str(row.get("zip_confidence_grade", "")) or "—"
        grade_col  = {"A": G_DARK, "B": "#F4A261", "C": "#E63946"}.get(grade_val, MUTED)
        rows_html += (
            f"<tr>"
            f"<td style='color:{MUTED};font-size:.7rem;'>{int(row['Rank'])}</td>"
            f"<td><strong>{row['zcta5']}</strong></td>"
            f"<td>{state_val}</td>"
            f"<td>{_score_bar(score_val, G_DARK if score_val >= 55 else G_MID)}</td>"
            f"<td style='color:{MUTED};font-size:.73rem;'>{pctl_val}</td>"
            f"<td style='color:{grade_col};font-weight:700;'>{grade_val}</td>"
            f"<td><span class='pill {tier_cls}'>{tier}</span></td>"
            f"<td>{pool_val}</td>"
            f"<td>{diab_val}</td>"
            f"<td>{pov_val}</td>"
            f"<td style='font-size:.73rem;'>{prog_val}</td>"
            f"</tr>"
        )

    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>#</th><th>ZIP</th><th>St.</th>'
        f'<th>Score {_iicon(METRIC_TOOLTIPS["zip_score"], pos="")}</th>'
        f'<th>Pctl {_iicon(METRIC_TOOLTIPS["zip_pctl"], pos="")}</th>'
        f'<th>Conf {_iicon(METRIC_TOOLTIPS["zip_conf"], pos="")}</th>'
        f'<th>Tier {_iicon(METRIC_TOOLTIPS["priority_tier"], pos="")}</th>'
        f'<th>Est. Pool {_iicon(METRIC_TOOLTIPS["zip_pool"], pos="")}</th>'
        f'<th>T2D%</th><th>Poverty%</th>'
        f'<th>Program {_iicon(METRIC_TOOLTIPS["recommended_intervention"], pos="")}</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    csv_dl = tbl.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Download Rankings CSV",
        data=csv_dl,
        file_name="zip_rankings.csv",
        mime="text/csv",
        key="zip_rank_dl",
    )
