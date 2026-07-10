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


SOURCE_REGISTRY: list[SourceSpec] = [
    SourceSpec(
        "PLACES County Health Data", "CDC", "2025 release (2023 BRFSS)",
        "cdc_places_county.parquet", "county", "diabetes_prevalence_pct",
        "Disease Burden · Diagnosis Gap",
        "https://www.cdc.gov/places/",
    ),
    SourceSpec(
        "PLACES County (prior release)", "CDC", "2022 archive (2020 BRFSS)",
        "cdc_places_prior.parquet", "county", None,
        "Trajectory (3-yr trend) · Campaign Measurement pre-period",
        "https://www.cdc.gov/places/",
        notes="Pinned archived dataset (xyst-f73f) — never the rolling ID.",
    ),
    SourceSpec(
        "American Community Survey (5-yr)", "US Census Bureau", "2022 5-year",
        "census_acs_2022.parquet", "county", "poverty_rate",
        "Social Determinants",
        "https://www.census.gov/programs-surveys/acs",
    ),
    SourceSpec(
        "MA County Penetration Report", "CMS", "monthly report",
        "cms_gv_puf_county.parquet", "county", "ma_penetration_rate",
        "Diagnosis Gap · Payer Landscape",
        "https://www.cms.gov/data-research/statistics-trends-reports/"
        "medicare-advantagepart-d-contract-and-enrollment-data",
    ),
    SourceSpec(
        "Health Professional Shortage Areas", "HRSA", "current designations",
        "hrsa_access.parquet", "county", None,
        "Access to Care",
        "https://data.hrsa.gov/topics/health-workforce/shortage-areas",
    ),
    SourceSpec(
        "County Health Rankings", "RWJ Foundation / UWPHI", "2024-2025 analytic file",
        "county_health_rankings.parquet", "county", None,
        "Access to Care · SDoH backup",
        "https://www.countyhealthrankings.org/",
        notes="Manual one-time download (site WAF blocks automation).",
    ),
    SourceSpec(
        "Food Environment Atlas", "USDA ERS", "latest release",
        "usda_food_atlas.parquet", "county", None,
        "Social Determinants (food access)",
        "https://www.ers.usda.gov/data-products/food-environment-atlas/",
    ),
    SourceSpec(
        "PLACES ZCTA Data", "CDC", "2024 release",
        "cdc_places_zcta.parquet", "ZIP (ZCTA)", "diabetes_prevalence_pct",
        "ZIP-level Disease Burden · Diagnosis Gap",
        "https://www.cdc.gov/places/",
    ),
    SourceSpec(
        "ACS ZCTA (5-yr)", "US Census Bureau", "2022 5-year",
        "acs_zcta.parquet", "ZIP (ZCTA)", "poverty_rate",
        "ZIP-level Social Determinants",
        "https://www.census.gov/programs-surveys/acs",
    ),
    SourceSpec(
        "ZCTA→County Relationship File", "US Census Bureau", "2020 tabulation",
        "zcta_county_crosswalk.parquet", "ZCTA-county pair", None,
        "ZIP↔county downscaling weights",
        "https://www.census.gov/geographies/reference-files/time-series/geo/"
        "relationship-files.html",
    ),
    SourceSpec(
        "Medicare Physician & Other Practitioners", "CMS", "2024-12 release (2023 data)",
        "cms_providers.parquet", "prescriber (NPI)", "tot_benes",
        "HCP Targeting (panel size, specialty, panel conditions)",
        "https://data.cms.gov/provider-summary-by-type-of-service/"
        "medicare-physician-other-practitioners",
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
