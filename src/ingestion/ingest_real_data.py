from __future__ import annotations
"""
Real Data Ingestion v2 — Silent Patient Pool Finder
====================================================
Builds a COMPLETE 3,144-county panel from real public data.

ROOT CAUSE FIXED:
  v1 anchored on data/synthetic/counties.parquet (259 rows) → all left-joins
  capped at 259.  v2 uses Census TIGER as the spine (3,144 US counties).

Data sources:
  1. Census TIGER national_county.txt  → county FIPS spine (3,144 counties)
  2. CDC PLACES 2024                   → disease burden (T2D, obesity, HTN, …)
  3. CDC PLACES 2022 (prior release)   → prevalence trend signal (trajectory)
  4. Census ACS 5-year (2022)          → SDoH (poverty, income, uninsured, …)
  5. CMS Geographic Variation PUF     → Medicare T2D + HTN diagnosed rates + MA penetration
  6. County Health Rankings 2024      → access to care + SDoH backup
  7. USDA Food Environment Atlas       → food desert % (social determinants)

Run:
  python3 src/ingestion/ingest_real_data.py

Output:
  data/scored/dimension_scores.parquet  (3,143 counties scored across 7 dimensions)

Security:
  Database credentials live in .streamlit/secrets.toml (gitignored).
  This script does NOT touch the database.
"""

# ── Path bootstrap ────────────────────────────────────────────────────────────
# Allows `python3 src/ingestion/<script>.py` from any directory: put the repo
# root first on sys.path (for `src.` imports) and pin the working directory so
# relative data/ paths resolve.
import sys as _sys
from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))
if __name__ == "__main__":
    import os as _os
    _os.chdir(_REPO_ROOT)

from src.ingestion.download import fetch

import io
import logging
import sys
import time
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

OPEN_DIR    = "data/open"
SCORED_DIR  = "data/scored"
TIMEOUT     = 60   # seconds per download attempt (CMS was timing out at 180s)
TIMEOUT_CMS = 30   # CMS endpoints are especially slow; fail fast and use synthetic

