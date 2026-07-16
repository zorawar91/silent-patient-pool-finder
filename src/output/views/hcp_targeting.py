from __future__ import annotations
# View: HCP Targeting — prescriber-level activation list built from the
# public CMS by-Provider file.

import pandas as pd
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.theme import (
    BG, G_DARK, G_MID, MUTED, STATE_ABBREV, _iicon, _score_bar,
)

# Geography weight label shown in the banner (keep in sync with hcp_scorer).
W_LBL_GEO = "40%"


def view_hcp_targeting(hcp: pd.DataFrame, state: list = None):
    """Prescriber-level activation list: who to call, where, and why."""

    # ── Empty state ───────────────────────────────────────────────────────────
    if hcp.empty:
        st.markdown(f"""
        <div class="card" style="padding:2rem;text-align:center;">
          <div style="font-size:2.5rem;margin-bottom:1rem;">🎯</div>
          <div class="sec-head">HCP target list not yet generated</div>
          <div class="sec-sub" style="max-width:560px;margin:0 auto 1.2rem;">
            Run the HCP ingestion pipeline to score prescribers from the public
            CMS Medicare Physician &amp; Other Practitioners file against your
            geography opportunity scores.
          </div>
          <code style="background:{BG};padding:.5rem 1rem;border-radius:6px;font-size:.82rem;">
            python3 src/ingestion/ingest_hcp_data.py
          </code>
          <div style="font-size:.72rem;color:{MUTED};margin-top:1rem;">
            Requires zip_scores.parquet and dimension_scores.parquet.
            100% public aggregate data — no PHI.
          </div>
        </div>""", unsafe_allow_html=True)
        return

    df = hcp.copy()
    if state and "state" in df.columns:
        abbrs = [STATE_ABBREV.get(s, s) for s in state]
        df = df[df["state"].isin(abbrs + list(state))]

    n_pri = int((df["hcp_tier"] == "Priority").sum())
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">HCP Targeting — Diagnosis-Support Detailing List</div>
      <div class="banner-stat">{len(df):,} prescribers {_iicon(METRIC_TOOLTIPS["hcp_count"], pos="", tip_cls="tip-l")}</div>
      <div class="banner-note">
        {n_pri:,} Priority · scored on geography opportunity ({W_LBL_GEO}),
        panel reach, metabolic burden &amp; specialty fit · public CMS data, no PHI
      </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        top_n = st.slider("Show top N prescribers", 25, 500, 100, step=25, key="hcp_n")
    with c2:
        spec_opts = ["All Specialties"] + sorted(df["specialty"].dropna().unique().tolist())
        spec_f = st.selectbox("Specialty", spec_opts, key="hcp_spec")
    with c3:
        tier_f = st.selectbox("Tier", ["All Tiers", "Priority", "Emerging", "Developing"],
                              key="hcp_tier_f")

    if spec_f != "All Specialties":
        df = df[df["specialty"] == spec_f]
    if tier_f != "All Tiers":
        df = df[df["hcp_tier"] == tier_f]
    ranked = df.nlargest(top_n, "hcp_priority_score").reset_index(drop=True)

    if ranked.empty:
        st.info("No prescribers match the current filters.")
        return

    rows_html = ""
    for i, row in ranked.iterrows():
        tier = str(row.get("hcp_tier", "Developing"))
        tier_cls = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
        sv = row["hcp_priority_score"]
        diab = (f"{row['panel_diabetes_pct']:.0f}%"
                if pd.notna(row.get("panel_diabetes_pct")) else "—")
        rows_html += (
            f"<tr>"
            f"<td style='color:{MUTED};font-size:.7rem;'>{i + 1}</td>"
            f"<td><strong>{row.get('name','')}</strong><br>"
            f"<span style='font-size:.68rem;color:{MUTED};'>NPI {row['npi']}</span></td>"
            f"<td style='font-size:.75rem;'>{row.get('specialty','')}</td>"
            f"<td style='font-size:.75rem;'>{row.get('city','')}, {row.get('state','')} {row.get('zip5','')}</td>"
            f"<td>{_score_bar(sv, G_DARK if sv >= 70 else G_MID)}</td>"
            f"<td><span class='pill {tier_cls}'>{tier}</span></td>"
            f"<td style='text-align:right;'>{int(row['panel_size']):,}</td>"
            f"<td style='text-align:right;'>{diab}</td>"
            f"<td style='font-size:.7rem;color:{MUTED};max-width:230px;'>{row.get('rationale','')}</td>"
            f"</tr>"
        )
    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>#</th><th>Prescriber</th><th>Specialty</th><th>Location</th>'
        f'<th>Priority Score {_iicon(METRIC_TOOLTIPS["hcp_score"], pos="")}</th>'
        f'<th>Tier {_iicon(METRIC_TOOLTIPS["hcp_tier"], pos="")}</th>'
        f'<th>Panel {_iicon(METRIC_TOOLTIPS["hcp_panel"], pos="")}</th>'
        f'<th>T2D% {_iicon(METRIC_TOOLTIPS["hcp_t2d"], pos="")}</th>'
        f'<th>Why {_iicon(METRIC_TOOLTIPS["hcp_why"], pos="")}</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    export_cols = [c for c in ["npi", "name", "specialty", "city", "state", "zip5",
                                "hcp_priority_score", "hcp_tier", "geo_percentile",
                                "panel_size", "panel_diabetes_pct", "rationale"]
                   if c in ranked.columns]
    st.download_button(
        "⬇️  Export call list (CRM-ready CSV)",
        ranked[export_cols].to_csv(index=False),
        file_name="sppf_hcp_call_list.csv", mime="text/csv", key="hcp_dl",
    )
    st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};margin-top:.6rem;">
      ⚠️ Prescriber data is public CMS Medicare aggregate reporting. Scores rank
      geographies and panel profiles for diagnosis-support programs — they make
      no claim about individual prescribing behaviour or patient outcomes.
    </div>""", unsafe_allow_html=True)
