from __future__ import annotations
# 7-Dimension Opportunity Scorer
# ================================
# Computes all 7 dimension scores (0-100) for each county,
# then produces a weighted composite Opportunity Score.
#
# Dimensions:
#   1. disease_burden       — how large is the total problem?
#   2. diagnosis_gap        — how much is undiagnosed/untreated?
#   3. access_to_care       — can a screened patient get treatment?
#   4. social_determinants  — what's causing the gap?
#   5. payer_landscape      — who pays, and what are their incentives?
#   6. commercial_readiness — how easy is it to run a program here?
#   7. trajectory           — is the opportunity growing or shrinking?

import logging
import numpy as np
import pandas as pd
import yaml
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler

log = logging.getLogger(__name__)

DIMENSIONS_CONFIG = "config/dimensions.yaml"

# Dimension weights (from config/dimensions.yaml)
DEFAULT_WEIGHTS = {
    "disease_burden":      0.20,
    "diagnosis_gap":       0.25,
    "access_to_care":      0.15,
    "social_determinants": 0.15,
    "payer_landscape":     0.10,
    "commercial_readiness":0.10,
    "trajectory":          0.05,
}


def compute_all_dimensions(
    panel: pd.DataFrame,
    orig_signals: pd.DataFrame | None = None,
    config_path: str = DIMENSIONS_CONFIG,
) -> pd.DataFrame:
    """
    Compute all 7 dimension scores for every county.

    Parameters
    ----------
    panel       : output of data_loader.load_all() — one row per county
    orig_signals: features_long from existing pipeline (for signal reuse)
    config_path : path to dimensions.yaml

    Returns
    -------
    DataFrame with county_fips + 7 dim scores (0-100) + composite (0-100)
    + intervention recommendation
    """
    weights = _load_weights(config_path)
    df = panel.copy()

    log.info("Computing 7 dimension scores ...")
    df = _dim_disease_burden(df)
    df = _dim_diagnosis_gap(df, orig_signals)
    df = _dim_access_to_care(df)
    df = _dim_social_determinants(df)
    df = _dim_payer_landscape(df)
    df = _dim_commercial_readiness(df, orig_signals)
    df = _dim_trajectory(df)

    # Composite opportunity score
    dim_cols = [
        "dim_disease_burden", "dim_diagnosis_gap", "dim_access_to_care",
        "dim_social_determinants", "dim_payer_landscape",
        "dim_commercial_readiness", "dim_trajectory",
    ]
    weight_vals = [
        weights["disease_burden"], weights["diagnosis_gap"],
        weights["access_to_care"], weights["social_determinants"],
        weights["payer_landscape"], weights["commercial_readiness"],
        weights["trajectory"],
    ]
    df["opportunity_score"] = sum(
        df[col] * w for col, w in zip(dim_cols, weight_vals)
    )

    # Opportunity tier
    # Threshold calibrated to 5 real data sources (CDC PLACES, Census ACS, CMS MA,
    # HRSA, County Health Rankings). Max observable score ~60-62; top 10 counties
    # score 55-61. Threshold of 55 selects the top ~0.3% of counties.
    #   ≥55 = Priority   (confirmed high-need by multiple real sources)
    #   40-55 = Emerging  (meaningful opportunity; watch for new data)
    #   <40  = Developing (lower near-term priority)
    df["opportunity_tier"] = pd.cut(
        df["opportunity_score"],
        bins=[0, 40, 55, 100],
        labels=["Developing", "Emerging", "Priority"],
        include_lowest=True,
    )

    # Recommended intervention
    df["recommended_intervention"] = df.apply(_recommend_intervention, axis=1)

    # Investment priority rank
    df["priority_rank"] = df["opportunity_score"].rank(ascending=False).astype(int)

    # Percentile score (0-100 = share of counties this county outranks).
    # This is the buyer-facing number: "94th percentile" is self-explanatory,
    # whereas the raw weighted composite tops out around ~62 by construction.
    df["opportunity_percentile"] = (
        df["opportunity_score"].rank(pct=True) * 100
    ).round(1)

    # Data-coverage confidence grade (A/B/C) per county
    df["confidence_grade"], df["confidence_sources"] = _confidence_grade(df)

    log.info(
        f"Dimension scoring complete. "
        f"Priority counties: {(df['opportunity_score'] >= 55).sum()}, "
        f"Emerging: {((df['opportunity_score'] >= 40) & (df['opportunity_score'] < 55)).sum()}"
    )
    return df


