from __future__ import annotations
"""
Data Provenance — source registry + live inspection.
=====================================================
Answers the first question every pharma analytics reviewer asks:
"where exactly does each number come from, how fresh is it, and how much
of the country does it actually cover?"

Everything is computed from the cached files on disk — no network calls —
so the provenance page always reflects what the scores were ACTUALLY built
from, not what the pipeline aspires to download.
"""

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

OPEN_DIR = Path("data/open")
SCORED_DIR = Path("data/scored")


@dataclass
class SourceSpec:
    name: str            # human-readable source name
    provider: str        # publishing organisation
    vintage: str         # data year / release
    filename: str        # cache file in data/open
    unit: str            # what one row represents
    marker: str | None   # column whose non-null count = real coverage
    dimensions: str      # which dimensions this source feeds
    url: str             # public landing page
    notes: str = ""
    # Where this source's signal survives in the COMMITTED scored outputs, as
    # (scored filename, column). data/open/ is gitignored — the raw caches are
    # large and regenerable, so a deployment (Streamlit Cloud, fresh clone) has
    # none of them. Without this, every source reported "missing" on the very
    # page meant to prove the data is real. Counting the marker in the shipped
    # scored artifact is both honest and more relevant: it measures how many
    # rows actually carry this source's signal in the data being displayed.
    scored_marker: tuple[str, str] | None = None


SOURCE_REGISTRY: list[SourceSpec] = [
    SourceSpec(
        "PLACES County Health Data", "CDC", "2025 release (2023 BRFSS)",
        "cdc_places_county.parquet", "county", "diabetes_prevalence_pct",
        "Disease Burden · Diagnosis Gap",
        "https://www.cdc.gov/places/",
        scored_marker=("dimension_scores.parquet", "diabetes_prevalence_pct"),
    ),
    SourceSpec(
        "PLACES County (prior release)", "CDC", "2022 archive (2020 BRFSS)",
        "cdc_places_prior.parquet", "county", None,
        "Trajectory (3-yr trend) · Campaign Measurement pre-period",
        "https://www.cdc.gov/places/",
        notes="Pinned archived dataset (xyst-f73f) — never the rolling ID.",
        scored_marker=("dimension_scores.parquet", "diabetes_prev_prior"),
    ),
    SourceSpec(
        "American Community Survey (5-yr)", "US Census Bureau", "2022 5-year",
        "census_acs_2022.parquet", "county", "poverty_rate",
        "Social Determinants",
        "https://www.census.gov/programs-surveys/acs",
        scored_marker=("dimension_scores.parquet", "poverty_rate"),
    ),
    SourceSpec(
        "MA County Penetration Report", "CMS", "monthly report",
        "cms_gv_puf_county.parquet", "county", "ma_penetration_rate",
        "Diagnosis Gap · Payer Landscape",
        "https://www.cms.gov/data-research/statistics-trends-reports/"
        "medicare-advantagepart-d-contract-and-enrollment-data",
        scored_marker=("dimension_scores.parquet", "ma_penetration_rate"),
    ),
    SourceSpec(
        "Health Professional Shortage Areas", "HRSA", "current designations",
        "hrsa_access.parquet", "county", None,
        "Access to Care",
        "https://data.hrsa.gov/topics/health-workforce/shortage-areas",
        scored_marker=("dimension_scores.parquet", "hpsa_flag"),
    ),
    SourceSpec(
        "County Health Rankings", "RWJ Foundation / UWPHI", "2024-2025 analytic file",
        "county_health_rankings.parquet", "county", None,
        "Access to Care · SDoH backup",
        "https://www.countyhealthrankings.org/",
        notes="Manual one-time download (site WAF blocks automation).",
        scored_marker=("dimension_scores.parquet", "chr_poor_health_pct"),
    ),
    SourceSpec(
        "Food Environment Atlas", "USDA ERS", "latest release",
        "usda_food_atlas.parquet", "county", None,
        "Social Determinants (food access)",
        "https://www.ers.usda.gov/data-products/food-environment-atlas/",
        scored_marker=("dimension_scores.parquet", "food_desert_pct"),
    ),
    SourceSpec(
        "PLACES ZCTA Data", "CDC", "2024 release",
        "cdc_places_zcta.parquet", "ZIP (ZCTA)", "diabetes_prevalence_pct",
        "ZIP-level Disease Burden · Diagnosis Gap",
        "https://www.cdc.gov/places/",
        scored_marker=("zip_scores.parquet", "diabetes_prevalence_pct"),
    ),
    SourceSpec(
        "ACS ZCTA (5-yr)", "US Census Bureau", "2022 5-year",
        "acs_zcta.parquet", "ZIP (ZCTA)", "poverty_rate",
        "ZIP-level Social Determinants",
        "https://www.census.gov/programs-surveys/acs",
        scored_marker=("zip_scores.parquet", "poverty_rate"),
    ),
    SourceSpec(
        "ZCTA→County Relationship File", "US Census Bureau", "2020 tabulation",
        "zcta_county_crosswalk.parquet", "ZCTA-county pair", None,
        "ZIP↔county downscaling weights",
        "https://www.census.gov/geographies/reference-files/time-series/geo/"
        "relationship-files.html",
        scored_marker=("zip_scores.parquet", "zip_dim_payer_landscape"),
    ),
    SourceSpec(
        "County Population by Age (PEP)", "US Census Bureau", "2023 vintage",
        "census_county_age.parquet", "county", "adult_population",
        "Undiagnosed-pool denominator (adults 18+) · age-weighted T2D rate",
        "https://www.census.gov/programs-surveys/popest.html",
        notes="Bulk file — no API key required.",
        scored_marker=("dimension_scores.parquet", "adult_population"),
    ),
    SourceSpec(
        "Medicare Physician & Other Practitioners", "CMS", "2024-12 release (2023 data)",
        "cms_providers.parquet", "prescriber (NPI)", "tot_benes",
        "HCP Targeting (panel size, specialty, panel conditions)",
        "https://data.cms.gov/provider-summary-by-type-of-service/"
        "medicare-physician-other-practitioners",
        scored_marker=("hcp_targets.parquet", "panel_size"),
    ),
]

