#!/usr/bin/env python3
"""
fix_zip_map.py — Patch ZIP centroids into existing zip_scores.parquet
======================================================================
Run this if ingest_zcta_data.py ran successfully but the map shows
"Centroid data not available" (Census Gazetteer download timed out).

Usage:
    python3 fix_zip_map.py

Downloads ZIP lat/lon from a fast GitHub-hosted CSV, merges it into
data/scored/zip_scores.parquet, and saves the patched file in place.
"""
from __future__ import annotations

import io
import logging
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

OPEN_DIR   = "data/open"
SCORED_DIR = "data/scored"
TIMEOUT    = 60


def main():
    zip_scores_path = Path(SCORED_DIR) / "zip_scores.parquet"
    centroids_cache = Path(OPEN_DIR) / "zcta_centroids.parquet"

    if not zip_scores_path.exists():
        log.error(f"zip_scores.parquet not found at {zip_scores_path}")
        log.error("Run python3 ingest_zcta_data.py first.")
        sys.exit(1)

    # 1. Download centroids
    log.info("Downloading ZCTA centroids …")
    centroids = _download_centroids(centroids_cache)

    if centroids.empty:
        log.error("Could not download centroids from any source. See above for details.")
        sys.exit(1)

    log.info(f"  → {len(centroids):,} ZCTA centroids loaded")

    # 2. Load and patch zip_scores
    log.info("Loading zip_scores.parquet …")
    df = pd.read_parquet(zip_scores_path)
    log.info(f"  → {len(df):,} rows loaded")

    # Drop any existing (possibly empty) lat/lon columns before patching
    for col in ["lat", "lon", "land_sqmi"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    # Merge centroids
    df = df.merge(centroids, on="zcta5", how="left")
    n_with_geo = df["lat"].notna().sum()
    pct = n_with_geo / len(df) * 100

    log.info(f"  → {n_with_geo:,}/{len(df):,} ZCTAs matched ({pct:.0f}%)")

    if n_with_geo < 1000:
        log.warning(f"Only {n_with_geo} ZCTAs got centroids — map coverage will be limited")

    # Save
    df.to_parquet(zip_scores_path, index=False)
    log.info(f"✅ Saved patched zip_scores.parquet ({n_with_geo:,} ZCTAs with lat/lon)")
    log.info("Refresh the Streamlit dashboard to see the ZIP map.")


def _download_centroids(cache_path: Path) -> pd.DataFrame:
    """Try multiple sources for ZCTA / ZIP lat-lon centroids."""
    Path(OPEN_DIR).mkdir(parents=True, exist_ok=True)

    # 0. Use cached file if already good
    if cache_path.exists():
        df = pd.read_parquet(cache_path)
        if not df.empty and "lat" in df.columns and len(df) > 10_000:
            log.info(f"  Centroids: {len(df):,} from cache")
            return df
        else:
            log.info("  Centroid cache empty or stale, re-downloading …")
            cache_path.unlink(missing_ok=True)

    # Source 1: Census Gazetteer (most authoritative, large ZIP download)
    df = _try_census_gazetteer()
    if not df.empty:
        df.to_parquet(cache_path, index=False)
        return df

    # Source 2: GitHub-hosted scpike US ZIP database (fast, ~2 MB)
    df = _try_github_scpike()
    if not df.empty:
        df.to_parquet(cache_path, index=False)
        return df

    # Source 3: SimpleMaps free basic dataset (hosted on their CDN)
    df = _try_simplemaps()
    if not df.empty:
        df.to_parquet(cache_path, index=False)
        return df

    # Source 4: Plotly datasets GitHub (US county centers as proxy for ZCTAs)
    df = _try_plotly_centers()
    if not df.empty:
        df.to_parquet(cache_path, index=False)
        return df

    return pd.DataFrame()


def _try_census_gazetteer() -> pd.DataFrame:
    """Census Gazetteer — definitive ZCTA centroids (large ZIP file)."""
    urls = [
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip",
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_zcta_national.zip",
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2022_Gazetteer/2022_Gaz_zcta_national.zip",
    ]
    for url in urls:
        try:
            log.info(f"  Census Gazetteer: {url[-50:]} …")
            resp = requests.get(url, timeout=90)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                txt = next((n for n in zf.namelist() if n.endswith(".txt")), None)
                if not txt:
                    continue
                content = zf.read(txt).decode("utf-8", errors="replace")

            raw = pd.read_csv(io.StringIO(content), sep="\t", low_memory=False)
            raw.columns = raw.columns.str.strip()
            log.info(f"    Cols: {list(raw.columns)}")

            # Normalize column names
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

            if "zcta5" not in raw.columns or "lat" not in raw.columns:
                log.warning(f"    Missing zcta5 or lat columns in Gazetteer file")
                continue

            result = pd.DataFrame({
                "zcta5": raw["zcta5"].astype(str).str.zfill(5),
                "lat":   pd.to_numeric(raw["lat"], errors="coerce"),
                "lon":   pd.to_numeric(raw["lon"], errors="coerce"),
            }).dropna(subset=["lat", "lon"])

            log.info(f"  Census Gazetteer: {len(result):,} ZCTAs ✅")
            return result.reset_index(drop=True)

        except Exception as e:
            log.warning(f"    Failed: {e}")
    return pd.DataFrame()


def _try_github_scpike() -> pd.DataFrame:
    """
    scpike/us-state-county-zip — GitHub-hosted US ZIP lat/lon (~2 MB CSV).
    Columns: state, state_abbr, zipcode, county, city, lat, lng
    """
    urls = [
        "https://raw.githubusercontent.com/scpike/us-state-county-zip/master/geo-data.csv",
        "https://raw.githubusercontent.com/midwire/free_zipcode_data/master/all_us_zipcodes.csv",
    ]
    for url in urls:
        try:
            log.info(f"  GitHub ZIP DB: {url[-55:]} …")
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            raw = pd.read_csv(io.StringIO(resp.text), low_memory=False)
            raw.columns = raw.columns.str.lower().str.strip()
            log.info(f"    Cols: {list(raw.columns[:8])}")

            # Flexible column detection
            zip_col = next((c for c in raw.columns if c in ("zipcode","zip","postal_code","zip_code")), None)
            lat_col = next((c for c in raw.columns if c in ("lat","latitude")), None)
            lon_col = next((c for c in raw.columns if c in ("lng","lon","long","longitude")), None)

            if not all([zip_col, lat_col, lon_col]):
                log.warning(f"    Missing required columns (zip={zip_col}, lat={lat_col}, lon={lon_col})")
                continue

            result = pd.DataFrame({
                "zcta5": raw[zip_col].astype(str).str.zfill(5),
                "lat":   pd.to_numeric(raw[lat_col], errors="coerce"),
                "lon":   pd.to_numeric(raw[lon_col], errors="coerce"),
            }).dropna(subset=["lat", "lon"]).drop_duplicates("zcta5")

            # Filter to CONUS + Hawaii + Alaska range
            result = result[
                result["lat"].between(-90, 90) & result["lon"].between(-180, 0)
            ]

            log.info(f"  GitHub ZIP DB: {len(result):,} ZCTAs ✅")
            return result.reset_index(drop=True)

        except Exception as e:
            log.warning(f"    Failed: {e}")
    return pd.DataFrame()


def _try_simplemaps() -> pd.DataFrame:
    """SimpleMaps free US ZIP code database."""
    urls = [
        "https://simplemaps.com/static/data/us-zips/1.0/basic/simplemaps_uszips_basicv1.0.zip",
        "https://simplemaps.com/static/data/us-cities/1.79/basic/simplemaps_uscities_basicv1.79.zip",
    ]
    for url in urls:
        try:
            log.info(f"  SimpleMaps: {url[-50:]} …")
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_files = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_files:
                    continue
                content = zf.read(csv_files[0]).decode("utf-8", errors="replace")

            raw = pd.read_csv(io.StringIO(content), low_memory=False)
            raw.columns = raw.columns.str.lower().str.strip()

            zip_col = next((c for c in raw.columns if c in ("zip","zipcode")), None)
            lat_col = next((c for c in raw.columns if c in ("lat","latitude")), None)
            lon_col = next((c for c in raw.columns if c in ("lng","lon","longitude")), None)

            if not all([zip_col, lat_col, lon_col]):
                continue

            result = pd.DataFrame({
                "zcta5": raw[zip_col].astype(str).str.zfill(5),
                "lat":   pd.to_numeric(raw[lat_col], errors="coerce"),
                "lon":   pd.to_numeric(raw[lon_col], errors="coerce"),
            }).dropna(subset=["lat", "lon"]).drop_duplicates("zcta5")

            log.info(f"  SimpleMaps: {len(result):,} ZCTAs ✅")
            return result.reset_index(drop=True)

        except Exception as e:
            log.warning(f"    Failed: {e}")
    return pd.DataFrame()


def _try_plotly_centers() -> pd.DataFrame:
    """
    Last resort: county centroids from Plotly's GitHub.
    Maps ZCTA → county FIPS → county centroid.
    Much less precise but at least puts a dot in roughly the right state.
    """
    try:
        log.info("  Plotly county centers (ZCTA proxy) …")
        xwalk_path = Path(OPEN_DIR) / "zcta_county_crosswalk.parquet"
        if not xwalk_path.exists():
            log.warning("    No ZCTA→county crosswalk found, can't use county proxy")
            return pd.DataFrame()

        xwalk = pd.read_parquet(xwalk_path)

        # Download county centers from Plotly
        url = "https://raw.githubusercontent.com/plotly/datasets/master/2011_us_ag_exports.csv"
        # Actually use the better county centers CSV
        url = "https://raw.githubusercontent.com/btskinner/spatial/master/data/county_centers.csv"
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        cc = pd.read_csv(io.StringIO(resp.text), low_memory=False)
        cc.columns = cc.columns.str.lower()
        log.info(f"    County centers cols: {list(cc.columns[:8])}")

        fips_col = next((c for c in cc.columns if "fips" in c or c == "fips"), None)
        lat_col  = next((c for c in cc.columns if c in ("lat","latitude","clat","clon")), None)
        lon_col  = next((c for c in cc.columns if c in ("lon","lng","longitude","clon","clon10")), None)

        if not all([fips_col, lat_col, lon_col]):
            log.warning(f"    Missing columns in county centers: {list(cc.columns)}")
            return pd.DataFrame()

        cc_clean = pd.DataFrame({
            "county_fips": cc[fips_col].astype(str).str.zfill(5),
            "lat": pd.to_numeric(cc[lat_col], errors="coerce"),
            "lon": pd.to_numeric(cc[lon_col], errors="coerce"),
        }).dropna()

        # Best-weight county per ZCTA
        best = (xwalk.sort_values("weight", ascending=False)
                .drop_duplicates("zcta5")[["zcta5", "county_fips"]])
        merged = best.merge(cc_clean, on="county_fips", how="inner")
        merged["zcta5"] = merged["zcta5"].astype(str).str.zfill(5)

        log.info(f"  County proxy centroids: {len(merged):,} ZCTAs ✅ (approx — county centroid)")
        return merged[["zcta5", "lat", "lon"]].reset_index(drop=True)

    except Exception as e:
        log.warning(f"    County proxy failed: {e}")
    return pd.DataFrame()


if __name__ == "__main__":
    main()