# ── Dimension 1: Disease Burden ───────────────────────────────────────────────

def _dim_disease_burden(df: pd.DataFrame) -> pd.DataFrame:
    """
    How large is the total undiagnosed opportunity?
    Combines: T2D prevalence, obesity (risk amplifier), comorbidities,
    hospitalization signal, poor physical health.
    """
    score = np.zeros(len(df))

    # T2D prevalence (primary signal)
    if "diabetes_prevalence_pct" in df.columns:
        score += 40 * _norm(df["diabetes_prevalence_pct"])

    # Obesity rate (strong T2D predictor / comorbidity)
    if "obesity_rate_pct" in df.columns:
        score += 25 * _norm(df["obesity_rate_pct"])

    # Hypertension co-occurrence (metabolic syndrome signal)
    if "hypertension_prevalence_pct" in df.columns:
        score += 15 * _norm(df["hypertension_prevalence_pct"])

    # Poor physical health (proxy for disease burden / untreated conditions)
    if "poor_physical_health_pct" in df.columns:
        score += 10 * _norm(df["poor_physical_health_pct"])

    # SES disadvantage as burden amplifier
    if "ses_disadvantage_index" in df.columns:
        score += 10 * _norm(df["ses_disadvantage_index"])

    df["dim_disease_burden"] = score.clip(0, 100)
    return df


# ── Dimension 2: Diagnosis Gap ────────────────────────────────────────────────

