from __future__ import annotations
"""
Campaign Measurement — matched controls + difference-in-differences.
=====================================================================
Turns SPPF from a planning tool into an outcomes tool: after a
diagnosis-support campaign runs in a set of counties, did the DIAGNOSED
prevalence rise faster there than in statistically similar counties that
got no campaign?

Why diagnosed prevalence: CDC PLACES measures *diagnosed* cases. A campaign
that finds undiagnosed patients converts hidden burden into diagnosed
burden — so success = diagnosed prevalence rising RELATIVE to matched
controls. (Absolute prevalence rising alone proves nothing; the DiD design
nets out secular trends.)

Design honesty notes (surface these to the buyer, never hide them):
  - PLACES model-based estimates smooth county data; small effects in small
    counties may not be detectable. Power depends on county count.
  - Two vintages ≈ two-year spacing; this measures multi-year campaigns,
    not quarterly pulses. Claims-data integration would tighten the window.
  - Matching is on observables. Pre-register the county list + covariates
    BEFORE the campaign to keep the analysis credible.
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_COVARIATES = [
    "diabetes_prev_prior",        # baseline outcome level (crucial matcher)
    "obesity_prev_prior",         # baseline risk factor
    "poverty_rate",
    "median_household_income",
    "uninsured_rate",
    "population",
    "is_rural",
]


@dataclass
class MatchResult:
    treated_fips: list[str]
    control_map: dict            # treated fips -> list of matched control fips
    control_fips: list[str]      # deduplicated control pool
    covariates_used: list[str]
    balance: pd.DataFrame        # treated vs control covariate means


@dataclass
class DiDResult:
    estimate: float              # DiD lift in outcome units (pct points)
    ci_low: float
    ci_high: float
    treated_delta: float         # mean post-pre among treated
    control_delta: float         # mean post-pre among controls
    n_treated: int
    n_control: int
    outcome_pre: str
    outcome_post: str
    significant: bool = field(init=False)

    def __post_init__(self):
        self.significant = not (self.ci_low <= 0.0 <= self.ci_high)


def match_controls(
    panel: pd.DataFrame,
    treated_fips: list[str],
    covariates: list[str] | None = None,
    k: int = 3,
) -> MatchResult:
    """
    For each treated county, find the k most similar untreated counties by
    Euclidean distance on standardized covariates.
    """
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler

    df = panel.copy()
    df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
    treated_fips = [str(f).zfill(5) for f in treated_fips]

    covs = [c for c in (covariates or DEFAULT_COVARIATES) if c in df.columns]
    if len(covs) < 3:
        raise ValueError(f"Too few matching covariates present ({covs}); "
                         "re-run ingest_real_data.py")

    work = df[["county_fips"] + covs].copy()
    for c in covs:
        col = pd.to_numeric(work[c], errors="coerce")
        work[c] = col.fillna(col.median())

    is_treated = work["county_fips"].isin(treated_fips)
    treated = work[is_treated]
    pool = work[~is_treated]
    if treated.empty:
        raise ValueError("None of the supplied FIPS codes are in the panel")
    if len(pool) < k:
        raise ValueError("Control pool too small")

    scaler = StandardScaler().fit(work[covs])
    nn = NearestNeighbors(n_neighbors=k).fit(scaler.transform(pool[covs]))
    _, idx = nn.kneighbors(scaler.transform(treated[covs]))

    control_map = {
        t_fips: pool.iloc[row]["county_fips"].tolist()
        for t_fips, row in zip(treated["county_fips"], idx)
    }
    control_fips = sorted({c for lst in control_map.values() for c in lst})

    balance = pd.DataFrame({
        "treated_mean": treated[covs].mean(),
        "control_mean": work[work["county_fips"].isin(control_fips)][covs].mean(),
        "pool_mean": pool[covs].mean(),
    }).round(3)

    log.info(f"Matched {len(treated)} treated counties to "
             f"{len(control_fips)} controls (k={k}, covs={len(covs)})")
    return MatchResult(
        treated_fips=treated["county_fips"].tolist(),
        control_map=control_map,
        control_fips=control_fips,
        covariates_used=covs,
        balance=balance,
    )


def diff_in_diff(
    panel: pd.DataFrame,
    treated_fips: list[str],
    control_fips: list[str],
    outcome_pre: str = "diabetes_prev_prior",
    outcome_post: str = "diabetes_prevalence_pct",
    n_boot: int = 2000,
    seed: int = 7,
) -> DiDResult:
    """
    DiD estimate = (post−pre | treated) − (post−pre | controls),
    with a percentile bootstrap CI (resampling counties within each arm).
    """
    df = panel.copy()
    df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
    for col in (outcome_pre, outcome_post):
        if col not in df.columns:
            raise ValueError(f"Outcome column missing: {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[outcome_pre, outcome_post])
    df["delta"] = df[outcome_post] - df[outcome_pre]

    t = df[df["county_fips"].isin([str(f).zfill(5) for f in treated_fips])]["delta"].values
    c = df[df["county_fips"].isin([str(f).zfill(5) for f in control_fips])]["delta"].values
    if len(t) == 0 or len(c) == 0:
        raise ValueError("Treated or control arm has no rows with both outcomes")

    # Unit normalisation: CDC PLACES stores prevalence as fractions
    # (0.136 = 13.6%). Report everything in PERCENTAGE POINTS so the
    # buyer-facing number reads "+0.4pp", never "+0.004pp".
    if float(np.nanmedian(df[outcome_post])) <= 1.0:
        t = t * 100.0
        c = c * 100.0

    est = float(t.mean() - c.mean())

    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        bt = rng.choice(t, size=len(t), replace=True)
        bc = rng.choice(c, size=len(c), replace=True)
        boots[i] = bt.mean() - bc.mean()
    lo, hi = np.percentile(boots, [2.5, 97.5])

    return DiDResult(
        estimate=round(est, 3),
        ci_low=round(float(lo), 3),
        ci_high=round(float(hi), 3),
        treated_delta=round(float(t.mean()), 3),
        control_delta=round(float(c.mean()), 3),
        n_treated=len(t),
        n_control=len(c),
        outcome_pre=outcome_pre,
        outcome_post=outcome_post,
    )
