"""HCP scorer tests — synthetic CMS provider frames through the full scorer."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.hcp_scorer import score_hcps, _standardise_providers, MIN_PANEL
from src.quality.qa_gate import HCP_CHECKS, run_gate

RNG = np.random.default_rng(11)
N = 20_000


def _synthetic_providers(n=N, cms_naming=True) -> pd.DataFrame:
    """Mimic the CMS by-Provider file (Rndrng_* naming, real quirks)."""
    zips = [f"{RNG.integers(501, 99950):05d}" for _ in range(n)]
    specs = RNG.choice(
        ["Family Practice", "Internal Medicine", "Nurse Practitioner",
         "Endocrinology", "Cardiology", "Dermatology"],
        size=n, p=[0.3, 0.3, 0.15, 0.05, 0.1, 0.1])
    df = pd.DataFrame({
        "Rndrng_NPI": [f"{RNG.integers(1_000_000_000, 1_999_999_999)}" for _ in range(n)],
        "Rndrng_Prvdr_Last_Org_Name": ["SMITH"] * n,
        "Rndrng_Prvdr_First_Name": ["JANE"] * n,
        "Rndrng_Prvdr_Type": specs,
        "Rndrng_Prvdr_City": ["HOUSTON"] * n,
        "Rndrng_Prvdr_State_Abrvtn": RNG.choice(["TX", "CA", "FL", "NY"], size=n),
        "Rndrng_Prvdr_Zip5": zips,
        "Tot_Benes": RNG.integers(10, 3000, size=n),
        "Bene_CC_PH_Diabetes_V2_Pct": RNG.uniform(5, 55, size=n).round(1),
    })
    if not cms_naming:
        df.columns = ["npi", "name_last", "name_first", "specialty", "city",
                      "state", "zip5", "panel_size", "panel_diabetes_pct"]
    return df


def _synthetic_zip_scores() -> pd.DataFrame:
    zctas = [f"{i:05d}" for i in range(501, 99950, 3)]
    return pd.DataFrame({
        "zcta5": zctas,
        "zip_opportunity_percentile": RNG.uniform(0, 100, len(zctas)).round(1),
    })


def _synthetic_county_scores() -> pd.DataFrame:
    return pd.DataFrame({
        "state_abbr": ["TX", "CA", "FL", "NY"],
        "opportunity_percentile": [72.0, 41.0, 63.0, 38.0],
    })


def test_end_to_end_scoring():
    out = score_hcps(_synthetic_providers(), _synthetic_zip_scores(),
                     _synthetic_county_scores())
    assert not out.empty
    assert out["hcp_priority_score"].between(0, 100).all()
    # Sorted descending
    assert out["hcp_priority_score"].is_monotonic_decreasing
    # Tiers present and Priority is ~5%
    share_pri = (out["hcp_tier"] == "Priority").mean()
    assert 0.03 <= share_pri <= 0.08
    # Panel floor applied
    assert (out["panel_size"] >= MIN_PANEL).all()
    # Rationale non-empty
    assert out["rationale"].str.len().gt(0).all()


def test_specialty_fit_ordering():
    """PCP with identical stats must outrank dermatology."""
    prov = pd.DataFrame({
        "npi": ["1000000001", "1000000002"],
        "name_last": ["A", "B"], "name_first": ["X", "Y"],
        "specialty": ["Family Practice", "Dermatology"],
        "city": ["H", "H"], "state": ["TX", "TX"],
        "zip5": ["77001", "77001"],
        "panel_size": [500, 500],
        "panel_diabetes_pct": [30.0, 30.0],
    })
    zs = pd.DataFrame({"zcta5": ["77001"], "zip_opportunity_percentile": [90.0]})
    out = score_hcps(prov, zs).set_index("npi")
    assert out.loc["1000000001", "hcp_priority_score"] > \
           out.loc["1000000002", "hcp_priority_score"]


def test_cms_column_naming_standardised():
    std = _standardise_providers(_synthetic_providers(cms_naming=True))
    assert {"npi", "specialty", "zip5", "panel_size"}.issubset(std.columns)
    assert std["zip5"].str.len().eq(5).all()


def test_missing_required_columns_raises():
    with pytest.raises(ValueError, match="missing required columns"):
        _standardise_providers(pd.DataFrame({"foo": [1]}))


def test_gate_passes_healthy_output():
    out = score_hcps(_synthetic_providers(), _synthetic_zip_scores(),
                     _synthetic_county_scores())
    run_gate(out, HCP_CHECKS, "hcp synthetic").raise_on_failure()


def test_gate_catches_dead_geo_join():
    """Empty zip_scores → every geo_percentile defaults to 50 → gate fails."""
    out = score_hcps(_synthetic_providers(),
                     pd.DataFrame(columns=["zcta5", "zip_opportunity_percentile"]))
    report = run_gate(out, HCP_CHECKS, "hcp dead join")
    assert not report.ok
    assert any("geo match rate" in r.name for r in report.critical_failures)


def test_float_artifact_zips_handled():
    prov = _synthetic_providers(n=100)
    prov["Rndrng_Prvdr_Zip5"] = prov["Rndrng_Prvdr_Zip5"].astype(str) + ".0"
    std = _standardise_providers(prov)
    assert std["zip5"].str.fullmatch(r"\d{5}").all()
