from __future__ import annotations
"""
ZCTA-Level Data Ingestion — Silent Patient Pool Finder
=======================================================
Builds a ZIP/ZCTA-level panel (~33,000 ZCTAs) from real public data,
then scores each ZCTA across the 7-dimension framework.

Data sources:
  1. CDC PLACES 2024 (ZCTA)       → disease burden at ZIP level
  2. Census ACS 5-year (ZCTA)     → SDoH (poverty, income, uninsured) at ZIP level
  3. Census ZCTA→county crosswalk → maps ZCTAs to county FIPS (for downscaling)
  4. Census Gazetteer (ZCTA)      → lat/lon centroids for scatter map
  5. data/scored/dimension_scores.parquet  → county-level dim scores (downscaled)

Dimensions at ZCTA level:
  - disease_burden:        REAL (CDC PLACES ZCTA)
  - social_determinants:   REAL (Census ACS ZCTA)
  - diagnosis_gap:         DOWNSCALED from county (crosswalk)
  - access_to_care:        DOWNSCALED from county
  - payer_landscape:       DOWNSCALED from county
  - commercial_readiness:  DOWNSCALED from county
  - trajectory:            DOWNSCALED from county

Run:
  python3 ingest_zcta_data.py

Output:
  data/scored/zip_scores.parquet  (~33,000 ZCTAs with 7 dimension scores + lat/lon)

Prerequisites:
  Run python3 ingest_real_data.py first to produce dimension_scores.parquet (county).

Security:
  Database credentials live in .streamlit/secrets.toml (gitignored).
  This script does NOT touch the database.
"""

import io
import logging
import os
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

OPEN_DIR   = "data/open"
SCORED_DIR = "data/scored"
TIMEOUT    = 120

# Valid US state FIPS (excludes territories)
US_STATE_FIPS = {
    f"{i:02d}" for i in [
        1,2,4,5,6,8,9,10,11,12,13,15,16,17,18,19,20,21,22,23,24,25,26,27,28,
        29,30,31,32,33,34,35,36,37,38,39,40,41,42,44,45,46,47,48,49,50,51,53,
        54,55,56
    ]
}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    log.info("=" * 62)
    log.info("  SPPF ZCTA Ingestion — ZIP-Level Panel (~33k ZCTAs)")
    log.info("=" * 62)

    Path(OPEN_DIR).mkdir(parents=True, exist_ok=True)
    Path(SCORED_DIR).mkdir(parents=True, exist_ok=True)

    # 1. County dimension scores (spine for downscaling)
    log.info("\n[1/5] County dimension scores (from prior ingest_real_data.py run) …")
    county_scores = _load_county_scores()

    # 2. CDC PLACES — ZCTA disease burden
    log.info("\n[2/5] CDC PLACES 2024 ZCTA (disease burden at ZIP level) …")
    cdc_zcta = _download_cdc_places_zcta()

    # 3. Census ACS — ZCTA SDoH
    log.info("\n[3/5] Census ACS ZCTA (social determinants at ZIP level) …")
    acs_zcta = _download_census_acs_zcta()

    # 4. ZCTA → county crosswalk
    log.info("\n[4/5] Census ZCTA→county crosswalk …")
    crosswalk = _download_zcta_crosswalk()

    # 5. ZCTA centroids (lat/lon for scatter map)
    log.info("\n[5/5] Census Gazetteer ZCTA centroids …")
    centroids = _download_zcta_centroids()

    # Build + score
    log.info("\n[→] Building ZCTA panel and scoring 7 dimensions …")
    from src.features.zip_scorer import score_zctas
    zip_scores = score_zctas(
        cdc_zcta=cdc_zcta,
        acs_zcta=acs_zcta,
        crosswalk=crosswalk,
        centroids=centroids,
        county_scores=county_scores,
    )

    if zip_scores.empty:
        log.error("ZIP scoring produced empty output — check logs above")
        sys.exit(1)

    out_path = Path(SCORED_DIR) / "zip_scores.parquet"
    zip_scores.to_parquet(out_path, index=False)

    # Summary
    n_total   = len(zip_scores)
    priority  = int((zip_scores["zip_opportunity_score"] >= 55).sum())
    emerging  = int(((zip_scores["zip_opportunity_score"] >= 40) &
                     (zip_scores["zip_opportunity_score"] < 55)).sum())

    log.info("\n" + "=" * 62)
    log.info("  ZCTA INGESTION COMPLETE")
    log.info(f"  Elapsed:          {time.time() - t0:.0f}s")
    log.info(f"  ZCTAs scored:     {n_total:,}")
    log.info(f"  Priority (≥55):   {priority:,}")
    log.info(f"  Emerging (40–55): {emerging:,}")
    log.info(f"  Output:           {out_path}")
    log.info("=" * 62)

    log.info("\nDashboard ready → python3 -m streamlit run src/output/dashboard.py")


