"""Regression tests for the CMS catalog dataset resolution (ingest_hcp_data)."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_spec = importlib.util.spec_from_file_location(
    "ihd", Path(__file__).resolve().parents[1] / "ingest_hcp_data.py")
ihd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ihd)

# Mimics the real data.cms.gov data.json structure, including BOTH production
# traps: a similarly-titled wrong dataset, and placeholder "default" hosts.
MOCK_CATALOG = {
    "dataset": [
        {
            "title": "Medicare Physician & Other Practitioners - by Provider and Service",
            "distribution": [
                {"title": "…by Provider and Service : 2023-01-01",
                 "accessURL": "https://default/data-api/v1/dataset/fb6d9fe8-38c1-4d24-83d4-0b7b291000b2/data"},
            ],
        },
        {
            "title": "Medicare Physician & Other Practitioners - by Provider",
            "distribution": [
                {"title": "Medicare Physician & Other Practitioners - by Provider : 2021-01-01",
                 "accessURL": "https://default/data-api/v1/dataset/aaaaaaaa-1111-2222-3333-444444444444/data"},
                {"title": "Medicare Physician & Other Practitioners - by Provider : 2023-01-01",
                 "accessURL": "https://default/data-api/v1/dataset/bbbbbbbb-5555-6666-7777-888888888888/data"},
            ],
        },
        {
            "title": "Medicare Physician & Other Practitioners - by Geography and Service",
            "distribution": [
                {"title": "…by Geography : 2023-01-01",
                 "accessURL": "https://default/data-api/v1/dataset/cccccccc-9999-0000-1111-222222222222/data"},
            ],
        },
    ]
}


def _mock_get(*a, **k):
    fake = MagicMock()
    fake.raise_for_status = lambda: None
    fake.json = lambda: MOCK_CATALOG
    return fake


def test_resolves_exact_dataset_latest_year_real_host():
    with patch.object(ihd.requests, "get", _mock_get):
        url = ihd._resolve_dataset_url()
    # Correct dataset (NOT "and Service"), latest year, host rebuilt
    assert url == ("https://data.cms.gov/data-api/v1/dataset/"
                   "bbbbbbbb-5555-6666-7777-888888888888/data.csv")


def test_missing_dataset_returns_none():
    with patch.object(ihd.requests, "get", _mock_get):
        old = ihd.DATASET_TITLE
        ihd.DATASET_TITLE = "nonexistent dataset"
        try:
            assert ihd._resolve_dataset_url() is None
        finally:
            ihd.DATASET_TITLE = old
