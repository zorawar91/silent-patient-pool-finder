from __future__ import annotations
"""
County adult age composition — Census Population Estimates Program (PEP).

Why this exists
---------------
The undiagnosed-pool estimate originally applied ONE national undiagnosis rate
(23.1% for T2D) to every county, multiplied by TOTAL population. Both are wrong
in a fixable way:

  1. The undiagnosed SHARE of diabetes cases varies strongly with age, and not
     in the direction people expect — it FALLS as age rises, because older
     adults are screened far more often (NHANES: 36.1% of cases undiagnosed at
     20-39, but 24.9% at 60+). A county with a young population therefore hides
     proportionally more cases than a flat rate implies.
  2. Prevalence rates are measured on ADULTS, so multiplying by total population
     (including children) over-estimates the pool in young counties.

This module supplies the county age mix that fixes both.

Source: PEP `cc-est2023-agesex-all.csv` on www2.census.gov — a bulk file, so it
needs NO Census API key (unlike the ACS API), which keeps a fresh clone able to
rebuild this without credentials. US federal work: public domain, commercially
redistributable.
"""

import io
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

PEP_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/"
    "2020-2023/counties/asrh/cc-est2023-agesex-all.csv"
)

# Bands published by PEP that we need. AGE18PLUS_TOT is the adult denominator.
_USECOLS = [
    "STATE", "COUNTY", "YEAR", "POPESTIMATE",
    "AGE1824_TOT", "AGE2544_TOT", "AGE4564_TOT", "AGE65PLUS_TOT",
    "AGE18PLUS_TOT",
]


def download(cache_dir: str = "data/open", force: bool = False) -> pd.DataFrame:
    """
    County adult population and age-band shares.

    Returns one row per county_fips with:
        adult_population        — 18+ (the correct prevalence denominator)
        age_share_young         — 18-44 as a share of adults
        age_share_middle        — 45-64
        age_share_older         — 65+

    Returns an empty frame on failure — callers fall back to national rates.
    """
    cache = Path(cache_dir) / "census_county_age.parquet"
    if cache.exists() and not force:
        df = pd.read_parquet(cache)
        if not df.empty:
            log.info(f"County age mix: {len(df):,} counties from cache")
            return df

    from src.ingestion.download import fetch

    try:
        log.info("Census PEP county age/sex file ...")
        resp = fetch(PEP_URL, timeout=180)
        resp.raise_for_status()
        raw = pd.read_csv(io.BytesIO(resp.content), usecols=_USECOLS,
                          encoding="latin-1")
    except Exception as exc:
        log.warning(f"County age mix unavailable ({exc}) — national rates will be used.")
        return pd.DataFrame()

    # YEAR is a vintage index; the largest value is the most recent estimate.
    raw = raw[raw["YEAR"] == raw["YEAR"].max()].copy()

    out = pd.DataFrame({
        "county_fips": (raw["STATE"].astype(int).astype(str).str.zfill(2)
                        + raw["COUNTY"].astype(int).astype(str).str.zfill(3)),
        "adult_population": pd.to_numeric(raw["AGE18PLUS_TOT"], errors="coerce"),
    })
    young  = pd.to_numeric(raw["AGE1824_TOT"], errors="coerce").fillna(0) \
           + pd.to_numeric(raw["AGE2544_TOT"], errors="coerce").fillna(0)
    middle = pd.to_numeric(raw["AGE4564_TOT"], errors="coerce").fillna(0)
    older  = pd.to_numeric(raw["AGE65PLUS_TOT"], errors="coerce").fillna(0)

    denom = (young + middle + older).replace(0, pd.NA)
    out["age_share_young"]  = (young / denom).astype(float)
    out["age_share_middle"] = (middle / denom).astype(float)
    out["age_share_older"]  = (older / denom).astype(float)
    out = out.dropna(subset=["county_fips"]).drop_duplicates("county_fips")

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache, index=False)
    log.info(f"County age mix: {len(out):,} counties cached")
    return out
