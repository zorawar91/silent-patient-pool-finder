from __future__ import annotations
# Data loading + data-shape helpers for the SPPF dashboard.
# Everything that reads parquet/DB or normalises score columns lives here;
# view modules stay purely presentational.

import json
import logging
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.features.dimension_scorer import DIM_ORDER, load_weights, _norm as _norm01

log = logging.getLogger(__name__)

_GEOJSON_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
_GEOJSON_CACHE = Path("data/open/geojson_counties_fips.json")

SCORES_PATH = Path("data/scored/dimension_scores.parquet")
ZIP_PATH = Path("data/scored/zip_scores.parquet")
HCP_PATH = Path("data/scored/hcp_targets.parquet")


def _file_stamp(path: Path) -> tuple[int, int]:
    """
    (mtime_ns, size) for a data file — used as a cache key.

    st.cache_data keys on arguments only. A loader that takes none is cached for
    the life of the process, so re-running an ingestion pipeline leaves a running
    dashboard serving the previous numbers indefinitely: Streamlit hot-reloads
    changed .py files but has no idea a parquet was rewritten underneath it.
    Passing this stamp in makes a regenerated file invalidate its own cache.
    """
    try:
        s = path.stat()
        return (s.st_mtime_ns, s.st_size)
    except OSError:
        return (0, 0)


@st.cache_data(show_spinner=False)
def _load_data_cached(stamp: tuple[int, int]):
    """`stamp` is unused inside — it exists purely to key the cache on the file."""
    # Always prefer local dimension_scores.parquet — most complete and up-to-date
    # (3,144 counties, 5 real data sources). Neon and legacy paths are fallbacks only.
    dim_path = SCORES_PATH
    if dim_path.exists():
        scores      = pd.read_parquet(dim_path)
        scores_long = pd.DataFrame()   # not needed — all signals are columns in scores
        return scores, scores_long

    # Neon fallback (cloud sync) — same connection helper as the pipeline.
    from src.db.connection import get_engine
    engine = get_engine()
    if engine is not None:
        try:
            scores      = pd.read_sql(
                "SELECT * FROM dimension_scores ORDER BY opportunity_score DESC", engine)
            scores_long = pd.DataFrame()
            return scores, scores_long
        except Exception as exc:
            log.warning("Neon dimension_scores read failed (%s) — trying legacy tables.", exc)
            try:
                scores      = pd.read_sql(
                    "SELECT * FROM scores ORDER BY overall_risk_score DESC", engine)
                scores_long = pd.read_sql("SELECT * FROM scores_long", engine)
                return scores, scores_long
            except Exception as exc2:
                log.warning("Neon legacy read failed too (%s) — falling back to local files.", exc2)

    # Legacy ML pipeline fallback (259-county synthetic output)
    legacy_path = Path("data/scored/scores.parquet")
    if not legacy_path.exists():
        st.error(
            "No data found. Run `python3 src/ingestion/ingest_real_data.py` "
            "to generate county scores."
        )
        st.stop()
    scores      = pd.read_parquet(legacy_path)
    scores_long = pd.read_parquet("data/scored/scores_long.parquet")
    return scores, scores_long


def load_data():
    """County scores, re-read automatically whenever the parquet changes."""
    return _load_data_cached(_file_stamp(SCORES_PATH))


