from __future__ import annotations
# View: Insights & Actions — auto-synthesised recommendations from the
# 7-dimension scores: top action counties, payer lead, counterintuitive find,
# most underserved market, fastest growers, and the next-move banner.

import pandas as pd
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.data import (
    _ensure_dims, _ensure_payer, _opp_score, condition_score, condition_tier,
    tier_basis_label,
)
from src.output.theme import (
    AMBER, BLUE, BORDER, DARK, G_DARK, G_MID, G_PALE, INTERV_META, MUTED,
    PURPLE, RED, STATE_ABBREV, _iicon,
)


def view_insights(scores: pd.DataFrame, scores_long: pd.DataFrame,
                  condition: str = "overall", cond_label: str = "All Conditions",
                  state: list = None, top_n: int = 20):
    """Auto-synthesises the 7-dimension data into immediate, specific recommendations.
    Designed to surface AHA moments without the viewer having to go hunting."""

    scores = _ensure_dims(scores)
    scores, _ = _ensure_payer(scores)
    opp_col = _opp_score(scores)
    # Rank by the condition the user selected; tiers stay on the composite
    # (the tier badge is explicitly an overall-opportunity classification).
    scores, rank_col = condition_score(scores, condition)
    # Tiers recalibrated to the selected condition (same selectivity as the
    # composite, so "Priority" keeps one meaning while membership responds).
    scores = scores.copy()
    scores["_tier"] = condition_tier(scores, condition, rank_col)

    # Apply state filter
    filtered = scores.copy()
    if state:
        filtered = filtered[filtered["state_name"].isin(state)]
    if len(filtered) == 0:
        st.warning("No data for the selected filters.")
        return

    geo_label = (
        ", ".join(state[:2]) + (f" +{len(state)-2} more" if len(state) > 2 else "")
        if state else "United States"
    )

    # ── Pre-compute key insight figures ──────────────────────────────────────
    all_sorted = filtered.sort_values(rank_col, ascending=False)
    priority   = filtered[filtered["_tier"] == "Priority"].sort_values(rank_col, ascending=False)
    top3       = all_sorted.head(3)

    # Most underserved = widest gap between Diagnosis Gap and Access to Care
    if "dim_diagnosis_gap" in filtered.columns and "dim_access_to_care" in filtered.columns:
        filtered = filtered.copy()
        filtered["_gap_minus_access"] = filtered["dim_diagnosis_gap"] - filtered["dim_access_to_care"]
        most_underserved = filtered.nlargest(1, "_gap_minus_access").iloc[0]
    else:
        most_underserved = all_sorted.iloc[0]

    # Best payer county = highest MA penetration in Priority tier (or overall)
    payer_col = "ma_penetration_rate" if "ma_penetration_rate" in filtered.columns else None
    base_pool  = priority if len(priority) > 0 else all_sorted
    if payer_col:
        best_payer_county = base_pool.nlargest(1, payer_col).iloc[0]
    else:
        best_payer_county = base_pool.iloc[0]

    # Counterintuitive find = top-quintile score but small estimated pool
    score_threshold = all_sorted[rank_col].quantile(0.80)
    if "total_estimated_pool" in filtered.columns:
        pop_threshold   = filtered["total_estimated_pool"].quantile(0.40)
        surprise_pool   = filtered[
            (filtered[rank_col] >= score_threshold) &
            (filtered["total_estimated_pool"] <= pop_threshold)
        ].sort_values(rank_col, ascending=False)
        surprise = (surprise_pool.iloc[0] if len(surprise_pool) > 0
                    else all_sorted.iloc[min(5, len(all_sorted)-1)])
    else:
        surprise = all_sorted.iloc[min(5, len(all_sorted)-1)]

    # Fastest-growing markets
    traj_col = "dim_trajectory" if "dim_trajectory" in filtered.columns else opp_col
    fast_growing = (
        filtered[filtered[opp_col] >= 40].nlargest(5, traj_col)
        if len(filtered[filtered[opp_col] >= 40]) >= 3
        else all_sorted.head(5)
    )

    n_priority = int((filtered["_tier"] == "Priority").sum())
    n_emerging = int((filtered["_tier"] == "Emerging").sum())

    # ── Banner ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">⚡ Insights &amp; Actions — {cond_label} · {geo_label}</div>
      <div class="banner-stat">Where to move next</div>
      <div class="banner-note">
        Auto-synthesised from 7-dimension scoring across {len(filtered):,} counties ·
        {n_priority} Priority  ·  {n_emerging} Emerging
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Top 3 Action Counties ─────────────────────────────────────────────────
    st.markdown(f"""<div class='ch'>
      <div class='sec-head'>🎯 Top 3 Counties to Act On Now {_iicon(METRIC_TOOLTIPS["opportunity_score"], pos="")}</div>
      <div class='sec-sub'>Highest {'composite opportunity' if condition == 'overall' else cond_label + ' risk'} scores in current filter — these are your first calls · tier = {tier_basis_label(condition, cond_label)}</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col_ui, (_, row) in zip([c1, c2, c3], top3.iterrows()):
        opp    = row.get(rank_col, 0)   # the score actually being ranked on
        pool   = int(row.get("total_estimated_pool", 0))
        interv = str(row.get("recommended_intervention", "Pharmacy-Based Screening"))
        imeta  = INTERV_META.get(interv, {"color": G_MID, "icon": "💊", "desc": interv})
        tier   = str(row.get("_tier", "Developing"))
        tcls   = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
        gap    = row.get("dim_diagnosis_gap", 0)
        gap_lbl = "Critical" if gap >= 70 else "High" if gap >= 50 else "Moderate"
        rank   = int(row.get("priority_rank", 0)) if "priority_rank" in row.index else "—"
        with col_ui:
            st.markdown(f"""
            <div class="card" style="border-left:3px solid {imeta['color']};min-height:215px;">
              <div style="font-size:.66rem;font-weight:700;color:{MUTED};letter-spacing:.04em;">
                NATIONAL RANK #{rank}
              </div>
              <div style="font-size:1.05rem;font-weight:800;color:{G_DARK};line-height:1.25;margin:.1rem 0 .15rem;">
                {row['county_name']}
              </div>
              <div style="font-size:.75rem;color:{MUTED};margin-bottom:.55rem;">{row.get('state_name','')}</div>
              <div style="display:flex;align-items:baseline;gap:.4rem;margin-bottom:.45rem;">
                <span class="pill {tcls}">{tier}</span>
                <span style="font-size:1.35rem;font-weight:900;color:{G_DARK};">{opp:.0f}</span>
                <span style="font-size:.7rem;color:{MUTED};">/100</span>
              </div>
              <div style="font-size:.77rem;color:{DARK};margin-bottom:.22rem;">
                <b>Est. silent pool:</b> {pool:,}
              </div>
              <div style="font-size:.77rem;color:{DARK};margin-bottom:.35rem;">
                <b>Diagnosis gap:</b> <span style="color:{RED};">{gap_lbl}</span>
                ({gap:.0f}/100)
              </div>
              <div style="border-top:1px solid {BORDER};padding-top:.35rem;margin-top:.1rem;
                          font-size:.74rem;color:{imeta['color']};font-weight:700;">
                {imeta['icon']} {interv}
              </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

    # ── Two-column mid section ────────────────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("""<div class='ch'>
          <div class='sec-head'>💳 Best Payer Conversation First</div>
          <div class='sec-sub'>Highest Medicare Advantage penetration in a Priority-tier county</div>
        </div>""", unsafe_allow_html=True)

        ma_rate    = best_payer_county.get("ma_penetration_rate", 0)
        pc_name    = best_payer_county.get("county_name", "—")
        pc_state   = best_payer_county.get("state_name", "")
        pc_pool    = int(best_payer_county.get("total_estimated_pool", 0))
        pc_opp     = best_payer_county.get(opp_col, 0)
        pc_abbr    = STATE_ABBREV.get(pc_state, pc_state)
        ma_pct     = ma_rate * 100 if ma_rate <= 1.0 else ma_rate

        st.markdown(f"""
        <div class="card" style="border-left:3px solid {BLUE};">
          <div style="font-size:.66rem;font-weight:700;color:{MUTED};letter-spacing:.04em;margin-bottom:.1rem;">
            LEAD WITH THIS COUNTY
          </div>
          <div style="font-size:1.1rem;font-weight:800;color:{G_DARK};">{pc_name}, {pc_abbr}</div>
          <div style="font-size:.75rem;color:{MUTED};margin-bottom:.5rem;">
            Opportunity score: {pc_opp:.0f}/100
          </div>
          <div style="font-size:1.7rem;font-weight:900;color:{BLUE};line-height:1;">{ma_pct:.0f}%</div>
          <div style="font-size:.74rem;color:{MUTED};margin-bottom:.5rem;">Medicare Advantage penetration</div>
          <div style="background:{G_PALE};border-radius:6px;padding:.5rem .7rem;
                      font-size:.77rem;color:{DARK};line-height:1.5;">
            📣 <b>Payer pitch:</b> "{pc_name} members have a {ma_pct:.0f}% MA rate
            and {pc_pool:,} undiagnosed patients. Closing this gap directly improves
            your Stars score and reduces downstream complication costs."
          </div>
        </div>""", unsafe_allow_html=True)

    with col_r:
        st.markdown("""<div class='ch'>
          <div class='sec-head'>💡 The Counterintuitive Find</div>
          <div class='sec-sub'>Top-quintile opportunity score · small county · competitors aren't looking here</div>
        </div>""", unsafe_allow_html=True)

        surp_name  = surprise.get("county_name", "—")
        surp_state = surprise.get("state_name", "")
        surp_abbr  = STATE_ABBREV.get(surp_state, surp_state)
        surp_opp   = surprise.get(opp_col, 0)
        surp_pool  = int(surprise.get("total_estimated_pool", 0))
        surp_gap   = surprise.get("dim_diagnosis_gap", 0)
        surp_rank  = int(surprise.get("priority_rank", 0)) if "priority_rank" in surprise.index else "—"

        st.markdown(f"""
        <div class="card" style="border-left:3px solid {AMBER};">
          <div style="font-size:.66rem;font-weight:700;color:{MUTED};letter-spacing:.04em;margin-bottom:.1rem;">
            NOT ON MOST RADARS · RANK #{surp_rank}
          </div>
          <div style="font-size:1.1rem;font-weight:800;color:{G_DARK};">{surp_name}, {surp_abbr}</div>
          <div style="font-size:.75rem;color:{MUTED};margin-bottom:.45rem;">
            Opportunity: {surp_opp:.0f}/100 · Diagnosis gap: {surp_gap:.0f}/100
          </div>
          <div style="font-size:.77rem;color:{DARK};margin-bottom:.45rem;">
            Est. silent pool: <b>{surp_pool:,}</b>
          </div>
          <div style="background:#FEF3C7;border-radius:6px;padding:.5rem .7rem;
                      font-size:.77rem;color:#92400E;line-height:1.5;">
            ⚡ <b>Why it matters:</b> Competitors target large metros. {surp_name} has a
            proportionally larger diagnosis gap and far less field traffic — first-mover
            advantage is still available here.
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

    # ── Bottom two-column section ─────────────────────────────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.markdown("""<div class='ch'>
          <div class='sec-head'>🏘️ Most Underserved Market</div>
          <div class='sec-sub'>Widest gap between disease burden and available care infrastructure</div>
        </div>""", unsafe_allow_html=True)

        us_name   = most_underserved.get("county_name", "—")
        us_state  = most_underserved.get("state_name", "")
        us_abbr   = STATE_ABBREV.get(us_state, us_state)
        us_opp    = most_underserved.get(opp_col, 0)
        us_gap    = most_underserved.get("dim_diagnosis_gap", 0)
        us_access = most_underserved.get("dim_access_to_care", 0)
        us_sdoh   = most_underserved.get("dim_social_determinants", 0)
        us_interv = str(most_underserved.get("recommended_intervention", "Community Health Center Partnership"))
        us_imeta  = INTERV_META.get(us_interv, {"color": PURPLE, "icon": "🏘️", "desc": us_interv})

        st.markdown(f"""
        <div class="card" style="border-left:3px solid {PURPLE};">
          <div style="font-size:1.05rem;font-weight:800;color:{G_DARK};">{us_name}, {us_abbr}</div>
          <div style="font-size:.75rem;color:{MUTED};margin-bottom:.55rem;">Opportunity: {us_opp:.0f}/100</div>
          <div class="sbar-wrap" style="margin-bottom:.3rem;">
            <span style="font-size:.71rem;color:{MUTED};width:7.5rem;flex-shrink:0;">Diagnosis Gap</span>
            <div class="sbar-bg"><div class="sbar-fill" style="width:{us_gap:.0f}%;background:{RED};"></div></div>
            <span class="snum">{us_gap:.0f}</span>
          </div>
          <div class="sbar-wrap" style="margin-bottom:.3rem;">
            <span style="font-size:.71rem;color:{MUTED};width:7.5rem;flex-shrink:0;">Access to Care</span>
            <div class="sbar-bg"><div class="sbar-fill" style="width:{us_access:.0f}%;background:{G_MID};"></div></div>
            <span class="snum">{us_access:.0f}</span>
          </div>
          <div class="sbar-wrap" style="margin-bottom:.55rem;">
            <span style="font-size:.71rem;color:{MUTED};width:7.5rem;flex-shrink:0;">Social Burden</span>
            <div class="sbar-bg"><div class="sbar-fill" style="width:{us_sdoh:.0f}%;background:{PURPLE};"></div></div>
            <span class="snum">{us_sdoh:.0f}</span>
          </div>
          <div style="font-size:.75rem;font-weight:700;color:{us_imeta['color']};">
            {us_imeta['icon']} Recommended: {us_interv}
          </div>
        </div>""", unsafe_allow_html=True)

    with col_r2:
        st.markdown("""<div class='ch'>
          <div class='sec-head'>📈 Fastest-Growing Markets</div>
          <div class='sec-sub'>Highest trajectory scores — move before the window closes</div>
        </div>""", unsafe_allow_html=True)

        rows_html = ""
        for _, row in fast_growing.iterrows():
            traj = row.get(traj_col, 0)
            opp  = row.get(rank_col, 0)
            tier = str(row.get("_tier", "Developing"))
            tcls = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
            st_abbr = STATE_ABBREV.get(row.get("state_name", ""), row.get("state_name", ""))
            rows_html += f"""
            <tr>
              <td style="font-weight:600">{row['county_name']}, {st_abbr}</td>
              <td><span class="pill {tcls}">{tier}</span></td>
              <td style="font-weight:700;color:{G_DARK}">{opp:.0f}</td>
              <td>
                <div class="sbar-wrap">
                  <div class="sbar-bg">
                    <div class="sbar-fill" style="width:{traj:.0f}%;background:#60A5FA;"></div>
                  </div>
                  <span class="snum" style="color:#2563EB">{traj:.0f}</span>
                </div>
              </td>
            </tr>"""

        st.markdown(f"""
        <div class="card">
          <table class="tbl">
            <thead><tr>
              <th>County</th><th>Tier</th><th>Score</th><th>Trajectory ↑</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>""", unsafe_allow_html=True)

    # ── State spotlight (single-state filter only) ────────────────────────────
    if state and len(state) == 1:
        st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)
        sname = state[0]
        st.markdown(f"""<div class='ch'>
          <div class='sec-head'>📍 {sname} State Spotlight</div>
          <div class='sec-sub'>Key intelligence for this specific market</div>
        </div>""", unsafe_allow_html=True)

        sc1, sc2, sc3, sc4 = st.columns(4)
        total_pool = int(filtered["total_estimated_pool"].sum()) if "total_estimated_pool" in filtered.columns else 0
        top_county = all_sorted.iloc[0]

        with sc1:
            st.markdown(f"""<div class="card-dark" style="text-align:center;">
              <div class="big-num-w">{n_priority}</div>
              <div class="label-w">Priority Counties</div>
              <div class="sub-w">Score ≥ 55</div>
            </div>""", unsafe_allow_html=True)
        with sc2:
            st.markdown(f"""<div class="card-blue" style="text-align:center;">
              <div class="big-num-w">{n_emerging}</div>
              <div class="label-w">Emerging Counties</div>
              <div class="sub-w">Score 40–54</div>
            </div>""", unsafe_allow_html=True)
        with sc3:
            pool_m = (f"{total_pool/1_000_000:.1f}M" if total_pool >= 1_000_000
                      else f"{total_pool/1_000:.0f}K")
            st.markdown(f"""<div class="card" style="text-align:center;">
              <div class="big-num">{pool_m}</div>
              <div class="label">Est. Silent Pool</div>
              <div class="sub">State-wide undiagnosed</div>
            </div>""", unsafe_allow_html=True)
        with sc4:
            st.markdown(f"""<div class="card" style="text-align:center;">
              <div style="font-size:1.05rem;font-weight:800;color:{G_DARK};line-height:1.25;">
                {top_county['county_name']}
              </div>
              <div class="label" style="margin-top:.2rem;">Top County</div>
              <div class="sub">Score: {top_county[opp_col]:.0f}/100</div>
            </div>""", unsafe_allow_html=True)

    # ── Summary action banner ─────────────────────────────────────────────────
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    top1       = all_sorted.iloc[0]
    top1_name  = top1.get("county_name", "—")
    top1_state = top1.get("state_name", "")
    top1_abbr  = STATE_ABBREV.get(top1_state, top1_state)
    top1_interv = str(top1.get("recommended_intervention", "Pharmacy-Based Screening"))
    top1_imeta  = INTERV_META.get(top1_interv, {"color": G_MID, "icon": "💊", "desc": top1_interv})

    st.markdown(f"""
    <div class="banner" style="margin-top:.4rem;">
      <div class="banner-title">⚡ Your Next Move</div>
      <div style="font-size:1.4rem;font-weight:800;line-height:1.3;margin:.1rem 0 .3rem;">
        Start in {top1_name}, {top1_abbr} — your highest-scored market right now
      </div>
      <div style="font-size:.88rem;opacity:.85;">
        {top1_imeta['icon']} Recommended program: <b>{top1_interv}</b>&nbsp;&nbsp;·&nbsp;&nbsp;
        {n_priority} Priority-tier counties in current filter ready for outreach
      </div>
    </div>""", unsafe_allow_html=True)
