"""Unit tests for the 7-dimension scorer — the core scoring logic.

Covers: score bounds, missing-column fallbacks, directionality (worse inputs
score higher on gap/burden dimensions), weight loading, and _norm edge cases.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.dimension_scorer import (
    DEFAULT_WEIGHTS,
    t2d_undiagnosed_rate,
    _norm,
    compute_all_dimensions,
    estimate_undiagnosed_pool,
    load_weights,
)

DIM_COLS = [
    "dim_disease_burden", "dim_diagnosis_gap", "dim_access_to_care",
    "dim_social_determinants", "dim_payer_landscape",
    "dim_commercial_readiness", "dim_trajectory",
]


def _panel(n: int = 30, seed: int = 7) -> pd.DataFrame:
    """Small synthetic county panel covering every column the scorer reads."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "county_fips":                 [f"{i:05d}" for i in range(n)],
        "population":                  rng.integers(2_000, 500_000, n),
        "diabetes_prevalence_pct":     rng.uniform(5, 18, n),
        "obesity_rate_pct":            rng.uniform(20, 45, n),
        "hypertension_prevalence_pct": rng.uniform(25, 45, n),
        "poor_physical_health_pct":    rng.uniform(8, 20, n),
        "ses_disadvantage_index":      rng.uniform(0, 1, n),
        "cms_t2d_diagnosed_rate":      rng.uniform(0.15, 0.35, n),
        "cms_htn_diagnosed_rate":      rng.uniform(0.45, 0.70, n),
        "annual_checkup_pct":          rng.uniform(0.55, 0.85, n),
        "uninsured_rate":              rng.uniform(0.03, 0.25, n),
        "hpsa_flag":                   rng.integers(0, 2, n),
        "fqhc_present":                rng.integers(0, 2, n),
        "is_rural":                    rng.integers(0, 2, n).astype(bool),
        "poverty_rate":                rng.uniform(0.05, 0.30, n),
        "racial_risk_index":           rng.uniform(0.1, 0.6, n),
        "food_desert_pct":             rng.uniform(0, 0.4, n),
        "hs_graduation_rate":          rng.uniform(0.7, 0.98, n),
        "ma_penetration_rate":         rng.uniform(0.1, 0.6, n),
        "medicaid_rate":               rng.uniform(0.05, 0.4, n),
        "commercial_rate":             rng.uniform(0.2, 0.7, n),
        "broadband_access_rate":       rng.uniform(0.5, 0.98, n),
        "median_household_income":     rng.uniform(35_000, 110_000, n),
        "median_age":                  rng.uniform(30, 55, n),
        "diabetes_trend":              rng.uniform(-1.5, 1.5, n),
        "htn_trend":                   rng.uniform(-1.5, 1.5, n),
    })


def test_all_dimension_scores_within_bounds():
    out = compute_all_dimensions(_panel())
    for col in DIM_COLS + ["opportunity_score"]:
        assert col in out.columns, f"missing {col}"
        assert out[col].between(0, 100).all(), f"{col} outside [0, 100]"


def test_output_has_tier_rank_percentile_confidence():
    out = compute_all_dimensions(_panel())
    assert set(out["opportunity_tier"].dropna().unique()) <= {"Developing", "Emerging", "Priority"}
    assert out["priority_rank"].min() == 1
    assert out["opportunity_percentile"].between(0, 100).all()
    assert set(out["confidence_grade"].unique()) <= {"A", "B", "C"}
    assert out["recommended_intervention"].notna().all()


def test_missing_columns_fall_back_without_crashing():
    # Only the bare minimum a panel could carry — every dimension must still
    # produce a bounded score via its fallback branch.
    minimal = _panel()[["county_fips", "diabetes_prevalence_pct",
                        "ses_disadvantage_index", "is_rural"]]
    out = compute_all_dimensions(minimal)
    for col in DIM_COLS + ["opportunity_score"]:
        assert out[col].between(0, 100).all(), f"{col} outside [0, 100] on minimal panel"


def test_diagnosis_gap_directionality():
    # A county with high uninsured rate + low checkup rate must not score
    # LOWER on diagnosis gap than an otherwise-identical well-served county.
    df = _panel()
    worst, best = 0, 1
    df.loc[worst, ["uninsured_rate", "annual_checkup_pct", "ses_disadvantage_index"]] = [0.30, 0.40, 1.0]
    df.loc[best,  ["uninsured_rate", "annual_checkup_pct", "ses_disadvantage_index"]] = [0.01, 0.95, 0.0]
    # Equalise the CMS/prevalence signals so only care-seeking varies
    for col in ["diabetes_prevalence_pct", "cms_t2d_diagnosed_rate", "cms_htn_diagnosed_rate"]:
        df.loc[[worst, best], col] = df[col].median()
    out = compute_all_dimensions(df)
    assert out.loc[worst, "dim_diagnosis_gap"] > out.loc[best, "dim_diagnosis_gap"]


def test_constant_cms_column_treated_as_absent():
    # A zero-variance CMS column is a filled national constant, not data —
    # the scorer must not crash and must still produce bounded scores.
    df = _panel()
    df["cms_t2d_diagnosed_rate"] = 0.25
    df["cms_htn_diagnosed_rate"] = 0.57
    out = compute_all_dimensions(df)
    assert out["dim_diagnosis_gap"].between(0, 100).all()


def test_load_weights_missing_file_falls_back_to_defaults():
    w = load_weights("does/not/exist.yaml")
    assert w == DEFAULT_WEIGHTS


def test_load_weights_malformed_config_raises(tmp_path):
    bad = tmp_path / "dimensions.yaml"
    bad.write_text("dimensions:\n  disease_burden: not-a-mapping\n")
    with pytest.raises(ValueError):
        load_weights(str(bad))


