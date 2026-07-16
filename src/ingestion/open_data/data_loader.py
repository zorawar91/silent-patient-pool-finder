from __future__ import annotations
# Open Data Loader — orchestrates all public data source downloads.
#
# For each source, tries real download first, falls back to enhanced synthetic
# data that preserves realistic distributions and county-level correlations.
#
# Usage:
#   from src.ingestion.open_data.data_loader import load_all
#   panel = load_all(counties_df, cache_dir="data/open")

import logging
import numpy as np
import pandas as pd
from pathlib import Path

log = logging.getLogger(__name__)


def load_all(
    counties: pd.DataFrame,
    cache_dir: str = "data/open",
    force_download: bool = False,
) -> pd.DataFrame:
    """
    Load all open data sources and merge into a single county-level panel.

    Parameters
    ----------
    counties : DataFrame with at least county_fips, population, is_rural,
               ses_disadvantage_index, state_abbr
    cache_dir : where to cache downloaded files
    force_download : re-download even if cache exists

    Returns
    -------
    DataFrame — one row per county_fips with all 7-dimension features
    """
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    panel = counties[["county_fips", "county_name", "state_name", "state_abbr",
                       "population", "is_rural", "ses_disadvantage_index"]].copy()

    # ── Source 1: CDC PLACES ──────────────────────────────────────────────────
    log.info("Loading CDC PLACES ...")
    try:
        from src.ingestion.open_data.cdc_places import download as cdc_dl
        cdc = cdc_dl(cache_dir=cache_dir, force=force_download)
        if not cdc.empty:
            panel = panel.merge(cdc, on="county_fips", how="left")
            log.info(f"  CDC PLACES: merged {cdc.columns.tolist()}")
        else:
            raise ValueError("Empty")
    except Exception as e:
        log.warning(f"  CDC PLACES unavailable ({e}), using synthetic fallback")
        panel = _synthetic_cdc_places(panel)

    # ── Source 2: Census ACS ──────────────────────────────────────────────────
    log.info("Loading Census ACS ...")
    try:
        from src.ingestion.open_data.census_acs import download as acs_dl
        acs = acs_dl(cache_dir=cache_dir, force=force_download)
        if not acs.empty:
            panel = panel.merge(acs, on="county_fips", how="left")
            log.info(f"  Census ACS: merged {len(acs.columns)} columns")
        else:
            raise ValueError("Empty")
    except Exception as e:
        log.warning(f"  Census ACS unavailable ({e}), using synthetic fallback")
        panel = _synthetic_acs(panel)

    # ── Source 3: HRSA ────────────────────────────────────────────────────────
    log.info("Loading HRSA ...")
    try:
        from src.ingestion.open_data.hrsa_data import download as hrsa_dl
        hrsa = hrsa_dl(cache_dir=cache_dir, force=force_download)
        if not hrsa.empty:
            panel = panel.merge(hrsa, on="county_fips", how="left")
            log.info(f"  HRSA: merged {hrsa.columns.tolist()}")
        else:
            raise ValueError("Empty")
    except Exception as e:
        log.warning(f"  HRSA unavailable ({e}), using synthetic fallback")
        panel = _synthetic_hrsa(panel)

    # ── Source 4: CMS Chronic Conditions + MA Penetration ─────────────────────
    log.info("Loading CMS data ...")
    try:
        from src.ingestion.open_data.cms_data import (
            download_chronic_conditions, download_ma_penetration
        )
        cms_cc = download_chronic_conditions(cache_dir=cache_dir, force=force_download)
        cms_ma = download_ma_penetration(cache_dir=cache_dir, force=force_download)

        if not cms_cc.empty:
            panel = panel.merge(cms_cc, on="county_fips", how="left")
        else:
            panel = _synthetic_cms_chronic(panel)

        if not cms_ma.empty:
            panel = panel.merge(cms_ma, on="county_fips", how="left")
        else:
            panel = _synthetic_cms_ma(panel)
    except Exception as e:
        log.warning(f"  CMS unavailable ({e}), using synthetic fallback")
        panel = _synthetic_cms_chronic(panel)
        panel = _synthetic_cms_ma(panel)

    # ── Fill any remaining NaNs with realistic values ─────────────────────────
    panel = _fill_missing(panel)

    log.info(f"Open data panel complete: {len(panel):,} counties × {len(panel.columns)} columns")
    return panel


# ── Synthetic fallbacks — realistic distributions, not random noise ───────────

HIGH_BURDEN_STATES = {"MS","AL","WV","KY","LA","AR","NM","SD","MT","ND","OK","TN"}

