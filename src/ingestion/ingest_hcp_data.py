#!/usr/bin/env python3
from __future__ import annotations
"""
ingest_hcp_data.py — HCP Activation Layer ingestion
====================================================
Downloads the CMS "Medicare Physician & Other Practitioners - by Provider"
public file (one row per NPI: specialty, ZIP, Medicare panel size, panel
chronic-condition percentages), scores every targetable prescriber against
the geography opportunity scores, and writes the rep-facing target list.

Usage:
    python3 src/ingestion/ingest_hcp_data.py

Requires (run first):
    python3 src/ingestion/ingest_real_data.py     → data/scored/dimension_scores.parquet
    python3 src/ingestion/ingest_zcta_data.py     → data/scored/zip_scores.parquet

Output:
    data/open/cms_providers.parquet     (cached raw provider extract)
    data/scored/hcp_targets.parquet     (scored target list)
    data/scored/hcp_targets.csv         (CRM-loadable export)

Data notes:
    - 100% public aggregate data (data.cms.gov). No PHI at any stage.
    - Dataset UUID is resolved at runtime from the data.cms.gov catalog
      (data.json) by title search, so CMS re-publishing under a new UUID
      does not break the pipeline.
    - Manual fallback: download the by-Provider CSV from
      https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-provider
      and save it to data/open/cms_providers_manual.csv
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

import logging
import sys
import time
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

OPEN_DIR   = "data/open"
SCORED_DIR = "data/scored"
TIMEOUT    = 120
CATALOG_URL = "https://data.cms.gov/data.json"
DATASET_TITLE = "medicare physician & other practitioners - by provider"

# Columns we actually need (keeps the ~1.3M-row download light)
KEEP_COLS = [
    "Rndrng_NPI", "Rndrng_Prvdr_Last_Org_Name", "Rndrng_Prvdr_First_Name",
    "Rndrng_Prvdr_Type", "Rndrng_Prvdr_City", "Rndrng_Prvdr_State_Abrvtn",
    "Rndrng_Prvdr_Zip5", "Tot_Benes",
    "Bene_CC_PH_Diabetes_V2_Pct", "Bene_CC_PH_Hypertension_V2_Pct",
    # Older vintages:
    "Bene_CC_Diab_Pct", "Bene_CC_Hypertension_Pct",
]

# Only these specialties are worth a diagnosis-support call (others still
# scored if present, but pre-filtering keeps the file small)
TARGET_SPECIALTIES = {
    "family practice", "family medicine", "internal medicine",
    "general practice", "geriatric medicine", "nurse practitioner",
    "physician assistant", "preventive medicine", "endocrinology",
    "cardiology", "cardiovascular disease (cardiology)", "nephrology",
}


def main():
    t0 = time.time()
    log.info("=" * 62)
    log.info("  SPPF HCP Ingestion — Prescriber Activation Layer")
    log.info("=" * 62)
    Path(OPEN_DIR).mkdir(parents=True, exist_ok=True)
    Path(SCORED_DIR).mkdir(parents=True, exist_ok=True)

    # Prerequisites
    zip_path = Path(SCORED_DIR) / "zip_scores.parquet"
    county_path = Path(SCORED_DIR) / "dimension_scores.parquet"
    if not zip_path.exists() or not county_path.exists():
        log.error("Missing geography scores. Run ingest_real_data.py and "
                  "ingest_zcta_data.py first.")
        sys.exit(1)
    zip_scores = pd.read_parquet(zip_path)
    county_scores = pd.read_parquet(county_path)

    # 1. Providers
    log.info("\n[1/3] CMS Medicare Physician & Other Practitioners (by Provider) …")
    providers = _load_providers()
    if providers.empty:
        log.error("No provider data. See manual fallback note in the file header.")
        sys.exit(1)

    # 2. Score
    log.info("\n[2/3] Scoring HCP priority …")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from src.features.hcp_scorer import score_hcps
    targets = score_hcps(providers, zip_scores, county_scores)

    # 3. QA gate + write
    log.info("\n[3/3] QA gate + export …")
    from src.quality.qa_gate import run_gate, HCP_CHECKS
    run_gate(targets, HCP_CHECKS, name="HCP target list").raise_on_failure()

    out_pq  = Path(SCORED_DIR) / "hcp_targets.parquet"
    out_csv = Path(SCORED_DIR) / "hcp_targets.csv"
    targets.to_parquet(out_pq, index=False)
    targets.head(50_000).to_csv(out_csv, index=False)   # CRM-loadable slice

    log.info("\n" + "=" * 62)
    log.info("  HCP INGESTION COMPLETE")
    log.info(f"  Elapsed:        {time.time() - t0:.0f}s")
    log.info(f"  NPIs scored:    {len(targets):,}")
    log.info(f"  Priority tier:  {(targets['hcp_tier'] == 'Priority').sum():,}")
    log.info(f"  Output:         {out_pq}")
    log.info("=" * 62)
    log.info("\nDashboard ready → python3 -m streamlit run src/output/dashboard.py")


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────

def _load_providers() -> pd.DataFrame:
    cache = Path(OPEN_DIR) / "cms_providers.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        log.info(f"  Providers: {len(df):,} NPIs from cache")
        return df

    # Manual fallback file takes precedence over network
    manual = Path(OPEN_DIR) / "cms_providers_manual.csv"
    if manual.exists():
        log.info(f"  Providers: parsing manual download {manual.name} …")
        df = _parse_provider_csv_chunked(manual)
        if not df.empty:
            df.to_parquet(cache, index=False)
            return df

    urls = _resolve_dataset_urls()
    if not urls:
        return pd.DataFrame()

    # ── Strategy 1: direct file download (one stream ≫ 280 slow API pages) ───
    if urls.get("download_url"):
        df = _download_provider_file(urls["download_url"])
        if not df.empty:
            df.to_parquet(cache, index=False)
            return df

    # ── Strategy 2: paged data-api (slow — CSV endpoint often times out;
    #    JSON endpoint is faster and cached server-side) ──────────────────────
    api = urls.get("api_url")
    if not api:
        return pd.DataFrame()
    json_api = api.replace("/data.csv", "/data")
    log.info(f"  Providers: paging JSON API {json_api[:80]} …")
    frames, offset, size = [], 0, 5000
    while True:
        chunk = None
        for attempt in (1, 2, 3):
            try:
                resp = fetch(
                    f"{json_api}?size={size}&offset={offset}", timeout=300)
                resp.raise_for_status()
                data = resp.json()
                chunk = pd.DataFrame(data)
                break
            except Exception as e:
                log.warning(f"    page offset={offset} attempt {attempt} failed: {e}")
                time.sleep(5 * attempt)
        if chunk is None or chunk.empty:
            break
        frames.append(_slim_provider_chunk(chunk))
        offset += size
        if offset % 100_000 == 0:
            log.info(f"    … {offset:,} rows fetched")
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    log.info(f"  Providers: {len(df):,} targetable NPIs downloaded")
    df.to_parquet(cache, index=False)
    return df


def _download_provider_file(url: str) -> pd.DataFrame:
    """Stream the full CSV (or zipped CSV) release file and parse in chunks."""
    import tempfile
    import zipfile

    log.info(f"  Providers: streaming direct download {url[:85]} …")
    try:
        with fetch(url, timeout=TIMEOUT, stream=True) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            with tempfile.NamedTemporaryFile(suffix=Path(url).suffix or ".csv",
                                             delete=False) as tmp:
                done = 0
                for part in resp.iter_content(chunk_size=8 * 1024 * 1024):
                    tmp.write(part)
                    done += len(part)
                    if total and done % (200 * 1024 * 1024) < 8 * 1024 * 1024:
                        log.info(f"    … {done/1e6:.0f} / {total/1e6:.0f} MB")
                tmp_path = Path(tmp.name)
        log.info(f"    downloaded {tmp_path.stat().st_size/1e6:.0f} MB")

        if zipfile.is_zipfile(tmp_path):
            with zipfile.ZipFile(tmp_path) as zf:
                name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
                if not name:
                    return pd.DataFrame()
                with zf.open(name) as fh:
                    df = _parse_provider_stream(fh)
        else:
            df = _parse_provider_stream(tmp_path)
        tmp_path.unlink(missing_ok=True)
        log.info(f"  Providers: {len(df):,} targetable NPIs from direct file")
        return df
    except Exception as e:
        log.warning(f"  Direct download failed: {e} — falling back to paged API")
        return pd.DataFrame()


def _parse_provider_stream(src) -> pd.DataFrame:
    frames = [
        _slim_provider_chunk(chunk)
        for chunk in pd.read_csv(src, chunksize=200_000, low_memory=False,
                                 encoding_errors="replace")
    ]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _resolve_dataset_urls() -> dict | None:
    """
    Find the by-Provider dataset's URLs from the CMS catalog.
    Returns {"api_url": …, "download_url": …} (either key may be absent).

    Two real-world traps handled here (both hit in production 2026-07):
      1. Title matching must be EXACT — a substring match on "by provider"
         also matches "…by Provider and Service" (a different, per-service
         dataset without panel condition columns).
      2. CMS catalog distribution URLs sometimes carry a placeholder host
         ("https://default/data-api/…") — never trust the host; extract the
         dataset UUID and rebuild the URL against data.cms.gov.
    """
    import re

    try:
        log.info("  Resolving dataset UUID from data.cms.gov catalog …")
        resp = fetch(CATALOG_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        catalog = resp.json()
    except Exception as e:
        log.warning(f"  Catalog fetch failed: {e}")
        return None

    def _fix_host(u: str) -> str:
        """CMS catalog URLs sometimes carry a placeholder host — rebuild it."""
        from urllib.parse import urlparse, urlunparse
        p = urlparse(u)
        if p.netloc in ("default", "", "localhost"):
            p = p._replace(scheme="https", netloc="data.cms.gov")
        return urlunparse(p)

    api_candidates = []    # (dist_title, uuid)
    file_candidates = []   # (dist_title, direct_url)
    for ds in catalog.get("dataset", []):
        title = str(ds.get("title", "")).strip().lower()
        # Exact dataset only — reject "…by provider and service" etc.
        if title != DATASET_TITLE:
            continue
        for dist in ds.get("distribution", []):
            dist_title = str(dist.get("title", "")) or title
            access = str(dist.get("accessURL", "") or "")
            download = str(dist.get("downloadURL", "") or "")
            m = re.search(r"dataset/([0-9a-fA-F-]{36})", access or download)
            if m:
                api_candidates.append((dist_title, m.group(1)))
            if download and ("csv" in download.lower() or "zip" in download.lower()):
                file_candidates.append((dist_title, _fix_host(download)))

    if not api_candidates and not file_candidates:
        log.warning(f"  Dataset '{DATASET_TITLE}' not found in catalog "
                    f"(or no usable distribution)")
        return None

    api_candidates.sort(reverse=True)    # latest year first (titles carry dates)
    file_candidates.sort(reverse=True)
    out = {}
    if api_candidates:
        dist_title, uuid = api_candidates[0]
        out["api_url"] = f"https://data.cms.gov/data-api/v1/dataset/{uuid}/data.csv"
        log.info(f"  Dataset resolved: {dist_title[:70]} → {uuid}")
    if file_candidates:
        out["download_url"] = file_candidates[0][1]
        log.info(f"  Direct file: {out['download_url'][:85]}")
    return out


def _slim_provider_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Keep needed columns + filter to target specialties + individuals."""
    cols = [c for c in chunk.columns if c in KEEP_COLS]
    slim = chunk[cols].copy() if cols else chunk.copy()
    type_col = next((c for c in slim.columns if c.lower() == "rndrng_prvdr_type"), None)
    if type_col is not None:
        slim = slim[slim[type_col].astype(str).str.lower().isin(TARGET_SPECIALTIES)]
    # Stabilise dtypes across chunks: pandas infers Zip5/NPI as int in chunks
    # without leading-zero values and str in chunks with them — pyarrow then
    # rejects the mixed column at parquet write time.
    for c in slim.columns:
        cl = c.lower()
        if "zip" in cl or "npi" in cl:
            slim[c] = slim[c].astype(str)
    return slim


def _parse_provider_csv_chunked(path: Path) -> pd.DataFrame:
    frames = []
    for chunk in pd.read_csv(path, chunksize=100_000, low_memory=False):
        frames.append(_slim_provider_chunk(chunk))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    log.info(f"  Providers: {len(df):,} targetable NPIs from manual file")
    return df


if __name__ == "__main__":
    main()
