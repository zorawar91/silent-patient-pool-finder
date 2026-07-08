from __future__ import annotations
"""
QA Gate — fail-loudly data quality checks for SPPF pipelines.
=============================================================
Motivation: a corrupt ZCTA→county crosswalk (wrong column parsed) once shipped
silently — 5 of 7 ZIP dimensions were 100% NaN and state filters returned zero
rows, with no error anywhere. This module makes that class of failure IMPOSSIBLE
to ship: every pipeline run ends with an explicit gate that either passes or
blocks the parquet write with an actionable message.

Usage:
    from src.quality.qa_gate import run_gate, Check

    report = run_gate(df, COUNTY_CHECKS, name="county dimension scores")
    report.raise_on_failure()          # raises QAGateError on any CRITICAL fail
    # or: if not report.ok: sys.exit(1)

Severity levels:
    CRITICAL — blocks the write. Data is unusable or misleading.
    WARN     — logged prominently; write proceeds. Coverage degraded but usable.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

log = logging.getLogger(__name__)

CRITICAL = "CRITICAL"
WARN = "WARN"


class QAGateError(RuntimeError):
    """Raised when a pipeline output fails one or more CRITICAL checks."""


@dataclass
class Check:
    """A single data-quality assertion against a DataFrame."""
    name: str
    fn: Callable[[pd.DataFrame], bool]      # True = pass
    detail: Callable[[pd.DataFrame], str]   # human-readable measurement
    severity: str = CRITICAL
    remedy: str = ""                        # what to do when it fails


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: str
    detail: str
    remedy: str


@dataclass
class GateReport:
    name: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    @property
    def critical_failures(self) -> list[CheckResult]:
        return [r for r in self.failures if r.severity == CRITICAL]

    @property
    def ok(self) -> bool:
        return not self.critical_failures

    def raise_on_failure(self) -> None:
        if self.ok:
            return
        lines = [f"QA GATE FAILED — {self.name}: "
                 f"{len(self.critical_failures)} critical failure(s)"]
        for r in self.critical_failures:
            lines.append(f"  ✗ {r.name}: {r.detail}")
            if r.remedy:
                lines.append(f"    → {r.remedy}")
        raise QAGateError("\n".join(lines))


def run_gate(df: pd.DataFrame, checks: list[Check], name: str) -> GateReport:
    """Run all checks against df, log a report card, return the report."""
    report = GateReport(name=name)
    log.info("─" * 62)
    log.info(f"  QA GATE — {name}")
    log.info("─" * 62)
    for c in checks:
        try:
            passed = bool(c.fn(df))
            detail = c.detail(df)
        except Exception as e:  # a crashing check is itself a failure
            passed, detail = False, f"check crashed: {e!r}"
        report.results.append(CheckResult(c.name, passed, c.severity, detail, c.remedy))
        icon = "✅" if passed else ("🛑" if c.severity == CRITICAL else "⚠️ ")
        log.info(f"  {icon} {c.name}: {detail}")
        if not passed and c.remedy:
            log.info(f"      → {c.remedy}")
    n_fail = len(report.failures)
    log.info(f"  Result: {len(checks) - n_fail}/{len(checks)} passed"
             + ("" if report.ok else "  — WRITE BLOCKED"))
    log.info("─" * 62)
    return report


# ── Reusable check builders ───────────────────────────────────────────────────

def max_null_share(col: str, limit: float, severity: str = CRITICAL,
                   remedy: str = "") -> Check:
    """Column must exist and be at most `limit` fraction null."""
    def _fn(df):
        return col in df.columns and df[col].isna().mean() <= limit
    def _detail(df):
        if col not in df.columns:
            return f"column '{col}' MISSING"
        share = df[col].isna().mean()
        return f"{col} null share {share:.1%} (limit {limit:.0%})"
    return Check(f"null-share {col}", _fn, _detail, severity, remedy)


def min_rows(n: int, severity: str = CRITICAL, remedy: str = "") -> Check:
    return Check(
        f"row count ≥ {n:,}",
        lambda df: len(df) >= n,
        lambda df: f"{len(df):,} rows (min {n:,})",
        severity, remedy,
    )


def min_std(col: str, floor: float, severity: str = CRITICAL,
            remedy: str = "") -> Check:
    """Column must vary — a (near-)constant score column means a broken join
    silently defaulted every row to the same fallback value."""
    def _fn(df):
        return col in df.columns and float(df[col].std() or 0) >= floor
    def _detail(df):
        if col not in df.columns:
            return f"column '{col}' MISSING"
        return f"{col} std {float(df[col].std() or 0):.2f} (floor {floor})"
    return Check(f"variance {col}", _fn, _detail, severity, remedy)


def value_range(col: str, lo: float, hi: float, severity: str = CRITICAL,
                remedy: str = "") -> Check:
    def _fn(df):
        if col not in df.columns:
            return False
        s = df[col].dropna()
        return s.empty or (s.min() >= lo and s.max() <= hi)
    def _detail(df):
        if col not in df.columns:
            return f"column '{col}' MISSING"
        s = df[col].dropna()
        return f"{col} in [{s.min():.1f}, {s.max():.1f}] (allowed [{lo}, {hi}])"
    return Check(f"range {col}", _fn, _detail, severity, remedy)


def code_format(col: str, width: int, severity: str = CRITICAL,
                remedy: str = "") -> Check:
    """All non-null values must be `width`-digit numeric strings.
    Catches the '00nan' / wrong-column class of parsing bug directly."""
    def _fn(df):
        if col not in df.columns:
            return False
        s = df[col].dropna().astype(str)
        return s.empty or s.str.fullmatch(r"\d{%d}" % width).all()
    def _detail(df):
        if col not in df.columns:
            return f"column '{col}' MISSING"
        s = df[col].dropna().astype(str)
        bad = s[~s.str.fullmatch(r"\d{%d}" % width)]
        return (f"{col}: all {len(s):,} values are {width}-digit codes" if bad.empty
                else f"{col}: {len(bad):,} malformed values e.g. {bad.head(3).tolist()}")
    return Check(f"code-format {col}", _fn, _detail, severity, remedy)


def min_unique(col: str, n: int, severity: str = CRITICAL,
               remedy: str = "") -> Check:
    def _fn(df):
        return col in df.columns and df[col].nunique() >= n
    def _detail(df):
        if col not in df.columns:
            return f"column '{col}' MISSING"
        return f"{col}: {df[col].nunique():,} unique (min {n:,})"
    return Check(f"uniqueness {col}", _fn, _detail, severity, remedy)


# ── Pipeline check suites ─────────────────────────────────────────────────────

_DIM_COLS = ["dim_disease_burden", "dim_diagnosis_gap", "dim_access_to_care",
             "dim_social_determinants", "dim_payer_landscape",
             "dim_commercial_readiness", "dim_trajectory"]

_ZIP_DIM_COLS = ["zip_" + c for c in _DIM_COLS]

RERUN_COUNTY = "Re-run: python3 ingest_real_data.py (delete data/open cache for the failing source first)"
RERUN_ZCTA = ("Delete data/open/zcta_county_crosswalk.parquet and re-run: "
              "python3 ingest_zcta_data.py")

COUNTY_CHECKS: list[Check] = (
    [
        min_rows(3_000, remedy="County spine incomplete — check Census TIGER download."),
        code_format("county_fips", 5, remedy=RERUN_COUNTY),
        min_unique("state_name", 45, remedy="State join broke — check county spine merge."),
        max_null_share("state_name", 0.01, remedy="State names missing — spine merge failed."),
        value_range("opportunity_score", 0, 100),
        min_std("opportunity_score", 1.0,
                remedy="Composite score is flat — a scoring input collapsed to a constant."),
    ]
    + [max_null_share(c, 0.05, remedy=RERUN_COUNTY) for c in _DIM_COLS]
    + [min_std(c, 0.5, remedy=RERUN_COUNTY) for c in _DIM_COLS]
    + [
        # Percentile + confidence grade (WARN — additive columns, older
        # parquets may predate them)
        max_null_share("opportunity_percentile", 0.01, WARN,
                       "Percentile missing — re-run ingest_real_data.py."),
        max_null_share("confidence_grade", 0.01, WARN,
                       "Confidence grade missing — re-run ingest_real_data.py."),
        # Coverage of key raw signals (WARN — degraded but usable)
        max_null_share("diabetes_prevalence_pct", 0.10, WARN,
                       "CDC PLACES coverage degraded — check download."),
        # Post-fill this column is never null — gate on TRUE pre-fill coverage
        # instead (confidence_sources_raw). CMS once covered only 236 counties
        # because '1,234'/'12.3%' strings coerced to NaN; that must WARN loudly.
        Check(
            "CMS true coverage",
            lambda df: ("confidence_sources_raw" not in df.columns
                        or (df["confidence_sources_raw"] >= 4).mean() > 0.85),
            lambda df: ("no pre-fill coverage column (older parquet)"
                        if "confidence_sources_raw" not in df.columns else
                        f"{(df['confidence_sources_raw'] >= 4).mean():.1%} of counties "
                        f"have ≥4 real sources pre-fill"),
            WARN,
            "A source collapsed — check CMS/CHR/USDA download logs; "
            "delete the failing cache in data/open and re-run.",
        ),
        max_null_share("ma_penetration_rate", 0.15, WARN,
                       "CMS MA data degraded — payer dimension is weakened."),
        max_null_share("poverty_rate", 0.10, WARN,
                       "Census ACS coverage degraded."),
    ]
)

ZCTA_CHECKS: list[Check] = (
    [
        min_rows(25_000, remedy=RERUN_ZCTA),
        code_format("zcta5", 5, remedy=RERUN_ZCTA),
        min_unique("zcta5", 25_000, remedy=RERUN_ZCTA),
        # THE crosswalk-bug detectors: state coverage + county-derived dims
        max_null_share("state_name", 0.05,
                       remedy="ZCTA→county crosswalk broken or missing. " + RERUN_ZCTA),
        min_unique("state_abbr", 45,
                   remedy="State coverage collapsed — crosswalk join failed. " + RERUN_ZCTA),
        value_range("zip_opportunity_score", 0, 100),
        min_std("zip_opportunity_score", 1.0, remedy=RERUN_ZCTA),
        max_null_share("lat", 0.02, WARN, "Centroids degraded — run fix_zip_map.py."),
    ]
    + [max_null_share(c, 0.05, remedy="County-dim downscale failed. " + RERUN_ZCTA)
       for c in _ZIP_DIM_COLS]
    + [min_std(c, 0.5, remedy="Dimension is constant — downscale defaulted to medians. "
               + RERUN_ZCTA)
       for c in _ZIP_DIM_COLS]
)

HCP_CHECKS: list[Check] = [
    min_rows(10_000, remedy="Provider download truncated — check data.cms.gov paging, "
             "or use the manual CSV fallback (see ingest_hcp_data.py header)."),
    code_format("npi", 10, remedy="NPIs malformed — wrong column parsed."),
    min_unique("npi", 10_000, remedy="Duplicate NPIs — paging fetched the same offset repeatedly."),
    code_format("zip5", 5, remedy="Provider ZIPs malformed — float artifact or wrong column."),
    value_range("hcp_priority_score", 0, 100),
    min_std("hcp_priority_score", 3.0,
            remedy="Score is flat — a component collapsed (check geo join match rate)."),
    Check(
        "ZIP→ZCTA geo match rate",
        lambda df: "geo_percentile" in df.columns
                   and (df["geo_percentile"] != 50.0).mean() > 0.50,
        lambda df: (f"{(df['geo_percentile'] != 50.0).mean():.1%} of NPIs matched "
                    f"to a real geography score (default-fill 50.0 excluded)"
                    if "geo_percentile" in df.columns else "geo_percentile MISSING"),
        remedy="Geography join failed — re-run ingest_zcta_data.py first.",
    ),
    max_null_share("panel_size", 0.02, remedy="Panel size missing — wrong column parsed."),
    max_null_share("panel_diabetes_pct", 0.60, WARN,
                   "Panel condition data sparse — burden component weakened."),
]

CROSSWALK_CHECKS: list[Check] = [
    min_rows(40_000, remedy="Crosswalk truncated — wrong column parsed or bad filter. "
             + RERUN_ZCTA),
    code_format("zcta5", 5, remedy="ZCTA codes malformed (e.g. '00nan') — parser grabbed "
                "an OID_* column instead of GEOID_*. " + RERUN_ZCTA),
    code_format("county_fips", 5, remedy=RERUN_ZCTA),
    min_unique("zcta5", 30_000, remedy=RERUN_ZCTA),
    Check(
        "weights sum to 1 per ZCTA",
        lambda df: ((df.groupby("zcta5")["weight"].sum() - 1.0).abs() < 0.01).mean() > 0.99,
        lambda df: (f"{((df.groupby('zcta5')['weight'].sum() - 1.0).abs() < 0.01).mean():.1%} "
                    f"of ZCTAs have weights summing to 1.0"),
        remedy="Weight normalization broken — check AREALAND_PART logic.",
    ),
]