def test_load_weights_real_config_sums_to_one():
    w = load_weights()
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_compute_all_dimensions_writes_total_pool():
    out = compute_all_dimensions(_panel())
    assert "total_estimated_pool" in out.columns
    assert (out["total_estimated_pool"] >= 0).all()
    assert out["total_estimated_pool"].sum() > 0


def test_pool_formula_and_components():
    df = pd.DataFrame({
        "population": [100_000, 0, 50_000],
        "diabetes_prevalence_pct": [0.10, 0.10, 0.10],
        "hypertension_prevalence_pct": [0.30, 0.30, 0.30],
    })
    out = estimate_undiagnosed_pool(df)
    # No age mix -> national NHANES adult rate 0.285.
    # T2D = 100000 * 0.10 * 0.285 = 2850 ; HTN = 100000*0.30*0.200 = 6000 ; Hypo = 100000*0.04*0.5 = 2000
    assert out.loc[0, "est_pool_t2d"] == 2850
    assert out.loc[0, "est_pool_htn"] == 6000
    assert out.loc[0, "est_pool_hypo"] == 2000
    assert out.loc[0, "total_estimated_pool"] == 2850 + 6000 + 2000
    # zero population -> zero pool
    assert out.loc[1, "total_estimated_pool"] == 0
    # total is always the sum of components
    assert (out["total_estimated_pool"]
            == out[["est_pool_t2d", "est_pool_htn", "est_pool_hypo"]].sum(axis=1)).all()


def test_pool_falls_back_to_total_population_and_handles_missing_prevalence():
    # No 'population' col (only total_population), no HTN prevalence -> HTN contributes 0, no NaN.
    df = pd.DataFrame({
        "total_population": [10_000],
        "diabetes_prevalence_pct": [0.10],
    })
    out = estimate_undiagnosed_pool(df)
    assert out["total_estimated_pool"].notna().all()
    assert out.loc[0, "est_pool_htn"] == 0
    assert out.loc[0, "est_pool_t2d"] == 285  # 10000 * 0.10 * 0.285


def test_norm_handles_all_nan_and_constant_series():
    all_nan = pd.Series([np.nan, np.nan, np.nan])
    out = _norm(all_nan)
    assert out.notna().all(), "_norm must not propagate NaN"
    constant = pd.Series([3.0, 3.0, 3.0])
    assert (_norm(constant) == 0.5).all()
    ramp = _norm(pd.Series([0.0, 5.0, 10.0]))
    assert ramp.iloc[0] == 0.0 and ramp.iloc[2] == 1.0


# ── NHANES age-weighted T2D undiagnosed rate ─────────────────────────────────

def test_age_weighted_rate_is_bounded_by_the_published_strata():
    """Any county's rate must sit inside the NHANES band range — a weighted
    average of the three published rates can never escape them."""
    df = pd.DataFrame({
        "population": [10_000] * 3,
        "diabetes_prevalence_pct": [0.10] * 3,
        "age_share_young":  [1.0, 0.0, 0.34],
        "age_share_middle": [0.0, 0.0, 0.33],
        "age_share_older":  [0.0, 1.0, 0.33],
    })
    r = t2d_undiagnosed_rate(df)
    assert abs(r.iloc[0] - 0.361) < 1e-9, "all-young county must equal the 20-39 rate"
    assert abs(r.iloc[1] - 0.249) < 1e-9, "all-older county must equal the 60+ rate"
    assert 0.249 <= r.iloc[2] <= 0.361


def test_younger_counties_have_a_higher_undiagnosed_share():
    """The counter-intuitive direction that motivates this whole change:
    older adults are screened more, so the undiagnosed SHARE falls with age."""
    df = pd.DataFrame({
        "age_share_young":  [0.7, 0.1],
        "age_share_middle": [0.2, 0.2],
        "age_share_older":  [0.1, 0.7],
    })
    r = t2d_undiagnosed_rate(df)
    assert r.iloc[0] > r.iloc[1]


def test_rate_falls_back_to_national_without_age_mix():
    df = pd.DataFrame({"population": [1_000], "diabetes_prevalence_pct": [0.1]})
    assert t2d_undiagnosed_rate(df).iloc[0] == pytest.approx(0.285)


def test_degenerate_age_mix_falls_back_rather_than_dividing_by_zero():
    df = pd.DataFrame({
        "age_share_young": [0.0, None], "age_share_middle": [0.0, None],
        "age_share_older": [0.0, None],
    })
    r = t2d_undiagnosed_rate(df)
    assert r.notna().all()
    assert ((r - 0.285).abs() < 1e-9).all()


def test_adult_population_is_preferred_denominator():
    """Prevalence is measured on adults; using total population over-counted
    young counties. adult_population must win when present."""
    df = pd.DataFrame({
        "population": [100_000], "adult_population": [50_000],
        "diabetes_prevalence_pct": [0.10], "hypertension_prevalence_pct": [0.0],
    })
    out = estimate_undiagnosed_pool(df)
    assert out.loc[0, "est_pool_t2d"] == round(50_000 * 0.10 * 0.285)


def test_pool_records_the_rate_it_actually_applied():
    df = pd.DataFrame({
        "adult_population": [10_000], "diabetes_prevalence_pct": [0.1],
        "age_share_young": [1.0], "age_share_middle": [0.0], "age_share_older": [0.0],
    })
    out = estimate_undiagnosed_pool(df)
    assert out.loc[0, "t2d_undiagnosed_rate"] == pytest.approx(0.361, abs=1e-4)
    assert out.loc[0, "est_pool_t2d"] == round(10_000 * 0.1 * 0.361)
