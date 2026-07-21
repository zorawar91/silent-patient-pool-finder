from __future__ import annotations
"""
Data-reproducibility guard — proves the committed scores match the code.
========================================================================
The dashboard ships a committed `dimension_scores.parquet` so a fresh clone
works with zero setup. That convenience hides a real risk: the snapshot can
drift from the scoring code and nobody notices. That is exactly how
`total_estimated_pool` once shipped missing, showing 0 for every county.

This guard closes it, WITHOUT any network access:

    the committed parquet retains every raw input the scorer reads,
    so we strip the derived columns, re-run compute_all_dimensions()
    on the inputs, and assert the result equals what was committed.

If the code changes and the parquet isn't regenerated (or vice versa), this
fails loudly — in CI, before it reaches a demo.

Run:
    python3 src/validation/verify_reproducible.py            # verify
    python3 src/validation/verify_reproducible.py --write-manifest
                                                             # verify + stamp

The manifest (data/scored/build_manifest.json) records when the scores were
generated, from which commit, and a content hash — so "reproducible" is a
checkable fact rather than a claim. The Data Provenance page displays it.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.features.dimension_scorer import compute_all_dimensions

SCORES_PATH = Path("data/scored/dimension_scores.parquet")
MANIFEST_PATH = Path("data/scored/build_manifest.json")

# Everything compute_all_dimensions() produces. Stripped before recomputation.
DERIVED_COLUMNS = [
    "dim_disease_burden", "dim_diagnosis_gap", "dim_access_to_care",
    "dim_social_determinants", "dim_payer_landscape",
    "dim_commercial_readiness", "dim_trajectory",
    "opportunity_score", "opportunity_tier", "recommended_intervention",
    "priority_rank", "opportunity_percentile",
    "confidence_grade", "confidence_sources",
    "est_pool_t2d", "est_pool_htn", "est_pool_hypo", "total_estimated_pool",
]

FLOAT_TOL = 1e-9


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()[:12]
    except Exception:
        return "unknown"


def content_hash(df: pd.DataFrame) -> str:
    """Stable hash of the derived columns (order-independent of column order)."""
    cols = sorted(c for c in DERIVED_COLUMNS if c in df.columns)
    payload = df[cols].astype(str).to_csv(index=False).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def verify(scores_path: Path = SCORES_PATH) -> tuple[bool, list[str]]:
    """Recompute derived columns from the committed inputs and compare."""
    if not scores_path.exists():
        return False, [f"{scores_path} not found — run the ingestion pipeline."]

    committed = pd.read_parquet(scores_path)
    inputs = committed.drop(columns=[c for c in DERIVED_COLUMNS if c in committed.columns])

    # Same call the real pipeline makes (ingest_real_data.py).
    recomputed = compute_all_dimensions(inputs, orig_signals=None)

    problems: list[str] = []
    for col in DERIVED_COLUMNS:
        if col not in committed.columns:
            problems.append(f"{col}: MISSING from committed parquet")
            continue
        if col not in recomputed.columns:
            problems.append(f"{col}: code no longer produces this column")
            continue

        want, got = committed[col], recomputed[col]
        if pd.api.types.is_numeric_dtype(want) and pd.api.types.is_numeric_dtype(got):
            diff = (pd.to_numeric(want, errors="coerce")
                    - pd.to_numeric(got, errors="coerce")).abs()
            n_bad = int((diff > FLOAT_TOL).sum())
            if n_bad:
                problems.append(
                    f"{col}: {n_bad:,} of {len(want):,} rows differ "
                    f"(max Δ {float(diff.max()):.6g})"
                )
        else:
            neq = (want.astype(str) != got.astype(str))
            n_bad = int(neq.sum())
            if n_bad:
                problems.append(f"{col}: {n_bad:,} of {len(want):,} values differ")

    return (not problems), problems


def write_manifest(scores_path: Path = SCORES_PATH) -> dict:
    df = pd.read_parquet(scores_path)
    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "git_commit": _git_commit(),
        "rows": int(len(df)),
        "national_estimated_pool": int(df["total_estimated_pool"].sum())
        if "total_estimated_pool" in df.columns else None,
        "content_hash": content_hash(df),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def load_manifest() -> dict | None:
    """Read the build manifest, or None when absent (older checkouts)."""
    try:
        return json.loads(MANIFEST_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None


ZIP_PATH = Path("data/scored/zip_scores.parquet")
HCP_PATH = Path("data/scored/hcp_targets.parquet")


def verify_zip(path: Path = ZIP_PATH) -> tuple[bool, list[str]]:
    """
    Internal-consistency check for the ZIP layer.

    The ZIP dimensions are downscaled from county scores through the Census
    crosswalk, which lives in the gitignored data/open/ — so a fresh CI clone
    cannot recompute them from scratch. What it CAN prove (and what catches
    stale derived columns) is that everything the file derives from its own
    retained inputs still holds: composite, tier, percentile, and pool.
    """
    if not path.exists():
        return True, []  # optional artifact — absent is not a failure

    from src.features.zip_scorer import _DIM_WEIGHTS

    df = pd.read_parquet(path)
    problems: list[str] = []

    # composite = weighted sum of the 7 zip dimensions.
    # Mirrors _composite_score() exactly: missing dims fill to a neutral 50,
    # each dim is clipped to 0-100, and the total is clipped again.
    if all(c in df.columns for c in _DIM_WEIGHTS):
        want = df["zip_opportunity_score"]
        got = sum(w * df[c].fillna(50.0).clip(0, 100) for c, w in _DIM_WEIGHTS.items())
        got = got.clip(0, 100)
        n_bad = int(((want - got).abs() > 1e-6).sum())
        if n_bad:
            problems.append(f"zip_opportunity_score: {n_bad:,} rows ≠ weighted dim sum")

    # pool components and total
    pool_parts = ["zip_t2d_pool", "zip_htn_pool", "zip_hypo_pool"]
    if all(c in df.columns for c in pool_parts + ["zip_total_pool"]):
        n_bad = int((df["zip_total_pool"] != df[pool_parts].sum(axis=1)).sum())
        if n_bad:
            problems.append(f"zip_total_pool: {n_bad:,} rows ≠ sum of components")

    # tier thresholds must match the score
    if "zip_opportunity_tier" in df.columns:
        s = df["zip_opportunity_score"]
        expect = pd.cut(s, bins=[0, 40, 55, 100],
                        labels=["Developing", "Emerging", "Priority"],
                        include_lowest=True).astype(str)
        n_bad = int((df["zip_opportunity_tier"].astype(str) != expect).sum())
        if n_bad:
            problems.append(f"zip_opportunity_tier: {n_bad:,} rows disagree with score")

    return (not problems), problems


def verify_hcp(path: Path = HCP_PATH) -> tuple[bool, list[str]]:
    """
    Internal-consistency check for the HCP layer: the priority score must equal
    the documented blend of its own retained component columns, and the tiers
    must match their percentile cut-offs.
    """
    if not path.exists():
        return True, []

    from src.features.hcp_scorer import W_BURDEN, W_GEO, W_REACH, W_SPECIALTY

    df = pd.read_parquet(path)
    problems: list[str] = []

    needed = ["geo_percentile", "reach_pctl", "burden_pctl", "specialty_fit",
              "hcp_priority_score"]
    if all(c in df.columns for c in needed):
        got = (W_GEO * df["geo_percentile"]
               + W_REACH * df["reach_pctl"]
               + W_BURDEN * df["burden_pctl"]
               + W_SPECIALTY * df["specialty_fit"] * 100).clip(0, 100).round(1)
        n_bad = int(((df["hcp_priority_score"] - got).abs() > 0.05).sum())
        if n_bad:
            problems.append(
                f"hcp_priority_score: {n_bad:,} rows ≠ "
                f"{W_GEO}/{W_REACH}/{W_BURDEN}/{W_SPECIALTY} component blend")

    if "hcp_tier" in df.columns:
        q95, q75 = df["hcp_priority_score"].quantile([0.95, 0.75])
        expect = pd.Series("Developing", index=df.index)
        expect[df["hcp_priority_score"] >= q75] = "Emerging"
        expect[df["hcp_priority_score"] >= q95] = "Priority"
        n_bad = int((df["hcp_tier"].astype(str) != expect).sum())
        if n_bad:
            problems.append(f"hcp_tier: {n_bad:,} rows disagree with score quantiles")

    return (not problems), problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-manifest", action="store_true",
                    help="Stamp the build manifest after a successful verify")
    args = ap.parse_args()

    print("─" * 62)
    print("  DATA REPRODUCIBILITY GUARD — committed scores vs scoring code")
    print("─" * 62)

    failed = False

    ok, problems = verify()
    if ok:
        df = pd.read_parquet(SCORES_PATH)
        print(f"  ✅ county — all {len(DERIVED_COLUMNS)} derived columns reproduce "
              f"exactly ({len(df):,} counties)")
        print(f"     content hash: {content_hash(df)}")
    else:
        failed = True
        print(f"  🛑 county — {len(problems)} mismatch(es); the committed parquet "
              f"does NOT match the scoring code:")
        for p in problems:
            print(f"     ✗ {p}")
        print("\n     Fix: re-run the ingestion pipeline (or, if only derived "
              "columns\n     changed, recompute and re-commit the parquet).")

    for label, fn, path, remedy in [
        ("ZIP", verify_zip, ZIP_PATH, "python3 src/ingestion/ingest_zcta_data.py"),
        ("HCP", verify_hcp, HCP_PATH, "python3 src/ingestion/ingest_hcp_data.py"),
    ]:
        ok_x, probs = fn()
        if not path.exists():
            print(f"  ⚪ {label} — artifact not present, skipped")
        elif ok_x:
            n = len(pd.read_parquet(path))
            print(f"  ✅ {label} — derived columns consistent with own inputs "
                  f"({n:,} rows)")
        else:
            failed = True
            print(f"  🛑 {label} — {len(probs)} inconsistency(ies):")
            for p in probs:
                print(f"     ✗ {p}")
            print(f"     Fix: re-run {remedy}")

    if failed:
        return 1

    if args.write_manifest:
        m = write_manifest()
        print(f"  ✅ manifest written → {MANIFEST_PATH}")
        print(f"     {m['generated_utc']} · commit {m['git_commit']} · "
              f"{m['rows']:,} rows")
    print("─" * 62)
    return 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
