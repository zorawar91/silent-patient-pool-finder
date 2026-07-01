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
    df["opportunity_tier"] = pd.cut(
        df["opportunity_score"],
        bins=[0, 40, 70, 100],
        labels=["Developing", "Emerging", "Priority"],
        include_lowest=True,
    )

    # Recommended intervention
    df["recommended_intervention"] = df.apply(_recommend_intervention, axis=1)

    # Investment priority rank
    df["priority_rank"] = df["opportunity_score"].rank(ascending=False).astype(int)

    log.info(
        f"Dimension scoring complete. "
        f"Priority counties: {(df['opportunity_score'] >= 70).sum()}, "
        f"Emerging: {((df['opportunity_score'] >= 40) & (df['opportunity_score'] < 70)).sum()}"
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
    Core signal: treatment penetration gap + diagnostic orphan ratio.
    """
    score = np.zeros(len(df))

    # Treatment penetration gap — higher gap = higher score
    if "cms_t2d_diagnosed_rate" in df.columns and "diabetes_prevalence_pct" in df.columns:
        # In Medicare population, some T2D is already found —
        # compare against estimated true prevalence from CDC PLACES
        gap = (df["diabetes_prevalence_pct"] - df["cms_t2d_diagnosed_rate"] * 0.6).clip(lower=0)
        score += 40 * _norm(gap)

    # Diagnostic orphan ratio (from existing pipeline signals)
    if signals is not None and "diagnostic_orphan_ratio" in signals.columns:
        t2d_sig = signals[signals["condition"] == "t2d"].groupby("county_fips")[
            "diagnostic_orphan_ratio"
        ].mean()
        orphan = df["county_fips"].map(t2d_sig).fillna(t2d_sig.median())
        score += 30 * _norm(orphan)
    elif "ses_disadvantage_index" in df.columns:
        # Proxy: high SES disadvantage + low checkup = high orphan ratio
        checkup_inv = 1 - df.get("annual_checkup_pct", pd.Series(0.72, index=df.index))
        score += 30 * _norm(0.5 * df["ses_disadvantage_index"] + 0.5 * checkup_inv)

    # Low checkup rate signals patients not presenting for care
    if "annual_checkup_pct" in df.columns:
        score += 20 * _norm(1 - df["annual_checkup_pct"])

    # Uninsured rate (uninsured patients can't afford diagnosis)
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
    """
    score = np.zeros(len(df))

    if "poverty_rate" in df.columns:
        score += 30 * _norm(df["poverty_rate"])

    if "ses_disadvantage_index" in df.columns:
        score += 25 * _norm(df["ses_disadvantage_index"])

    if "racial_risk_index" in df.columns:
        score += 20 * _norm(df["racial_risk_index"])

    if "uninsured_rate" in df.columns:
        score += 15 * _norm(df["uninsured_rate"])

    # Low education = health literacy barrier
    if "hs_graduation_rate" in df.columns:
        score += 10 * _norm(1 - df["hs_graduation_rate"])

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
    Currently uses demographic proxies; real version uses multi-year CMS/CDC trend data.
    """
    score = np.zeros(len(df))

    # Aging population = future T2D burden growing (T2D risk increases with age)
    if "median_age" in df.columns:
        score += 40 * _norm(df["median_age"])

    # Obesity rate trend proxy — high current obesity = high future T2D incidence
    if "obesity_rate_pct" in df.columns:
        score += 30 * _norm(df["obesity_rate_pct"])

    # Rural + high SDoH = gap likely widening (less investment, more need)
    if "ses_disadvantage_index" in df.columns and "is_rural" in df.columns:
        widening_proxy = (
            0.6 * df["ses_disadvantage_index"] +
            0.4 * df["is_rural"].astype(float)
        )
        score += 30 * _norm(widening_proxy)

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
