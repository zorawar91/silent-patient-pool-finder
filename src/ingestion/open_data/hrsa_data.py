from __future__ import annotations
# HRSA Health Professional Shortage Area (HPSA) + FQHC data — county-level.
#
# Key variables used:
#   - HPSA designation (primary care shortage area flag)
#   - FQHC presence (Federally Qualified Health Center)
#
# Sources (new DataDownload endpoint — old /api/download path retired 2024):
#   HRSA HPSA PC: https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_PC.csv
#   HRSA FQHC:    https://data.hrsa.gov/DataDownload/DD_Files/FQHC_LOOK_ALIKES.csv
#                 https://data.hrsa.gov/DataDownload/DD_Files/BCD_HCOP_MAIN_FCT.csv (fallback)

import logging
from pathlib import Path
from io import StringIO

import pandas as pd
import requests

log = logging.getLogger(__name__)

# HRSA redesigned their data portal in 2024; old /api/download URLs now 404.
# New pattern: https://data.hrsa.gov/DataDownload/DD_Files/{filename}.csv
HPSA_URLS = [
    "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_PC.csv",
]
FQHC_URLS = [
    "https://data.hrsa.gov/DataDownload/DD_Files/FQHC_LOOK_ALIKES.csv",
    "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HCOP_MAIN_FCT.csv",
]

_HEADERS = {
    "User-Agent": "SPPF/1.0 (research; contact zorawarnandwal@gmail.com)",
    "Accept":     "text/csv,*/*",
    "Referer":    "https://data.hrsa.gov/data/download",
    "Accept-Encoding": "identity",  # disable gzip — avoids LibreSSL 2.8.3 corruption
}


def _find_csv_start(text: str) -> str:
    """
    HRSA CSVs sometimes begin with a multi-line disclaimer before the real headers.
    Finds the first line that looks like a real CSV header (>=5 comma-separated fields,
    not ending with a period like a sentence).
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.count(",") >= 4 and not line.strip().endswith("."):
            if i > 0:
                log.info(f"  HRSA: skipped {i} disclaimer line(s), CSV starts at line {i+1}")
            return "\n".join(lines[i:])
    return text  # fallback: return as-is


def download(cache_dir: str = "data/open", force: bool = False) -> pd.DataFrame:
    """
    Download HRSA access-to-care data by county.
    Returns: county_fips, hpsa_flag, fqhc_count, fqhc_present
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

    result = _combine(hpsa_df, fqhc_df)
    result.to_parquet(cache_path, index=False)
    log.info(f"HRSA: {len(result):,} counties cached | "
             f"HPSA {result['hpsa_flag'].sum():,} | FQHC {result['fqhc_present'].sum():,}")
    return result


def _fetch_hpsa() -> pd.DataFrame:
    for url in HPSA_URLS:
        try:
            log.info(f"  HRSA HPSA: {url}")
            resp = requests.get(url, timeout=90, headers=_HEADERS)
            resp.raise_for_status()
            if len(resp.content) < 10_000:
                log.warning(f"  HRSA HPSA: response too small ({len(resp.content):,} bytes)")
                continue

            csv_text = _find_csv_start(resp.text)
            df = pd.read_csv(StringIO(csv_text), low_memory=False, on_bad_lines="skip")
            log.info(f"  HRSA HPSA: {len(df):,} rows, columns: {list(df.columns[:8])}")

            # Filter to Primary Care HPSAs only
            disc_col = next((c for c in df.columns if "discipline" in c.lower()), None)
            if disc_col:
                df = df[df[disc_col].astype(str).str.lower().str.contains(
                    "primary care|primary", na=False
                )].copy()
            else:
                log.warning("  HRSA HPSA: no discipline column — using all rows")

            # Build county FIPS
            if "County Equivalent FIPS Code" in df.columns:
                df["county_fips"] = df["County Equivalent FIPS Code"].astype(str).str.zfill(5)
            elif "State FIPS Code" in df.columns and "County FIPS Code" in df.columns:
                df["county_fips"] = (
                    df["State FIPS Code"].astype(str).str.zfill(2)
                    + df["County FIPS Code"].astype(str).str.zfill(3)
                )
            elif "State Fips" in df.columns and "County Fips" in df.columns:
                df["county_fips"] = (
                    df["State Fips"].astype(str).str.zfill(2)
                    + df["County Fips"].astype(str).str.zfill(3)
                )
            else:
                fips_col = next(
                    (c for c in df.columns
                     if "fips" in c.lower() and
                     df[c].astype(str).str.match(r"^\d{4,5}$").sum() > 100),
                    None
                )
                if fips_col:
                    df["county_fips"] = df[fips_col].astype(str).str.zfill(5)
                else:
                    log.warning(f"  HRSA HPSA: no FIPS column found. "
                                f"Columns: {list(df.columns[:12])}")
                    continue

            shortage = df.groupby("county_fips").size().reset_index(name="hpsa_area_count")
            shortage["hpsa_flag"] = 1
            log.info(f"  HRSA HPSA: {len(shortage):,} counties with shortage areas")
            return shortage[["county_fips", "hpsa_flag", "hpsa_area_count"]]

        except Exception as e:
            log.warning(f"  HRSA HPSA {url}: {e}")

    return pd.DataFrame()