# US states + DC FIPS codes (exclude territories: 60 AS, 66 GU, 69 MP, 72 PR, 78 VI)
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
    log.info("  SPPF Real Data Ingestion v2 — Full 3,144-County Panel")
    log.info("=" * 62)

    Path(OPEN_DIR).mkdir(parents=True, exist_ok=True)
    Path(SCORED_DIR).mkdir(parents=True, exist_ok=True)

    # 1. County spine ──────────────────────────────────────────────────────────
    log.info("\n[1/8] Census TIGER county list …")
    counties = _download_census_counties()
    log.info(f"      Spine: {len(counties):,} counties")

    # 2. CDC PLACES — disease burden (current year) ───────────────────────────
    log.info("\n[2/8] CDC PLACES 2024 (disease burden — current) …")
    cdc = _download_cdc_places()

    # 3. CDC PLACES — prior year (for trajectory trend) ───────────────────────
    log.info("\n[3/8] CDC PLACES prior release (trajectory trend signal) …")
    cdc_prior = _download_cdc_places_prior()

    # 4. Census ACS — SDoH ────────────────────────────────────────────────────
    log.info("\n[4/8] Census ACS 5-year estimates (social determinants) …")
    acs = _download_census_acs()

    # 5. CMS GV PUF — diagnosis gap + MA penetration ─────────────────────────
    log.info("\n[5/8] CMS Geographic Variation PUF (Medicare rates) …")
    cms = _download_cms_gv_puf()

    # 6. County Health Rankings — access + SDoH backup ────────────────────────
    log.info("\n[6/8] County Health Rankings 2024 (access / SDoH backup) …")
    chr_df = _download_county_health_rankings()

    # 7. USDA Food Environment Atlas — food desert signal ─────────────────────
    log.info("\n[7/8] USDA Food Environment Atlas (food access / SDoH) …")
    usda = _download_usda_food_atlas()

    # 8. Build panel + score ──────────────────────────────────────────────────
    log.info("\n[8/8] Building merged panel and scoring 7 dimensions …")
    panel = _build_panel(counties, cdc, acs, cms, chr_df, usda, cdc_prior)

    from src.features.dimension_scorer import compute_all_dimensions
    # No synthetic signals — use real-data proxies for all dimensions
    dim_scores = compute_all_dimensions(panel, orig_signals=None)

    # QA gate — block the write if output is corrupt or silently degraded
    from src.quality.qa_gate import run_gate, COUNTY_CHECKS
    run_gate(dim_scores, COUNTY_CHECKS, name="county dimension scores").raise_on_failure()

    out_path = Path(SCORED_DIR) / "dimension_scores.parquet"
    dim_scores.to_parquet(out_path, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    n_total    = len(dim_scores)
    priority   = int((dim_scores["opportunity_score"] >= 55).sum())
    emerging   = int(((dim_scores["opportunity_score"] >= 40) &
                      (dim_scores["opportunity_score"] < 55)).sum())
    developing = int((dim_scores["opportunity_score"] < 40).sum())

    log.info("\n" + "=" * 62)
    log.info("  INGESTION COMPLETE")
    log.info(f"  Elapsed:           {time.time() - t0:.0f}s")
    log.info(f"  Counties scored:   {n_total:,}")
    log.info(f"  Priority (≥55):    {priority:,}  ← top counties confirmed by 2+ real sources")
    log.info(f"  Emerging (40–55):  {emerging:,}")
    log.info(f"  Developing (<40):  {developing:,}")
    log.info(f"  Output:            {out_path}")
    log.info("  NOTE: Priority threshold = 55 (7 real sources; max observable score ~60-65)")
    log.info("=" * 62)

    top10 = dim_scores.nlargest(10, "opportunity_score")[
        ["county_name", "state_name", "opportunity_score",
         "dim_disease_burden", "dim_diagnosis_gap", "recommended_intervention"]
    ]
    log.info(f"\nTop 10 Opportunity Counties:\n{top10.to_string(index=False)}")

    _log_provenance(cdc, cdc_prior, acs, cms, chr_df, usda)
    log.info("\nDashboard ready → python3 -m streamlit run src/output/dashboard.py")


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOADERS
# ─────────────────────────────────────────────────────────────────────────────

def _download_census_counties() -> pd.DataFrame:
    """
    Get the complete 3,143-county US list.

    Sources tried in order:
      1. Cached parquet (skip if empty — previous run may have saved 0 rows)
      2. Census TIGER national_county.txt (live download)
      3. Local cdc_places_raw.csv (LocationID + LocationName already on disk)
      4. Census ACS API (county NAME field as fallback)
    """
    cache = Path(OPEN_DIR) / "census_counties.parquet"

    # ── 1. Cache (only use if non-empty) ──────────────────────────────────────
    if cache.exists():
        df = pd.read_parquet(cache)
        if not df.empty:
            log.info(f"  Census counties: {len(df):,} from cache")
            return df
        else:
            log.warning("  Census counties: cache was empty, deleting and re-downloading")
            cache.unlink()

    # ── 2. Census TIGER live download ──────────────────────────────────────────
    url = "https://www2.census.gov/geo/docs/reference/codes/files/national_county.txt"
    try:
        resp = fetch(url, timeout=30)
        resp.raise_for_status()
        rows = []
        for line in resp.text.strip().splitlines()[1:]:   # skip header
            parts = line.strip().split("|")
            if len(parts) < 4:
                continue
            state_abbr  = parts[0].strip()
            state_fips  = parts[1].strip().zfill(2)
            county_part = parts[2].strip().zfill(3)
            county_name = parts[3].strip()
            if state_fips not in US_STATE_FIPS:
                continue
            rows.append({
                "county_fips": state_fips + county_part,
                "county_name": county_name,
                "state_abbr":  state_abbr,
                "state_name":  _STATE_NAMES.get(state_abbr, state_abbr),
            })
        if rows:
            df = pd.DataFrame(rows)
            df.to_parquet(cache, index=False)
            log.info(f"  Census counties: {len(df):,} downloaded from TIGER")
            return df
    except Exception as e:
        log.warning(f"  Census TIGER download failed ({e})")

    # ── 3. Build spine from local CDC PLACES CSV (fast — already on disk) ─────
    cdc_raw = Path(OPEN_DIR) / "cdc_places_raw.csv"
    if cdc_raw.exists():
        log.info("  Census counties: building spine from local cdc_places_raw.csv")
        df = _counties_from_cdc_places_csv(cdc_raw)
        if not df.empty:
            df.to_parquet(cache, index=False)
            log.info(f"  Census counties: {len(df):,} extracted from CDC PLACES CSV")
            return df

    # ── 4. ACS API fallback ────────────────────────────────────────────────────
    log.warning("  Census TIGER: all sources failed, trying ACS API …")
    return _census_counties_acs_fallback()


def _counties_from_cdc_places_csv(raw_path: Path) -> pd.DataFrame:
    """
    Extract unique county FIPS + names from the local CDC PLACES CSV.
    Works on both old and new CDC PLACES formats (LocationID is always present).
    """
    try:
        raw = pd.read_csv(raw_path, low_memory=False,
                          usecols=lambda c: c in [
                              "LocationID", "LocationName", "StateAbbr", "StateDesc",
                              "locationid", "locationname", "stateabbr", "statedesc",
                          ])
        # Normalise column names
        raw.columns = raw.columns.str.strip()
        col_lower = {c.lower(): c for c in raw.columns}
        def _col(name):
            return col_lower.get(name.lower(), name)

        fips_col  = _col("LocationID")
        name_col  = _col("LocationName")
        abbr_col  = _col("StateAbbr")
        sname_col = _col("StateDesc")

        if fips_col not in raw.columns:
            log.warning("  CDC PLACES CSV has no LocationID column")
            return pd.DataFrame()

        # IMPORTANT: pandas may read "01001" as integer 1001 (drops leading zero).
        # Always zero-pad to 5 chars first, then filter by valid state FIPS prefix.
        # State-level rows (e.g. "01" → "00001") get state-part "00" — invalid → excluded.
        raw["county_fips"] = raw[fips_col].astype(str).str.strip().str.zfill(5)

        # County rows: valid US state FIPS prefix (also excludes territories + state totals)
        county_mask = raw["county_fips"].str[:2].isin(US_STATE_FIPS)
        counties = raw[county_mask].copy()

        result = counties[["county_fips"]].copy()
        if name_col in counties.columns:
            result["county_name"] = counties[name_col].values
        else:
            result["county_name"] = "County " + result["county_fips"]

        if abbr_col in counties.columns:
            result["state_abbr"] = counties[abbr_col].values
        else:
            result["state_abbr"] = result["county_fips"].str[:2].map(
                {v: k for k, v in {  # fips → abbr from _STATE_NAMES
                    "01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO",
                    "09":"CT","10":"DE","11":"DC","12":"FL","13":"GA","15":"HI",
                    "16":"ID","17":"IL","18":"IN","19":"IA","20":"KS","21":"KY",
                    "22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN",
                    "28":"MS","29":"MO","30":"MT","31":"NE","32":"NV","33":"NH",
                    "34":"NJ","35":"NM","36":"NY","37":"NC","38":"ND","39":"OH",
                    "40":"OK","41":"OR","42":"PA","44":"RI","45":"SC","46":"SD",
                    "47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA",
                    "54":"WV","55":"WI","56":"WY",
                }.items()}.get
            )

        if sname_col in counties.columns:
            result["state_name"] = counties[sname_col].values
        else:
            result["state_name"] = result["state_abbr"].map(_STATE_NAMES)

        result = result.drop_duplicates("county_fips").reset_index(drop=True)
        return result

    except Exception as e:
        log.warning(f"  CDC PLACES CSV county extraction failed: {e}")
        return pd.DataFrame()


def _census_counties_acs_fallback() -> pd.DataFrame:
    """
    Build county spine from ACS NAME field (format: 'CountyName, StateName').
    Used only if Census TIGER download fails.
    """
    try:
        url = ("https://api.census.gov/data/2022/acs/acs5"
               "?get=NAME,B01003_001E&for=county:*&in=state:*")
        resp = fetch(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        df_raw = pd.DataFrame(data[1:], columns=data[0])
        df_raw["county_fips"] = (df_raw["state"].str.zfill(2)
                                  + df_raw["county"].str.zfill(3))
        # NAME format: "Autauga County, Alabama"
        df_raw[["county_name", "state_name"]] = (
            df_raw["NAME"].str.split(", ", n=1, expand=True)
        )
        # Map state_name → state_abbr
        inv_map = {v: k for k, v in _STATE_NAMES.items()}
        df_raw["state_abbr"] = df_raw["state_name"].map(inv_map).fillna("??")
        df_raw = df_raw[df_raw["state"].isin(US_STATE_FIPS)].copy()
        df = df_raw[["county_fips", "county_name", "state_name", "state_abbr"]]
        cache = Path(OPEN_DIR) / "census_counties.parquet"
        df.to_parquet(cache, index=False)
        log.info(f"  ACS fallback county list: {len(df):,} counties")
        return df
    except Exception as e2:
        log.error(f"  ACS county fallback also failed ({e2}). "
                  "Cannot build a complete county spine. "
                  "Check your internet connection and retry.")
        sys.exit(1)


def _download_cdc_places() -> pd.DataFrame:
    """CDC PLACES — disease burden for all US counties."""
    try:
        from src.ingestion.open_data.cdc_places import download as cdc_dl
        df = cdc_dl(cache_dir=OPEN_DIR, force=False)
        if df.empty:
            raise ValueError("empty")
        log.info(f"  CDC PLACES: {len(df):,} counties | "
                 f"diabetes avg {df['diabetes_prevalence_pct'].mean()*100:.1f}%")
        return df
    except Exception as e:
        log.warning(f"  CDC PLACES failed ({e}) — disease burden → synthetic fallback")
        return pd.DataFrame()


def _download_census_acs() -> pd.DataFrame:
    """
    Census ACS 5-year estimates — SDoH for all US counties.
    Falls back to Census SAIPE (poverty + income only) if ACS API fails.
    """
    try:
        from src.ingestion.open_data.census_acs import download as acs_dl
        df = acs_dl(cache_dir=OPEN_DIR, force=False)
        if df.empty:
            raise ValueError("empty")
        log.info(f"  Census ACS: {len(df):,} counties | "
                 f"poverty avg {df['poverty_rate'].mean()*100:.1f}%")
        return df
    except Exception as e:
        log.warning(f"  Census ACS failed ({e})")

    # Fallback: SAIPE provides poverty rate + median income via direct XLS download
    # (www2.census.gov is a different server — avoids Census API SSL issues)
    log.info("  Census ACS: trying SAIPE fallback (poverty + income only) …")
    saipe = _download_saipe()
    if not saipe.empty:
        return saipe

    log.warning("  Census ACS + SAIPE: all failed → SDoH using synthetic defaults")
    return pd.DataFrame()


def _download_saipe() -> pd.DataFrame:
    """
    Census SAIPE — poverty rate + median income for all US counties.
    Downloads est{year}all.xls from www2.census.gov using xlrd engine.

    SAIPE uses old .xls format (BIFF8), which requires xlrd < 2.0.
    Install once: pip3 install "xlrd<2" --user

    Column layout in est{year}all.xls (0-indexed after skiprows=4):
      0: State FIPS   1: County FIPS   7: Poverty % All Ages   22: Median Income
    """
    cache = Path(OPEN_DIR) / "saipe_county.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        if not df.empty:
            log.info(f"  SAIPE: {len(df):,} counties from cache")
            return df

    for year in [2022, 2021]:
        year2 = str(year)[-2:]
        url = (f"https://www2.census.gov/programs-surveys/saipe/datasets/{year}/"
               f"{year}-state-and-county/est{year2}all.xls")
        try:
            log.info(f"  SAIPE {year}: {url}")
            resp = fetch(url, timeout=60)
            resp.raise_for_status()
            if len(resp.content) < 100_000:
                log.warning(f"  SAIPE: response too small ({len(resp.content):,} bytes)")
                continue

            # Detect actual file format from magic bytes
            magic = resp.content[:4]
            is_xlsx = magic[:2] == b'PK'   # ZIP / OOXML → .xlsx in disguise
            is_xls  = magic == b'\xd0\xcf\x11\xe0'  # OLE2 compound doc → real .xls
            log.info(f"  SAIPE file magic: {magic.hex()} → "
                     f"{'xlsx-in-disguise' if is_xlsx else 'xls' if is_xls else 'unknown'}")

            xls = None
            for engine, label in (
                [("openpyxl", "openpyxl"),   # works if file is actually xlsx
                 ("xlrd",    "xlrd<2")]       # works for genuine BIFF8 .xls
            ):
                try:
                    xls = pd.read_excel(io.BytesIO(resp.content), engine=engine,
                                        header=None, skiprows=4)
                    log.info(f"  SAIPE: read with engine={engine}")
                    break
                except Exception as exc:
                    log.warning(f"  SAIPE engine={engine} failed: "
                                f"{type(exc).__name__}: {exc}")

            if xls is None:
                log.warning(
                    "  SAIPE: all Excel engines failed. Options:\n"
                    "  ▶  pip3 install \"xlrd<2\" --user\n"
                    "  ▶  Or get a free Census API key (best): "
                    "https://api.census.gov/data/key_signup.html"
                )
                return pd.DataFrame()

            n_cols = xls.shape[1]
            log.info(f"  SAIPE: {xls.shape[0]} rows × {n_cols} cols")

            result = pd.DataFrame()
            result["county_fips"] = (
                xls.iloc[:, 0].astype(str).str.strip().str.zfill(2) +
                xls.iloc[:, 1].astype(str).str.strip().str.zfill(3)
            )

            # Poverty % All Ages — column 7; validate expected range (3–40%)
            if n_cols > 7:
                pov = pd.to_numeric(xls.iloc[:, 7], errors="coerce")
                if 3 <= pov.median(skipna=True) <= 40:
                    result["poverty_rate"] = (pov / 100.0).clip(0, 1)

            # Median household income — typically column 22; scan nearby if not there
            for col_idx in [22, 21, 20, 19, 18, 17, 16]:
                if col_idx >= n_cols:
                    continue
                candidate = pd.to_numeric(xls.iloc[:, col_idx], errors="coerce")
                if candidate.median(skipna=True) > 30_000:
                    result["median_household_income"] = candidate.values
                    break

            # Filter to county rows; exclude state totals (last 3 FIPS chars = "000")
            result = result[result["county_fips"].str[-3:] != "000"]
            result = result[result["county_fips"].str[:2].isin(US_STATE_FIPS)]
            result = result.dropna(subset=["county_fips"])

            if "poverty_rate" in result.columns and len(result) > 2_000:
                if "median_household_income" not in result.columns:
                    result["median_household_income"] = np.nan
                result = result.reset_index(drop=True)
                result.to_parquet(cache, index=False)
                avg_pov = result["poverty_rate"].mean() * 100
                avg_inc = result["median_household_income"].mean()
                log.info(f"  SAIPE {year}: {len(result):,} counties | "
                         f"poverty avg {avg_pov:.1f}% | income avg ${avg_inc:,.0f}")
                return result
            else:
                log.warning(f"  SAIPE {year}: only {len(result)} valid rows, trying next year")

        except Exception as e:
            log.warning(f"  SAIPE {year}: {e}")

    return pd.DataFrame()


def _download_cms_gv_puf() -> pd.DataFrame:
    """
    CMS Geographic Variation PUF — county-level Medicare statistics.
    Provides: cms_t2d_diagnosed_rate, ma_penetration_rate, cms_htn_diagnosed_rate.
    """
    cache = Path(OPEN_DIR) / "cms_gv_puf_county.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        log.info(f"  CMS GV PUF: {len(df):,} counties from cache")
        return df

    # Multiple API endpoint candidates (CMS changes these occasionally).
    # Note: the /api/1/datastore/query/ endpoints return JSON-wrapped CSV which
    # pandas can't read directly — use the data-api v1 endpoint instead.
    urls = [
        # CMS data API v1 — county level GV PUF, filtered to key columns
        "https://data.cms.gov/data-api/v1/dataset/9767cb68-8ea9-4abb-bb58-c966df773bc6/data.csv?size=50000",
        # Alternative: 2022 PUF dataset (different UUID)
        "https://data.cms.gov/data-api/v1/dataset/77e2b3b7-56c1-43a5-917c-d7e0e7f1427c/data.csv?size=50000",
    ]

    for url in urls:
        try:
            log.info(f"  CMS GV PUF: trying {url[:75]} …")
            resp = fetch(url, timeout=TIMEOUT_CMS)
            resp.raise_for_status()
            if len(resp.content) < 1000:
                log.warning("    Response too small, skipping")
                continue
            raw = pd.read_csv(io.StringIO(resp.text), low_memory=False)
            result = _parse_cms_gv_puf(raw)
            if not result.empty and len(result) > 100:
                result.to_parquet(cache, index=False)
                log.info(f"  CMS GV PUF: {len(result):,} counties | "
                         f"T2D {result['cms_t2d_diagnosed_rate'].mean()*100:.1f}% avg | "
                         f"MA {result['ma_penetration_rate'].mean()*100:.1f}% avg")
                return result
            log.warning(f"    Parsed only {len(result)} rows, trying next URL …")
        except Exception as e:
            log.warning(f"    Failed: {e}")

    # Attempt direct CMS download for MA penetration (separate report)
    log.info("  CMS GV PUF: falling back to CMS MA penetration report …")
    ma_df = _download_cms_ma_penetration_report()
    if not ma_df.empty:
        ma_df.to_parquet(cache, index=False)
        log.info(f"  CMS MA penetration: {len(ma_df):,} counties")
        return ma_df

    log.warning("  CMS GV PUF: all attempts failed — payer landscape → synthetic fallback")
    return pd.DataFrame()


def _parse_cms_gv_puf(df: pd.DataFrame) -> pd.DataFrame:
    """Parse CMS Geographic Variation PUF CSV into standardised county-level rows."""
    df.columns = df.columns.str.lower().str.strip()

    # Filter to county-level rows
    for geo_col in ["bene_geo_lvl", "geo_lvl", "level"]:
        if geo_col in df.columns:
            df = df[df[geo_col].str.lower().str.strip().isin(
                ["county", "county level"]
            )].copy()
            break

    result = pd.DataFrame()
    # FIPS column
    for fips_col in ["bene_geo_cd", "county_fips", "fips_cd", "geo_cd"]:
        if fips_col in df.columns:
            result["county_fips"] = df[fips_col].astype(str).str.strip().str.zfill(5)
            break

    if "county_fips" not in result.columns or len(result) == 0:
        return pd.DataFrame()

    result = result.reset_index(drop=True)

    def _extract(df_reset, candidates):
        for c in candidates:
            if c in df_reset.columns:
                vals = _to_num(df_reset[c])   # handles '1,234', '12.3%', '*'
                if vals.median() > 1:
                    vals = vals / 100.0
                return vals.clip(0, 1)
        return pd.Series(np.nan, index=df_reset.index)

    df_r = df.reset_index(drop=True)
    result["cms_t2d_diagnosed_rate"]  = _extract(df_r, ["diab_pct","pct_diab","diabetes_pct"])
    result["cms_htn_diagnosed_rate"]  = _extract(df_r, ["hypert_pct","pct_hypert","hypertension_pct"])
    result["ma_penetration_rate"]     = _extract(df_r, ["ma_prtcptn_rate","ma_pct","pct_ma","ma_penetration"])

    for src in ["tot_benes","bene_cnt","tot_mdcr_benes"]:
        if src in df_r.columns:
            result["total_medicare_beneficiaries"] = _to_num(df_r[src])
            break

    result = result[result["county_fips"].str.match(r"^\d{5}$", na=False)]
    result = result[result["county_fips"].str[:2].isin(US_STATE_FIPS)]
    return result.reset_index(drop=True)


def _download_cms_ma_penetration_report() -> pd.DataFrame:
    """
    Download CMS monthly County Market Penetration report (ZIP → CSV).
    Provides ma_penetration_rate; used as fallback when GV PUF fails.
    """
    zip_urls = [
        # CMS county-level MA penetration — new URL format (old year-prefixed paths 404 since 2024)
        "https://www.cms.gov/files/zip/ma-state/county-penetration-december-2024.zip",
        "https://www.cms.gov/files/zip/ma-state/county-penetration-november-2024.zip",
        "https://www.cms.gov/files/zip/ma-state/county-penetration-january-2025.zip",
        "https://www.cms.gov/files/zip/ma-state/county-penetration-october-2024.zip",
    ]
    for url in zip_urls:
        try:
            log.info(f"  CMS MA ZIP: {url}")
            resp = fetch(url, timeout=TIMEOUT)
            resp.raise_for_status()
            import zipfile
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    continue
                # Pick the most relevant file (county-level)
                target = next((n for n in csv_names if "county" in n.lower()), csv_names[0])
                raw = pd.read_csv(zf.open(target), low_memory=False)

            raw.columns = raw.columns.str.lower().str.strip().str.replace(" ", "_")
            result = pd.DataFrame()
            for fips_col in ["fips_code", "county_fips", "ssa_code", "fips"]:
                if fips_col in raw.columns:
                    # Strip float artifacts ('1001.0') before zfill — otherwise
                    # the code gets the WRONG state prefix and passes the filter
                    result["county_fips"] = (
                        raw[fips_col].astype(str).str.strip()
                        .str.replace(r"\.0$", "", regex=True).str.zfill(5)
                    )
                    break
            if "county_fips" not in result.columns:
                continue

            for ma_col in ["penetration_rate", "ma_penetration_rate", "ma_pct",
                           "pct_ma", "total_ma_plan_enrollment"]:
                if ma_col in raw.columns:
                    # _to_num handles '12.34%', '1,234', '*' suppression —
                    # naive to_numeric here once dropped coverage to 236 counties
                    vals = _to_num(raw[ma_col])
                    if vals.median() > 1:
                        vals = vals / 100.0
                    result["ma_penetration_rate"] = vals.clip(0, 1)
                    break

            if "ma_penetration_rate" not in result.columns:
                # CMS MA files often have separate enrollment + eligibles columns
                enroll_col = next((c for c in raw.columns if "enroll" in c), None)
                elig_col   = next((c for c in raw.columns if "elig" in c), None)
                if enroll_col and elig_col:
                    result["ma_penetration_rate"] = (
                        _to_num(raw[enroll_col]) /
                        _to_num(raw[elig_col]).clip(lower=1)
                    ).clip(0, 1)

            result = result.dropna(subset=["county_fips"])
            result = result[result["county_fips"].str[:2].isin(US_STATE_FIPS)]
            if not result.empty:
                return result.reset_index(drop=True)
        except Exception as e:
            log.warning(f"  CMS MA ZIP failed: {e}")
    return pd.DataFrame()


def _download_county_health_rankings() -> pd.DataFrame:
    """
    County Health Rankings & Roadmaps (Robert Wood Johnson Foundation).
    Covers all 3,143 US counties. Provides: access to care proxies, SDoH backup signals.

    NOTE: CHR blocks automated downloads via WAF/TLS fingerprinting.
    Manual download instructions (one-time setup):
      1. Open in your browser:
         https://www.countyhealthrankings.org/health-data/county-health-rankings-reports
      2. Click "Download" next to the most recent year → "CSV Data"
         (or direct link: https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data2025_v3.csv)
      3. Save the file to:  data/open/analytic_data_chr.csv
      The pipeline will pick it up automatically on next run.
    """
    cache = Path(OPEN_DIR) / "county_health_rankings.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        log.info(f"  CHR: {len(df):,} counties from cache")
        return df

    # Check for manually downloaded CSV first
    manual_paths = [
        Path(OPEN_DIR) / "analytic_data_chr.csv",
        Path(OPEN_DIR) / "analytic_data2025_v3.csv",
        Path(OPEN_DIR) / "analytic_data2024.csv",
        Path(OPEN_DIR) / "analytic_data2023.csv",
    ]
    for local in manual_paths:
        if local.exists():
            log.info(f"  CHR: loading manually downloaded file: {local.name}")
            try:
                raw = pd.read_csv(local, low_memory=False, skiprows=1)
                result = _parse_chr(raw)
                if not result.empty and len(result) > 1000:
                    result.to_parquet(cache, index=False)
                    log.info(f"  CHR: {len(result):,} counties loaded + cached")
                    return result
            except Exception as e:
                log.warning(f"  CHR: local file parse failed: {e}")

    # Automated download — often blocked by CHR's WAF; kept as best-effort
    _session = requests.Session()
    from src.ingestion.download import _ca_bundle
    _session.verify = _ca_bundle()
    _session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/csv,application/octet-stream,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Referer": "https://www.countyhealthrankings.org/health-data/county-health-rankings-reports",
    })

    urls = [
        "https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data2025_v3.csv",
        "https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data2024.csv",
        "https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data2023.csv",
    ]

    for url in urls:
        try:
            log.info(f"  CHR: trying {url}")
            resp = _session.get(url, timeout=TIMEOUT)
            if resp.status_code == 403:
                # WAF block — skip remaining URLs, they will all 403
                log.warning(
                    "  CHR: WAF blocked automated download (403). "
                    "Download manually → save to data/open/analytic_data_chr.csv"
                )
                break
            resp.raise_for_status()
            if len(resp.content) < 100_000:
                continue
            raw = pd.read_csv(io.StringIO(resp.text), low_memory=False, skiprows=1)
            result = _parse_chr(raw)
            if not result.empty and len(result) > 1000:
                result.to_parquet(cache, index=False)
                log.info(f"  CHR: {len(result):,} counties")
                return result
        except Exception as e:
            log.warning(f"  CHR URL failed: {e}")

    log.warning(
        "  County Health Rankings unavailable — "
        "save CSV to data/open/analytic_data_chr.csv and re-run to activate."
    )
    return pd.DataFrame()


