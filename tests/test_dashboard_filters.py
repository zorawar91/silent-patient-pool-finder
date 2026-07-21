"""Tests for the sidebar filter contract and condition-aware scoring/tiering.

Guards two regressions that shipped silently before:
  1. Views resolved a `{condition}_risk_score` column that the real pipeline
     never produces, so the Condition filter was a no-op everywhere.
  2. A filter rendered for a view that ignores it looks live but changes
     nothing — worse than no control at all.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.output.data import (
    TIER_EMERGING_CUT,
    TIER_PRIORITY_CUT,
    condition_score,
    condition_tier,
    tier_basis_label,
)
from src.output.sidebar import AUDIT_VIEWS, DECISION_VIEWS, VIEW_FILTERS

CONDITIONS = ["t2d", "htn", "hyperthyroidism"]


def _scores(n: int = 400, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "county_fips": [f"{i:05d}" for i in range(n)],
        "county_name": [f"C{i}" for i in range(n)],
        "state_name": ["Texas"] * n,
        "opportunity_score": rng.uniform(28, 65, n),
    })
    for k in ["disease_burden", "diagnosis_gap", "access_to_care",
              "social_determinants", "payer_landscape",
              "commercial_readiness", "trajectory"]:
        df[f"dim_{k}"] = rng.uniform(0, 100, n)
    df["opportunity_tier"] = pd.cut(
        df["opportunity_score"], bins=[0, TIER_EMERGING_CUT, TIER_PRIORITY_CUT, 100],
        labels=["Developing", "Emerging", "Priority"], include_lowest=True).astype(str)
    return df


# ── condition_score ───────────────────────────────────────────────────────────

def test_overall_uses_composite_column():
    df = _scores()
    out, col = condition_score(df, "overall")
    assert col == "opportunity_score"


def test_each_condition_yields_a_distinct_materialised_score():
    df = _scores()
    seen = {}
    for cond in CONDITIONS:
        out, col = condition_score(df, cond)
        assert col in out.columns, f"{cond}: score column not materialised"
        assert col != "opportunity_score", f"{cond}: silently fell back to composite"
        seen[cond] = out[col].round(6)
    # the whole bug was every condition resolving to the same numbers
    for a in CONDITIONS:
        for b in CONDITIONS:
            if a < b:
                assert not seen[a].equals(seen[b]), f"{a} and {b} produce identical scores"


def test_legacy_risk_score_column_is_preferred_when_present():
    df = _scores()
    df["t2d_risk_score"] = 42.0
    _, col = condition_score(df, "t2d")
    assert col == "t2d_risk_score"


# ── condition_tier ────────────────────────────────────────────────────────────

def test_overall_tier_is_the_persisted_column():
    df = _scores()
    out, col = condition_score(df, "overall")
    assert condition_tier(out, "overall", col).equals(df["opportunity_tier"].astype(str))


def test_condition_tiers_preserve_composite_selectivity():
    """'Priority' must keep one meaning: the same share of counties, whichever
    condition is selected. Applying the raw 55/40 cut-offs instead would flag
    ~7x more counties for T2D purely because that score spreads wider."""
    df = _scores()
    base = df["opportunity_tier"].value_counts()
    for cond in CONDITIONS:
        out, col = condition_score(df, cond)
        tiers = condition_tier(out, cond, col).value_counts()
        for label in ["Priority", "Emerging"]:
            assert abs(int(tiers.get(label, 0)) - int(base.get(label, 0))) <= 1, (
                f"{cond}: {label} count {tiers.get(label, 0)} != composite {base.get(label, 0)}")


def test_condition_tier_membership_tracks_the_condition():
    df = _scores()
    members = {}
    for cond in CONDITIONS:
        out, col = condition_score(df, cond)
        t = condition_tier(out, cond, col)
        members[cond] = set(out.loc[t == "Priority", "county_fips"])
    assert members["t2d"] != members["htn"], "tiers did not respond to the condition"


def test_condition_tier_labels_are_valid_and_complete():
    df = _scores()
    out, col = condition_score(df, "t2d")
    t = condition_tier(out, "t2d", col)
    assert set(t.unique()) <= {"Priority", "Emerging", "Developing"}
    assert t.notna().all() and len(t) == len(df)


def test_tier_basis_label_distinguishes_the_scale():
    assert str(TIER_PRIORITY_CUT) in tier_basis_label("overall")
    assert "Type 2 Diabetes" in tier_basis_label("t2d", "Type 2 Diabetes")


# ── sidebar filter contract ───────────────────────────────────────────────────

def test_every_nav_view_declares_its_filters():
    """Adding a view without declaring its filters would silently render every
    control as live for it."""
    nav = {v.split("  ")[1] for v in DECISION_VIEWS + AUDIT_VIEWS}
    assert nav == set(VIEW_FILTERS), (
        f"undeclared: {nav - set(VIEW_FILTERS)}; stale: {set(VIEW_FILTERS) - nav}")


def test_filter_names_are_known():
    known = {"condition", "state", "county", "top_n", "tier"}
    for view, filters in VIEW_FILTERS.items():
        assert filters <= known, f"{view} declares unknown filter(s): {filters - known}"


def test_county_filter_requires_state_filter():
    """The county dropdown is only reachable once a single state is chosen."""
    for view, filters in VIEW_FILTERS.items():
        if "county" in filters:
            assert "state" in filters, f"{view} allows county without state"
