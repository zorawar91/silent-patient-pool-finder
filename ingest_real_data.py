from __future__ import annotations
"""
Real Data Ingestion — Silent Patient Pool Finder
================================================
Downloads CDC PLACES + Census ACS data and rebuilds the 7-dimension scores.

Run this ONCE (or whenever you want to refresh data):

    python3 ingest_real_data.py

Then launch the dashboard normally:

    python3 -m streamlit run src/output/dashboard.py

What this does
--------------
1. Downloads CDC PLACES county data (≈30 MB) from data.cdc.gov
   → Real diagnosed diabetes, hypertension, obesity prevalence for all US counties
2. Downloads Census ACS 5-year estimates (via Census API, no key required)
   → Real poverty rate, median income, uninsured rate, broadband access, etc.
3. Re-computes all 7 dimension scores from real data
4. Saves dimension_scores.parquet to data/scored/ (picked up by the dashboard)
5. Recalculates undiagnosed pool estimates using CDC-published undiagnosis rates:
   - T2D: 23.1% of all diabetes is undiagnosed (CDC NHANES 2017-2020)
   - HTN: ~20% of hypertension is uncontrolled/undiagnosed
   - Hypothyroidism: ~50% undiagnosed (ATA literature)

Data sources
------------
- CDC PLACES: https://www.cdc.gov/places/index.html
- Census ACS:  https://www.census.gov/programs-surveys/acs/
- HRSA HPSA:  https://data.hrsa.gov/topics/health-workforce/shortage-areas

Prerequisites
-------------
- Python packages: pandas, requests, pyarrow, scikit-learn
- Internet connection (downloads ~30–50 MB total)
- Existing counties.parquet (run `python3 run.py --skip-train` first if missing)
"""

import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR    = "data/synthetic"
OPEN_DIR    = "data/open"
SCORED_DIR  = "data/scored"


def main():
    t_start = time.time()
    log.info("=" * 60)
    log.info("  SPPF Real Data Ingestion")
    log.info("=" * 60)

    # ── 0. Load county list ───────────────────────────────────────────────────
    counties_path = Path(DATA_DIR) / "counties.parquet"
    if not counties_path.exists():
        log.error(
            f"counties.parquet not found at {counties_path}\n"
            "Run `python3 run.py --skip-train` first to generate synthetic county data."
        )
        sys.exit(1)

    import pandas as pd
    counties = pd.read_parquet(counties_path)
    log.info(f"Loaded {len(counties):,} counties from {counties_path}")

    # ── 1. Download + process CDC PLACES ─────────────────────────────────────
    log.info("\n--- Step 1: CDC PLACES ---")
    try:
        from src.ingestion.open_data.cdc_places import download as cdc_dl
        cdc = cdc_dl(cache_dir=OPEN_DIR, force=False)
        if cdc.empty:
            log.warning("CDC PLACES returned empty — will use synthetic fallback for disease burden")
        else:
            log.info(f"CDC PLACES: {len(cdc):,} counties, "
                     f"diabetes range {cdc['diabetes_prevalence_pct'].min()*100:.1f}%–"
                     f"{cdc['diabetes_prevalence_pct'].max()*100:.1f}%")
    except Exception as e:
        log.warning(f"CDC PLACES failed ({e}) — disease burden will use synthetic estimates")
        cdc = None

    # ── 2. Download Census ACS ────────────────────────────────────────────────
    log.info("\n--- Step 2: Census ACS 5-Year Estimates ---")
    try:
        from src.ingestion.open_data.census_acs import download as acs_dl
        acs = acs_dl(cache_dir=OPEN_DIR, force=False)
        if acs.empty:
            log.warning("Census ACS returned empty — will use synthetic SDoH fallback")
        else:
            log.info(f"Census ACS: {len(acs):,} counties, "
                     f"poverty range {acs['poverty_rate'].min()*100:.1f}%–"
                     f"{acs['poverty_rate'].max()*100:.1f}%")
    except Exception as e:
        log.warning(f"Census ACS failed ({e}) — SDoH will use synthetic estimates")
        acs = None

    # ── 3. Build panel + compute 7-dimension scores ───────────────────────────
    log.info("\n--- Step 3: Open Data Panel + 7-Dimension Scoring ---")
    from src.ingestion.open_data.data_loader import load_all
    panel = load_all(counties, cache_dir=OPEN_DIR, force_download=False)

    from src.features.dimension_scorer import compute_all_dimensions
    try:
        features_long = pd.read_parquet(Path(DATA_DIR) / "features_long.parquet")
        log.info("Using existing pipeline features for diagnosis gap + commercial readiness")
    except Exception:
        features_long = None
        log.info("No pipeline features found — using proxy estimates for all dimensions")

    dim_scores = compute_all_dimensions(panel, orig_signals=features_long)

    Path(SCORED_DIR).mkdir(parents=True, exist_ok=True)
    out_path = Path(SCORED_DIR) / "dimension_scores.parquet"
    dim_scores.to_parquet(out_path, index=False)

    # ── 4. Summary ────────────────────────────────────────────────────────────
    priority = int((dim_scores["opportunity_score"] >= 70).sum())
    emerging = int(((dim_scores["opportunity_score"] >= 40) & (dim_scores["opportunity_score"] < 70)).sum())
    developing = int((dim_scores["opportunity_score"] < 40).sum())

    log.info("\n" + "=" * 60)
    log.info("  INGESTION COMPLETE")
    log.info(f"  Elapsed:           {time.time() - t_start:.0f}s")
    log.info(f"  Counties scored:   {len(dim_scores):,}")
    log.info(f"  Priority (≥70):    {priority:,}")
    log.info(f"  Emerging (40-70):  {emerging:,}")
    log.info(f"  Developing (<40):  {developing:,}")
    log.info(f"  Output:            {out_path}")
    log.info("=" * 60)

    # Top 10 counties
    top10 = dim_scores.nlargest(10, "opportunity_score")[
        ["county_name", "state_name", "opportunity_score",
         "dim_disease_burden", "dim_diagnosis_gap",
         "recommended_intervention"]
    ]
    log.info(f"\nTop 10 Opportunity Counties (real data):\n{top10.to_string(index=False)}")

    # Data provenance note
    using_real_cdc = cdc is not None and not cdc.empty
    using_real_acs = acs is not None and not acs.empty
    log.info(
        f"\nData provenance:\n"
        f"  Disease burden:      {'✅ REAL (CDC PLACES)' if using_real_cdc else '⚠️  synthetic fallback'}\n"
        f"  Social determinants: {'✅ REAL (Census ACS)' if using_real_acs else '⚠️  synthetic fallback'}\n"
        f"  Access to care:      ⚠️  synthetic (HRSA HPSA — add manually if needed)\n"
        f"  Payer landscape:     ⚠️  synthetic (CMS MA data — add manually if needed)\n"
    )

    if not using_real_cdc:
        log.info(
            "\nTo use real CDC PLACES data:\n"
            "  1. Download from: https://data.cdc.gov/browse?category=500+Cities+%26+Places\n"
            "  2. Save CSV as:   data/open/cdc_places_raw.csv\n"
            "  3. Re-run:        python3 ingest_real_data.py"
        )

    log.info("\nDashboard ready. Launch with:")
    log.info("  python3 -m streamlit run src/output/dashboard.py")


if __name__ == "__main__":
    main()
