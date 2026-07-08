"""
Unit tests for ingestion helpers.
Run with: poetry run pytest tests/ -v
"""

import sys
from pathlib import Path
from datetime import date

import pandas as pd
import pytest

# Legacy synthetic (Synthea) pipeline tests — superseded by the real-data
# pipeline. Skip cleanly when its optional deps are absent instead of
# breaking collection for the whole suite.
pytest.importorskip("loguru", reason="legacy synthetic pipeline deps not installed")

# Allow importing from src/ingestion without installing
sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "ingestion"))

from ingest_synthea import classify_rx, SNOMED_TO_GROUP, TARGET_LAB_LOINCS
from simulate_otc import (
    random_dates_before,
    random_dates_around,
    months_between,
    generate_otc_for_patient,
)


# ── ingest_synthea ────────────────────────────────────────────────────────────

class TestClassifyRx:
    def test_metformin_is_chronic(self):
        assert classify_rx("Metformin 500 MG Oral Tablet") == "chronic"

    def test_lisinopril_is_chronic(self):
        assert classify_rx("Lisinopril 10 MG Oral Tablet") == "chronic"

    def test_omeprazole_is_symptom_adjacent(self):
        assert classify_rx("Omeprazole 20 MG Oral Capsule") == "symptom_adjacent"

    def test_unknown_is_other(self):
        assert classify_rx("Amoxicillin 500 MG Capsule") == "other"

    def test_case_insensitive(self):
        assert classify_rx("METFORMIN 1000MG") == "chronic"


class TestSnomedMapping:
    def test_type2_diabetes_maps_to_diabetes(self):
        assert SNOMED_TO_GROUP["44054006"] == "diabetes"

    def test_hypertension_maps_correctly(self):
        assert SNOMED_TO_GROUP["59621000"] == "hypertension"

    def test_hypothyroidism_maps_correctly(self):
        assert SNOMED_TO_GROUP["40930008"] == "thyroid"


class TestTargetLabs:
    def test_hba1c_is_target(self):
        assert "4548-4" in TARGET_LAB_LOINCS

    def test_tsh_is_target(self):
        assert "3016-3" in TARGET_LAB_LOINCS

    def test_random_loinc_not_target(self):
        assert "99999-9" not in TARGET_LAB_LOINCS


# ── simulate_otc ─────────────────────────────────────────────────────────────

class TestDateHelpers:
    def test_random_dates_before_all_before_anchor(self):
        anchor = date(2023, 6, 15)
        dates = random_dates_before(anchor, n=20, months_back=12)
        assert all(d < anchor for d in dates)

    def test_random_dates_before_count(self):
        anchor = date(2023, 6, 15)
        dates = random_dates_before(anchor, n=10)
        assert len(dates) == 10

    def test_months_between_positive(self):
        assert months_between(date(2022, 1, 1), date(2023, 1, 1)) == 12

    def test_months_between_zero(self):
        assert months_between(date(2022, 6, 1), date(2022, 6, 1)) == 0


class TestGenerateOtc:
    def test_diagnosed_generates_rows(self):
        rows = generate_otc_for_patient(
            patient_id="test-uuid",
            zip_code="02101",
            condition_group="diabetes",
            diagnosis_date=date(2022, 6, 1),
            cohort="diagnosed",
            n_transactions=5,
        )
        assert len(rows) == 5
        assert all(r["transaction_date"] < date(2022, 6, 1) for r in rows)

    def test_all_rows_have_required_keys(self):
        rows = generate_otc_for_patient(
            patient_id="test-uuid",
            zip_code="02101",
            condition_group="hypertension",
            diagnosis_date=date(2023, 1, 1),
            cohort="diagnosed",
            n_transactions=3,
        )
        required = {"patient_id", "transaction_date", "product_code", "quantity", "zip"}
        for row in rows:
            assert required.issubset(row.keys())

    def test_control_returns_empty(self):
        rows = generate_otc_for_patient(
            patient_id="test-uuid",
            zip_code="02101",
            condition_group="diabetes",
            diagnosis_date=None,
            cohort="control",
        )
        assert rows == []

    def test_silent_has_no_diagnosis_date_in_rows(self):
        rows = generate_otc_for_patient(
            patient_id="test-uuid",
            zip_code="02101",
            condition_group="thyroid",
            diagnosis_date=None,
            cohort="silent",
            n_transactions=4,
        )
        assert all(r["months_to_diagnosis"] is None for r in rows)
