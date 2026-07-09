"""
M1 — Synthetic OTC pharmacy transaction simulator.

Reads the ingested Synthea patients + conditions tables and generates
realistic OTC pharmacy transaction histories for three cohorts:

  1. diagnosed   — patients WITH a formal diabetes/hypertension/thyroid
                   condition record. OTC proxy purchases generated going
                   back up to 18 months before their diagnosis date.
                   These serve as POSITIVE training labels.

  2. silent      — patients WITHOUT a formal diagnosis but assigned OTC
                   proxy purchase patterns similar to pre-diagnosis
                   patients. These simulate the real-world undiagnosed pool.
                   They also serve as POSITIVE training labels (at inference
                   time we don't know their true status).

  3. control     — patients with no relevant conditions and random,
                   unrelated OTC purchases. NEGATIVE training labels.

The cohort label is written back to the patients.cohort column.

Usage:
    poetry run python src/ingestion/simulate_otc.py
    # or:
    make simulate
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import text
from tqdm import tqdm

from config import get_engine

# ── Constants ───────────────────────────────────────────────────────────────

random.seed(42)
np.random.seed(42)

# Conditions that make a patient "diagnosed" for our purposes
TARGET_CONDITION_GROUPS = {"diabetes", "hypertension", "thyroid"}

# OTC product codes by condition (from otc_proxy_products table)
OTC_BY_CONDITION: dict[str, list[str]] = {
    "diabetes":    ["OTC-GLU-001", "OTC-GLU-002", "OTC-GLU-003", "OTC-DM-001",
                    "OTC-DM-002", "OTC-DM-003", "OTC-DM-004", "OTC-DM-005",
                    "OTC-DM-006", "OTC-DM-007", "OTC-DM-008", "OTC-DM-009"],
    "hypertension": ["OTC-HTN-001", "OTC-HTN-002", "OTC-HTN-003", "OTC-HTN-004",
                     "OTC-HTN-005", "OTC-HTN-006", "OTC-HTN-007", "OTC-HTN-008",
                     "OTC-HTN-009"],
    "thyroid":     ["OTC-THY-001", "OTC-THY-002", "OTC-THY-003", "OTC-THY-004",
                    "OTC-THY-005", "OTC-THY-006", "OTC-THY-007"],
}

# Unrelated OTC products for control cohort
UNRELATED_OTC = [
    "OTC-CTRL-001", "OTC-CTRL-002", "OTC-CTRL-003",
    "OTC-CTRL-004", "OTC-CTRL-005",
]

# What fraction of "no-diagnosis" patients become the "silent" cohort
SILENT_FRACTION = 0.30


# ── Helpers ─────────────────────────────────────────────────────────────────

def random_dates_before(
    anchor_date: date,
    n: int,
    months_back: int = 18,
) -> list[date]:
    """Return n random dates in the window [anchor - months_back, anchor)."""
    start = anchor_date - timedelta(days=months_back * 30)
    delta = (anchor_date - start).days
    return [start + timedelta(days=random.randint(0, delta - 1)) for _ in range(n)]


def random_dates_around(
    center_date: date,
    n: int,
    window_months: int = 12,
) -> list[date]:
    """Return n dates scattered around center_date ±window_months."""
    start = center_date - timedelta(days=window_months * 30)
    end   = center_date + timedelta(days=window_months * 30)
    delta = (end - start).days
    return [start + timedelta(days=random.randint(0, delta)) for _ in range(n)]


def months_between(d1: date, d2: date) -> int:
    return (d2.year - d1.year) * 12 + d2.month - d1.month


def generate_otc_for_patient(
    patient_id: str,
    zip_code: str,
    condition_group: str,
    diagnosis_date: date | None,
    cohort: str,
    n_transactions: int = 8,
) -> list[dict]:
    """Generate OTC transaction rows for a single patient."""
    products = OTC_BY_CONDITION.get(condition_group, [])
    if not products:
        return []

    rows = []

    if cohort == "diagnosed" and diagnosis_date:
        tx_dates = random_dates_before(diagnosis_date, n_transactions)
    elif cohort == "silent":
        # Silent patients: random anchor in last 2 years
        anchor = date.today() - timedelta(days=random.randint(0, 730))
        tx_dates = random_dates_around(anchor, n_transactions)
        diagnosis_date = None
    else:
        return []  # control — handled separately

    for tx_date in tx_dates:
        product = random.choice(products)
        rows.append({
            "patient_id":         patient_id,
            "transaction_date":   tx_date,
            "product_code":       product,
            "quantity":           random.randint(1, 3),
            "zip":                zip_code,
            "months_to_diagnosis": (
                months_between(tx_date, diagnosis_date) if diagnosis_date else None
            ),
        })
    return rows


def generate_control_otc(
    patient_id: str,
    zip_code: str,
    n_transactions: int = 4,
) -> list[dict]:
    """Generate random, unrelated OTC transactions for control patients."""
    anchor = date.today() - timedelta(days=random.randint(90, 730))
    tx_dates = random_dates_around(anchor, n_transactions, window_months=6)
    rows = []
    for tx_date in tx_dates:
        rows.append({
            "patient_id":          patient_id,
            "transaction_date":    tx_date,
            "product_code":        None,   # no proxy product — unrelated
            "quantity":            random.randint(1, 2),
            "zip":                 zip_code,
            "months_to_diagnosis": None,
        })
    return rows


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    engine = get_engine()

    with engine.connect() as conn:
        # Load all patients
        patients_df = pd.read_sql("SELECT patient_id, zip FROM patients", conn)

        # Load earliest target condition per patient
        conditions_df = pd.read_sql(
            """
            SELECT patient_id, condition_group, MIN(start_date) AS diagnosis_date
            FROM   conditions
            WHERE  condition_group = ANY(ARRAY['diabetes','hypertension','thyroid'])
            GROUP BY patient_id, condition_group
            """,
            conn,
        )

    # Merge
    merged = patients_df.merge(conditions_df, on="patient_id", how="left")
    diagnosed_mask = merged["condition_group"].notna()

    diagnosed_df  = merged[diagnosed_mask].copy()
    no_diag_df    = merged[~diagnosed_mask].copy()

    # Split no-diagnosis patients into silent + control
    silent_n = int(len(no_diag_df) * SILENT_FRACTION)
    silent_idx = no_diag_df.sample(n=silent_n, random_state=42).index

    no_diag_df["cohort"] = "control"
    no_diag_df.loc[silent_idx, "cohort"] = "silent"
    diagnosed_df["cohort"] = "diagnosed"

    # Pick a random condition group for silent patients (mirrors prevalence)
    condition_groups = diagnosed_df["condition_group"].value_counts(normalize=True)
    no_diag_df.loc[silent_idx, "condition_group"] = np.random.choice(
        condition_groups.index,
        size=silent_n,
        p=condition_groups.values,
    )

    logger.info(
        f"Cohorts — diagnosed: {len(diagnosed_df):,} | "
        f"silent: {silent_n:,} | control: {len(no_diag_df) - silent_n:,}"
    )

    # ── Generate OTC transactions ──────────────────────────
    all_transactions: list[dict] = []

    for _, row in tqdm(diagnosed_df.iterrows(), total=len(diagnosed_df), desc="Diagnosed OTC"):
        txns = generate_otc_for_patient(
            patient_id=row["patient_id"],
            zip_code=str(row["zip"]),
            condition_group=row["condition_group"],
            diagnosis_date=row["diagnosis_date"],
            cohort="diagnosed",
            n_transactions=random.randint(5, 15),
        )
        all_transactions.extend(txns)

    for _, row in tqdm(no_diag_df[no_diag_df.cohort == "silent"].iterrows(),
                       total=silent_n, desc="Silent OTC"):
        txns = generate_otc_for_patient(
            patient_id=row["patient_id"],
            zip_code=str(row["zip"]),
            condition_group=row["condition_group"],
            diagnosis_date=None,
            cohort="silent",
            n_transactions=random.randint(4, 12),
        )
        all_transactions.extend(txns)

    for _, row in tqdm(no_diag_df[no_diag_df.cohort == "control"].iterrows(),
                       total=len(no_diag_df) - silent_n, desc="Control OTC"):
        txns = generate_control_otc(
            patient_id=row["patient_id"],
            zip_code=str(row["zip"]),
            n_transactions=random.randint(2, 6),
        )
        all_transactions.extend(txns)

    # ── Write to DB ───────────────────────────────────────
    otc_df = pd.DataFrame(all_transactions)
    # Drop control rows with no product_code (unrelated OTC — we track as nulls)
    with engine.begin() as conn:
        otc_df.to_sql("otc_transactions", conn, if_exists="append",
                      index=False, chunksize=5000, method="multi")
        logger.success(f"OTC transactions inserted: {len(otc_df):,} rows")

        # Write cohort labels back to patients table
        all_patients = pd.concat([diagnosed_df, no_diag_df])[["patient_id", "cohort"]]
        for _, row in all_patients.iterrows():
            conn.execute(
                text("UPDATE patients SET cohort = :cohort WHERE patient_id = :pid"),
                {"cohort": row["cohort"], "pid": row["patient_id"]},
            )
        logger.success("Cohort labels written to patients table")

    # ── Summary ───────────────────────────────────────────
    with engine.connect() as conn:
        summary = pd.read_sql(
            "SELECT cohort, COUNT(*) AS n FROM patients GROUP BY cohort ORDER BY cohort",
            conn,
        )
    logger.success(f"\n{summary.to_string(index=False)}")
    logger.success("OTC simulation complete.")


if __name__ == "__main__":
    main()
