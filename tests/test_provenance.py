"""Provenance module tests — must degrade gracefully with missing files."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.quality.provenance import (
    OPEN_DIR, SCORED_DIR, SOURCE_REGISTRY, build_output_provenance,
    build_provenance, capture_source_coverage, load_source_coverage,
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


# ── Observed-coverage manifest (deployments don't ship data/open/) ────────────

def _seed_cache(base: Path, spec, n_rows: int, n_observed: int) -> None:
    """Write a raw cache whose marker column is observed for n_observed rows."""
    (base / OPEN_DIR).mkdir(parents=True, exist_ok=True)
    col = spec.marker or "value"
    vals = [1.0] * n_observed + [None] * (n_rows - n_observed)
    pd.DataFrame({col: vals}).to_parquet(base / OPEN_DIR / spec.filename, index=False)


def test_capture_records_observed_not_row_count(tmp_path):
    spec = SOURCE_REGISTRY[0]                      # CDC PLACES, has a marker
    _seed_cache(tmp_path, spec, n_rows=3_144, n_observed=2_956)
    m = capture_source_coverage(base=tmp_path)
    assert m[spec.filename]["rows"] == 3_144
    assert m[spec.filename]["observed"] == 2_956   # imputation-free truth


def test_manifest_gives_exact_coverage_when_cache_absent(tmp_path):
    """The deployment case: no data/open/, but the committed manifest is there."""
    spec = SOURCE_REGISTRY[0]
    _seed_cache(tmp_path, spec, n_rows=3_144, n_observed=2_956)
    capture_source_coverage(base=tmp_path)
    (tmp_path / OPEN_DIR / spec.filename).unlink()          # deployment has no caches

    row = build_provenance(base=tmp_path).iloc[0]
    assert row["status"] == "✅ observed"
    assert row["coverage"] == 2_956
    assert not row["post_fill"], "exact figure must not be flagged an upper bound"


def test_post_fill_fallback_is_flagged_as_upper_bound(tmp_path):
    """With neither cache nor manifest, counting imputed scored data is allowed
    but must be marked so it is never read as observed coverage."""
    spec = SOURCE_REGISTRY[0]
    scored_file, col = spec.scored_marker
    (tmp_path / SCORED_DIR).mkdir(parents=True, exist_ok=True)
    pd.DataFrame({col: [1.0] * 3_144}).to_parquet(
        tmp_path / SCORED_DIR / scored_file, index=False)

    row = build_provenance(base=tmp_path).iloc[0]
    assert row["status"] == "✅ in scored data"
    assert bool(row["post_fill"])   # numpy bool from pandas
    assert "upper bound" in row["notes"]


def test_capture_merges_and_does_not_drop_other_pipelines(tmp_path):
    """Re-running one ingest must not erase coverage captured by another."""
    county, hcp = SOURCE_REGISTRY[0], SOURCE_REGISTRY[-1]
    _seed_cache(tmp_path, hcp, n_rows=500, n_observed=500)
    capture_source_coverage(base=tmp_path)
    (tmp_path / OPEN_DIR / hcp.filename).unlink()           # only county cache present now
    _seed_cache(tmp_path, county, n_rows=100, n_observed=90)
    m = capture_source_coverage(base=tmp_path)
    assert hcp.filename in m, "earlier pipeline's entry was dropped"
    assert m[county.filename]["observed"] == 90


def test_raw_cache_wins_over_manifest(tmp_path):
    """A present cache is the freshest truth and must take precedence."""
    spec = SOURCE_REGISTRY[0]
    _seed_cache(tmp_path, spec, n_rows=100, n_observed=10)
    capture_source_coverage(base=tmp_path)
    _seed_cache(tmp_path, spec, n_rows=100, n_observed=77)  # cache refreshed, manifest stale
    row = build_provenance(base=tmp_path).iloc[0]
    assert row["status"] == "✅ live"
    assert row["coverage"] == 77


def test_load_missing_manifest_is_empty_not_error(tmp_path):
    assert load_source_coverage(base=tmp_path) == {}