def _dim_diagnosis_gap(df: pd.DataFrame, signals: pd.DataFrame | None) -> pd.DataFrame:
    """
    How much of the disease burden is hidden from the healthcare system?

    Signal design (weights sum to 100):
      T2D gap    35 — CDC PLACES prevalence × below-average CMS diagnosis rate
      HTN gap    20 — CMS Medicare HTN rate relative to national county median
                      (real CMS GV PUF signal; counties diagnosing fewer HTN
                       cases than the national Medicare average have a larger gap)
      Orphan     25 — diagnostic orphan proxy: SES disadvantage + low checkup
      Checkup    10 — low annual checkup rate = patients not entering the system
      Uninsured  10 — inability to afford diagnosis = hidden burden

    All CMS signals use within-sample medians as the reference baseline so the
    score reflects relative county performance, not absolute Medicare prevalence.
    """
    score = np.zeros(len(df))

    # A CMS column with (near-)zero variance is a filled national constant,
    # not data — treat it as absent so the honest fallback runs. A flat
    # default once shipped here masquerading as a real detection signal.
    def _real(col: str) -> bool:
        return col in df.columns and float(
            pd.to_numeric(df[col], errors="coerce").std() or 0.0) > 1e-9

    # ── T2D treatment penetration gap (CMS GV PUF × CDC PLACES) ─────────────
    # CDC PLACES diabetes_prevalence_pct = adults diagnosed with T2D (general pop)
    # cms_t2d_diagnosed_rate = % Medicare benes with T2D Dx code (≥65 population)
    # A county below the national Medicare median is catching FEWER T2D cases
    # than its peers → the gap between true burden and detected burden is wider.
    if _real("cms_t2d_diagnosed_rate") and "diabetes_prevalence_pct" in df.columns:
        cms_med = df["cms_t2d_diagnosed_rate"].median()
        # Below-median counties have a detection deficit
        cms_deficit = (cms_med - df["cms_t2d_diagnosed_rate"]).clip(lower=0)
        # Amplify by CDC burden: high prevalence + detection deficit = larger gap
        t2d_gap = df["diabetes_prevalence_pct"] * (1.0 + cms_deficit)
        score += 35 * _norm(t2d_gap)
    elif "diabetes_prevalence_pct" in df.columns:
        # No CMS data — use CDC burden alone (scaled by national undiagnosed fraction)
        score += 35 * _norm(df["diabetes_prevalence_pct"] * 0.231)

    # ── HTN diagnosis gap (CMS GV PUF real signal) ───────────────────────────
    # Medicare HTN diagnosed rate nationally ~57-60%; counties below median are
    # systematically failing to identify hypertension in their Medicare population.
    # HTN is the most common undiagnosed condition (27% undiagnosed per AHA).
    if _real("cms_htn_diagnosed_rate"):
        htn_med = df["cms_htn_diagnosed_rate"].median()
        htn_deficit = (htn_med - df["cms_htn_diagnosed_rate"]).clip(lower=0)
        score += 20 * _norm(htn_deficit)
    else:
        # CMS HTN signal unavailable — redistribute its 20 weight across the
        # remaining REAL gap signals (care-seeking + affordability) rather
        # than award a hidden flat constant.
        if "annual_checkup_pct" in df.columns:
            score += 10 * _norm(1 - df["annual_checkup_pct"])
        if "uninsured_rate" in df.columns:
            score += 10 * _norm(df["uninsured_rate"])

    # ── Diagnostic orphan proxy ───────────────────────────────────────────────
    # Proxy: counties with high SES disadvantage AND low checkup rates have the
    # highest diagnostic orphan ratio (lab ordered, no follow-up Rx).
    if signals is not None and "diagnostic_orphan_ratio" in signals.columns:
        t2d_sig = signals[signals["condition"] == "t2d"].groupby("county_fips")[
            "diagnostic_orphan_ratio"
        ].mean()
        orphan = df["county_fips"].map(t2d_sig).fillna(t2d_sig.median())
        score += 25 * _norm(orphan)
    elif "ses_disadvantage_index" in df.columns:
        checkup_inv = 1 - df.get("annual_checkup_pct", pd.Series(0.72, index=df.index))
        score += 25 * _norm(0.5 * df["ses_disadvantage_index"] + 0.5 * checkup_inv)

    # ── Annual checkup rate (care-seeking behaviour) ──────────────────────────
    if "annual_checkup_pct" in df.columns:
        score += 10 * _norm(1 - df["annual_checkup_pct"])

    # ── Uninsured rate (cost barrier to diagnosis) ────────────────────────────
    if "uninsured_rate" in df.columns:
        score += 10 * _norm(df["uninsured_rate"])

    df["dim_diagnosis_gap"] = score.clip(0, 100)
    return df


# ── Dimension 3: Access to Care ───────────────────────────────────────────────

def _dim_access_to_care(df: pd.DataFrame) -> pd.DataFrame:
    """
    Can a patient who is identified actually get diagnosed and treated?
    NOTE: Low access = HIGH gap score (inverted — shortage = opportunity challenge).
    We score ACCESS (higher = better infrastructure), not shortage.
    """
    score = np.zeros(len(df))

    # HPSA designation = shortage = LOW access
    if "hpsa_flag" in df.columns:
        score += 35 * _norm(1 - df["hpsa_flag"].clip(0, 1))

    # FQHC presence = some safety net exists
    if "fqhc_present" in df.columns:
        score += 25 * _norm(df["fqhc_present"])

    # Rural = lower access
    if "is_rural" in df.columns:
        score += 20 * _norm(1 - df["is_rural"].astype(float))

    # Checkup rate as proxy for primary care utilization
    if "annual_checkup_pct" in df.columns:
        score += 20 * _norm(df["annual_checkup_pct"])

    df["dim_access_to_care"] = score.clip(0, 100)
    return df


# ── Dimension 4: Social Determinants ─────────────────────────────────────────