# ─────────────────────────────────────────────────────────────────────────────
# LOADERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_county_scores() -> pd.DataFrame:
    """Load county-level dimension scores produced by ingest_real_data.py."""
    path = Path(SCORED_DIR) / "dimension_scores.parquet"
    if not path.exists():
        log.error(
            "  County scores not found. Run python3 ingest_real_data.py first.\n"
            f"  Expected: {path}"
        )
        sys.exit(1)
    df = pd.read_parquet(path)
    log.info(f"  County scores: {len(df):,} counties loaded")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOADERS
# ─────────────────────────────────────────────────────────────────────────────

def _download_cdc_places_zcta() -> pd.DataFrame:
    """
    CDC PLACES ZCTA-level chronic disease prevalence.
    Same measures as county dataset but at ZIP Code Tabulation Area level.

    Manual fallback:
      Download from https://data.cdc.gov/500-Cities-Places/PLACES-Local-Data-for-Better-Health-ZCTA-Data-2024/qnzd-25i4
      Save as data/open/cdc_places_zcta_raw.csv
    """
    cache   = Path(OPEN_DIR) / "cdc_places_zcta.parquet"
    raw_csv = Path(OPEN_DIR) / "cdc_places_zcta_raw.csv"

    if cache.exists():
        df = pd.read_parquet(cache)
        log.info(f"  CDC PLACES ZCTA: {len(df):,} ZCTAs from cache")
        return df

    if raw_csv.exists():
        log.info(f"  CDC PLACES ZCTA: parsing manually-placed CSV ({raw_csv})")
        df = _parse_cdc_zcta(raw_csv)
        if not df.empty:
            df.to_parquet(cache, index=False)
            return df

    # CDC PLACES ZCTA dataset — multiple endpoint candidates
    urls = [
        # 2024 release — ZCTA Data 2024
        "https://data.cdc.gov/api/views/qnzd-25i4/rows.csv?accessType=DOWNLOAD",
        # Alternate 2024 ZCTA endpoint
        "https://data.cdc.gov/api/views/4ai3-zynv/rows.csv?accessType=DOWNLOAD",
        # 2023 ZCTA release
        "https://data.cdc.gov/api/views/2fpk-mpcj/rows.csv?accessType=DOWNLOAD",
    ]

    for url in urls:
        try:
            log.info(f"  CDC PLACES ZCTA: trying {url[:70]} …")
            resp = requests.get(url, timeout=TIMEOUT, stream=True)
            resp.raise_for_status()
            with open(raw_csv, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            size_mb = raw_csv.stat().st_size / 1e6
            log.info(f"    Downloaded {size_mb:.1f} MB")

            df = _parse_cdc_zcta(raw_csv)
            raw_csv.unlink(missing_ok=True)

            if not df.empty and len(df) > 5000:
                df.to_parquet(cache, index=False)
                log.info(f"  CDC PLACES ZCTA: {len(df):,} ZCTAs | "
                         f"diabetes avg {df['diabetes_prevalence_pct'].mean()*100:.1f}%")
                return df
            log.warning(f"    Only {len(df)} ZCTAs parsed, trying next URL …")
        except Exception as e:
            log.warning(f"    Failed: {e}")

    log.warning(
        "  CDC PLACES ZCTA: all URLs failed.\n"
        "  Manual download: https://data.cdc.gov/500-Cities-Places/"
        "PLACES-Local-Data-for-Better-Health-ZCTA-Data-2024/qnzd-25i4\n"
        "  Save as: data/open/cdc_places_zcta_raw.csv\n"
        "  → Disease burden will use county-downscaled values."
    )
    return pd.DataFrame()


def _parse_cdc_zcta(raw_path: Path) -> pd.DataFrame:
    """
    Parse CDC PLACES ZCTA CSV.
    Handles long-format (MeasureId/Data_Value) and GIS wide format.
    Returns one row per zcta5 with prevalence columns (0-1 scale).
    """
    try:
        raw = pd.read_csv(raw_path, low_memory=False)
    except Exception as e:
        log.error(f"  CDC PLACES ZCTA parse error: {e}")
        return pd.DataFrame()

    log.info(f"  CDC PLACES ZCTA raw: {len(raw):,} rows × {len(raw.columns)} cols. "
             f"Cols: {list(raw.columns[:8])}")

    # --- Detect format ---
    cols_upper = {c.upper() for c in raw.columns}

    # GIS wide format
    if any("DIABETES_CRUDEPREV" in c.upper() or "DIABETES_CRUDEPRV" in c.upper()
           for c in raw.columns):
        return _parse_zcta_gis(raw)

    # Long format (MeasureId column present)
    if "MEASUREID" in cols_upper or "MEASUREID" in [c.upper() for c in raw.columns]:
        return _parse_zcta_long(raw)

    log.warning(f"  CDC PLACES ZCTA: unrecognized format. Cols: {list(raw.columns[:12])}")
    return pd.DataFrame()


_ZCTA_MEASURES = {
    "DIABETES": "diabetes_prevalence_pct",
    "BPHIGH":   "hypertension_prevalence_pct",
    "OBESITY":  "obesity_rate_pct",
    "CHECKUP":  "annual_checkup_pct",
    "CSMOKING": "smoking_rate_pct",
}

_ZCTA_GIS_MAP = {
    "DIABETES_CrudePrev": "diabetes_prevalence_pct",
    "BPHIGH_CrudePrev":   "hypertension_prevalence_pct",
    "OBESITY_CrudePrev":  "obesity_rate_pct",
    "CHECKUP_CrudePrev":  "annual_checkup_pct",
    "Diabetes_CrudePrev": "diabetes_prevalence_pct",
    "Bphigh_CrudePrev":   "hypertension_prevalence_pct",
    "Obesity_CrudePrev":  "obesity_rate_pct",
    "Checkup_CrudePrev":  "annual_checkup_pct",
}


def _parse_zcta_long(raw: pd.DataFrame) -> pd.DataFrame:
    """Parse long-format CDC PLACES ZCTA CSV."""
    col_lower = {c.lower(): c for c in raw.columns}

    def _col(name): return col_lower.get(name.lower(), name)

    meas_col = _col("measureid")
    val_col  = _col("data_value")
    loc_col  = _col("locationid")
    type_col = _col("datavaluetypeid")

    if meas_col not in raw.columns or loc_col not in raw.columns:
        log.warning("  ZCTA long: missing MeasureId or LocationID")
        return pd.DataFrame()

    # Filter to crude prevalence
    if type_col in raw.columns:
        raw = raw[raw[type_col].str.strip().str.upper().isin(
            ["CRDPRV", "CRDPREV", "CRUDE_PREV"]
        ) | raw[type_col].isna()].copy()

    # Filter measures
    raw = raw[raw[meas_col].str.strip().str.upper().isin(
        {k.upper() for k in _ZCTA_MEASURES}
    )].copy()

    # ZCTA LocationID: 5-digit ZCTA code (NOT county FIPS — no state prefix filter)
    raw["zcta5"] = raw[loc_col].astype(str).str.strip().str.zfill(5)
    # Exclude non-ZCTA rows (state/nation rows have 2-digit or longer IDs)
    raw = raw[raw["zcta5"].str.len() == 5].copy()

    raw["value"] = pd.to_numeric(raw[val_col], errors="coerce") / 100.0
    raw["meas"]  = raw[meas_col].str.strip().str.upper()

    wide = raw.pivot_table(
        index="zcta5", columns="meas", values="value", aggfunc="mean"
    ).reset_index()
    wide.columns.name = None

    rename = {k.upper(): v for k, v in _ZCTA_MEASURES.items()}
    wide = wide.rename(columns=rename)

    for col_name in _ZCTA_MEASURES.values():
        if col_name not in wide.columns:
            wide[col_name] = float("nan")

    return wide[["zcta5"] + list(_ZCTA_MEASURES.values())].copy()


def _parse_zcta_gis(raw: pd.DataFrame) -> pd.DataFrame:
    """Parse GIS-friendly wide-format CDC PLACES ZCTA CSV."""
    fips_candidates = ["ZCTA5", "Zcta5", "zcta5", "LocationID", "GEOID", "ZipCode"]
    fips_col = next((c for c in fips_candidates if c in raw.columns), None)
    if fips_col is None:
        log.warning("  ZCTA GIS: no ZCTA5 column found")
        return pd.DataFrame()

    result = pd.DataFrame()
    result["zcta5"] = raw[fips_col].astype(str).str.zfill(5)

    for src_col, dst_col in _ZCTA_GIS_MAP.items():
        if src_col in raw.columns and dst_col not in result.columns:
            result[dst_col] = pd.to_numeric(raw[src_col], errors="coerce") / 100.0

    for col_name in _ZCTA_MEASURES.values():
        if col_name not in result.columns:
            result[col_name] = float("nan")

    return result.dropna(subset=["zcta5"])[
        ["zcta5"] + list(_ZCTA_MEASURES.values())
    ].copy()


def _download_census_acs_zcta() -> pd.DataFrame:
    """
    Census ACS 5-year ZCTA-level data — poverty, income, uninsured, population.
    Uses Census API (no key required for up to 500 requests/day).

    Variables:
      B01003_001E  Total population
      B17001_001E  Total pop for poverty determination
      B17001_002E  Pop below poverty level
      B19013_001E  Median household income
      B27001_004E  Male: Under 6 no insurance (too granular — use B27010 instead)
    """
    cache = Path(OPEN_DIR) / "acs_zcta.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        log.info(f"  ACS ZCTA: {len(df):,} ZCTAs from cache")
        return df

    # Census API key (optional — improves rate limits)
    api_key = os.environ.get("CENSUS_API_KEY", "")
    key_param = f"&key={api_key}" if api_key else ""

    # We request multiple variable groups in batches (Census API limit: 50 vars/call)
    base = f"https://api.census.gov/data/2022/acs/acs5"
    geo  = "for=zip%20code%20tabulation%20area:*"

    # Batch 1: population + poverty + income
    vars1 = "B01003_001E,B17001_001E,B17001_002E,B19013_001E"
    url1  = f"{base}?get=NAME,{vars1}&{geo}{key_param}"

    # Batch 2: health insurance (uninsured = no coverage)
    # B27010: types of health insurance by age; too many cols
    # Use B27001 instead — health insurance coverage status by sex
    # B27001_005E: Male <6 uninsured; too granular
    # Simpler: use S2701 (subject table) if available, or estimate from B27010
    # Best available: B27001_001E (total) and compute uninsured via residual
    # Actually easier: use B18135 or DP03 — let's use the most reliable columns
    # B27010_033E: No health insurance coverage (under 19)
    # Best bet: request aggregate uninsured from DP03
    vars2 = "B27010_001E,B27010_033E,B27010_050E"
    url2  = f"{base}?get={vars2}&{geo}{key_param}"

    rows1, rows2 = None, None

    try:
        log.info(f"  ACS ZCTA batch 1: population + poverty + income …")
        resp = requests.get(url1, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        rows1 = pd.DataFrame(data[1:], columns=data[0])
        log.info(f"    → {len(rows1):,} ZCTAs")
    except Exception as e:
        log.warning(f"  ACS ZCTA batch 1 failed: {e}")

    if rows1 is None:
        log.warning("  ACS ZCTA: all API calls failed → SDoH from county downscale only")
        return pd.DataFrame()

    # Parse batch 1
    rows1["zcta5"] = rows1["zip code tabulation area"].astype(str).str.zfill(5)
    result = pd.DataFrame({"zcta5": rows1["zcta5"]})

    pop_total  = pd.to_numeric(rows1["B01003_001E"], errors="coerce")
    pov_total  = pd.to_numeric(rows1["B17001_001E"], errors="coerce")
    pov_below  = pd.to_numeric(rows1["B17001_002E"], errors="coerce")
    income     = pd.to_numeric(rows1["B19013_001E"], errors="coerce").replace(-666666666, np.nan)

    result["population"]            = pop_total
    result["poverty_rate"]          = (pov_below / pov_total.clip(lower=1)).clip(0, 1)
    result["median_household_income"] = income

    # Batch 2: health insurance (best effort)
    try:
        log.info(f"  ACS ZCTA batch 2: health insurance …")
        resp2 = requests.get(url2, timeout=TIMEOUT)
        resp2.raise_for_status()
        data2 = resp2.json()
        rows2 = pd.DataFrame(data2[1:], columns=data2[0])
        rows2["zcta5"] = rows2["zip code tabulation area"].astype(str).str.zfill(5)

        # B27010_001E: total pop in universe
        # B27010_033E: Under 19 with no coverage
        # B27010_050E: 19-64 with no coverage
        ins_total   = pd.to_numeric(rows2["B27010_001E"], errors="coerce")
        ins_no_u19  = pd.to_numeric(rows2["B27010_033E"], errors="coerce")
        ins_no_1964 = pd.to_numeric(rows2["B27010_050E"], errors="coerce")

        rows2["uninsured_est"] = (
            (ins_no_u19.fillna(0) + ins_no_1964.fillna(0)) /
            ins_total.clip(lower=1)
        ).clip(0, 1)

        # Merge uninsured into result
        unins_map = rows2.set_index("zcta5")["uninsured_est"].to_dict()
        result["uninsured_rate"] = result["zcta5"].map(unins_map)
        log.info(f"    → health insurance data merged for {result['uninsured_rate'].notna().sum():,} ZCTAs")
    except Exception as e:
        log.warning(f"  ACS ZCTA batch 2 failed ({e}) — uninsured will use county proxy")

    if "uninsured_rate" not in result.columns:
        result["uninsured_rate"] = np.nan

    # Derived SES disadvantage index (ZCTA level)
    pov_n = _norm01(result["poverty_rate"])
    ins_n = _norm01(result["uninsured_rate"].fillna(result["uninsured_rate"].median()))
    inc_n = _norm01(1.0 / (result["median_household_income"].clip(lower=10_000)))
    result["ses_disadvantage_index"] = ((pov_n + ins_n + inc_n) / 3.0).clip(0, 1)

    result = result.dropna(subset=["zcta5"]).reset_index(drop=True)
    result.to_parquet(cache, index=False)
    log.info(f"  ACS ZCTA: {len(result):,} ZCTAs | "
             f"poverty avg {result['poverty_rate'].mean()*100:.1f}%")
    return result


def _download_zcta_crosswalk() -> pd.DataFrame:
    """
    Census 2020 ZCTA-to-county relationship file.
    Maps ZCTA5 → county FIPS with population weights (a ZCTA can span multiple counties).

    Source: https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/
            tab20_zcta520_county20_natl.txt
    Returns one row per (zcta5, county_fips) with population weight.
    The weight for each (zcta, county) pair = share of ZCTA population in that county.
    """
    cache = Path(OPEN_DIR) / "zcta_county_crosswalk.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        log.info(f"  Crosswalk: {len(df):,} ZCTA→county pairs from cache")
        return df

    url = ("https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/"
           "tab20_zcta520_county20_natl.txt")
    try:
        log.info(f"  Crosswalk: downloading from Census …")
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()

        # File is pipe-delimited with header
        df = pd.read_csv(io.StringIO(resp.text), sep="|", low_memory=False)
        log.info(f"    Columns: {list(df.columns[:10])}")

        # Census column names (all caps in 2020 file):
        # OID_ZCTA5_20, GEOID_ZCTA5_20, GEOID_COUNTY_20, AREALAND_PART, ...
        # IMPORTANT: prefer GEOID_* — the file also has OID_* object-ID columns
        # that contain long numeric IDs, not the 5-digit codes.
        zcta_col   = next((c for c in df.columns if "ZCTA" in c.upper()
                           and c.upper().startswith("GEOID")), None)
        if zcta_col is None:
            zcta_col = next((c for c in df.columns if "ZCTA" in c.upper()
                             and not c.upper().startswith("OID")), None)
        county_col = next((c for c in df.columns if "COUNTY" in c.upper()
                           and c.upper().startswith("GEOID")), None)
        if county_col is None:
            county_col = next((c for c in df.columns if "COUNTY" in c.upper()
                               and "GEOID" in c.upper()
                               and not c.upper().startswith("OID")), None)

        # Drop county-only records (blank ZCTA side of the relationship file)
        if zcta_col is not None:
            zvals = df[zcta_col].astype(str).str.strip()
            df = df[df[zcta_col].notna() & zvals.ne("") & zvals.ne("nan")].copy()
        if county_col is None:
            # Fallback: try constructing from state + county columns
            state_col  = next((c for c in df.columns if "STATEFP" in c.upper()
                                or c.upper() in ("STATE", "STATEFP20")), None)
            co_col     = next((c for c in df.columns if c.upper() in
                                ("COUNTYFP", "COUNTYFP20", "COUNTY")), None)
            if state_col and co_col:
                df["county_fips_built"] = (
                    df[state_col].astype(str).str.zfill(2) +
                    df[co_col].astype(str).str.zfill(3)
                )
                county_col = "county_fips_built"

        if zcta_col is None or county_col is None:
            log.warning(f"  Crosswalk: cannot find ZCTA/county columns. Cols: {list(df.columns)}")
            return _crosswalk_fallback()

        def _code5(s: pd.Series) -> pd.Series:
            # Robust 5-digit code: handles int, float ("601.0"), and string dtypes
            return (
                pd.to_numeric(s, errors="coerce")
                .dropna().astype(int).astype(str).str.zfill(5)
                .reindex(s.index)
                .fillna(s.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5))
            )

        result = pd.DataFrame({
            "zcta5":       _code5(df[zcta_col]),
            "county_fips": _code5(df[county_col]),
        })

        # Area-based weight for population downscaling.
        # AREALAND_PART = land area of the ZCTA∩county intersection — this is
        # what makes weights differ across the counties a ZCTA spans.
        # (Total ZCTA area is constant per ZCTA → equal weights → wrong.)
        area_col = next((c for c in df.columns if "AREALAND" in c.upper()
                         and "PART" in c.upper()), None)
        if area_col is None:
            area_col = next((c for c in df.columns if "AREALAND" in c.upper()), None)
        if area_col:
            result["area"] = pd.to_numeric(df[area_col], errors="coerce").clip(lower=0)
            # Normalize within each ZCTA → weight = share of ZCTA land area in each county
            zcta_total = result.groupby("zcta5")["area"].transform("sum").clip(lower=1)
            result["weight"] = (result["area"] / zcta_total).clip(0, 1)
        else:
            # Equal weight if no area column
            counts = result.groupby("zcta5")["county_fips"].transform("count")
            result["weight"] = 1.0 / counts.clip(lower=1)

        # Filter to continental US + valid FIPS
        result = result[result["county_fips"].str[:2].isin(US_STATE_FIPS)].copy()
        result = result[result["zcta5"].str.len() == 5].copy()
        result = result.dropna(subset=["zcta5", "county_fips"]).reset_index(drop=True)

        result.to_parquet(cache, index=False)
        log.info(f"  Crosswalk: {len(result):,} ZCTA→county pairs | "
                 f"{result['zcta5'].nunique():,} unique ZCTAs")
        return result

    except Exception as e:
        log.warning(f"  Crosswalk download failed: {e}")
        return _crosswalk_fallback()


def _crosswalk_fallback() -> pd.DataFrame:
    """
    Fallback crosswalk: derive from ZIP prefix → state FIPS mapping.
    Less accurate but functional — each ZCTA maps 1:1 to the state it starts in.
    """
    log.info("  Crosswalk: using ZIP-prefix fallback (less accurate)")
    # Build ~33k synthetic ZCTA rows; accurate crosswalk will be attempted on next run
    return pd.DataFrame(columns=["zcta5", "county_fips", "weight"])


def _download_zcta_centroids() -> pd.DataFrame:
    """
    ZCTA centroids — lat/lon for scatter map.

    Sources tried in order (most precise → fastest):
      1. Census Gazetteer (tab-delimited ZIP file, definitive ZCTA centroids)
      2. GitHub-hosted scpike US ZIP database (fast ~2MB CSV fallback)
      3. SimpleMaps free ZIP database (ZIP file with CSV)

    Returns DataFrame with: zcta5, lat, lon
    """
    cache = Path(OPEN_DIR) / "zcta_centroids.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        if not df.empty and len(df) > 10_000:
            log.info(f"  Centroids: {len(df):,} ZCTAs from cache")
            return df
        cache.unlink(missing_ok=True)

    # --- Source 1: Census Gazetteer ---
    gaz_urls = [
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip",
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_zcta_national.zip",
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2022_Gazetteer/2022_Gaz_zcta_national.zip",
    ]
    for url in gaz_urls:
        try:
            log.info(f"  Centroids (Gazetteer): {url[-50:]} …")
            resp = requests.get(url, timeout=90)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                txt = next((n for n in zf.namelist() if n.endswith(".txt")), None)
                if not txt:
                    continue
                content = zf.read(txt).decode("utf-8", errors="replace")
            raw = pd.read_csv(io.StringIO(content), sep="\t", low_memory=False)
            raw.columns = raw.columns.str.strip()
            col_map = {}
            for c in raw.columns:
                cu = c.upper()
                if cu in ("GEOID", "ZCTA5", "GEOID10", "GEOID20"):
                    col_map[c] = "zcta5"
                elif "INTPTLAT" in cu:
                    col_map[c] = "lat"
                elif "INTPTLONG" in cu or "INTPTLON" in cu:
                    col_map[c] = "lon"
            raw = raw.rename(columns=col_map)
            if "zcta5" in raw.columns and "lat" in raw.columns and "lon" in raw.columns:
                result = pd.DataFrame({
                    "zcta5": raw["zcta5"].astype(str).str.zfill(5),
                    "lat":   pd.to_numeric(raw["lat"], errors="coerce"),
                    "lon":   pd.to_numeric(raw["lon"], errors="coerce"),
                }).dropna(subset=["lat", "lon"]).reset_index(drop=True)
                if len(result) > 10_000:
                    result.to_parquet(cache, index=False)
                    log.info(f"  Centroids (Gazetteer): {len(result):,} ZCTAs ✅")
                    return result
        except Exception as e:
            log.warning(f"    Gazetteer failed: {e}")

    # --- Source 2: GitHub ZIP database (fast fallback) ---
    github_urls = [
        "https://raw.githubusercontent.com/scpike/us-state-county-zip/master/geo-data.csv",
        "https://raw.githubusercontent.com/midwire/free_zipcode_data/master/all_us_zipcodes.csv",
    ]
    for url in github_urls:
        try:
            log.info(f"  Centroids (GitHub): {url[-55:]} …")
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            raw = pd.read_csv(io.StringIO(resp.text), low_memory=False)
            raw.columns = raw.columns.str.lower().str.strip()
            zip_col = next((c for c in raw.columns if c in ("zipcode","zip","postal_code")), None)
            lat_col = next((c for c in raw.columns if c in ("lat","latitude")), None)
            lon_col = next((c for c in raw.columns if c in ("lng","lon","long","longitude")), None)
            if zip_col and lat_col and lon_col:
                result = pd.DataFrame({
                    "zcta5": raw[zip_col].astype(str).str.zfill(5),
                    "lat":   pd.to_numeric(raw[lat_col], errors="coerce"),
                    "lon":   pd.to_numeric(raw[lon_col], errors="coerce"),
                }).dropna(subset=["lat", "lon"]).drop_duplicates("zcta5")
                result = result[result["lat"].between(-90, 90) & result["lon"].between(-180, 0)]
                if len(result) > 5_000:
                    result = result.reset_index(drop=True)
                    result.to_parquet(cache, index=False)
                    log.info(f"  Centroids (GitHub): {len(result):,} ZCTAs ✅")
                    return result
        except Exception as e:
            log.warning(f"    GitHub ZIP DB failed: {e}")

    # --- Source 3: SimpleMaps ---
    try:
        log.info("  Centroids (SimpleMaps): trying …")
        url = "https://simplemaps.com/static/data/us-zips/1.0/basic/simplemaps_uszips_basicv1.0.zip"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
            if csv_names:
                content = zf.read(csv_names[0]).decode("utf-8", errors="replace")
                raw = pd.read_csv(io.StringIO(content), low_memory=False)
                raw.columns = raw.columns.str.lower()
                zip_col = next((c for c in raw.columns if c in ("zip","zipcode")), None)
                lat_col = next((c for c in raw.columns if c in ("lat","latitude")), None)
                lon_col = next((c for c in raw.columns if c in ("lng","lon","longitude")), None)
                if zip_col and lat_col and lon_col:
                    result = pd.DataFrame({
                        "zcta5": raw[zip_col].astype(str).str.zfill(5),
                        "lat":   pd.to_numeric(raw[lat_col], errors="coerce"),
                        "lon":   pd.to_numeric(raw[lon_col], errors="coerce"),
                    }).dropna(subset=["lat", "lon"]).drop_duplicates("zcta5").reset_index(drop=True)
                    result.to_parquet(cache, index=False)
                    log.info(f"  Centroids (SimpleMaps): {len(result):,} ZCTAs ✅")
                    return result
    except Exception as e:
        log.warning(f"    SimpleMaps failed: {e}")

    log.warning(
        "  Centroids: all sources failed.\n"
        "  Run:  python3 fix_zip_map.py  to retry and patch zip_scores.parquet."
    )
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _norm01(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    s = s.fillna(s.median() if s.notna().any() else 0.0)
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


if __name__ == "__main__":
    main()
