from __future__ import annotations
"""
ZIP / ZCTA Scorer — Silent Patient Pool Finder
===============================================
Scores ~33,000 ZCTAs across the same 7-dimension framework used for counties.

Dimension sources at ZCTA level:
  disease_burden        → CDC PLACES ZCTA (real data)
  social_determinants   → Census ACS ZCTA (real data)
  diagnosis_gap         → county score downscaled via ZCTA→county crosswalk
  access_to_care        → county score downscaled
  payer_landscape       → county score downscaled
  commercial_readiness  → county score downscaled
  trajectory            → county score downscaled

Composite score = same weighted formula as county pipeline:
  Disease Burden (20%) + Diagnosis Gap (25%) + Access (15%) + SDoH (15%)
  + Payer (10%) + Commercial (10%) + Trajectory (5%)
"""

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Dimension weights — must match config/dimensions.yaml
_DIM_WEIGHTS = {
    "zip_dim_disease_burden":       0.20,
    "zip_dim_diagnosis_gap":        0.25,
    "zip_dim_access_to_care":       0.15,
    "zip_dim_social_determinants":  0.15,
    "zip_dim_payer_landscape":      0.10,
    "zip_dim_commercial_readiness": 0.10,
    "zip_dim_trajectory":           0.05,
}

# National defaults (same source as county scorer)
_DEFAULTS = {
    "diabetes_prevalence_pct":     0.113,
    "obesity_rate_pct":            0.320,
    "hypertension_prevalence_pct": 0.470,
    "annual_checkup_pct":          0.720,
    "poverty_rate":                0.125,
    "uninsured_rate":              0.090,
    "median_household_income":     74_580,
    "ses_disadvantage_index":      0.300,
}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def score_zctas(
    cdc_zcta:      pd.DataFrame,
    acs_zcta:      pd.DataFrame,
    crosswalk:     pd.DataFrame,
    centroids:     pd.DataFrame,
    county_scores: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a scored ZCTA panel and return it.

    Parameters
    ----------
    cdc_zcta      : CDC PLACES ZCTA-level prevalence (from _download_cdc_places_zcta)
    acs_zcta      : Census ACS ZCTA-level SDoH (from _download_census_acs_zcta)
    crosswalk     : ZCTA→county mapping with population weights
    centroids     : ZCTA lat/lon centroids (from _download_zcta_centroids)
    county_scores : County-level dimension_scores.parquet (for downscaling)

    Returns
    -------
    DataFrame with one row per ZCTA containing 7 zip_dim_* scores,
    zip_opportunity_score, lat, lon, and key raw signals.
    """
    log.info("ZIP scorer: building ZCTA panel …")

    # 1. Build ZCTA spine from whichever sources have data
    zcta_set = _collect_zctas(cdc_zcta, acs_zcta, crosswalk, centroids)
    if zcta_set.empty:
        log.error("ZIP scorer: no ZCTAs found in any source")
        return pd.DataFrame()

    log.info(f"  ZCTA spine: {len(zcta_set):,} ZCTAs")

    # 2. Merge ZCTA-level real data
    panel = _merge_zcta_sources(zcta_set, cdc_zcta, acs_zcta, centroids)

    # 3. Build county→dim lookup for downscaling
    county_dim = _prep_county_dims(county_scores)

    # 4. Downscale county dimensions → ZCTA via crosswalk
    panel = _downscale_county_dims(panel, crosswalk, county_dim)

    # 5. Score each dimension
    panel = _score_dimensions(panel)

    # 6. Composite score + tier + intervention
    panel = _composite_score(panel)

    # 7. Estimated patient pool per ZCTA
    panel = _estimate_pool(panel)

    # 8. Percentile score + data-coverage confidence grade
    panel["zip_opportunity_percentile"] = (
        panel["zip_opportunity_score"].rank(pct=True) * 100
    ).round(1)
    panel["zip_confidence_grade"] = _zip_confidence_grade(panel)

    n_valid = panel["zip_opportunity_score"].notna().sum()
    n_pri   = int((panel["zip_opportunity_score"] >= 55).sum())
    log.info(f"ZIP scorer: {n_valid:,} ZCTAs scored | {n_pri:,} priority (≥55)")
    return panel.reset_index(drop=True)


def _zip_confidence_grade(panel: pd.DataFrame) -> pd.Series:
    """
    Grade each ZCTA by real data coverage:
      A — direct ZCTA-level CDC + ACS data AND county-derived dims present
      B — direct ZCTA data present, county downscale missing (or vice versa)
      C — mostly proxies/defaults
    """
    has_cdc    = panel.get("diabetes_prevalence_pct", pd.Series(index=panel.index)).notna()
    has_acs    = panel.get("poverty_rate", pd.Series(index=panel.index)).notna()
    has_county = panel.get("zip_dim_payer_landscape", pd.Series(index=panel.index)).notna()

    n = has_cdc.astype(int) + has_acs.astype(int) + has_county.astype(int)
    grade = pd.Series("C", index=panel.index)
    grade[n >= 2] = "B"
    grade[n == 3] = "A"
    return grade


# ─────────────────────────────────────────────────────────────────────────────
# PANEL BUILDING
# ─────────────────────────────────────────────────────────────────────────────

def _collect_zctas(cdc_zcta, acs_zcta, crosswalk, centroids) -> pd.DataFrame:
    """Build the ZCTA spine from all available sources."""
    sources = []
    for df in [cdc_zcta, acs_zcta, crosswalk, centroids]:
        if not df.empty and "zcta5" in df.columns:
            sources.append(df[["zcta5"]].drop_duplicates())

    if not sources:
        return pd.DataFrame()

    all_zctas = pd.concat(sources, ignore_index=True).drop_duplicates("zcta5")
    # Keep only valid 5-digit ZCTAs
    all_zctas = all_zctas[all_zctas["zcta5"].str.match(r"^\d{5}$", na=False)]
    return all_zctas.reset_index(drop=True)


def _merge_zcta_sources(
    spine: pd.DataFrame,
    cdc_zcta: pd.DataFrame,
    acs_zcta: pd.DataFrame,
    centroids: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join all ZCTA-level sources onto the spine."""
    panel = spine.copy()
    n_base = len(panel)

    def _merge(right, name, check_col=None):
        nonlocal panel
        if right.empty or "zcta5" not in right.columns:
            log.info(f"  {name}: empty, skipped")
            return
        right = right.drop_duplicates("zcta5")
        panel = panel.merge(right, on="zcta5", how="left")
        assert len(panel) == n_base, f"Row drift after {name}: {len(panel)}"
        if check_col and check_col in panel.columns:
            n = panel[check_col].notna().sum()
            log.info(f"  After {name}: {n:,}/{n_base:,} ZCTAs have {check_col}")

    _merge(cdc_zcta,   "CDC PLACES ZCTA",  "diabetes_prevalence_pct")
    _merge(acs_zcta,   "Census ACS ZCTA",  "poverty_rate")
    _merge(centroids,  "Centroids",         "lat")

    return panel


def _prep_county_dims(county_scores: pd.DataFrame) -> pd.DataFrame:
    """Extract and normalise county dimension columns for downscaling."""
    if county_scores.empty:
        return pd.DataFrame()

    dim_cols = [c for c in county_scores.columns if c.startswith("dim_")]
    keep     = ["county_fips"] + dim_cols

    # Also keep a few raw signals useful for ZIP-level displays
    extra = [c for c in [
        "state_name", "state_abbr",
        "ma_penetration_rate", "medicaid_rate", "commercial_rate",
        "cms_t2d_diagnosed_rate", "hpsa_flag",
    ] if c in county_scores.columns]

    df = county_scores[keep + extra].copy()
    df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
    return df.drop_duplicates("county_fips").reset_index(drop=True)


def _downscale_county_dims(
    panel: pd.DataFrame,
    crosswalk: pd.DataFrame,
    county_dim: pd.DataFrame,
) -> pd.DataFrame:
    """
    Population-weighted downscale of county dimension scores → ZCTA.

    For each ZCTA that spans multiple counties, the county dimension scores
    are weighted by the ZCTA's land-area share in each county.
    """
    if crosswalk.empty or county_dim.empty:
        log.warning("  Downscale: no crosswalk or county dims — using county median defaults")
        # Fill with national medians from county data
        if not county_dim.empty:
            for col in [c for c in county_dim.columns if c.startswith("dim_")]:
                zip_col = "zip_" + col  # e.g. zip_dim_diagnosis_gap
                panel[zip_col] = county_dim[col].median()
        return panel

    # Join crosswalk → county dims
    xw = crosswalk.merge(
        county_dim,
        on="county_fips",
        how="left",
    )

    dim_cols = [c for c in county_dim.columns if c.startswith("dim_")]

    # Also carry extra county-level signals (state info, payer mix)
    extra_cols = [c for c in county_dim.columns
                  if c not in ["county_fips"] + dim_cols]

    # Weighted aggregate per ZCTA
    records = []
    for zcta5, grp in xw.groupby("zcta5"):
        row = {"zcta5": zcta5}
        w = grp["weight"].fillna(1.0)
        total_w = w.sum() or 1.0

        for col in dim_cols:
            vals = grp[col].fillna(grp[col].median() if grp[col].notna().any() else 50.0)
            row["zip_" + col] = float((vals * w).sum() / total_w)

        # For non-numeric extra cols: take the majority (highest weight) county's value
        if extra_cols:
            best_idx = w.idxmax()
            best_row = grp.loc[best_idx]
            for col in extra_cols:
                row[col] = best_row.get(col, np.nan)

        records.append(row)

    downscaled = pd.DataFrame(records)
    n_before = len(panel)
    panel = panel.merge(downscaled, on="zcta5", how="left")
    assert len(panel) == n_before, f"Row drift after downscale: {len(panel)}"

    filled = {
        c: int(panel["zip_" + c].notna().sum())
        for c in dim_cols
        if "zip_" + c in panel.columns
    }
    log.info(f"  Downscaled county dims to {max(filled.values(), default=0):,} ZCTAs "
             f"(example: zip_dim_diagnosis_gap)")
    return panel


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSION SCORING
# ─────────────────────────────────────────────────────────────────────────────

def _score_dimensions(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all 7 zip_dim_* scores (0-100 each)."""
    df = df.copy()

    # ── 1. Disease Burden ──────────────────────────────────────────────────────
    # Real ZCTA data from CDC PLACES; fallback to downscaled county
    burden = _score_disease_burden(df)
    df["zip_dim_disease_burden"] = burden

    # ── 2. Diagnosis Gap ──────────────────────────────────────────────────────
    # Downscaled from county (has CMS T2D + HTN signals)
    if "zip_dim_diagnosis_gap" in df.columns:
        df["zip_dim_diagnosis_gap"] = df["zip_dim_diagnosis_gap"].clip(0, 100)
    else:
        df["zip_dim_diagnosis_gap"] = df["zip_dim_disease_burden"] * 0.8  # proxy

    # ── 3. Social Determinants ────────────────────────────────────────────────
    sdoh = _score_social_determinants(df)
    df["zip_dim_social_determinants"] = sdoh

    # ── 4. Access to Care ─────────────────────────────────────────────────────
    if "zip_dim_access_to_care" in df.columns:
        df["zip_dim_access_to_care"] = df["zip_dim_access_to_care"].clip(0, 100)
    else:
        df["zip_dim_access_to_care"] = 50.0  # neutral default

    # ── 5. Payer Landscape ────────────────────────────────────────────────────
    if "zip_dim_payer_landscape" in df.columns:
        df["zip_dim_payer_landscape"] = df["zip_dim_payer_landscape"].clip(0, 100)
    else:
        df["zip_dim_payer_landscape"] = 50.0

    # ── 6. Commercial Readiness ───────────────────────────────────────────────
    if "zip_dim_commercial_readiness" in df.columns:
        df["zip_dim_commercial_readiness"] = df["zip_dim_commercial_readiness"].clip(0, 100)
    else:
        df["zip_dim_commercial_readiness"] = 50.0

    # ── 7. Trajectory ─────────────────────────────────────────────────────────
    if "zip_dim_trajectory" in df.columns:
        df["zip_dim_trajectory"] = df["zip_dim_trajectory"].clip(0, 100)
    else:
        df["zip_dim_trajectory"] = 50.0

    return df


def _score_disease_burden(df: pd.DataFrame) -> pd.Series:
    """
    Disease Burden (0-100):
      - T2D prevalence:   35 pts  (CDC PLACES ZCTA)
      - HTN prevalence:   30 pts  (CDC PLACES ZCTA)
      - Obesity rate:     20 pts  (CDC PLACES ZCTA, strong T2D proxy)
      - Checkup gap:      15 pts  (1 - annual_checkup_pct, access barrier proxy)

    Falls back to downscaled county dim_disease_burden if PLACES ZCTA unavailable.
    """
    score = pd.Series(0.0, index=df.index)
    has_zcta_data = (
        "diabetes_prevalence_pct" in df.columns and
        df["diabetes_prevalence_pct"].notna().sum() > 1000
    )

    if has_zcta_data:
        score += 35 * _norm(df["diabetes_prevalence_pct"].fillna(
            _DEFAULTS["diabetes_prevalence_pct"]
        ))
        if "hypertension_prevalence_pct" in df.columns:
            score += 30 * _norm(df["hypertension_prevalence_pct"].fillna(
                _DEFAULTS["hypertension_prevalence_pct"]
            ))
        if "obesity_rate_pct" in df.columns:
            score += 20 * _norm(df["obesity_rate_pct"].fillna(
                _DEFAULTS["obesity_rate_pct"]
            ))
        if "annual_checkup_pct" in df.columns:
            score += 15 * _norm(1.0 - df["annual_checkup_pct"].fillna(
                _DEFAULTS["annual_checkup_pct"]
            ))
        return score.clip(0, 100)

    # Fallback: downscaled county burden
    if "zip_dim_disease_burden" in df.columns:
        return df["zip_dim_disease_burden"].fillna(50.0).clip(0, 100)

    return pd.Series(50.0, index=df.index)


def _score_social_determinants(df: pd.DataFrame) -> pd.Series:
    """
    Social Determinants (0-100):
      - Poverty rate:        35 pts  (Census ACS ZCTA)
      - Uninsured rate:      30 pts  (Census ACS ZCTA)
      - Income deprivation:  20 pts  (1/income, Census ACS ZCTA)
      - SES index backup:    15 pts  (ses_disadvantage_index)

    Falls back to downscaled county dim_social_determinants if ACS ZCTA unavailable.
    """
    has_acs = (
        "poverty_rate" in df.columns and
        df["poverty_rate"].notna().sum() > 1000
    )

    if has_acs:
        score = pd.Series(0.0, index=df.index)
        score += 35 * _norm(df["poverty_rate"].fillna(_DEFAULTS["poverty_rate"]))
        if "uninsured_rate" in df.columns:
            score += 30 * _norm(df["uninsured_rate"].fillna(_DEFAULTS["uninsured_rate"]))
        if "median_household_income" in df.columns:
            inc = df["median_household_income"].clip(lower=10_000).fillna(
                _DEFAULTS["median_household_income"]
            )
            score += 20 * _norm(1.0 / inc)
        if "ses_disadvantage_index" in df.columns:
            score += 15 * _norm(df["ses_disadvantage_index"].fillna(
                _DEFAULTS["ses_disadvantage_index"]
            ))
        return score.clip(0, 100)

    if "zip_dim_social_determinants" in df.columns:
        return df["zip_dim_social_determinants"].fillna(50.0).clip(0, 100)

    return pd.Series(50.0, index=df.index)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE SCORE + EXTRAS
# ─────────────────────────────────────────────────────────────────────────────

def _composite_score(df: pd.DataFrame) -> pd.DataFrame:
    """Weighted sum of all 7 dimensions → zip_opportunity_score."""
    df = df.copy()

    score = pd.Series(0.0, index=df.index)
    for col, weight in _DIM_WEIGHTS.items():
        if col in df.columns:
            score += weight * df[col].fillna(50.0).clip(0, 100)
        else:
            score += weight * 50.0  # neutral default

    df["zip_opportunity_score"] = score.clip(0, 100)

    df["zip_opportunity_tier"] = pd.cut(
        df["zip_opportunity_score"],
        bins=[0, 40, 55, 100],
        labels=["Developing", "Emerging", "Priority"],
        include_lowest=True,
    ).astype(str)

    # Recommended intervention (simplified vs county — based on zip dim signals)
    df["zip_recommended_intervention"] = df.apply(_zip_intervention, axis=1)

    return df


def _zip_intervention(row: pd.Series) -> str:
    ma  = row.get("ma_penetration_rate", 0.44) or 0.44
    sdh = row.get("zip_dim_social_determinants", 50) or 50
    com = row.get("zip_dim_commercial_readiness", 50) or 50
    acc = row.get("zip_dim_access_to_care", 50) or 50

    if ma >= 0.45:
        return "Payer Partnership Program"
    if sdh >= 65 and acc <= 45:
        return "Community Health Center Partnership"
    if com >= 60:
        return "Employer Wellness Program"
    if com >= 45:
        return "Digital Health Program"
    return "Pharmacy-Based Screening"


def _estimate_pool(df: pd.DataFrame) -> pd.DataFrame:
    """
    Estimate undiagnosed patient count per ZCTA.
    Uses the county pipeline's NATIONAL rates. Unlike the county layer this
    cannot age-weight the T2D rate or use an adult denominator — no ZCTA-level
    age composition is ingested — so ZIP pools are systematically slightly
    higher than the county figures they downscale from. Documented, not hidden.
      T2D undiagnosed:  population × diabetes_prevalence_pct × 0.285
      HTN undiagnosed:  population × hypertension_prevalence_pct × 0.200
      Hypo undiagnosed: population × 0.04 × 0.50 (national avg)
    """
    df = df.copy()
    pop = df.get("population", pd.Series(5_000, index=df.index)).fillna(5_000)

    t2d_prev  = df.get("diabetes_prevalence_pct",
                        pd.Series(_DEFAULTS["diabetes_prevalence_pct"], index=df.index)
                ).fillna(_DEFAULTS["diabetes_prevalence_pct"])
    htn_prev  = df.get("hypertension_prevalence_pct",
                        pd.Series(_DEFAULTS["hypertension_prevalence_pct"], index=df.index)
                ).fillna(_DEFAULTS["hypertension_prevalence_pct"])

    df["zip_t2d_pool"]   = (pop * t2d_prev * 0.285).round().astype(int)
    df["zip_htn_pool"]   = (pop * htn_prev * 0.200).round().astype(int)
    df["zip_hypo_pool"]  = (pop * 0.040    * 0.500).round().astype(int)
    df["zip_total_pool"] = df["zip_t2d_pool"] + df["zip_htn_pool"] + df["zip_hypo_pool"]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _norm(s: pd.Series) -> pd.Series:
    """Min-max normalize to [0, 1]."""
    s = pd.to_numeric(s, errors="coerce")
    s = s.fillna(s.median() if s.notna().any() else 0.0)
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(0.5, index=s.index)
    return ((s - mn) / (mx - mn)).clip(0, 1)