def _dim_social_determinants(df: pd.DataFrame) -> pd.DataFrame:
    """
    What structural factors are driving the diagnosis gap?
    High score = high SDoH burden = complex but important target.

    Weights (sum = 100):
      poverty_rate          25  — core economic hardship
      ses_disadvantage_idx  25  — composite deprivation
      racial_risk_index     20  — structural-risk uplift. NOTE: currently an
                                   SES-derived proxy (0.15 + 0.35 × SES index),
                                   NOT demographic composition data. Rename /
                                   replace with real ACS demographics before
                                   any claim referencing demographics is made.
      uninsured_rate        15  — insurance access barrier
      food_desert_pct       10  — USDA Food Environment Atlas (real) or CHR proxy
      hs_graduation_rate     5  — health literacy barrier
    """
    score = np.zeros(len(df))

    if "poverty_rate" in df.columns:
        score += 25 * _norm(df["poverty_rate"])

    if "ses_disadvantage_index" in df.columns:
        score += 25 * _norm(df["ses_disadvantage_index"])

    if "racial_risk_index" in df.columns:
        score += 20 * _norm(df["racial_risk_index"])

    if "uninsured_rate" in df.columns:
        score += 15 * _norm(df["uninsured_rate"])

    # Food desert: % population with low access to grocery stores
    # Real: USDA Food Environment Atlas (PCT_LACCESS_POP15)
    # Proxy: CHR food_insecurity_pct when USDA unavailable
    if "food_desert_pct" in df.columns:
        score += 10 * _norm(df["food_desert_pct"])

    # Low education = health literacy barrier
    if "hs_graduation_rate" in df.columns:
        score += 5 * _norm(1 - df["hs_graduation_rate"])

    df["dim_social_determinants"] = score.clip(0, 100)
    return df


# ── Dimension 5: Payer Landscape ──────────────────────────────────────────────

def _dim_payer_landscape(df: pd.DataFrame) -> pd.DataFrame:
    """
    Who insures these patients, and what are their program funding incentives?
    High MA penetration = Medicare Advantage plan has Stars incentives to fund screening.
    """
    score = np.zeros(len(df))

    # MA penetration — MA plans have quality metric incentives (Stars ratings)
    if "ma_penetration_rate" in df.columns:
        score += 40 * _norm(df["ma_penetration_rate"])

    # Medicaid penetration — MCOs have HEDIS incentives
    if "medicaid_rate" in df.columns:
        score += 30 * _norm(df["medicaid_rate"])

    # Commercial coverage — employer wellness opportunity
    if "commercial_rate" in df.columns:
        score += 20 * _norm(df["commercial_rate"])

    # Dual eligible (Medicare + Medicaid) = highest-need, highest-incentive
    if "dual_eligible_rate" in df.columns:
        score += 10 * _norm(df["dual_eligible_rate"])
    else:
        # Proxy: high Medicare + high Medicaid counties likely have dual eligibles
        if "ma_penetration_rate" in df.columns and "medicaid_rate" in df.columns:
            dual_proxy = (df["ma_penetration_rate"] * df["medicaid_rate"]).clip(0, 1)
            score += 10 * _norm(dual_proxy)

    df["dim_payer_landscape"] = score.clip(0, 100)
    return df


# ── Dimension 6: Commercial Readiness ─────────────────────────────────────────

def _dim_commercial_readiness(df: pd.DataFrame, signals: pd.DataFrame | None) -> pd.DataFrame:
    """
    How feasible is it to actually launch and scale a program here?
    Combines pharmacy access, digital readiness, existing program infrastructure.
    """
    score = np.zeros(len(df))

    # Broadband access = digital health program feasibility
    if "broadband_access_rate" in df.columns:
        score += 30 * _norm(df["broadband_access_rate"])

    # Urban/suburban = better pharmacy density and infrastructure
    if "is_rural" in df.columns:
        score += 25 * _norm(1 - df["is_rural"].astype(float))

    # OTC proxy score = patients already engaging with health products
    if signals is not None and "otc_proxy_score" in signals.columns:
        t2d_otc = signals[signals["condition"] == "t2d"].groupby("county_fips")[
            "otc_proxy_score"
        ].mean()
        otc = df["county_fips"].map(t2d_otc).fillna(t2d_otc.median())
        score += 25 * _norm(otc)
    else:
        # Proxy: higher income = more OTC purchasing
        if "median_household_income" in df.columns:
            score += 25 * _norm(df["median_household_income"])

    # Annual checkup rate = existing care relationship (easier to recruit)
    if "annual_checkup_pct" in df.columns:
        score += 20 * _norm(df["annual_checkup_pct"])

    df["dim_commercial_readiness"] = score.clip(0, 100)
    return df


