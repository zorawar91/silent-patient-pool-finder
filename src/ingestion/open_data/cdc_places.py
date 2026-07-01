from __future__ import annotations
# CDC PLACES — Local Data for Better Health
# County-level chronic disease prevalence estimates for all US counties.
# Source: https://data.cdc.gov/dataset/PLACES-Local-Data-for-Better-Health-County-Data-20/swc5-untb
#
# Key measures used:
#   DIABETES     — % adults with diagnosed diabetes
#   BPHIGH       — % adults with high blood pressure
#   OBESITY      — % adults with obesity (BMI >= 30)
#   CSMOKING     — % adults who smoke (T2D risk factor)
#   PHLTH        — % adults reporting poor physical health
#   CHECKUP      — % adults with routine checkup in past year (access proxy)

import logging
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

CDC_PLACES_URL = (
    "https://data.cdc.gov/api/views/swc5-untb/rows.csv?accessType=DOWNLOAD"
)

MEASURES_NEEDED = {
    "DIABETES": "diabetes_prevalence_pct",
    "BPHIGH":   "hypertension_prevalence_pct",
    "OBESITY":  "obesity_rate_pct",
    "CSMOKING": "smoking_rate_pct",
    "PHLTH":    "poor_physical_health_pct",
    "CHECKUP":  "annual_checkup_pct",
}


def download(cache_dir: str = "data/open", force: bool = False) -> pd.DataFrame:
    """
    Download CDC PLACES county-level data, cache locally, return processed DataFrame.
    Returns one row per county_fips with normalized measure columns.
    """
    cache_path = Path(cache_dir) / "cdc_places_county.parquet"
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force:
        log.info(f"CDC PLACES: loading from cache ({cache_path})")
        return pd.read_parquet(cache_path)

    log.info("CDC PLACES: downloading from data.cdc.gov ...")
    try:
        resp = requests.get(CDC_PLACES_URL, timeout=120, stream=True)
        resp.raise_for_status()
        raw_path = Path(cache_dir) / "cdc_places_raw.csv"
        with open(raw_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        log.info(f"CDC PLACES: downloaded {raw_path.stat().st_size / 1e6:.1f} MB")
    except Exception as e:
        log.warning(f"CDC PLACES download failed: {e}. Returning empty DataFrame.")
        return pd.DataFrame()

    df = _parse(raw_path)
    df.to_parquet(cache_path, index=False)
    log.info(f"CDC PLACES: {len(df):,} counties cached → {cache_path}")
    return df


def _parse(raw_path: Path) -> pd.DataFrame:
    """Parse raw CDC PLACES CSV into one-row-per-county wide format."""
    raw = pd.read_csv(raw_path, low_memory=False)

    # Filter to county-level, most recent year, crude prevalence
    raw = raw[
        (raw["GeographicLevel"] == "County")
        & (raw["DataValueTypeID"] == "CrdPrv")
    ].copy()

    # Keep only the measures we need
    raw = raw[raw["MeasureId"].isin(MEASURES_NEEDED.keys())].copy()

    # Standardize FIPS to 5-digit string
    raw["county_fips"] = raw["LocationID"].astype(str).str.zfill(5)
    raw["value"] = pd.to_numeric(raw["Data_Value"], errors="coerce") / 100.0

    # Pivot to wide format
    wide = raw.pivot_table(
        index="county_fips",
        columns="MeasureId",
        values="value",
        aggfunc="mean",
    ).reset_index()

    # Rename columns
    wide = wide.rename(columns=MEASURES_NEEDED)
    wide.columns.name = None

    # Ensure all expected columns exist
    for col in MEASURES_NEEDED.values():
        if col not in wide.columns:
            wide[col] = float("nan")

    return wide[["county_fips"] + list(MEASURES_NEEDED.values())]
