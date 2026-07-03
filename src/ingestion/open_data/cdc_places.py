from __future__ import annotations
# CDC PLACES — Local Data for Better Health
# County-level chronic disease prevalence estimates for all US counties.
#
# Source: https://data.cdc.gov/browse?category=500+Cities+%26+Places
# PLACES uses BRFSS survey data modelled to county level via CDC methods.
#
# Manual download fallback:
#   If auto-download fails, manually download the CSV from:
#   https://data.cdc.gov/500-Cities-Places/PLACES-Local-Data-for-Better-Health-County-Data-20/swc5-untb
#   Save it as:  data/open/cdc_places_raw.csv
#
# Key measures used:
#   DIABETES    — % adults with diagnosed diabetes (crude prevalence)
#   BPHIGH      — % adults with high blood pressure
#   OBESITY     — % adults with obesity (BMI >= 30)
#   CSMOKING    — % adults who currently smoke
#   PHLTH       — % adults reporting poor physical health ≥14 days/month
#   CHECKUP     — % adults with routine checkup in past year (access proxy)

import logging
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

# Try multiple release-year URLs in order (most recent first)
CDC_PLACES_URLS = [
    # 2024 release — long format (MeasureId / Data_Value structure)
    "https://data.cdc.gov/api/views/yjkw-uj5s/rows.csv?accessType=DOWNLOAD",
    # 2023 release
    "https://data.cdc.gov/api/views/swc5-untb/rows.csv?accessType=DOWNLOAD",
    # 2022 release (GIS-friendly wide format — different column layout)
    "https://data.cdc.gov/api/views/i46a-9kgh/rows.csv?accessType=DOWNLOAD",
    # 2024 alternative endpoint
    "https://data.cdc.gov/api/views/duw2-7jbt/rows.csv?accessType=DOWNLOAD",
]

MEASURES_NEEDED = {
    "DIABETES": "diabetes_prevalence_pct",
    "BPHIGH":   "hypertension_prevalence_pct",
    "OBESITY":  "obesity_rate_pct",
    "CSMOKING": "smoking_rate_pct",
    "PHLTH":    "poor_physical_health_pct",
    "CHECKUP":  "annual_checkup_pct",
}

# GIS-friendly wide format uses these column names instead of MeasureId
GIS_COL_MAP = {
    "DIABETES_CrudePrev":    "diabetes_prevalence_pct",
    "BPHIGH_CrudePrev":      "hypertension_prevalence_pct",
    "OBESITY_CrudePrev":     "obesity_rate_pct",
    "CSMOKING_CrudePrev":    "smoking_rate_pct",
    "PHLTH_CrudePrev":       "poor_physical_health_pct",
    "CHECKUP_CrudePrev":     "annual_checkup_pct",
    # 2024 GIS column names (slightly different capitalization)
    "Diabetes_CrudePrev":    "diabetes_prevalence_pct",
    "Bphigh_CrudePrev":      "hypertension_prevalence_pct",
    "Obesity_CrudePrev":     "obesity_rate_pct",
    "Csmoking_CrudePrev":    "smoking_rate_pct",
    "Phlth_CrudePrev":       "poor_physical_health_pct",
    "Checkup_CrudePrev":     "annual_checkup_pct",
}