@st.cache_data
def load_geojson():
    """County-boundary GeoJSON for the choropleth. Cached to disk after the
    first successful download so the map survives network hiccups. Returns
    None when unavailable — the geographic view falls back to state bars and
    tells the user why."""
    if _GEOJSON_CACHE.exists():
        try:
            return json.loads(_GEOJSON_CACHE.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("GeoJSON disk cache unreadable (%s) — re-downloading.", exc)
    try:
        with urllib.request.urlopen(_GEOJSON_URL, timeout=10) as r:
            data = json.loads(r.read())
        try:
            _GEOJSON_CACHE.parent.mkdir(parents=True, exist_ok=True)
            _GEOJSON_CACHE.write_text(json.dumps(data))
        except OSError as exc:
            log.warning("Could not cache GeoJSON to disk: %s", exc)
        return data
    except Exception as exc:
        log.warning("County GeoJSON download failed: %s", exc)
        return None


@st.cache_data(show_spinner=False)
def _load_zip_cached(stamp: tuple[int, int]) -> pd.DataFrame:
    return pd.read_parquet(ZIP_PATH) if ZIP_PATH.exists() else pd.DataFrame()


def load_zip_data() -> pd.DataFrame:
    """ZCTA-level scores from src/ingestion/ingest_zcta_data.py."""
    return _load_zip_cached(_file_stamp(ZIP_PATH))


@st.cache_data(show_spinner=False)
def _load_hcp_cached(stamp: tuple[int, int]) -> pd.DataFrame:
    return pd.read_parquet(HCP_PATH) if HCP_PATH.exists() else pd.DataFrame()


def load_hcp_data() -> pd.DataFrame:
    """Scored HCP targets from src/ingestion/ingest_hcp_data.py."""
    return _load_hcp_cached(_file_stamp(HCP_PATH))


def _opp_score(df: pd.DataFrame) -> str:
    """Return column to use as composite opportunity score."""
    return "opportunity_score" if "opportunity_score" in df.columns else "overall_risk_score"


# Per-condition dimension weights — used when {ckey}_risk_score doesn't exist.
# T2D:            disease burden (diabetes prevalence dominant) + diagnosis gap
# HTN:            disease burden (hypertension signal) + social determinants (SES → untreated HTN)
# Hypothyroidism: diagnosis gap (detection failure) + access to care (no TSH screening)
_COND_DIM_WEIGHTS = {
    "t2d":             {"dim_disease_burden": 0.60, "dim_diagnosis_gap": 0.40},
    "htn":             {"dim_disease_burden": 0.50, "dim_social_determinants": 0.50},
    "hyperthyroidism": {"dim_diagnosis_gap":  0.60, "dim_access_to_care": 0.40},
}


def _cond_proxy(df: pd.DataFrame, ckey: str) -> pd.Series:
    """
    Return a per-condition risk score Series.
    Uses {ckey}_risk_score if present (legacy ML pipeline);
    otherwise blends dimension scores per _COND_DIM_WEIGHTS.
    """
    legacy_col = f"{ckey}_risk_score"
    if legacy_col in df.columns:
        return df[legacy_col]
    opp_col = _opp_score(df)
    weights = _COND_DIM_WEIGHTS.get(ckey, {})
    result = None
    for dim, w in weights.items():
        if dim in df.columns:
            chunk = df[dim].clip(0, 100) * w
            result = chunk if result is None else result + chunk
    return result if result is not None else df[opp_col]


def condition_score(df: pd.DataFrame, condition: str) -> tuple[pd.DataFrame, str]:
    """
    Resolve the score column that the sidebar's Condition filter selects.

    'overall'            → the composite opportunity score.
    a specific condition → the legacy `{cond}_risk_score` column when it exists
                           (old synthetic ML pipeline), otherwise a materialised
                           per-condition blend of the dimension scores.

    The real-data pipeline produces NO `*_risk_score` columns, so views that
    looked one up silently fell back to the composite — which made the Condition
    filter a no-op everywhere. Going through this helper keeps the filter live.

    Returns (df, column_name); df may gain the computed column.
    """
    if condition == "overall":
        return df, _opp_score(df)
    legacy = f"{condition}_risk_score"
    if legacy in df.columns:
        return df, legacy
    out = df.copy()
    col = f"_cond_score_{condition}"
    out[col] = _cond_proxy(df, condition)
    return out, col


# Composite tier cut-offs (config/dimensions.yaml). These are calibrated to the
# composite's distribution, which is deliberately compressed — no county leads
# all seven dimensions, so it tops out near 65 and ≥55 selects ~0.6% of counties.
TIER_PRIORITY_CUT = 55
TIER_EMERGING_CUT = 40


def condition_tier(df: pd.DataFrame, condition: str, score_col: str) -> pd.Series:
    """
    Tier labels for the score the Condition filter selected.

    'overall' → the persisted composite tier (unchanged, matches the parquet).

    A specific condition → tiers recalibrated to that condition's own
    distribution, holding SELECTIVITY constant: whatever share of counties the
    composite calls Priority, the same share of the top of the condition ranking
    is called Priority. Applying the raw 55/40 cut-offs instead would be
    meaningless — a condition score blends only two dimensions, so it spreads
    wider (T2D reaches 80) and ≥55 would flag 140 counties instead of 20,
    silently redefining the word "Priority" every time the dropdown changes.
    """
    if condition == "overall" and "opportunity_tier" in df.columns:
        return df["opportunity_tier"].astype(str)

    opp = pd.to_numeric(df[_opp_score(df)], errors="coerce")
    share_priority = float((opp >= TIER_PRIORITY_CUT).mean())
    share_emerging = float(
        ((opp >= TIER_EMERGING_CUT) & (opp < TIER_PRIORITY_CUT)).mean())

    s = pd.to_numeric(df[score_col], errors="coerce")
    out = pd.Series("Developing", index=df.index)
    # Guard the degenerate ends so quantile() stays in [0, 1].
    if share_priority > 0:
        out[s >= s.quantile(max(0.0, 1.0 - share_priority))] = "Priority"
    cum = share_priority + share_emerging
    if 0 < cum <= 1:
        emerging_cut = s.quantile(max(0.0, 1.0 - cum))
        out[(s >= emerging_cut) & (out != "Priority")] = "Emerging"
    return out


def tier_basis_label(condition: str, cond_label: str = "") -> str:
    """One-line description of what the tier badge is measuring, so a condition
    score is never silently read against the composite's thresholds."""
    if condition == "overall":
        return f"Opportunity Score ≥{TIER_PRIORITY_CUT}"
    # Sidebar labels carry a leading emoji ("🩸 Type 2 Diabetes"); drop it so the
    # phrase reads cleanly mid-sentence.
    clean = "".join(ch for ch in cond_label if ch.isalnum() or ch in " -/").strip()
    return f"top-ranked for {clean or cond_label}"


def _has_dims(df: pd.DataFrame) -> bool:
    return "dim_disease_burden" in df.columns


def _get_intervention(row: pd.Series) -> str:
    if "recommended_intervention" in row.index and pd.notna(row.get("recommended_intervention")):
        return str(row["recommended_intervention"])
    # Fallback from signals
    signals = {
        "Payer Partnership Program":          row.get("diagnostic_orphan_ratio", 0),
        "Pharmacy-Based Screening":           row.get("otc_proxy_score", 0),
        "Community Health Center Partnership":row.get("geo_burden_index_scaled", 0),
        "Digital Health Program":             row.get("hcp_symptom_rx_ratio", 0),
    }
    return max(signals, key=signals.get)


def _norm100(s: pd.Series) -> pd.Series:
    """Min-max normalise to 0–100 (delegates to the scorer's shared _norm)."""
    return (_norm01(s) * 100.0).clip(0, 100)


def _compute_fallback_dims(df: pd.DataFrame) -> pd.DataFrame:
    """Estimate 7 dimension scores from XGBoost signals when open-data pipeline hasn't run.
    Uses whatever signal columns exist in scores.parquet to produce reasonable proxies."""
    out = df.copy()

    base    = _norm100(out.get("overall_risk_score",  pd.Series(50.0, index=out.index)))
    otc     = _norm100(out["otc_proxy_score"])           if "otc_proxy_score"           in out.columns else base.copy()
    orphan  = _norm100(out["diagnostic_orphan_ratio"])   if "diagnostic_orphan_ratio"   in out.columns else base.copy()
    hcp     = _norm100(out["hcp_symptom_rx_ratio"])      if "hcp_symptom_rx_ratio"      in out.columns else base.copy()
    geo     = _norm100(out["geo_burden_index_scaled"])   if "geo_burden_index_scaled"   in out.columns else base.copy()
    ses     = _norm100(out["ses_disadvantage_index"])    if "ses_disadvantage_index"    in out.columns else base.copy()

    out["dim_disease_burden"]       = (0.55 * base   + 0.30 * otc    + 0.15 * geo).clip(0, 100)
    out["dim_diagnosis_gap"]        = (0.45 * orphan + 0.35 * base   + 0.20 * otc).clip(0, 100)
    out["dim_access_to_care"]       = (100 - 0.50 * geo - 0.30 * ses + 0.20 * base).clip(0, 100)
    out["dim_social_determinants"]  = (0.60 * ses    + 0.40 * geo).clip(0, 100)
    out["dim_payer_landscape"]      = (0.50 * otc    + 0.50 * hcp).clip(0, 100)
    out["dim_commercial_readiness"] = (0.45 * hcp    + 0.35 * otc    + 0.20 * (100 - ses)).clip(0, 100)
    out["dim_trajectory"]           = (0.50 * base   + 0.30 * orphan + 0.20 * geo).clip(0, 100)

    # Same weights as the real scorer (config/dimensions.yaml).
    weights = load_weights()
    out["opportunity_score"] = sum(weights[k] * out[f"dim_{k}"] for k in DIM_ORDER)
    out["opportunity_tier"]  = pd.cut(
        out["opportunity_score"], bins=[0, 40, 55, 100],
        labels=["Developing", "Emerging", "Priority"], include_lowest=True,
    ).astype(str)
    out["recommended_intervention"] = out.apply(
        lambda r: (
            "Payer Partnership Program"          if r.get("dim_payer_landscape", 0)   >= 65 else
            "Community Health Center Partnership" if r.get("dim_social_determinants", 0) >= 60 else
            "Employer Wellness Program"           if r.get("dim_commercial_readiness", 0) >= 60 else
            "Digital Health Program"              if r.get("dim_commercial_readiness", 0) >= 50 else
            "Pharmacy-Based Screening"
        ), axis=1,
    )
    out["priority_rank"] = out["opportunity_score"].rank(ascending=False).astype(int)
    return out


def _ensure_dims(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with dimension columns guaranteed — real if available, fallback otherwise."""
    if _has_dims(df):
        return df
    return _compute_fallback_dims(df)


def _ensure_payer(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Return (df_with_payer_cols, is_synthetic).
    Synthesises realistic county-level payer mix when CMS data hasn't been ingested.
    Rates are seeded from SES signals so high-deprivation counties skew Medicaid-heavy,
    consistent with published CMS county benchmarks."""
    payer_cols = ["ma_penetration_rate", "medicaid_rate", "commercial_rate"]
    if all(c in df.columns for c in payer_cols):
        return df, False

    out = df.copy()
    rng = np.random.default_rng(42)
    n   = len(out)

    # Normalise SES disadvantage if available; else flat mid-point
    if "ses_disadvantage_index" in out.columns:
        s = out["ses_disadvantage_index"]
        ses_n = ((s - s.min()) / (s.max() - s.min() + 1e-6)).values
    else:
        ses_n = np.full(n, 0.5)

    # MA penetration: national avg ~38 %, higher in high-SES (older, Medicare pop)
    out["ma_penetration_rate"] = np.clip(
        0.38 + 0.06 * (1 - ses_n) + 0.08 * rng.standard_normal(n), 0.10, 0.72
    )
    # Medicaid: national avg ~18 %, higher in high-SES-disadvantage counties
    out["medicaid_rate"] = np.clip(
        0.18 + 0.16 * ses_n + 0.04 * rng.standard_normal(n), 0.05, 0.60
    )
    # Commercial: residual, inversely correlated with SES disadvantage
    out["commercial_rate"] = np.clip(
        0.50 - 0.22 * ses_n + 0.04 * rng.standard_normal(n), 0.10, 0.70
    )
    return out, True
