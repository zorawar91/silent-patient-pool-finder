"""
QA gate tests — including regression tests reproducing the July 2026
crosswalk corruption that shipped silently (OID column parsed as ZCTA →
'00nan' codes → 5/7 ZIP dimensions 100% NaN → state filters returned 0 rows).
Every scenario here MUST be caught by the gate.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.dimension_scorer import estimate_undiagnosed_pool
from src.quality.qa_gate import (
    COUNTY_CHECKS, CROSSWALK_CHECKS, ZCTA_CHECKS,
    QAGateError, run_gate,
)

RNG = np.random.default_rng(7)


# ── Fixtures: healthy pipeline outputs ────────────────────────────────────────

def _healthy_crosswalk(n_zcta=33_000) -> pd.DataFrame:
    zctas = [f"{i:05d}" for i in range(1, n_zcta + 1)]
    rows = []
    for z in zctas:
        counties = [f"{RNG.integers(1, 56):02d}{RNG.integers(1, 199):03d}"]
        if RNG.random() < 0.3:  # ~30% span two counties
            counties.append(f"{RNG.integers(1, 56):02d}{RNG.integers(1, 199):03d}")
        w = RNG.dirichlet(np.ones(len(counties)))
        for c, wt in zip(counties, w):
            rows.append({"zcta5": z, "county_fips": c, "weight": float(wt)})
    return pd.DataFrame(rows)


def _healthy_county_scores(n=3_144) -> pd.DataFrame:
    states = [f"State{i}" for i in range(50)]
    df = pd.DataFrame({
        "county_fips": [f"{i:05d}" for i in range(1001, 1001 + n)],
        "county_name": [f"County {i}" for i in range(n)],
        "state_name": [states[i % 50] for i in range(n)],
        "diabetes_prevalence_pct": RNG.normal(11, 2, n).clip(4, 25),
        "ma_penetration_rate": RNG.beta(4, 6, n),
        "poverty_rate": RNG.beta(2, 8, n),
    })
    for c in ["dim_disease_burden", "dim_diagnosis_gap", "dim_access_to_care",
              "dim_social_determinants", "dim_payer_landscape",
              "dim_commercial_readiness", "dim_trajectory"]:
        df[c] = RNG.normal(45, 12, n).clip(0, 100)
    df["opportunity_score"] = RNG.normal(41, 5, n).clip(0, 100)
    df["population"] = RNG.integers(2_000, 500_000, n)
    df["hypertension_prevalence_pct"] = RNG.normal(0.33, 0.05, n).clip(0.1, 0.6)
    df = estimate_undiagnosed_pool(df)
    return df


def _healthy_zip_scores(n=33_000) -> pd.DataFrame:
    abbrs = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL",
             "IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT",
             "NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI",
             "SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
    df = pd.DataFrame({
        "zcta5": [f"{i:05d}" for i in range(1, n + 1)],
        "state_name": [f"State {abbrs[i % 50]}" for i in range(n)],
        "state_abbr": [abbrs[i % 50] for i in range(n)],
        "zip_opportunity_score": RNG.normal(40, 5, n).clip(0, 100),
        "lat": RNG.uniform(25, 49, n),
        "lon": RNG.uniform(-124, -67, n),
    })
    for c in ["zip_dim_disease_burden", "zip_dim_diagnosis_gap",
              "zip_dim_access_to_care", "zip_dim_social_determinants",
              "zip_dim_payer_landscape", "zip_dim_commercial_readiness",
              "zip_dim_trajectory"]:
        df[c] = RNG.normal(45, 10, n).clip(0, 100)
    return df


# ── Healthy data must pass ────────────────────────────────────────────────────

def test_healthy_crosswalk_passes():
    run_gate(_healthy_crosswalk(), CROSSWALK_CHECKS, "xw").raise_on_failure()


def test_healthy_county_scores_pass():
    run_gate(_healthy_county_scores(), COUNTY_CHECKS, "county").raise_on_failure()


def test_healthy_zip_scores_pass():
    run_gate(_healthy_zip_scores(), ZCTA_CHECKS, "zip").raise_on_failure()


# ── Regression: the exact historical crosswalk corruption ─────────────────────

def test_gate_catches_00nan_crosswalk():
    """The shipped bug: 849 rows, zcta5 = '00nan' (OID column + zfilled NaN)."""
    bad = pd.DataFrame({
        "zcta5": ["00nan"] * 849,
        "county_fips": [f"{RNG.integers(1, 56):02d}{RNG.integers(1, 199):03d}"
                        for _ in range(849)],
        "weight": [np.nan] * 849,
    })
    report = run_gate(bad, CROSSWALK_CHECKS, "corrupt xw")
    assert not report.ok
    failed = {r.name for r in report.critical_failures}
    assert any("code-format zcta5" in f for f in failed)
    assert any("row count" in f for f in failed)
    with pytest.raises(QAGateError):
        report.raise_on_failure()


def test_gate_catches_all_nan_zip_dims():
    """Downstream symptom of the crosswalk bug: 5/7 ZIP dims 100% NaN,
    state_name 100% null."""
    z = _healthy_zip_scores()
    for c in ["zip_dim_diagnosis_gap", "zip_dim_access_to_care",
              "zip_dim_payer_landscape", "zip_dim_commercial_readiness",
              "zip_dim_trajectory"]:
        z[c] = np.nan
    z["state_name"] = None
    z["state_abbr"] = None
    report = run_gate(z, ZCTA_CHECKS, "corrupt zip")
    assert not report.ok
    assert len(report.critical_failures) >= 6  # 5 dims + state coverage


def test_gate_catches_constant_dims():
    """Downscale fallback silently filling a dimension with the median."""
    z = _healthy_zip_scores()
    z["zip_dim_diagnosis_gap"] = 47.3  # constant — no information
    report = run_gate(z, ZCTA_CHECKS, "flat dim")
    assert not report.ok
    assert any("variance zip_dim_diagnosis_gap" in r.name
               for r in report.critical_failures)


def test_gate_catches_zero_match_state_join():
    z = _healthy_zip_scores()
    # Both state columns come from the same crosswalk join — they die together
    z.loc[z.index[:-100], ["state_abbr", "state_name"]] = None  # 99.7% null
    report = run_gate(z, ZCTA_CHECKS, "dead join")
    assert not report.ok


def test_gate_catches_truncated_county_panel():
    c = _healthy_county_scores(n=259)  # the old "259-county bug"
    report = run_gate(c, COUNTY_CHECKS, "truncated")
    assert not report.ok
    assert any("row count" in r.name for r in report.critical_failures)


def test_gate_catches_score_out_of_range():
    c = _healthy_county_scores()
    c.loc[0, "opportunity_score"] = 240.0
    report = run_gate(c, COUNTY_CHECKS, "range")
    assert not report.ok


def test_warn_does_not_block():
    """Degraded WARN-level coverage logs but does not raise."""
    c = _healthy_county_scores()
    c.loc[c.index[: int(len(c) * 0.12)], "diabetes_prevalence_pct"] = np.nan  # 12% > 10% WARN
    report = run_gate(c, COUNTY_CHECKS, "warn only")
    assert report.ok  # still passes — CRITICALs all green
    assert any(r.severity == "WARN" for r in report.failures)
    report.raise_on_failure()  # must not raise