OUTPUT_REGISTRY = [
    ("County opportunity scores", "dimension_scores.parquet", "county"),
    ("ZIP opportunity scores", "zip_scores.parquet", "ZIP (ZCTA)"),
    ("HCP target list", "hcp_targets.parquet", "prescriber (NPI)"),
]


def build_provenance(base: Path | str = ".") -> pd.DataFrame:
    """One row per registered source, computed from files on disk."""
    base = Path(base)
    _coverage = load_source_coverage(base)
    rows = []
    for spec in SOURCE_REGISTRY:
        path = base / OPEN_DIR / spec.filename
        row = {
            "source": spec.name,
            "provider": spec.provider,
            "vintage": spec.vintage,
            "unit": spec.unit,
            "dimensions": spec.dimensions,
            "url": spec.url,
            "notes": spec.notes,
            "status": "❌ missing",
            "rows": 0,
            "coverage": 0,
            "cached": None,
            "post_fill": False,   # True when counted from imputed scored data
        }
        if path.exists():
            try:
                df = pd.read_parquet(path)
                row["rows"] = len(df)
                # case-insensitive marker lookup (raw CMS files keep their
                # original CamelCase headers)
                marker_col = None
                if spec.marker:
                    marker_col = next(
                        (c for c in df.columns if c.lower() == spec.marker.lower()),
                        None)
                if marker_col:
                    row["coverage"] = int(df[marker_col].notna().sum())
                else:
                    row["coverage"] = len(df)
                row["cached"] = dt.datetime.fromtimestamp(
                    path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                row["status"] = "✅ live"
            except Exception as e:
                row["status"] = f"⚠️ unreadable ({type(e).__name__})"
        elif spec.filename in _coverage:
            # Exact observed coverage captured at ingest time and committed.
            entry = _coverage[spec.filename]
            row["rows"] = int(entry.get("rows", 0))
            row["coverage"] = int(entry.get("observed", 0))
            row["cached"] = entry.get("cache_mtime")
            row["status"] = "✅ observed"
            row["notes"] = (
                (spec.notes + " " if spec.notes else "")
                + f"Raw cache not shipped here; coverage recorded at ingest "
                  f"({entry.get('captured_utc', 'unknown')})."
            )
        elif spec.scored_marker:
            # No raw cache (deployments don't ship data/open/). Count the
            # source's signal where it survives — in the committed scored data
            # this dashboard is actually reading.
            scored_file, col = spec.scored_marker
            scored_path = base / SCORED_DIR / scored_file
            if scored_path.exists():
                try:
                    sdf = pd.read_parquet(scored_path, columns=[col])
                    row["rows"] = len(sdf)
                    row["coverage"] = int(sdf[col].notna().sum())
                    row["cached"] = dt.datetime.fromtimestamp(
                        scored_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    row["status"] = "✅ in scored data"
                    row["post_fill"] = True
                    row["notes"] = (
                        (spec.notes + " " if spec.notes else "")
                        + f"Raw cache not shipped here; count is rows in "
                          f"{scored_file} POST-imputation, so it is an upper "
                          f"bound — not raw observed coverage."
                    )
                except Exception as e:
                    row["status"] = f"⚠️ unreadable ({type(e).__name__})"
        rows.append(row)
    return pd.DataFrame(rows)


def build_output_provenance(base: Path | str = ".") -> pd.DataFrame:
    """One row per scored output file."""
    base = Path(base)
    rows = []
    for name, filename, unit in OUTPUT_REGISTRY:
        path = base / SCORED_DIR / filename
        row = {"output": name, "unit": unit, "status": "❌ not generated",
               "rows": 0, "generated": None}
        if path.exists():
            try:
                df = pd.read_parquet(path)
                row.update(
                    rows=len(df),
                    generated=dt.datetime.fromtimestamp(
                        path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                    status="✅ current",
                )
            except Exception as e:
                row["status"] = f"⚠️ unreadable ({type(e).__name__})"
        rows.append(row)
    return pd.DataFrame(rows)


# ── Observed-coverage manifest ────────────────────────────────────────────────
# Captured at ingest time, while the raw caches are on disk, and committed (a
# few hundred bytes). Lets a deployment report EXACT observed coverage instead
# of the post-imputation upper bound, without shipping the caches themselves.
COVERAGE_MANIFEST = SCORED_DIR / "source_coverage.json"


def capture_source_coverage(base: Path | str = ".") -> dict:
    """
    Record observed coverage for every source whose raw cache is present.

    Merges into any existing manifest rather than replacing it, so running one
    pipeline (e.g. ZCTA) doesn't erase entries captured by another (county/HCP).
    Each entry carries the cache's own mtime, so staleness is detectable.
    """
    base = Path(base)
    manifest = load_source_coverage(base)
    captured = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    for spec in SOURCE_REGISTRY:
        path = base / OPEN_DIR / spec.filename
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
        except Exception:
            continue
        marker_col = None
        if spec.marker:
            marker_col = next(
                (c for c in df.columns if c.lower() == spec.marker.lower()), None)
        manifest[spec.filename] = {
            "rows": int(len(df)),
            "observed": int(df[marker_col].notna().sum()) if marker_col else int(len(df)),
            "marker": marker_col,
            "cache_mtime": dt.datetime.fromtimestamp(
                path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            "captured_utc": captured,
        }

    out = base / COVERAGE_MANIFEST
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def load_source_coverage(base: Path | str = ".") -> dict:
    """Read the committed coverage manifest, or {} when absent/unreadable."""
    try:
        return json.loads((Path(base) / COVERAGE_MANIFEST).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def run_all_gates(base: Path | str = ".") -> list:
    """Run every applicable QA gate against outputs on disk.
    Returns list of (gate_name, GateReport)."""
    from src.quality.qa_gate import (
        COUNTY_CHECKS, CROSSWALK_CHECKS, HCP_CHECKS, ZCTA_CHECKS, run_gate,
    )
    base = Path(base)
    reports = []
    targets = [
        ("County scores", SCORED_DIR / "dimension_scores.parquet", COUNTY_CHECKS),
        ("ZIP scores", SCORED_DIR / "zip_scores.parquet", ZCTA_CHECKS),
        ("HCP targets", SCORED_DIR / "hcp_targets.parquet", HCP_CHECKS),
        ("ZCTA crosswalk", OPEN_DIR / "zcta_county_crosswalk.parquet", CROSSWALK_CHECKS),
    ]
    for name, rel, checks in targets:
        path = base / rel
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            reports.append((name, run_gate(df, checks, name=name)))
        except Exception:
            continue
    return reports


if __name__ == "__main__":
    # Capture observed coverage while the raw caches are on disk:
    #   python3 -m src.quality.provenance
    m = capture_source_coverage()
    print(f"Captured observed coverage for {len(m)} source(s) → {COVERAGE_MANIFEST}")
    for fn, e in sorted(m.items()):
        print(f"  {fn:34s} {e['observed']:>7,} / {e['rows']:>7,} observed")
