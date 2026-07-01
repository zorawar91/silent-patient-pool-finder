from __future__ import annotations
# CMS Open Data — Part D drug utilization + Medicare Chronic Conditions
#
# Part D County-Level Drug Utilization:
#   CMS releases annual county-level summaries of Part D drug claims.
#   Used to compute: T2D Rx penetration rate, treatment gap, diagnostic orphan ratio.
#   Source: https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug
#
# Medicare Chronic Conditions Dashboard:
#   County-level prevalence of chronic conditions in Medicare population.
#   Used to compute: diagnosed T2D rate, comorbidity index (HTN+T2D+Obesity).
#   Source: https://data.cms.gov/medicare-chronic-conditions
#
# Medicare Advantage Penetration:
#   County-level MA enrollment vs. total Medicare eligibles.
#   Source: https://www.cms.gov/data-research/statistics-trends-and-reports/

import logging
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

# CMS Geographic Variation Public Use File — county-level Medicare statistics
# Includes: chronic condition rates, spending, utilization
CMS_GEO_VAR_URL = (
    "https://data.cms.gov/api/1/datastore/query/77e2b3b7-56c1-43a5-917c-d7e0e7f1427c/0"
    "?keys=true&format=csv"
)

# CMS State/County-level Medicare information (MA penetration proxy)
CMS_MA_URL = (
    "https://data.cms.gov/api/1/datastore/query/"
    "3c77b065-a22e-4e88-909c-16bef2cf9e22/0?keys=true&format=csv"
)


def download_chronic_conditions(cache_dir: str = "data/open", force: bool = False) -> pd.DataFrame:
    """
    Download CMS Medicare chronic condition county-level data.
    Returns one row per county_fips with T2D diagnosed rate and comorbidity index.
    """
    cache_path = Path(cache_dir) / "cms_chronic_county.parquet"
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force:
        log.info("CMS Chronic: loading from cache")
        return pd.read_parquet(cache_path)

    log.info("CMS Chronic Conditions: attempting download ...")
    try:
        # Try the CMS Geographic Variation PUF
        df = _fetch_cms_geo_variation(cache_dir)
        df.to_parquet(cache_path, index=False)
        log.info(f"CMS Chronic: {len(df):,} counties cached")
        return df
    except Exception as e:
        log.warning(f"CMS Chronic download failed: {e}. Will use synthetic fallback.")
        return pd.DataFrame()


def download_ma_penetration(cache_dir: str = "data/open", force: bool = False) -> pd.DataFrame:
    """
    Medicare Advantage penetration by county.
    Returns county_fips, ma_penetration_rate (0-1), total_medicare_beneficiaries.
    """
    cache_path = Path(cache_dir) / "cms_ma_penetration.parquet"
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force:
        log.info("CMS MA Penetration: loading from cache")
        return pd.read_parquet(cache_path)

    log.info("CMS MA Penetration: attempting download ...")
    try:
        df = _fetch_ma_data(cache_dir)
        df.to_parquet(cache_path, index=False)
        log.info(f"CMS MA Penetration: {len(df):,} counties cached")
        return df
    except Exception as e:
        log.warning(f"CMS MA download failed: {e}. Will use synthetic fallback.")
        return pd.DataFrame()


def _fetch_cms_geo_variation(cache_dir: str) -> pd.DataFrame:
    """Fetch and parse CMS Geographic Variation PUF."""
    url = (
        "https://data.cms.gov/api/1/datastore/query/"
        "9767cb68-8ea9-4abb-bb58-c966df773bc6/0?keys=true&format=csv"
    )
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    from io import StringIO
    df = pd.read_csv(StringIO(resp.text), low_memory=False)

    # Find county-level rows
    if "bene_geo_lvl" in df.columns:
        df = df[df["bene_geo_lvl"].str.lower() == "county"].copy()

    if "bene_geo_cd" in df.columns:
        df["county_fips"] = df["bene_geo_cd"].astype(str).str.zfill(5)
    else:
        return pd.DataFrame()

    result = pd.DataFrame()
    result["county_fips"] = df["county_fips"]

    # T2D prevalence in Medicare population
    for col in ["diab_pct", "diabetes_pct", "pct_diab"]:
        if col in df.columns:
            result["cms_t2d_diagnosed_rate"] = pd.to_numeric(df[col], errors="coerce") / 100
            break

    # HTN prevalence
    for col in ["hypert_pct", "hypertension_pct", "pct_hypert"]:
        if col in df.columns:
            result["cms_htn_diagnosed_rate"] = pd.to_numeric(df[col], errors="coerce") / 100
            break

    return result.dropna(subset=["county_fips"])


def _fetch_ma_data(cache_dir: str) -> pd.DataFrame:
    """Fetch Medicare Advantage penetration from CMS."""
    # CMS County-level enrollment file
    url = "https://data.cms.gov/api/1/datastore/query/3c77b065-a22e-4e88-909c-16bef2cf9e22/0?format=csv"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    from io import StringIO
    df = pd.read_csv(StringIO(resp.text), low_memory=False)

    # Standardize
    result = pd.DataFrame()
    for fips_col in ["fips_code", "county_fips", "ssa_code"]:
        if fips_col in df.columns:
            result["county_fips"] = df[fips_col].astype(str).str.zfill(5)
            break

    for ma_col in ["ma_penetration", "ma_pct", "pct_ma"]:
        if ma_col in df.columns:
            result["ma_penetration_rate"] = pd.to_numeric(df[ma_col], errors="coerce") / 100
            break

    return result.dropna(subset=["county_fips"])
