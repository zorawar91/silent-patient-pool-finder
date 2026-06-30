"""
M1 — Synthea CSV → PostgreSQL ingestion script.

Reads Synthea-generated CSVs from data/synthetic/csv/ and loads them
into the sppf PostgreSQL database.

Condition codes are mapped to our internal condition_group classification.
Lab observations are flagged as target labs (diagnostic orphan candidates).
Medications are classified as chronic vs symptom-adjacent.

Usage:
    poetry run python src/ingestion/ingest_synthea.py
    # or:
    make ingest
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path
from loguru import logger
from tqdm import tqdm

from config import get_engine, SYNTHEA_CSV

# ── Mappings ────────────────────────────────────────────────────────────────

# SNOMED codes → condition group (must match condition_codes table)
SNOMED_TO_GROUP: dict[str, str] = {
    "44054006":  "diabetes",
    "15777000":  "diabetes",
    "237599002": "diabetes",
    "59621000":  "hypertension",
    "1201005":   "hypertension",
    "40930008":  "thyroid",
    "83986005":  "thyroid",
    "414916001": "metabolic",
    "162864005": "metabolic",
}

# LOINC codes for target labs (diagnostic orphan candidates)
TARGET_LAB_LOINCS: set[str] = {
    "4548-4",    # HbA1c
    "17856-6",   # HbA1c (alternative)
    "1558-6",    # Fasting glucose
    "2345-7",    # Glucose
    "57698-3",   # Lipid panel
    "2093-3",    # Total cholesterol
    "3016-3",    # TSH
    "11580-8",   # TSH (alternative)
    "2089-1",    # LDL cholesterol
    "2085-9",    # HDL cholesterol
    "55284-4",   # Blood pressure panel
}

# RxNorm-based classification — keywords in description → rx_type
CHRONIC_RX_KEYWORDS = [
    "metformin", "insulin", "glipizide", "glimepiride", "sitagliptin",
    "lisinopril", "amlodipine", "atenolol", "losartan", "hydrochlorothiazide",
    "levothyroxine", "synthroid",
]
SYMPTOM_ADJACENT_KEYWORDS = [
    "metoclopramide", "pantoprazole", "omeprazole", "ranitidine",
    "ibuprofen", "naproxen", "acetaminophen",
    "vitamin b", "b12", "thiamine",
    "amlodipine",  # sometimes used symptomatically before HTN Dx
]


def classify_rx(description: str) -> str:
    desc = description.lower()
    if any(kw in desc for kw in CHRONIC_RX_KEYWORDS):
        return "chronic"
    if any(kw in desc for kw in SYMPTOM_ADJACENT_KEYWORDS):
        return "symptom_adjacent"
    return "other"


# ── Loaders ─────────────────────────────────────────────────────────────────

def load_patients(csv_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_dir / "patients.csv")
    df = df.rename(columns=str.upper)
    out = pd.DataFrame({
        "patient_id": df["ID"],
        "birth_date":  pd.to_datetime(df["BIRTHDATE"], errors="coerce").dt.date,
        "death_date":  pd.to_datetime(df["DEATHDATE"], errors="coerce").dt.date,
        "gender":      df["GENDER"].str[0].str.upper(),
        "race":        df["RACE"],
        "ethnicity":   df["ETHNICITY"],
        "city":        df["CITY"],
        "state":       df["STATE"],
        "zip":         df["ZIP"].astype(str).str.zfill(5),
        "lat":         pd.to_numeric(df["LAT"], errors="coerce"),
        "lon":         pd.to_numeric(df["LON"], errors="coerce"),
        "cohort":      None,  # assigned by simulate_otc.py
    })
    return out


def load_encounters(csv_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_dir / "encounters.csv")
    df = df.rename(columns=str.upper)
    out = pd.DataFrame({
        "encounter_id":    df["ID"],
        "patient_id":      df["PATIENT"],
        "start_ts":        pd.to_datetime(df["START"], errors="coerce"),
        "stop_ts":         pd.to_datetime(df["STOP"], errors="coerce"),
        "encounter_class": df["ENCOUNTERCLASS"],
        "code":            df["CODE"].astype(str),
        "description":     df["DESCRIPTION"],
        "reason_code":     df["REASONCODE"].astype(str),
        "reason_desc":     df["REASONDESCRIPTION"],
    })
    return out


def load_conditions(csv_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_dir / "conditions.csv")
    df = df.rename(columns=str.upper)
    out = pd.DataFrame({
        "patient_id":       df["PATIENT"],
        "encounter_id":     df["ENCOUNTER"],
        "start_date":       pd.to_datetime(df["START"], errors="coerce").dt.date,
        "stop_date":        pd.to_datetime(df["STOP"], errors="coerce").dt.date,
        "snomed_code":      df["CODE"].astype(str),
        "description":      df["DESCRIPTION"],
        "condition_group":  df["CODE"].astype(str).map(SNOMED_TO_GROUP),
    })
    return out


def load_medications(csv_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_dir / "medications.csv")
    df = df.rename(columns=str.upper)
    out = pd.DataFrame({
        "patient_id":    df["PATIENT"],
        "encounter_id":  df["ENCOUNTER"],
        "start_date":    pd.to_datetime(df["START"], errors="coerce").dt.date,
        "stop_date":     pd.to_datetime(df["STOP"], errors="coerce").dt.date,
        "rxnorm_code":   df["CODE"].astype(str),
        "description":   df["DESCRIPTION"],
        "dispenses":     pd.to_numeric(df["DISPENSES"], errors="coerce").fillna(1).astype(int),
        "reason_code":   df["REASONCODE"].astype(str),
        "reason_desc":   df["REASONDESCRIPTION"],
        "rx_type":       df["DESCRIPTION"].apply(classify_rx),
    })
    return out


def load_observations(csv_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_dir / "observations.csv")
    df = df.rename(columns=str.upper)
    out = pd.DataFrame({
        "patient_id":    df["PATIENT"],
        "encounter_id":  df["ENCOUNTER"],
        "obs_date":      pd.to_datetime(df["DATE"], errors="coerce").dt.date,
        "loinc_code":    df["CODE"].astype(str),
        "description":   df["DESCRIPTION"],
        "value":         df["VALUE"].astype(str),
        "units":         df["UNITS"].astype(str),
        "obs_type":      df["TYPE"],
        "is_target_lab": df["CODE"].astype(str).isin(TARGET_LAB_LOINCS),
    })
    return out


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    csv_dir = SYNTHEA_CSV

    if not csv_dir.exists():
        logger.error(
            f"Synthea CSV directory not found: {csv_dir}\n"
            "Run `make synthea-run` first to generate synthetic data."
        )
        raise SystemExit(1)

    engine = get_engine()

    steps = [
        ("patients",     load_patients,     "patients"),
        ("encounters",   load_encounters,   "encounters"),
        ("conditions",   load_conditions,   "conditions"),
        ("medications",  load_medications,  "medications"),
        ("observations", load_observations, "observations"),
    ]

    for label, loader_fn, table_name in tqdm(steps, desc="Ingesting Synthea CSVs"):
        logger.info(f"Loading {label}...")
        try:
            df = loader_fn(csv_dir)
            df.to_sql(
                table_name,
                engine,
                if_exists="append",
                index=False,
                chunksize=5000,
                method="multi",
            )
            logger.success(f"  {label}: {len(df):,} rows → {table_name}")
        except FileNotFoundError:
            logger.warning(f"  {label}: CSV not found — skipping")

    logger.success("Synthea ingestion complete.")


if __name__ == "__main__":
    main()
