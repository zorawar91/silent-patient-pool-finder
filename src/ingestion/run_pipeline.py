"""
M1 — Full pipeline runner.

Runs ingestion + OTC simulation in sequence with logging.
Equivalent to `make pipeline` but runnable directly.

Usage:
    poetry run python src/ingestion/run_pipeline.py
"""

from loguru import logger
import sys

def main():
    logger.info("=" * 60)
    logger.info("Silent Patient Pool Finder — M1 Pipeline")
    logger.info("=" * 60)

    # Step 1: Ingest Synthea CSVs
    logger.info("\n[1/2] Ingesting Synthea CSVs...")
    try:
        import ingest_synthea
        ingest_synthea.main()
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)

    # Step 2: Simulate OTC transactions
    logger.info("\n[2/2] Simulating OTC transactions...")
    try:
        import simulate_otc
        simulate_otc.main()
    except Exception as e:
        logger.error(f"OTC simulation failed: {e}")
        sys.exit(1)

    logger.info("\n" + "=" * 60)
    logger.success("M1 Pipeline complete.")
    logger.info(
        "Next step: M2 — Feature engineering\n"
        "  Run: poetry run python src/features/compute_signals.py"
    )


if __name__ == "__main__":
    main()
