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


@st.cache_data
def load_data():
    # Always prefer local dimension_scores.parquet — most complete and up-to-date
    # (3,144 counties, 5 real data sources). Neon and legacy paths are fallbacks only.
    dim_path = Path("data/scored/dimension_scores.parquet")
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


@st.cache_data
def load_zip_data() -> pd.DataFrame:
    """Load ZCTA-level scores produced by src/ingestion/ingest_zcta_data.py."""
    path = Path("data/scored/zip_scores.parquet")
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


@st.cache_data
def load_hcp_data() -> pd.DataFrame:
    """Load scored HCP targets produced by src/ingestion/ingest_hcp_data.py."""
    path = Path("data/scored/hcp_targets.parquet")
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


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