# ── Dimension 7: Trajectory ───────────────────────────────────────────────────

def _dim_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Is the opportunity growing or shrinking?
    High score = widening gap OR growing high-risk population = move now.

    Signal design (weights sum to 100):
      T2D prevalence trend  35  — CDC PLACES YoY delta (2020→2022 data)
                                   Real: counties where diabetes burden increased
                                   Proxy (if prior unavailable): aging + obesity
      HTN prevalence trend  20  — CDC PLACES YoY delta for hypertension
                                   Real: counties where HTN burden increased
      Aging population      25  — median_age (future T2D/HTN incidence driver)
      SDoH + rural          20  — high deprivation + rural = gap widening trend

    CDC PLACES prior-year data covers the PLACES 2022 release (2020 BRFSS data).
    Current covers the PLACES 2024 release (2022 BRFSS data).
    Positive trend = prevalence growing = opportunity expanding.
    """
    score = np.zeros(len(df))

    # ── T2D prevalence trend (real CDC PLACES YoY) ───────────────────────────
    # Positive delta = diabetes burden grew between releases = gap widening
    has_t2d_trend = "diabetes_trend" in df.columns and df["diabetes_trend"].notna().sum() > 100
    if has_t2d_trend:
        # Counties with growing T2D burden score higher on trajectory
        score += 35 * _norm(df["diabetes_trend"].fillna(0))
    else:
        # Proxy: aging + obesity = future T2D incidence driver
        if "obesity_rate_pct" in df.columns:
            score += 35 * _norm(df["obesity_rate_pct"])

    # ── HTN prevalence trend (real CDC PLACES YoY) ───────────────────────────
    has_htn_trend = "htn_trend" in df.columns and df["htn_trend"].notna().sum() > 100
    if has_htn_trend:
        score += 20 * _norm(df["htn_trend"].fillna(0))
    else:
        # Proxy: high SES disadvantage → more untreated HTN progression
        if "ses_disadvantage_index" in df.columns:
            score += 20 * _norm(df["ses_disadvantage_index"])

    # ── Aging population (future burden driver — always real from Census ACS) ─
    if "median_age" in df.columns:
        score += 25 * _norm(df["median_age"])

    # ── Rural + SDoH (structural factors that make gaps widen over time) ──────
    if "ses_disadvantage_index" in df.columns and "is_rural" in df.columns:
        widening_proxy = (
            0.6 * df["ses_disadvantage_index"] +
            0.4 * df["is_rural"].astype(float)
        )
        score += 20 * _norm(widening_proxy)
    elif "ses_disadvantage_index" in df.columns:
        score += 20 * _norm(df["ses_disadvantage_index"])

    df["dim_trajectory"] = score.clip(0, 100)
    return df


# ── Intervention Recommendation ───────────────────────────────────────────────

def _recommend_intervention(row: pd.Series) -> str:
    """
    Select the most appropriate program type based on the county's dimension profile.
    Maps to 5 intervention types from dimensions.yaml.
    """
    payer   = row.get("dim_payer_landscape", 50)
    access  = row.get("dim_access_to_care", 50)
    sdoh    = row.get("dim_social_determinants", 50)
    ready   = row.get("dim_commercial_readiness", 50)
    ma_rate = row.get("ma_penetration_rate", 0.3)
    rural   = row.get("is_rural", False)
    broadband = row.get("broadband_access_rate", 0.7)
    commercial = row.get("commercial_rate", 0.4)

    # Payer Partnership: high MA penetration, good payer incentives
    if payer >= 65 and ma_rate >= 0.35:
        return "Payer Partnership Program"

    # Community Health: high SDoH burden, low access
    if sdoh >= 65 and access <= 45:
        return "Community Health Center Partnership"

    # Employer Wellness: high commercial, urban/suburban
    if commercial >= 0.45 and not rural:
        return "Employer Wellness Program"

    # Digital Health: high broadband, good commercial coverage
    if broadband >= 0.75 and commercial >= 0.40:
        return "Digital Health Program"

    # Default: Pharmacy-based screening
    return "Pharmacy-Based Screening"


# ── Weight Sensitivity ────────────────────────────────────────────────────────

DIM_ORDER = ["disease_burden", "diagnosis_gap", "access_to_care",
             "social_determinants", "payer_landscape",
             "commercial_readiness", "trajectory"]


def recompute_composite(df: pd.DataFrame, weights: dict) -> pd.Series:
    """
    Recompute the composite opportunity score from existing dim_* columns
    under a custom weight set. Weights are normalised to sum to 1, so the
    caller can pass any non-negative numbers (e.g. raw slider values).
    """
    total = sum(max(float(weights.get(k, 0.0)), 0.0) for k in DIM_ORDER)
    if total <= 0:
        raise ValueError("At least one weight must be positive")
    score = pd.Series(0.0, index=df.index)
    for k in DIM_ORDER:
        w = max(float(weights.get(k, 0.0)), 0.0) / total
        col = f"dim_{k}"
        if col in df.columns:
            score = score + w * df[col].fillna(df[col].median())
    return score.clip(0, 100)


def rank_stability(base: pd.Series, custom: pd.Series, top_n: int = 50) -> dict:
    """
    How much does the ranking move when weights change?

    Returns:
      spearman     — rank correlation across all rows (1.0 = identical order)
      top_overlap  — share of the default top-N still in the custom top-N
      max_jump     — largest absolute rank change among default top-N rows
    """
    r_base = base.rank(ascending=False)
    r_cust = custom.rank(ascending=False)
    spearman = float(base.corr(custom, method="spearman"))
    top_base = set(r_base.nsmallest(top_n).index)
    top_cust = set(r_cust.nsmallest(top_n).index)
    overlap = len(top_base & top_cust) / max(top_n, 1)
    max_jump = int((r_cust - r_base).loc[list(top_base)].abs().max()) if top_base else 0
    return {"spearman": spearman, "top_overlap": overlap, "max_jump": max_jump}


# ── Confidence Grade ──────────────────────────────────────────────────────────

# One representative column per real data source. A county's confidence grade
# reflects how many independent sources actually cover it — counties scored
# mostly from fallback proxies get a visibly lower grade.
_SOURCE_MARKERS = {
    "CDC PLACES":             "diabetes_prevalence_pct",
    "CDC PLACES prior":       "diabetes_prev_prior",
    "Census ACS":             "poverty_rate",
    "CMS GV PUF":             "ma_penetration_rate",
    "HRSA":                   "hpsa_flag",
    "County Health Rankings": "chr_poor_health_pct",
    "USDA Food Atlas":        "food_desert_pct",
}


def _confidence_grade(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    Grade each row by how many real data sources cover it.

    Uses confidence_sources_raw (pre-fill coverage captured by
    ingest_real_data._fill_missing) when available — AFTER the panel's
    median-fill step, notna() would report full coverage everywhere.

    Returns (grade, n_sources):
      A — 6+ of 7 sources present   (fully corroborated)
      B — 4-5 sources               (solid, minor gaps)
      C — <4 sources                (score leans on proxies; treat with caution)
    """
    if "confidence_sources_raw" in df.columns:
        present = df["confidence_sources_raw"].fillna(0).astype(int)
    else:
        present = pd.Series(0, index=df.index, dtype=int)
        for col in _SOURCE_MARKERS.values():
            if col in df.columns:
                present += df[col].notna().astype(int)

    grade = pd.Series("C", index=df.index)
    grade[present >= 4] = "B"
    grade[present >= 6] = "A"
    return grade, present


# ── Utilities ─────────────────────────────────────────────────────────────────

def _norm(series: pd.Series) -> pd.Series:
    """Min-max normalize a Series to [0, 1], handling edge cases."""
    s = pd.to_numeric(series, errors="coerce").fillna(series.median() or 0)
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


def _load_weights(config_path: str) -> dict:
    """Load dimension weights from YAML config."""
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return {k: v["weight"] for k, v in cfg["dimensions"].items()}
    except Exception:
        return DEFAULT_WEIGHTS
