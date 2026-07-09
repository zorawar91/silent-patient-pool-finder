"""Provenance module tests — must degrade gracefully with missing files."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.quality.provenance import (
    SOURCE_REGISTRY, build_output_provenance, build_provenance,
)


def test_missing_files_reported_not_crashed(tmp_path):
    """Empty base dir → every source 'missing', nothing raises."""
    src = build_provenance(base=tmp_path)
    assert len(src) == len(SOURCE_REGISTRY)
    assert (src["status"] == "❌ missing").all()
    out = build_output_provenance(base=tmp_path)
    assert (out["status"] == "❌ not generated").all()


def test_live_file_coverage_counted(tmp_path):
    """A real parquet with a marker column reports non-null coverage."""
    open_dir = tmp_path / "data" / "open"
    open_dir.mkdir(parents=True)
    df = pd.DataFrame({
        "county_fips": ["01001", "01003", "01005"],
        "diabetes_prevalence_pct": [11.2, None, 9.8],
    })
    df.to_parquet(open_dir / "cdc_places_county.parquet", index=False)
    src = build_provenance(base=tmp_path).set_index("source")
    row = src.loc["PLACES County Health Data"]
    assert row["status"] == "✅ live"
    assert row["rows"] == 3
    assert row["coverage"] == 2   # marker non-null count, not row count


def test_case_insensitive_marker(tmp_path):
    """Raw CMS files keep CamelCase headers — marker lookup must still work."""
    open_dir = tmp_path / "data" / "open"
    open_dir.mkdir(parents=True)
    pd.DataFrame({"Rndrng_NPI": ["1"] * 4, "Tot_Benes": [100, 200, None, 300]}) \
        .to_parquet(open_dir / "cms_providers.parquet", index=False)
    src = build_provenance(base=tmp_path).set_index("source")
    assert src.loc["Medicare Physician & Other Practitioners", "coverage"] == 3