def _parse_chr(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse County Health Rankings CSV.
    The analytic CSV has two header rows; caller should skiprows=1 to get variable IDs as headers.
    """
    # Find FIPS column
    fips_col = next(
        (c for c in df.columns if c.lower().strip() in ("fipscode", "fips", "5-digit fips code")),
        None
    )
    if fips_col is None:
        log.warning("  CHR: no FIPS column found. Columns: " + str(list(df.columns[:10])))
        return pd.DataFrame()

    result = pd.DataFrame()
    result["county_fips"] = df[fips_col].astype(str).str.strip().str.zfill(5)

    # CHR 2024 variable → our column name
    _CHR_VARS = {
        # Health outcomes
        "v002_rawvalue": "chr_poor_health_pct",       # fair/poor health %
        "v036_rawvalue": "chr_premature_death",
        # Health behaviors
        "v009_rawvalue": "chr_smoking_pct",
        "v011_rawvalue": "chr_obesity_pct",            # % obese
        "v070_rawvalue": "chr_physical_inactivity_pct",
        # Clinical care / access
        "v023_rawvalue": "chr_uninsured_pct",          # % uninsured
        "v021_rawvalue": "chr_primary_care_ratio",     # ratio persons:PCP
        "v062_rawvalue": "chr_mental_health_ratio",    # ratio persons:MH provider
        "v060_rawvalue": "chr_diabetes_pct",           # diagnosed diabetes %
        # SDoH
        "v051_rawvalue": "chr_poverty_pct",            # % in poverty
        "v063_rawvalue": "chr_median_income",          # median household income
        "v069_rawvalue": "chr_hs_grad_pct",            # HS graduation rate %
        "v085_rawvalue": "chr_broadband_pct",          # % with broadband
        "v052_rawvalue": "chr_unemployment_pct",
        "v133_rawvalue": "chr_social_associations",    # social associations per 10k
        "v082_rawvalue": "chr_children_poverty_pct",
        "v143_rawvalue": "chr_housing_problems_pct",
        "v124_rawvalue": "chr_food_insecurity_pct",
    }

    for src_col, dst_col in _CHR_VARS.items():
        if src_col in df.columns:
            result[dst_col] = pd.to_numeric(df[src_col], errors="coerce")

    # Remove state-total rows (county FIPS part = "000")
    result = result[result["county_fips"].str[-3:] != "000"]
    result = result[result["county_fips"].str[:2].isin(US_STATE_FIPS)]
    return result.reset_index(drop=True)


def _download_cdc_places_prior() -> pd.DataFrame:
    """
    CDC PLACES prior-year release — used to compute disease prevalence trend.
    Downloads an earlier PLACES release (~2 years prior) and returns the
    same key measures with `_prior` suffix for trend calculation.

    Trajectory signal = current_release - prior_release (positive = growing burden).
    Current: PLACES 2024 (2022 data).  Prior: PLACES 2022 (2020 data).
    """
    cache = Path(OPEN_DIR) / "cdc_places_prior.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        log.info(f"  CDC PLACES (prior): {len(df):,} counties from cache")
        return df

    # IMPORTANT: dataset i46a-9kgh is the *rolling latest* release (CDC
    # repoints it each year) — using it as "prior" once made prior == current
    # and silently zeroed the entire trajectory trend. Pin ARCHIVED releases:
    #   xyst-f73f — PLACES 2022 release (2020 BRFSS), GIS wide format
    #   mssc-ksj7 — PLACES 2020 release (2018 BRFSS), GIS wide format
    urls = [
        "https://data.cdc.gov/api/views/xyst-f73f/rows.csv?accessType=DOWNLOAD",  # 2022 release
        "https://data.cdc.gov/api/views/mssc-ksj7/rows.csv?accessType=DOWNLOAD",  # 2020 release
    ]

    for url in urls:
        try:
            log.info(f"  CDC PLACES (prior): trying {url[:70]} …")
            resp = fetch(url, timeout=TIMEOUT, stream=True)
            resp.raise_for_status()
            raw_path = Path(OPEN_DIR) / "_cdc_places_prior_raw.csv"
            with open(raw_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            size_mb = raw_path.stat().st_size / 1e6
            log.info(f"    Downloaded {size_mb:.1f} MB")

            from src.ingestion.open_data.cdc_places import _parse
            df_raw = _parse(raw_path)
            raw_path.unlink(missing_ok=True)  # clean up temp file

            if df_raw.empty or len(df_raw) < 500:
                log.warning("    Parsed too few rows, trying next URL …")
                continue

            # Rename to `_prior` suffix for trend calculation
            rename = {
                "diabetes_prevalence_pct":      "diabetes_prev_prior",
                "hypertension_prevalence_pct":  "htn_prev_prior",
                "obesity_rate_pct":             "obesity_prev_prior",
            }
            result = df_raw[["county_fips"]].copy()
            for src, dst in rename.items():
                if src in df_raw.columns:
                    result[dst] = df_raw[src]

            result = result.dropna(subset=list(rename.values()), how="all")

            # Sanity check: a "prior" release identical to the current one is
            # the rolling-latest-ID trap — reject it and try the next URL.
            cur_cache = Path(OPEN_DIR) / "cdc_places_county.parquet"
            if cur_cache.exists() and "diabetes_prev_prior" in result.columns:
                cur = pd.read_parquet(cur_cache)
                m = result.merge(
                    cur[["county_fips", "diabetes_prevalence_pct"]],
                    on="county_fips", how="inner")
                if len(m) and (m["diabetes_prev_prior"]
                               == m["diabetes_prevalence_pct"]).mean() > 0.95:
                    log.warning("    Prior release is identical to current "
                                "(rolling dataset ID) — rejecting, trying next URL …")
                    continue

            result.to_parquet(cache, index=False)
            log.info(
                f"  CDC PLACES (prior): {len(result):,} counties | "
                f"diabetes avg {result['diabetes_prev_prior'].mean()*100:.1f}%"
            )
            return result
        except Exception as e:
            log.warning(f"    Failed: {e}")

    log.warning("  CDC PLACES (prior): unavailable — trajectory will use demographic proxies only")
    return pd.DataFrame()


def _download_usda_food_atlas() -> pd.DataFrame:
    """
    USDA Food Environment Atlas — county-level food access data.
    Provides: food_desert_pct (% population with low access to grocery stores).
    Source: USDA Economic Research Service (ERS).
    Sheet: ACCESS → PCT_LACCESS_POP15 (% population, low food access, 2015).

    Manual fallback: download FoodEnvironmentAtlas.xls from
    https://www.ers.usda.gov/data-products/food-environment-atlas/
    and save to data/open/FoodEnvironmentAtlas.xls
    """
    cache = Path(OPEN_DIR) / "usda_food_atlas.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        log.info(f"  USDA Food Atlas: {len(df):,} counties from cache")
        return df

    urls = [
        # Current XLSX (updated 2025-07-30) — USDA moved to /media/ path
        "https://www.ers.usda.gov/media/5569/food-environment-atlas-data-download.xlsx?v=26424",
        # 2020 archive (XLS) — stable fallback with ACCESS sheet + PCT_LACCESS_POP15
        "https://www.ers.usda.gov/media/5558/2020-food-environment-atlas-data-download.xls?v=33909",
        # Legacy /webdocs/ paths (kept for reference; 404 as of mid-2025)
        # "https://www.ers.usda.gov/webdocs/DataFiles/50048/FoodEnvironmentAtlas.xls",
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    for url in urls:
        try:
            log.info(f"  USDA Food Atlas: trying {url[:70]} …")
            resp = fetch(url, timeout=TIMEOUT, headers=headers)
            resp.raise_for_status()
            if len(resp.content) < 10_000:
                log.warning("    Response too small, skipping")
                continue
            raw = _read_usda_excel(io.BytesIO(resp.content))
            result = _parse_usda_food_atlas(raw)
            if not result.empty and len(result) > 500:
                result.to_parquet(cache, index=False)
                avg_pct = result["food_desert_pct"].mean() * 100
                log.info(
                    f"  USDA Food Atlas: {len(result):,} counties | "
                    f"food_desert_pct avg {avg_pct:.1f}%"
                )
                return result
            log.warning(f"    Parsed only {len(result)} rows, trying next URL …")
        except Exception as e:
            log.warning(f"    Failed: {e}")

    # Try manual local download
    for local_name in ["FoodEnvironmentAtlas.xlsx", "FoodEnvironmentAtlas.xls",
                        "food-environment-atlas-data-download.xlsx"]:
        local = Path(OPEN_DIR) / local_name
        if not local.exists():
            continue
        try:
            raw = _read_usda_excel(local)
            result = _parse_usda_food_atlas(raw)
            if not result.empty:
                result.to_parquet(cache, index=False)
                log.info(f"  USDA Food Atlas: {len(result):,} counties from local file")
                return result
        except Exception as e:
            log.warning(f"    Local file parse failed: {e}")

    log.warning(
        "  USDA Food Atlas: unavailable — social_determinants will use CHR food_insecurity as proxy.\n"
        "  To activate: download FoodEnvironmentAtlas.xls from\n"
        "    https://www.ers.usda.gov/data-products/food-environment-atlas/\n"
        "  and save to data/open/FoodEnvironmentAtlas.xls, then re-run."
    )
    return pd.DataFrame()


def _read_usda_excel(source) -> pd.DataFrame:
    """
    Read the USDA Food Environment Atlas Excel file, auto-discovering the
    correct sheet. Tries 'ACCESS' first, then any sheet containing LACCESS data.
    The 2025 current version is XLSX; 2020 archive is XLS — both handled.
    """
    xl = pd.ExcelFile(source)
    sheet_names = xl.sheet_names
    log.info(f"    USDA Excel sheets: {sheet_names[:8]}")

    # Try ACCESS sheet first (standard location in all archive versions)
    for candidate in ["ACCESS", "Access", "access"]:
        if candidate in sheet_names:
            df = xl.parse(candidate)
            if any("LACCESS" in str(c).upper() for c in df.columns):
                return df

    # Fall back: search all sheets for LACCESS column
    for sheet in sheet_names:
        try:
            df = xl.parse(sheet)
            if any("LACCESS" in str(c).upper() for c in df.columns):
                log.info(f"    Found LACCESS data in sheet: {sheet}")
                return df
        except Exception:
            continue

    # Last resort: return first sheet (caller will handle empty result)
    log.warning("    No sheet with LACCESS columns found — returning first sheet")
    return xl.parse(sheet_names[0])


def _parse_usda_food_atlas(df: pd.DataFrame) -> pd.DataFrame:
    """Parse USDA Food Environment Atlas ACCESS sheet into county-level rows."""
    df = df.copy()
    df.columns = df.columns.str.strip()

    result = pd.DataFrame()

    # FIPS column — stored as int (e.g. 1001) or string; zfill to 5 digits
    for col in df.columns:
        if col.upper() == "FIPS":
            result["county_fips"] = (
                df[col].astype(str).str.strip().str.split(".").str[0].str.zfill(5)
            )
            break

    if "county_fips" not in result.columns or result.empty:
        return pd.DataFrame()

    # % population with low access to grocery stores (food desert proxy)
    # Prefer most-recent year available
    for pct_col in ["PCT_LACCESS_POP15", "PCT_LACCESS_POP10", "PCT_LACCESS_POP"]:
        if pct_col in df.columns:
            vals = pd.to_numeric(df[pct_col], errors="coerce")
            # ERS stores as 0-100 percentage
            if vals.median(skipna=True) > 1.5:
                vals = vals / 100.0
            result["food_desert_pct"] = vals.clip(0, 1)
            break

    if "food_desert_pct" not in result.columns:
        return pd.DataFrame()

    result = result[result["county_fips"].str.match(r"^\d{5}$", na=False)]
    result = result[result["county_fips"].str[:2].isin(US_STATE_FIPS)]
    return result.drop_duplicates("county_fips").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# PANEL BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_panel(
    counties: pd.DataFrame,
    cdc: pd.DataFrame,
    acs: pd.DataFrame,
    cms: pd.DataFrame,
    chr_df: pd.DataFrame,
    usda: pd.DataFrame,
    cdc_prior: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge all sources onto the Census TIGER county spine.
    Spine is always 3,143 rows; all joins are left so it never shrinks.
    """
    if counties.empty or "county_fips" not in counties.columns:
        log.error(
            "County spine is empty — cannot build panel.\n"
            "Delete data/open/census_counties.parquet and retry: "
            "the script will rebuild from cdc_places_raw.csv or Census TIGER."
        )
        raise RuntimeError("Empty county spine — see log above for recovery steps.")

    panel = counties.copy()
    n_base = len(panel)

    def _merge(right, name, check_col=None):
        nonlocal panel
        if right.empty:
            log.info(f"  {name}: empty, skipped")
            return
        panel = panel.merge(right, on="county_fips", how="left")
        assert len(panel) == n_base, f"Row count drifted after {name}: {len(panel)}"
        if check_col and check_col in panel.columns:
            n_filled = panel[check_col].notna().sum()
            log.info(f"  After {name}: {n_filled:,}/{n_base:,} counties have {check_col}")

    _merge(cdc,       "CDC PLACES",         "diabetes_prevalence_pct")
    _merge(cdc_prior, "CDC PLACES (prior)", "diabetes_prev_prior")
    _merge(acs,       "Census ACS",         "poverty_rate")
    _merge(cms,       "CMS GV PUF",         "cms_t2d_diagnosed_rate")
    _merge(chr_df,    "CHR",                "chr_poverty_pct")
    _merge(usda,      "USDA Food Atlas",    "food_desert_pct")

    # Try HRSA if available (adds hpsa_flag, fqhc_present)
    try:
        from src.ingestion.open_data.hrsa_data import download as hrsa_dl
        hrsa = hrsa_dl(cache_dir=OPEN_DIR, force=False)
        _merge(hrsa, "HRSA", "hpsa_flag")
    except Exception:
        pass  # Will derive proxies below

    panel = _derive_features(panel)
    panel = _fill_missing(panel)

    log.info(f"  Final panel: {len(panel):,} counties × {len(panel.columns)} columns")
    return panel


def _derive_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all columns required by dimension_scorer.py that aren't
    directly available from a single raw source.
    """
    # ── Population ────────────────────────────────────────────────────────────
    if "population" not in df.columns:
        if "total_population" in df.columns:
            df["population"] = df["total_population"]
        else:
            df["population"] = np.nan  # filled later

    # ── is_rural: proxy from population (Census rural = <50 k, but ACS has pop) ──
    if "is_rural" not in df.columns:
        pop = df.get("population", df.get("total_population",
                     pd.Series(50_000, index=df.index))).fillna(50_000)
        df["is_rural"] = (pop < 50_000).astype(int)

    # ── SES disadvantage index ────────────────────────────────────────────────
    if "ses_disadvantage_index" not in df.columns:
        ses_parts = []
        for col in ["poverty_rate", "uninsured_rate"]:
            if col in df.columns:
                ses_parts.append(_norm01(df[col]))
        if "hs_graduation_rate" in df.columns:
            ses_parts.append(_norm01(1 - df["hs_graduation_rate"]))
        if "median_household_income" in df.columns:
            ses_parts.append(_norm01(1.0 / (df["median_household_income"].clip(lower=1000))))
        # CHR backups
        if not ses_parts:
            if "chr_poverty_pct" in df.columns:
                ses_parts.append(_norm01(df["chr_poverty_pct"] / 100))
            if "chr_uninsured_pct" in df.columns:
                ses_parts.append(_norm01(df["chr_uninsured_pct"] / 100))
        df["ses_disadvantage_index"] = (
            np.mean(ses_parts, axis=0) if ses_parts else pd.Series(0.30, index=df.index)
        )

    # ── Racial risk index ─────────────────────────────────────────────────────
    if "racial_risk_index" not in df.columns:
        df["racial_risk_index"] = np.clip(
            0.15 + 0.35 * df["ses_disadvantage_index"], 0, 0.65
        )

    # ── CHR → primary columns (use as backup when ACS/PLACES columns missing) ──
    # CHR stores proportion measures as fractions (0-1), e.g. 0.12 = 12%.
    # Some CHR releases use 0-100 scale; _chr_pct() auto-detects and normalises.
    def _chr_pct(col_name):
        """Return CHR column normalised to 0-1 scale."""
        vals = pd.to_numeric(df[col_name], errors="coerce")
        if vals.median() > 1.5:   # stored as 0-100 (percentage)
            vals = vals / 100.0
        return vals.clip(0, 1)

    _chr_fallbacks = {
        "diabetes_prevalence_pct":     "chr_diabetes_pct",
        "obesity_rate_pct":            "chr_obesity_pct",
        "hypertension_prevalence_pct": "chr_poor_health_pct",   # rough proxy
        "poor_physical_health_pct":    "chr_poor_health_pct",
        "poverty_rate":                "chr_poverty_pct",
        "uninsured_rate":              "chr_uninsured_pct",
        "broadband_access_rate":       "chr_broadband_pct",
        "hs_graduation_rate":          "chr_hs_grad_pct",
    }
    for dst, src in _chr_fallbacks.items():
        if dst not in df.columns and src in df.columns:
            df[dst] = _chr_pct(src)

    # Median income is in dollars — no scaling needed
    if "median_household_income" not in df.columns and "chr_median_income" in df.columns:
        df["median_household_income"] = pd.to_numeric(df["chr_median_income"], errors="coerce")

    # ── Prevalence trend (multi-year CDC PLACES delta) ───────────────────────
    # diabetes_trend > 0 = burden growing (gap likely widening)
    # diabetes_trend < 0 = burden shrinking (gap may be narrowing)
    if "diabetes_prev_prior" in df.columns and "diabetes_prevalence_pct" in df.columns:
        df["diabetes_trend"] = (
            df["diabetes_prevalence_pct"] - df["diabetes_prev_prior"]
        ).clip(-0.05, 0.05)  # cap extreme outliers (data error guard)
    else:
        df["diabetes_trend"] = np.nan  # falls back to demographic proxy in scorer

    if "htn_prev_prior" in df.columns and "hypertension_prevalence_pct" in df.columns:
        df["htn_trend"] = (
            df["hypertension_prevalence_pct"] - df["htn_prev_prior"]
        ).clip(-0.10, 0.10)
    else:
        df["htn_trend"] = np.nan

    # ── Food desert (food access barrier) ────────────────────────────────────
    if "food_desert_pct" not in df.columns:
        if "chr_food_insecurity_pct" in df.columns:
            # CHR food insecurity is a reasonable SDoH proxy when USDA unavailable
            vals = pd.to_numeric(df["chr_food_insecurity_pct"], errors="coerce")
            if vals.median(skipna=True) > 1.5:
                vals = vals / 100.0
            df["food_desert_pct"] = vals.clip(0, 1)
        else:
            df["food_desert_pct"] = _DEFAULTS["food_desert_pct"]

    # ── checkup rate: no direct backup; use national avg if missing ───────────
    if "annual_checkup_pct" not in df.columns:
        df["annual_checkup_pct"] = _DEFAULTS["annual_checkup_pct"]

    # ── smoking rate ──────────────────────────────────────────────────────────
    if "smoking_rate_pct" not in df.columns:
        if "chr_smoking_pct" in df.columns:
            df["smoking_rate_pct"] = df["chr_smoking_pct"] / 100
        else:
            df["smoking_rate_pct"] = _DEFAULTS["smoking_rate_pct"]

    # ── Access to care: hpsa_flag + fqhc_present ─────────────────────────────
    if "hpsa_flag" not in df.columns:
        if "chr_primary_care_ratio" in df.columns:
            # Primary care ratio > 3,500 persons per physician = shortage
            df["hpsa_flag"] = (df["chr_primary_care_ratio"] > 3_500).astype(int)
        else:
            ses = df["ses_disadvantage_index"].fillna(0.30)
            rural = df["is_rural"].fillna(0).astype(float)
            rng = np.random.default_rng(44)
            df["hpsa_flag"] = (
                (ses > 0.55) | (rural == 1) | (rng.random(len(df)) < 0.22)
            ).astype(int)

    if "fqhc_present" not in df.columns:
        if "chr_primary_care_ratio" in df.columns:
            # Areas with 1,500–5,000 persons/PCP more likely to have FQHCs
            df["fqhc_present"] = (
                df["chr_primary_care_ratio"].between(1_500, 5_000)
            ).astype(int)
        else:
            # Rough rule: counties with HPSA shortage AND moderate SES
            df["fqhc_present"] = (df["hpsa_flag"] == 1).astype(int)

    if "fqhc_count" not in df.columns:
        df["fqhc_count"] = df["fqhc_present"]

    # ── Payer mix ─────────────────────────────────────────────────────────────
    if "medicaid_rate" not in df.columns:
        ses = df["ses_disadvantage_index"].fillna(0.30)
        df["medicaid_rate"] = np.clip(0.18 + 0.22 * ses, 0.05, 0.60)

    if "commercial_rate" not in df.columns:
        ma       = df.get("ma_penetration_rate", pd.Series(np.nan, index=df.index)).fillna(0.44)
        medicaid = df["medicaid_rate"].fillna(0.20)
        unins    = df.get("uninsured_rate", pd.Series(0.09, index=df.index)).fillna(0.09)
        df["commercial_rate"] = np.clip(1.0 - ma - medicaid - unins, 0.05, 0.70)

    if "dual_eligible_rate" not in df.columns:
        # Proxy: counties with high MA + high Medicaid have more dual-eligibles
        ma  = df.get("ma_penetration_rate", pd.Series(0.44, index=df.index)).fillna(0.44)
        med = df["medicaid_rate"].fillna(0.20)
        df["dual_eligible_rate"] = np.clip(ma * med * 2.5, 0.02, 0.25)

    return df


def _fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill NaN with state-level median first, then national defaults.
    Preserves geographic variation far better than a flat national median.
    """
    df = df.copy()

    # Capture TRUE data coverage BEFORE filling — the confidence grade
    # (dimension_scorer._confidence_grade) needs to know which counties were
    # actually observed vs. median-filled. Without this, every county grades A.
    try:
        from src.features.dimension_scorer import _SOURCE_MARKERS
        df["confidence_sources_raw"] = sum(
            df[c].notna().astype(int)
            for c in _SOURCE_MARKERS.values() if c in df.columns
        )
    except Exception:
        pass

    df["_sfips"] = df["county_fips"].str[:2]

    for col, default in _DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
            continue
        if df[col].isna().any():
            # State median fill
            state_med = df.groupby("_sfips")[col].transform("median")
            df[col] = df[col].fillna(state_med)
            # National fallback
            df[col] = df[col].fillna(default)

    df = df.drop(columns=["_sfips"], errors="ignore")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _to_num(s: pd.Series) -> pd.Series:
    """
    Robust numeric parse for government CSV columns.

    CMS/Census files format numbers as '1,234' (thousands commas), '12.34%',
    ' 12.3 ' (padding), '*' / '.' / '' (suppression markers). Naive
    pd.to_numeric coerces ALL of those to NaN — which once silently reduced
    CMS MA coverage to 236 tiny comma-free counties out of 3,128.
    """
    cleaned = (
        s.astype(str)
         .str.strip()
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.replace("$", "", regex=False)
    )
    cleaned = cleaned.replace({"*": None, ".": None, "": None, "nan": None,
                               "N/A": None, "NA": None, "--": None})
    return pd.to_numeric(cleaned, errors="coerce")


def _norm01(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    s = s.fillna(s.median() or 0.0)
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


def _log_provenance(cdc, cdc_prior, acs, cms, chr_df, usda):
    def ok(df):
        return "✅ REAL" if not df.empty else "⚠️  synthetic"
    log.info(
        "\nData provenance:"
        f"\n  Disease burden:      {ok(cdc)} (CDC PLACES 2024)"
        f"\n  Trajectory trend:    {ok(cdc_prior)} (CDC PLACES 2022 prior release)"
        f"\n  Social determinants: {ok(acs)} (Census ACS)"
        f"\n  Food desert signal:  {ok(usda)} (USDA Food Environment Atlas)"
        f"\n  Medicare T2D/HTN:    {ok(cms)} (CMS Geographic Variation PUF)"
        f"\n  MA penetration:      {ok(cms)} (CMS Geographic Variation PUF)"
        f"\n  Access/SDoH backup:  {ok(chr_df)} (County Health Rankings)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# NATIONAL DEFAULTS  (CDC / Census 2022-2024 estimates)
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULTS = {
    "diabetes_prevalence_pct":     0.113,   # CDC 2022: 11.3%
    "obesity_rate_pct":            0.320,   # CDC 2022: 32.0%
    "hypertension_prevalence_pct": 0.470,   # CDC 2022: 47.0%
    "poor_physical_health_pct":    0.140,
    "annual_checkup_pct":          0.720,
    "smoking_rate_pct":            0.120,
    "poverty_rate":                0.125,   # Census 2022: 12.5%
    "median_household_income":     74_580,  # Census 2022
    "uninsured_rate":              0.090,   # Census 2022
    "hs_graduation_rate":          0.885,
    "broadband_access_rate":       0.820,
    "median_age":                  38.9,    # Census 2022
    "racial_risk_index":           0.200,
    "ses_disadvantage_index":      0.300,
    # NOTE: cms_t2d/htn_diagnosed_rate deliberately NOT defaulted — a flat
    # national constant is not data. When the GV PUF download is unavailable
    # the columns stay absent and the scorer uses its documented CDC-only
    # fallback for the Diagnosis Gap dimension.
    "ma_penetration_rate":         0.540,   # CMS 2024: 54% nationally (updated)
    "medicaid_rate":               0.210,
    "commercial_rate":             0.380,
    "dual_eligible_rate":          0.115,
    "population":                  100_000,
    "total_population":            100_000,
    "is_rural":                    0,
    "hpsa_flag":                   0,
    "fqhc_count":                  1,
    "fqhc_present":                1,
    "food_desert_pct":             0.195,  # USDA ERS: ~19.5% US pop has low food access
}


# ─────────────────────────────────────────────────────────────────────────────
# STATE LOOKUP TABLES
# ─────────────────────────────────────────────────────────────────────────────

_STATE_NAMES = {
    "AL": "Alabama",          "AK": "Alaska",         "AZ": "Arizona",
    "AR": "Arkansas",         "CA": "California",     "CO": "Colorado",
    "CT": "Connecticut",      "DE": "Delaware",       "DC": "District of Columbia",
    "FL": "Florida",          "GA": "Georgia",        "HI": "Hawaii",
    "ID": "Idaho",            "IL": "Illinois",       "IN": "Indiana",
    "IA": "Iowa",             "KS": "Kansas",         "KY": "Kentucky",
    "LA": "Louisiana",        "ME": "Maine",          "MD": "Maryland",
    "MA": "Massachusetts",    "MI": "Michigan",       "MN": "Minnesota",
    "MS": "Mississippi",      "MO": "Missouri",       "MT": "Montana",
    "NE": "Nebraska",         "NV": "Nevada",         "NH": "New Hampshire",
    "NJ": "New Jersey",       "NM": "New Mexico",     "NY": "New York",
    "NC": "North Carolina",   "ND": "North Dakota",   "OH": "Ohio",
    "OK": "Oklahoma",         "OR": "Oregon",         "PA": "Pennsylvania",
    "RI": "Rhode Island",     "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee",        "TX": "Texas",          "UT": "Utah",
    "VT": "Vermont",          "VA": "Virginia",       "WA": "Washington",
    "WV": "West Virginia",    "WI": "Wisconsin",      "WY": "Wyoming",
}


if __name__ == "__main__":
    main()
