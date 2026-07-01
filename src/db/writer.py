from __future__ import annotations
# Pipeline DB writer — pushes all generated DataFrames to Neon (PostgreSQL).
# Called from run.py with --db flag after the scoring step completes.
#
# Each run does a full replace (if_exists="replace") so the DB always reflects
# the latest synthetic run. In production, swap to upsert / partitioned tables.

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Mapping: table_name → parquet file path relative to data_dir or scored_dir
SYNTHETIC_TABLES = {
    "counties":     ("synthetic", "counties.parquet"),
    "ground_truth": ("synthetic", "ground_truth.parquet"),
    "otc_signals":  ("synthetic", "otc_signals.parquet"),
    "lab_signals":  ("synthetic", "lab_signals.parquet"),
    "hcp_signals":  ("synthetic", "hcp_signals.parquet"),
    "geo_burden":   ("synthetic", "geo_burden.parquet"),
    "features_long":("synthetic", "features_long.parquet"),
    "features_wide":("synthetic", "features_wide.parquet"),
}

SCORED_TABLES = {
    "scores":            ("scored", "scores.parquet"),
    "scores_long":       ("scored", "scores_long.parquet"),
    "dimension_scores":  ("scored", "dimension_scores.parquet"),
}


def write_all_to_db(
    engine,
    data_dir: str = "data/synthetic",
    scored_dir: str = "data/scored",
) -> None:
    """
    Write every pipeline output to Neon.
    Replaces tables on each run — safe for synthetic / dev data.
    """
    base = Path("data")
    dirs = {"synthetic": Path(data_dir), "scored": Path(scored_dir)}

    all_tables = {**SYNTHETIC_TABLES, **SCORED_TABLES}
    total = 0

    for table, (kind, fname) in all_tables.items():
        path = dirs[kind] / fname
        if not path.exists():
            log.warning(f"  Skipping {table} — {path} not found.")
            continue
        df = pd.read_parquet(path)
        _write(df, table, engine)
        total += len(df)
        log.info(f"  ✓ {table}: {len(df):,} rows")

    log.info(f"DB write complete — {total:,} total rows across {len(all_tables)} tables.")


def _write(df: pd.DataFrame, table: str, engine) -> None:
    """Write a DataFrame to a Postgres table, replacing existing data."""
    # Boolean columns must be cast — Postgres is strict
    for col in df.select_dtypes(include="bool").columns:
        df[col] = df[col].astype(bool)

    df.to_sql(
        table,
        con=engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )
