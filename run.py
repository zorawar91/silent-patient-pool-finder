"""
Silent Patient Pool Finder — Pipeline Orchestrator
===================================================
Single entry point for the full pipeline.

Usage:
    python run.py                        # Full pipeline, US, all conditions
    python run.py --country us           # Explicit country
    python run.py --skip-data            # Skip data generation (use existing)
    python run.py --skip-train           # Skip training (use existing models)
    python run.py --dashboard            # Launch dashboard after scoring

Steps:
    1. Generate synthetic data (M1)
    2. Compute feature signals (M2)
    3. Train XGBoost scoring models (M3)
    4. Score all counties → Geography Risk Score (M3)
    5. Launch Streamlit dashboard (M4) — optional
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
    launch_dashboard: bool = False,
):
    country_config = f"config/{country}.yaml"
    conditions_config = "config/conditions.yaml"
    data_dir = "data/synthetic"
    model_dir = "data/models"
    scored_dir = "data/scored"

    # Validate configs exist
    for path in [country_config, conditions_config]:
        if not Path(path).exists():
            log.error(f"Config not found: {path}")
            sys.exit(1)

    total_steps = 4 + (1 if launch_dashboard else 0)

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
    # Step 2: Feature Engineering
    # ------------------------------------------------------------------
    banner("Feature Engineering", 2, total_steps)
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
    # Step 3: Model Training
    # ------------------------------------------------------------------
    if not skip_train:
        banner("Model Training (XGBoost + SHAP)", 3, total_steps)
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
    # Step 4: Scoring
    # ------------------------------------------------------------------
    banner("Geography Risk Scoring", 4, total_steps)
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

    # Top 10 preview
    score_col = "overall_risk_score"
    preview = scores[["county_name", "state_name", "overall_risk_score",
                       "total_estimated_pool"]].head(10)
    log.info(f"\nTop 10 opportunity counties:\n{preview.to_string(index=False)}")

    # ------------------------------------------------------------------
    # Step 5: Dashboard (optional)
    # ------------------------------------------------------------------
    if launch_dashboard:
        banner("Launching Streamlit Dashboard", 5, total_steps)
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
        "--dashboard", action="store_true",
        help="Launch Streamlit dashboard after pipeline completes"
    )

    args = parser.parse_args()
    run_pipeline(
        country=args.country,
        skip_data=args.skip_data,
        skip_train=args.skip_train,
        launch_dashboard=args.dashboard,
    )


if __name__ == "__main__":
    main()
