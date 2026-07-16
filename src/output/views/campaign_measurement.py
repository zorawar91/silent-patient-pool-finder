from __future__ import annotations
# View: Campaign Measurement — matched-control diff-in-diff on CDC PLACES
# diagnosed-prevalence changes.

import pandas as pd
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.theme import BLUE, G_DARK, MUTED, STATE_ABBREV, _iicon

_CM_OUTCOMES = {
    "Type 2 Diabetes (diagnosed prevalence)": ("diabetes_prev_prior", "diabetes_prevalence_pct"),
    "Hypertension (diagnosed prevalence)":    ("htn_prev_prior", "hypertension_prevalence_pct"),
}


def view_campaign_measurement(scores: pd.DataFrame):
    """Matched-control diff-in-diff: did diagnosed prevalence rise faster in
    campaign counties than in statistically similar untouched counties?"""
    st.markdown("""
    <div class="banner">
      <div class="banner-title">Campaign Measurement — Diagnosis-Rate Lift</div>
      <div class="banner-stat">Matched-control diff-in-diff</div>
      <div class="banner-note">
        Select your campaign counties → we match each to its most similar
        untouched counties → lift = how much faster diagnosed prevalence grew
        in your counties, net of the secular trend.
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Inputs ────────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        state_pick = st.multiselect(
            "Campaign states", sorted(scores["state_name"].unique().tolist()),
            key="cm_states")
        county_pool = scores[scores["state_name"].isin(state_pick)] if state_pick else scores
        county_opts = (county_pool["county_name"] + ", "
                       + county_pool["state_name"].map(STATE_ABBREV).fillna("")).tolist()
        fips_by_label = dict(zip(county_opts, county_pool["county_fips"]))
        picked = st.multiselect(
            f"Campaign counties ({len(county_opts):,} available)",
            sorted(county_opts), key="cm_counties")
    with c2:
        outcome_label = st.selectbox("Outcome", list(_CM_OUTCOMES.keys()), key="cm_outcome")
    with c3:
        k = st.slider("Controls per county", 1, 5, 3, key="cm_k")

    fips_text = st.text_input(
        "…or paste county FIPS codes (comma-separated)",
        placeholder="48479, 48215, 36005", key="cm_fips_text")

    treated = [str(fips_by_label[p]).zfill(5) for p in picked]
    if fips_text.strip():
        treated += [f.strip().zfill(5) for f in fips_text.split(",") if f.strip()]
    treated = sorted(set(treated))

    if len(treated) < 5:
        st.markdown("""
        <div class="card" style="padding:1.4rem;text-align:center;margin-top:.8rem;">
          <div style="font-size:2rem;">📐</div>
          <div class="sec-head">Select at least 5 campaign counties</div>
          <div class="sec-sub" style="max-width:600px;margin:0 auto;">
            Fewer than 5 counties rarely has the statistical power to separate a
            campaign effect from noise. For a pre-campaign plan: pick the counties
            you intend to target, export the matched-control list below, and
            <strong>pre-register both lists before launch</strong> — that's what
            makes the post-campaign readout credible.
          </div>
        </div>""", unsafe_allow_html=True)
        return

    pre_col, post_col = _CM_OUTCOMES[outcome_label]
    if pre_col not in scores.columns or post_col not in scores.columns:
        st.error(f"Outcome columns unavailable ({pre_col}/{post_col}) — "
                 "re-run src/ingestion/ingest_real_data.py.")
        return

    # ── Match + estimate ──────────────────────────────────────────────────────
    from src.features.campaign_measurement import diff_in_diff, match_controls
    try:
        match = match_controls(scores, treated, k=k)
        res = diff_in_diff(scores, match.treated_fips, match.control_fips,
                           outcome_pre=pre_col, outcome_post=post_col)
    except ValueError as e:
        st.error(str(e))
        return

    # ── Results ───────────────────────────────────────────────────────────────
    sig_color = G_DARK if (res.significant and res.estimate > 0) else "#F4A261"
    r1, r2, r3, r4 = st.columns(4)
    r1.markdown(f"""<div class="card-dark">
      <div class="label-w">Diagnosis-rate lift{_iicon(METRIC_TOOLTIPS["cm_lift"], tip_cls="tip-r")}</div>
      <div class="big-num-w">{res.estimate:+.2f}pp</div>
      <div class="sub-w">95% CI [{res.ci_low:+.2f}, {res.ci_high:+.2f}]</div></div>""",
      unsafe_allow_html=True)
    r2.markdown(f"""<div class="card" style="border-top:3px solid {sig_color};">
      <div class="label">Verdict{_iicon(METRIC_TOOLTIPS["cm_verdict"])}</div>
      <div style="font-size:.95rem;font-weight:800;color:{sig_color};margin-top:.35rem;">
        {"✅ Significant lift" if (res.significant and res.estimate > 0)
         else ("⚠️ Significant decline" if res.significant else "— Not distinguishable from zero")}
      </div>
      <div class="sub-muted" style="margin-top:.3rem;">bootstrap, 2,000 resamples</div></div>""",
      unsafe_allow_html=True)
    r3.markdown(f"""<div class="card" style="border-top:3px solid {BLUE};">
      <div class="label">Campaign counties{_iicon(METRIC_TOOLTIPS["cm_treated"])}</div>
      <div class="big-num">{res.n_treated}</div>
      <div class="sub-muted">Δ diagnosed: {res.treated_delta:+.2f}pp</div></div>""",
      unsafe_allow_html=True)
    r4.markdown(f"""<div class="card" style="border-top:3px solid #8338EC;">
      <div class="label">Matched controls{_iicon(METRIC_TOOLTIPS["cm_controls"])}</div>
      <div class="big-num">{res.n_control}</div>
      <div class="sub-muted">Δ diagnosed: {res.control_delta:+.2f}pp</div></div>""",
      unsafe_allow_html=True)

    # ── Covariate balance ────────────────────────────────────────────────────
    with st.expander("⚖️ Matching quality (covariate balance)"):
        bal = match.balance.reset_index().rename(columns={"index": "covariate"})
        rows = "".join(
            f"<tr><td>{r['covariate']}</td>"
            f"<td style='text-align:right;'>{r['treated_mean']:,.3f}</td>"
            f"<td style='text-align:right;'>{r['control_mean']:,.3f}</td>"
            f"<td style='text-align:right;color:{MUTED};'>{r['pool_mean']:,.3f}</td></tr>"
            for _, r in bal.iterrows()
        )
        st.markdown(
            f'<table class="tbl"><thead><tr><th>Covariate</th><th>Campaign mean</th>'
            f'<th>Matched-control mean</th><th>All-US mean</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:.7rem;color:{MUTED};margin-top:.4rem;'>"
                    f"Good matching: control means close to campaign means, both "
                    f"potentially far from the US average.</div>", unsafe_allow_html=True)

    # ── Pre-registration export ──────────────────────────────────────────────
    pairs = pd.DataFrame(
        [(t, c) for t, ctrls in match.control_map.items() for c in ctrls],
        columns=["campaign_county_fips", "matched_control_fips"])
    st.download_button(
        "⬇️  Export pre-registration file (campaign + matched controls)",
        pairs.to_csv(index=False),
        file_name="sppf_campaign_preregistration.csv", mime="text/csv", key="cm_dl")

    st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};margin-top:.8rem;line-height:1.6;">
      <strong>Read this before quoting the number:</strong>
      Outcomes are CDC PLACES <em>diagnosed</em> prevalence between the two most
      recent releases (~2-year spacing) — suited to multi-year campaigns, not
      quarterly pulses. Matching is on observables only; pre-register the county
      and control lists before launch. PLACES model-smoothing limits power in
      small counties. Claims-data integration would tighten both the time window
      and the confidence intervals.
    </div>""", unsafe_allow_html=True)
