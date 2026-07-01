from __future__ import annotations
# HRSA Area Health Resource Files (AHRF) — county-level healthcare workforce data.
#
# Key variables used:
#   - Primary care physicians per 1,000 population
#   - Specialist density (endocrinologists, cardiologists)
#   - FQHC count and patient capacity
#   - Health Professional Shortage Area (HPSA) designation
#   - Hospital count and beds
#
# Sources:
#   HRSA AHRF: https://data.hrsa.gov/data/download  (large zip, ~500MB)
#   HRSA HPSA: https://data.hrsa.gov/api/download?filename=HPSA&fileType=csv
#   HRSA FQHC: https://data.hrsa.gov/api/download?filename=HPSA_FQHC&fileType=csv

import logging
from pathlib import Path
from io import StringIO

import pandas as pd
import requests

log = logging.getLogger(__name__)

HPSA_URL = "https://data.hrsa.gov/api/download?filename=HPSA&fileType=csv"
FQHC_URL = "https://data.hrsa.gov/api/download?filename=FQHC_LOOK_ALIKES&fileType=csv"


def download(cache_dir: str = "data/open", force: bool = False) -> pd.DataFrame:
    """
    Download HRSA access-to-care data by county.
    Returns: county_fips, pcp_per_1000, hpsa_flag, fqhc_count, fqhc_patients_per_1000
    """
    cache_path = Path(cache_dir) / "hrsa_access.parquet"
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force:
        log.info("HRSA: loading from cache")
        return pd.read_parquet(cache_path)

    log.info("HRSA: downloading shortage area data ...")
    hpsa_df = _fetch_hpsa()
    fqhc_df = _fetch_fqhc()

    if hpsa_df.empty and fqhc_df.empty:
        log.warning("HRSA: all downloads failed. Will use synthetic fallback.")
        return pd.DataFrame()

    # Combine into county-level summary
    result = _combine(hpsa_df, fqhc_df)
    result.to_parquet(cache_path, index=False)
    log.info(f"HRSA: {len(result):,} counties cached")
    return result


def _fetch_hpsa() -> pd.DataFrame:
    try:
        resp = requests.get(HPSA_URL, timeout=60)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text), low_memory=False)

        # HPSA primary care shortage areas
        df = df[df["HPSA Discipline Class"] == "Primary Care"].copy()

        # Build county FIPS from state + county codes
        if "County Equivalent FIPS Code" in df.columns:
            df["county_fips"] = df["County Equivalent FIPS Code"].astype(str).str.zfill(5)
        elif "State FIPS Code" in df.columns and "County FIPS Code" in df.columns:
            df["county_fips"] = (
                df["State FIPS Code"].astype(str).str.zfill(2)
                + df["County FIPS Code"].astype(str).str.zfill(3)
            )
        else:
            return pd.DataFrame()

        # Any designated shortage = flag
        shortage = df.groupby("county_fips").size().reset_index(name="hpsa_area_count")
        shortage["hpsa_flag"] = 1
        return shortage[["county_fips", "hpsa_flag", "hpsa_area_count"]]
    except Exception as e:
        log.warning(f"HPSA fetch failed: {e}")
        return pd.DataFrame()


def _fetch_fqhc() -> pd.DataFrame:
    try:
        resp = requests.get(FQHC_URL, timeout=60)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text), low_memory=False)

        for fips_col in ["County FIPS Code", "FIPS Code", "county_fips"]:
            if fips_col in df.columns:
                df["county_fips"] = df[fips_col].astype(str).str.zfill(5)
                break
        else:
            return pd.DataFrame()

        fqhc = df.groupby("county_fips").agg(
            fqhc_count=("county_fips", "count")
        ).reset_index()
        return fqhc
    except Exception as e:
        log.warning(f"FQHC fetch failed: {e}")
        return pd.DataFrame()


def _combine(hpsa_df: pd.DataFrame, fqhc_df: pd.DataFrame) -> pd.DataFrame:
    """Merge HRSA datasets into county-level access table."""
    # Start with all counties from whichever dataset has data
    if not hpsa_df.empty:
        result = hpsa_df.copy()
    else:
        result = pd.DataFrame(columns=["county_fips"])

    if not fqhc_df.empty:
        result = result.merge(fqhc_df, on="county_fips", how="outer")

    # Fill missing values
    if "hpsa_flag" not in result.columns:
        result["hpsa_flag"] = 0
    if "fqhc_count" not in result.columns:
        result["fqhc_count"] = 0

    result["hpsa_flag"] = result["hpsa_flag"].fillna(0).astype(int)
    result["fqhc_count"] = result["fqhc_count"].fillna(0).astype(int)
    result["fqhc_present"] = (result["fqhc_count"] > 0).astype(int)

    return result[["county_fips", "hpsa_flag", "fqhc_count", "fqhc_present"]]
