"""Campaign measurement — the estimator must recover a known synthetic lift."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.campaign_measurement import diff_in_diff, match_controls

RNG = np.random.default_rng(21)
N = 800
TRUE_LIFT = 1.5   # pct-point diagnosis lift injected into treated counties


def _panel(n=N) -> pd.DataFrame:
    """Synthetic county panel with a common secular trend + known lift."""
    base = RNG.normal(10, 2, n).clip(4, 20)
    df = pd.DataFrame({
        "county_fips": [f"{i:05d}" for i in range(1001, 1001 + n)],
        "diabetes_prev_prior": base,
        "obesity_prev_prior": RNG.normal(33, 4, n),
        "poverty_rate": RNG.beta(2, 8, n),
        "median_household_income": RNG.normal(58_000, 12_000, n),
        "uninsured_rate": RNG.beta(2, 16, n),
        "population": RNG.integers(5_000, 900_000, n),
        "is_rural": RNG.integers(0, 2, n),
    })
    secular = RNG.normal(0.4, 0.3, n)          # everyone drifts up a little
    df["diabetes_prevalence_pct"] = base + secular
    return df


def test_did_recovers_known_lift():
    df = _panel()
    treated = df["county_fips"].sample(40, random_state=1).tolist()
    mask = df["county_fips"].isin(treated)
    df.loc[mask, "diabetes_prevalence_pct"] += TRUE_LIFT   # inject campaign effect

    match = match_controls(df, treated, k=3)
    res = diff_in_diff(df, match.treated_fips, match.control_fips)

    assert res.estimate == pytest.approx(TRUE_LIFT, abs=0.3)
    assert res.ci_low < TRUE_LIFT < res.ci_high
    assert res.significant


def test_no_effect_is_not_significant():
    df = _panel()
    treated = df["county_fips"].sample(40, random_state=2).tolist()
    match = match_controls(df, treated, k=3)
    res = diff_in_diff(df, match.treated_fips, match.control_fips)
    assert abs(res.estimate) < 0.5
    assert not res.significant     # CI must straddle zero


def test_matching_improves_balance():
    """Matched controls must resemble treated counties more than the raw pool
    on the baseline outcome (the covariate that matters most)."""
    df = _panel()
    # Treat a NON-random slice: the highest-poverty counties
    treated = df.nlargest(40, "poverty_rate")["county_fips"].tolist()
    match = match_controls(df, treated, k=3)
    b = match.balance
    gap_matched = abs(b.loc["poverty_rate", "treated_mean"] - b.loc["poverty_rate", "control_mean"])
    gap_pool = abs(b.loc["poverty_rate", "treated_mean"] - b.loc["poverty_rate", "pool_mean"])
    assert gap_matched < gap_pool


def test_controls_never_include_treated():
    df = _panel()
    treated = df["county_fips"].sample(25, random_state=3).tolist()
    match = match_controls(df, treated, k=3)
    assert not set(match.control_fips) & set(match.treated_fips)


def test_unknown_fips_raises():
    with pytest.raises(ValueError, match="None of the supplied FIPS"):
        match_controls(_panel(), ["99999"])


def test_fraction_units_scaled_to_pp():
    """CDC PLACES stores prevalence as fractions — results must be in pp."""
    df = _panel()
    df["diabetes_prev_prior"] /= 100.0
    df["diabetes_prevalence_pct"] /= 100.0
    treated = df["county_fips"].sample(40, random_state=4).tolist()
    mask = df["county_fips"].isin(treated)
    df.loc[mask, "diabetes_prevalence_pct"] += TRUE_LIFT / 100.0
    m = match_controls(df, treated, k=3)
    res = diff_in_diff(df, m.treated_fips, m.control_fips)
    assert res.estimate == pytest.approx(TRUE_LIFT, abs=0.3)   # pp, not fraction


def test_missing_outcome_column_raises():
    df = _panel().drop(columns=["diabetes_prev_prior"])
    with pytest.raises(ValueError, match="Outcome column missing"):
        diff_in_diff(df, ["01001"], ["01003"])