def _synthetic_cdc_places(df: pd.DataFrame) -> pd.DataFrame:
    """Generate CDC PLACES-like prevalence estimates from SDoH proxies."""
    rng = np.random.default_rng(42)
    ses = df["ses_disadvantage_index"].fillna(0.3)
    rural = df["is_rural"].fillna(False).astype(float)
    high_burden = df["state_abbr"].isin(HIGH_BURDEN_STATES).astype(float)

    base_t2d = 0.113  # CDC national T2D prevalence
    df["diabetes_prevalence_pct"] = np.clip(
        base_t2d + 0.08 * ses + 0.02 * rural + 0.025 * high_burden
        + rng.normal(0, 0.015, len(df)), 0.04, 0.35
    )
    df["hypertension_prevalence_pct"] = np.clip(
        0.47 + 0.10 * ses + 0.03 * rural + 0.03 * high_burden
        + rng.normal(0, 0.02, len(df)), 0.20, 0.70
    )
    df["obesity_rate_pct"] = np.clip(
        0.32 + 0.12 * ses + 0.05 * rural + 0.04 * high_burden
        + rng.normal(0, 0.025, len(df)), 0.10, 0.55
    )
    df["smoking_rate_pct"] = np.clip(
        0.14 + 0.08 * ses + 0.04 * rural + 0.03 * high_burden
        + rng.normal(0, 0.02, len(df)), 0.03, 0.35
    )
    df["poor_physical_health_pct"] = np.clip(
        0.14 + 0.10 * ses + 0.03 * rural + rng.normal(0, 0.02, len(df)), 0.05, 0.35
    )
    df["annual_checkup_pct"] = np.clip(
        0.72 - 0.15 * ses - 0.08 * rural + rng.normal(0, 0.03, len(df)), 0.35, 0.90
    )
    return df


def _synthetic_acs(df: pd.DataFrame) -> pd.DataFrame:
    """Generate ACS-like SDoH features."""
    rng = np.random.default_rng(43)
    ses = df["ses_disadvantage_index"].fillna(0.3)
    rural = df["is_rural"].fillna(False).astype(float)
    pop = df["population"].fillna(50000)

    df["poverty_rate"] = np.clip(
        0.13 + 0.18 * ses + rng.normal(0, 0.02, len(df)), 0.04, 0.40
    )
    df["median_household_income"] = np.clip(
        75000 - 30000 * ses + rng.normal(0, 5000, len(df)), 28000, 150000
    )
    df["median_age"] = np.clip(
        38 + 6 * rural - 3 * (pop > 500000).astype(float)
        + rng.normal(0, 2, len(df)), 26, 55
    )
    df["uninsured_rate"] = np.clip(
        0.09 + 0.12 * ses + rng.normal(0, 0.02, len(df)), 0.02, 0.28
    )
    df["hs_graduation_rate"] = np.clip(
        0.88 - 0.12 * ses + rng.normal(0, 0.03, len(df)), 0.55, 0.98
    )
    df["broadband_access_rate"] = np.clip(
        0.85 - 0.20 * rural - 0.10 * ses + rng.normal(0, 0.04, len(df)), 0.40, 0.97
    )
    # Racial risk index — correlated with SES and geography
    df["racial_risk_index"] = np.clip(
        0.15 + 0.25 * ses + rng.normal(0, 0.05, len(df)), 0.01, 0.65
    )
    df["total_population"] = pop
    return df


def _synthetic_hrsa(df: pd.DataFrame) -> pd.DataFrame:
    """Generate HRSA-like access-to-care features."""
    rng = np.random.default_rng(44)
    ses = df["ses_disadvantage_index"].fillna(0.3)
    rural = df["is_rural"].fillna(False).astype(float)
    pop = df["population"].fillna(50000)

    df["hpsa_flag"] = (
        (ses > 0.5) | (rural == 1) | (rng.random(len(df)) < 0.25)
    ).astype(int)
    df["fqhc_count"] = np.maximum(0, np.round(
        (pop / 100000) * (0.5 + 0.8 * ses) + rng.normal(0, 0.3, len(df))
    )).astype(int)
    df["fqhc_present"] = (df["fqhc_count"] > 0).astype(int)
    return df


def _synthetic_cms_chronic(df: pd.DataFrame) -> pd.DataFrame:
    """Generate CMS Chronic Conditions-like Medicare rates."""
    rng = np.random.default_rng(45)
    ses = df["ses_disadvantage_index"].fillna(0.3)

    # Medicare T2D rate is higher than general population (older patients)
    df["cms_t2d_diagnosed_rate"] = np.clip(
        0.28 + 0.12 * ses + rng.normal(0, 0.03, len(df)), 0.15, 0.55
    )
    df["cms_htn_diagnosed_rate"] = np.clip(
        0.58 + 0.10 * ses + rng.normal(0, 0.04, len(df)), 0.35, 0.80
    )
    return df


def _synthetic_cms_ma(df: pd.DataFrame) -> pd.DataFrame:
    """Generate CMS Medicare Advantage penetration estimates."""
    rng = np.random.default_rng(46)
    rural = df["is_rural"].fillna(False).astype(float)
    # MA penetration is lower in rural areas, higher in suburban
    df["ma_penetration_rate"] = np.clip(
        0.45 - 0.15 * rural + rng.normal(0, 0.08, len(df)), 0.10, 0.80
    )
    df["medicaid_rate"] = np.clip(
        0.20 + 0.15 * df["ses_disadvantage_index"].fillna(0.3)
        + rng.normal(0, 0.04, len(df)), 0.05, 0.55
    )
    df["commercial_rate"] = np.clip(
        1 - df["ma_penetration_rate"] - df["medicaid_rate"]
        - 0.08 + rng.normal(0, 0.03, len(df)), 0.05, 0.65
    )
    return df


def _fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Fill any remaining NaN values with column medians."""
    numeric_cols = df.select_dtypes(include="number").columns
    for col in numeric_cols:
        median = df[col].median()
        if pd.isna(median):
            median = 0.0
        df[col] = df[col].fillna(median)
    return df
