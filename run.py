from __future__ import annotations
"""
Silent Patient Pool Finder — Pipeline Orchestrator
===================================================
Single entry point for the full pipeline.

Usage:
    python run.py                        # Full pipeline, US, all conditions
    python run.py --country us           # Explicit country
    python run.py --skip-data            # Skip data generation (use existing)
    python run.py --skip-train           # Skip model training (use existing)
    python run.py --skip-open-data       # Skip open data download (use cache)
    python run.py --db                   # Write all outputs to Neon after scoring
    python run.py --dashboard            # Launch dashboard after scoring

Steps:
    1. Generate synthetic data (M1)
    2. Load open data + compute 7-dimension scores (NEW)
    3. Compute feature signals (M2)
    4. Train XGBoost scoring models (M3)
    5. Score all counties → Geography Risk Score + Opportunity Score (M3)
    6. Write to Neon DB (optional, --db)
    7. Launch Streamlit dashboard (M4, optional, --dashboard)
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def banner(step: str, n: int, total: int):
    log.info(f"{'='*60}")
    log.info(f"  STEP {n}/{total}: {step}")
    log.info(f"{'='*60}")


def run_pipeline(
    country: str = "us",
    skip_data: bool = False,
    skip_train: bool = False,
    skip_open_data: bool = False,
    write_db: bool = False,
    launch_dashboard: bool = False,
):
    country_config = f"config/{country}.yaml"
    conditions_config = "config/conditions.yaml"
    data_dir = "data/synthetic"
    open_data_dir = "data/open"
    model_dir = "data/models"
    scored_dir = "data/scored"

    # Validate configs exist
    for path in [country_config, conditions_config]:
        if not Path(path).exists():
            log.error(f"Config not found: {path}")
            sys.exit(1)

    total_steps = 5 + (1 if write_db else 0) + (1 if launch_dashboard else 0)

    # ------------------------------------------------------------------
    # Step 1: Synthetic Data Generation
    # ------------------------------------------------------------------
    if not skip_data:
        banner("Synthetic Data Generation", 1, total_steps)
        t0 = time.time()
        from src.ingestion.synthetic_generator import run as gen_run
        gen_run(
            country_config_path=country_config,
            conditions_config_path=conditions_config,
            output_dir=data_dir,
        )
        log.info(f"✓ Data generation complete ({time.time()-t0:.1f}s)")
    else:
        log.info("Skipping data generation (--skip-data)")

    # ------------------------------------------------------------------
    # Step 2: Open Data + 7-Dimension Scoring
    # ------------------------------------------------------------------
    dim_scores_path = Path(scored_dir) / "dimension_scores.parquet"
    if not skip_open_data or not dim_scores_path.exists():
        banner("Open Data Download + 7-Dimension Scoring", 2, total_steps)
        t0 = time.time()
        try:
            import pandas as pd
            counties = pd.read_parquet(Path(data_dir) / "counties.parquet")
            from src.ingestion.open_data.data_loader import load_all
            panel = load_all(counties, cache_dir=open_data_dir,
                             force_download=(not skip_open_data))
            from src.features.dimension_scorer import compute_all_dimensions
            try:
                features_long = pd.read_parquet(Path(data_dir) / "features_long.parquet")
            except Exception:
                features_long = None
            dim_scores = compute_all_dimensions(panel, orig_signals=features_long)
            Path(scored_dir).mkdir(parents=True, exist_ok=True)
            dim_scores.to_parquet(dim_scores_path, index=False)
            log.info(f"✓ 7-dimension scoring complete ({time.time()-t0:.1f}s)")
            log.info(f"  Priority counties (score≥55): {(dim_scores['opportunity_score'] >= 55).sum()}")
        except Exception:
            # Keep the legacy pipeline usable without open data, but make the
            # degradation impossible to miss: full traceback + banner warning.
            log.exception("Open data / dimension scoring FAILED — "
                          "dimension_scores.parquet was NOT refreshed.")
            log.warning("=" * 60)
            log.warning("  CONTINUING WITH DEGRADED OUTPUT (no 7-dimension scores)")
            log.warning("=" * 60)
    else:
        log.info("Skipping open data download (--skip-open-data and cache exists)")

    # ------------------------------------------------------------------
    # Step 3: Feature Engineering
    # ------------------------------------------------------------------
    banner("Feature Engineering", 3, total_steps)
    t0 = time.time()
    from src.features.signals import run as feat_run
    feat_run(
        data_dir=data_dir,
        country_config_path=country_config,
        conditions_config_path=conditions_config,
        output_dir=data_dir,
    )
    log.info(f"✓ Feature engineering complete ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    # Step 4: Model Training
    # ------------------------------------------------------------------
    if not skip_train:
        banner("Model Training (XGBoost + SHAP)", 4, total_steps)
        t0 = time.time()
        from src.model.train import run as train_run
        train_run(
            data_dir=data_dir,
            model_dir=model_dir,
            country_config_path=country_config,
            conditions_config_path=conditions_config,
        )
        log.info(f"✓ Training complete ({time.time()-t0:.1f}s)")
    else:
        log.info("Skipping training (--skip-train)")

    # ------------------------------------------------------------------
    # Step 5: Scoring
    # ------------------------------------------------------------------
    banner("Geography Risk Scoring + Opportunity Score", 5, total_steps)
    t0 = time.time()
    from src.model.score import run as score_run
    scores = score_run(
        data_dir=data_dir,
        model_dir=model_dir,
        output_dir=scored_dir,
        country_config_path=country_config,
        conditions_config_path=conditions_config,
    )
    log.info(f"✓ Scoring complete ({time.time()-t0:.1f}s)")

    # Summary
    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info(f"  Scored counties:      {len(scores):,}")
    log.info(f"  Opportunity table:    {scored_dir}/opportunity_table.csv")
    log.info(f"  Full scores:          {scored_dir}/scores.parquet")
    log.info("=" * 60)

    preview = scores[["county_name", "state_name", "overall_risk_score",
                       "total_estimated_pool"]].head(10)
    log.info(f"\nTop 10 opportunity counties:\n{preview.to_string(index=False)}")

    # ------------------------------------------------------------------
    # Step 6: Write to Neon (optional)
    # ------------------------------------------------------------------
    if write_db:
        step_n = 6
        banner("Writing All Data to Neon (PostgreSQL)", step_n, total_steps)
        t0 = time.time()
        from src.db.connection import get_engine
        from src.db.writer import write_all_to_db

        engine = get_engine()
        if engine is None:
            log.error(
                "No database URL found. Set NEON_DATABASE_URL in your environment "
                "or in .streamlit/secrets.toml before running --db."
            )
            sys.exit(1)

        write_all_to_db(engine, data_dir=data_dir, scored_dir=scored_dir)
        log.info(f"✓ Neon write complete ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    # Step 6: Dashboard (optional)
    # ------------------------------------------------------------------
    if launch_dashboard:
        step_n = total_steps
        banner("Launching Streamlit Dashboard", step_n, total_steps)
        log.info("Dashboard: http://localhost:8501")
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "src/output/dashboard.py"],
            check=True,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Silent Patient Pool Finder — Pipeline Orchestrator"
    )
    parser.add_argument(
        "--country", default="us",
        help="Country code (must match config/<country>.yaml). Default: us"
    )
    parser.add_argument(
        "--skip-data", action="store_true",
        help="Skip synthetic data generation (use existing data)"
    )
    parser.add_argument(
        "--skip-train", action="store_true",
        help="Skip model training (use existing models)"
    )
    parser.add_argument(
        "--skip-open-data", action="store_true",
        help="Skip open data re-download (use cached files if available)"
    )
    parser.add_argument(
        "--db", action="store_true",
        help="Write all pipeline outputs to Neon after scoring"
    )
    parser.add_argument(
        "--dashboard", action="store_true",
        help="Launch Streamlit dashboard after pipeline completes"
    )

    args = parser.parse_args()
    run_pipeline(
        country=args.country,
        skip_data=args.skip_data,
        skip_train=args.skip_train,
        skip_open_data=args.skip_open_data,
        write_db=args.db,
        launch_dashboard=args.dashboard,
    )


if __name__ == "__main__":
    main()