def download(cache_dir: str = "data/open", force: bool = False) -> pd.DataFrame:
    """
    Download CDC PLACES county-level data, cache locally, return processed DataFrame.
    Returns one row per county_fips with normalized measure columns.

    Falls back to loading data/open/cdc_places_raw.csv if already placed there manually.
    """
    cache_path = Path(cache_dir) / "cdc_places_county.parquet"
    raw_path   = Path(cache_dir) / "cdc_places_raw.csv"
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    # Return cached parquet if fresh
    if cache_path.exists() and not force:
        log.info(f"CDC PLACES: loading from cache ({cache_path})")
        return pd.read_parquet(cache_path)

    # If user manually placed the CSV, parse it directly
    if raw_path.exists() and not force:
        log.info(f"CDC PLACES: parsing manually-placed CSV ({raw_path})")
        df = _parse(raw_path)
        if not df.empty:
            df.to_parquet(cache_path, index=False)
            log.info(f"CDC PLACES: {len(df):,} counties cached → {cache_path}")
            return df

    # Try each known URL in order
    downloaded = False
    for url in CDC_PLACES_URLS:
        log.info(f"CDC PLACES: trying {url[:80]}...")
        try:
            resp = requests.get(url, timeout=180, stream=True)
            resp.raise_for_status()
            with open(raw_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            size_mb = raw_path.stat().st_size / 1e6
            log.info(f"CDC PLACES: downloaded {size_mb:.1f} MB from {url[:60]}")
            downloaded = True
            break
        except Exception as e:
            log.warning(f"  URL failed ({e}), trying next ...")

    if not downloaded:
        log.warning(
            "CDC PLACES: all URLs failed. To use real data, manually download from:\n"
            "  https://data.cdc.gov/500-Cities-Places/"
            "PLACES-Local-Data-for-Better-Health-County-Data-20/swc5-untb\n"
            f"  and save as {raw_path}"
        )
        return pd.DataFrame()

    df = _parse(raw_path)
    if df.empty:
        log.warning("CDC PLACES: parsed file was empty — check raw CSV structure")
        return pd.DataFrame()

    df.to_parquet(cache_path, index=False)
    log.info(f"CDC PLACES: {len(df):,} counties cached → {cache_path}")
    return df


def _parse(raw_path: Path) -> pd.DataFrame:
    """
    Parse CDC PLACES CSV — handles both long-format and GIS-friendly wide format.
    Returns one row per county_fips with standardized prevalence columns (0-1 scale).
    """
    try:
        raw = pd.read_csv(raw_path, low_memory=False)
    except Exception as e:
        log.error(f"CDC PLACES: failed to read CSV ({e})")
        return pd.DataFrame()

    log.info(f"CDC PLACES raw: {len(raw):,} rows × {len(raw.columns)} cols. "
             f"Sample cols: {list(raw.columns[:8])}")

    # ── Detect format: GIS-friendly (wide) vs. long format ───────────────────
    if "DIABETES_CrudePrev" in raw.columns or "Diabetes_CrudePrev" in raw.columns:
        return _parse_gis_format(raw)
    elif "MeasureId" in raw.columns or "measureid" in raw.columns.str.lower().tolist():
        return _parse_long_format(raw)
    else:
        log.warning(f"CDC PLACES: unrecognized format. Columns: {list(raw.columns[:15])}")
        return pd.DataFrame()


def _parse_long_format(raw: pd.DataFrame) -> pd.DataFrame:
    """Parse the standard long-format CDC PLACES file (MeasureId/Data_Value rows)."""
    # Normalize column names (sometimes lowercase in newer releases)
    col_map = {c: c for c in raw.columns}
    lower_cols = {c.lower(): c for c in raw.columns}

    def col(name: str) -> str:
        return col_map.get(name) or lower_cols.get(name.lower()) or name

    # Filter to county-level data with crude prevalence values
    geo_col   = col("GeographicLevel")
    type_col  = col("DataValueTypeID")
    meas_col  = col("MeasureId")
    loc_col   = col("LocationID")
    val_col   = col("Data_Value")

    raw = raw[raw[geo_col].str.strip().str.lower() == "county"].copy()

    if type_col in raw.columns:
        crude_mask = raw[type_col].str.strip().str.upper().isin(["CRDPRV", "CRUDE_PREV", "AGE-ADJUSTED"])
        raw = raw[crude_mask | raw[type_col].isna()].copy()

    # Filter to measures we need
    raw = raw[raw[meas_col].str.strip().str.upper().isin(
        {k.upper() for k in MEASURES_NEEDED}
    )].copy()

    raw["county_fips"] = raw[loc_col].astype(str).str.zfill(5)
    raw["value"] = pd.to_numeric(raw[val_col], errors="coerce") / 100.0
    raw["measure_upper"] = raw[meas_col].str.strip().str.upper()

    wide = raw.pivot_table(
        index="county_fips",
        columns="measure_upper",
        values="value",
        aggfunc="mean",
    ).reset_index()
    wide.columns.name = None

    # Rename from MeasureId to our standard names
    rename = {k.upper(): v for k, v in MEASURES_NEEDED.items()}
    wide = wide.rename(columns=rename)

    for col_name in MEASURES_NEEDED.values():
        if col_name not in wide.columns:
            wide[col_name] = float("nan")

    result = wide[["county_fips"] + list(MEASURES_NEEDED.values())]
    log.info(f"CDC PLACES (long format): {len(result):,} counties parsed, "
             f"diabetes range: {result['diabetes_prevalence_pct'].min():.3f}–"
             f"{result['diabetes_prevalence_pct'].max():.3f}")
    return result


def _parse_gis_format(raw: pd.DataFrame) -> pd.DataFrame:
    """Parse the GIS-friendly wide-format CDC PLACES file."""
    # Find FIPS column
    fips_candidates = ["CountyFIPS", "GEOID", "LocationID", "county_fips", "FIPS"]
    fips_col = next((c for c in fips_candidates if c in raw.columns), None)
    if fips_col is None:
        log.warning("CDC PLACES GIS format: no FIPS column found")
        return pd.DataFrame()

    result = pd.DataFrame()
    result["county_fips"] = raw[fips_col].astype(str).str.zfill(5)

    for src_col, dst_col in GIS_COL_MAP.items():
        if src_col in raw.columns and dst_col not in result.columns:
            result[dst_col] = pd.to_numeric(raw[src_col], errors="coerce") / 100.0

    for col_name in MEASURES_NEEDED.values():
        if col_name not in result.columns:
            result[col_name] = float("nan")

    result = result.dropna(subset=["county_fips"])
    result = result[["county_fips"] + list(MEASURES_NEEDED.values())]
    log.info(f"CDC PLACES (GIS format): {len(result):,} counties parsed, "
             f"diabetes range: {result['diabetes_prevalence_pct'].dropna().min():.3f}–"
             f"{result['diabetes_prevalence_pct'].dropna().max():.3f}")
    return result