def _fetch_fqhc() -> pd.DataFrame:
    for url in FQHC_URLS:
        try:
            log.info(f"  HRSA FQHC: {url}")
            resp = requests.get(url, timeout=90, headers=_HEADERS)
            resp.raise_for_status()
            if len(resp.content) < 5_000:
                log.warning(f"  HRSA FQHC: response too small ({len(resp.content):,} bytes)")
                continue

            csv_text = _find_csv_start(resp.text)
            df = pd.read_csv(StringIO(csv_text), low_memory=False, on_bad_lines="skip")
            log.info(f"  HRSA FQHC: {len(df):,} rows, columns: {list(df.columns[:8])}")

            fips_col = None
            for candidate in ["County FIPS Code", "County Equivalent FIPS Code",
                               "FIPS Code", "county_fips", "County Fips"]:
                if candidate in df.columns:
                    fips_col = candidate
                    break
            if fips_col is None:
                fips_col = next(
                    (c for c in df.columns
                     if "fips" in c.lower() and
                     df[c].astype(str).str.match(r"^\d{4,5}$").sum() > 50),
                    None
                )
            if fips_col is None:
                log.warning(f"  HRSA FQHC: no FIPS column. Columns: {list(df.columns[:12])}")
                continue

            df["county_fips"] = df[fips_col].astype(str).str.zfill(5)
            fqhc = df.groupby("county_fips").agg(
                fqhc_count=("county_fips", "count")
            ).reset_index()
            log.info(f"  HRSA FQHC: {len(fqhc):,} counties with FQHCs")
            return fqhc

        except Exception as e:
            log.warning(f"  HRSA FQHC {url}: {e}")

    return pd.DataFrame()


def _combine(hpsa_df: pd.DataFrame, fqhc_df: pd.DataFrame) -> pd.DataFrame:
    """Merge HRSA datasets into county-level access table."""
    if not hpsa_df.empty:
        result = hpsa_df.copy()
    else:
        result = pd.DataFrame(columns=["county_fips"])

    if not fqhc_df.empty:
        result = result.merge(fqhc_df, on="county_fips", how="outer")

    if "hpsa_flag" not in result.columns:
        result["hpsa_flag"] = 0
    if "fqhc_count" not in result.columns:
        result["fqhc_count"] = 0

    result["hpsa_flag"]    = result["hpsa_flag"].fillna(0).astype(int)
    result["fqhc_count"]   = result["fqhc_count"].fillna(0).astype(int)
    result["fqhc_present"] = (result["fqhc_count"] > 0).astype(int)

    cols = ["county_fips", "hpsa_flag", "fqhc_count", "fqhc_present"]
    if "hpsa_area_count" in result.columns:
        cols.insert(2, "hpsa_area_count")
    return result[cols].copy()
