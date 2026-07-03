from __future__ import annotations
"""
Scoring — Geography Risk Score Generator
=========================================
Loads trained models, runs inference on the full county feature matrix,
and outputs a Geography Risk Score (0-100) per county × condition.

Also produces:
  - An overall_risk_score (weighted average across conditions)
  - Top driving signal per county (for the dashboard tooltip)
  - Estimated undiagnosed pool size

Output: data/scored/scores.parquet
"""

import pandas as pd
import numpy as np
import yaml
import joblib
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _load_config(country_config_path: str) -> dict:
    with open(country_config_path) as f:
        return yaml.safe_load(f)


def _scale_to_risk_score(values: np.ndarray) -> np.ndarray:
    """Min-max scale predicted undiagnosed rates to 0-100 risk score."""
    min_v, max_v = values.min(), values.max()
    if max_v == min_v:
        return np.full_like(values, 50.0)
    return 100.0 * (values - min_v) / (max_v - min_v)


def _top_signal(row: pd.Series) -> str:
    """Return the name of the highest-value signal for a given row."""
    signal_cols = {
        "OTC Proxy Score": row.get("otc_proxy_score", 0),
        "Diagnostic Orphan Ratio": row.get("diagnostic_orphan_ratio", 0),
        "HCP Symptom Rx Ratio": row.get("hcp_symptom_rx_ratio", 0),
        "Geo Burden Index": row.get("geo_burden_index_scaled", 0),
    }
    return max(signal_cols, key=signal_cols.get)


def run(
    data_dir: str = "data/synthetic",
    model_dir: str = "data/models",
    output_dir: str = "data/scored",
    country_config_path: str = "config/us.yaml",
    conditions_config_path: str = "config/conditions.yaml",
) -> pd.DataFrame:
    """
    Score all counties for all active conditions.
    Returns and saves the scored DataFrame.
    """
    cfg = _load_config(country_config_path)
    active_conditions = cfg["data"]["active_conditions"]

    data_path = Path(data_dir)
    model_path = Path(model_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    features_long = pd.read_parquet(data_path / "features_long.parquet")
    counties = pd.read_parquet(data_path / "counties.parquet")
    ground_truth = pd.read_parquet(data_path / "ground_truth.parquet")

    feature_cols = [
        "otc_proxy_score",
        "diagnostic_orphan_ratio",
        "hcp_symptom_rx_ratio",
        "geo_burden_index_scaled",
        "composite_signal",
    ]

    # Score per condition
    condition_scores = []
    for condition in active_conditions:
        model_file = model_path / f"model_{condition}.joblib"
        if not model_file.exists():
            log.warning(f"Model not found for {condition}, skipping.")
            continue

        model = joblib.load(model_file)
        cond_features = features_long[features_long["condition"] == condition].copy()

        X = cond_features[feature_cols].values
        predicted_rate = model.predict(X)
        risk_score = _scale_to_risk_score(predicted_rate)

        cond_features[f"predicted_undiagnosed_rate"] = predicted_rate
        cond_features[f"risk_score"] = risk_score
        cond_features["condition"] = condition
        cond_features["top_signal"] = cond_features.apply(_top_signal, axis=1)

        condition_scores.append(
            cond_features[["county_fips", "condition", "risk_score",
                           "predicted_undiagnosed_rate", "top_signal",
                           "otc_proxy_score", "diagnostic_orphan_ratio",
                           "hcp_symptom_rx_ratio", "geo_burden_index_scaled"]]
        )
        log.info(f"  [{condition}] Scored {len(cond_features):,} counties. "
                 f"Risk score range: {risk_score.min():.1f}–{risk_score.max():.1f}")

    long_scores = pd.concat(condition_scores, ignore_index=True)

    # Pivot to wide format for the county-level view
    wide = long_scores.pivot_table(
        index="county_fips",
        columns="condition",
        values="risk_score",
        aggfunc="first",
    )
    wide.columns = [f"{c}_risk_score" for c in wide.columns]
    wide = wide.reset_index()

    # Overall risk score = unweighted mean across conditions
    score_cols = [c for c in wide.columns if c.endswith("_risk_score")]
    wide["overall_risk_score"] = wide[score_cols].mean(axis=1)

    # Add county metadata
    wide = wide.merge(
        counties[["county_fips", "county_name", "state_name", "state_abbr",
                  "population", "is_rural", "ses_disadvantage_index"]],
        on="county_fips",
    )

    # Add top driving signal (from the condition with highest risk score)
    top_signal_map = (
        long_scores.loc[long_scores.groupby("county_fips")["risk_score"].idxmax()]
        [["county_fips", "top_signal", "condition"]]
        .rename(columns={"condition": "top_condition"})
    )
    wide = wide.merge(top_signal_map, on="county_fips", how="left")

    # Add estimated undiagnosed pool from ground truth (synthetic fallback)
    pool_by_county = (
        ground_truth.groupby("county_fips")["estimated_undiagnosed_pool"]
        .sum()
        .reset_index()
        .rename(columns={"estimated_undiagnosed_pool": "total_estimated_pool"})
    )
    wide = wide.merge(pool_by_county, on="county_fips", how="left")

    # ------------------------------------------------------------------
    # Recalculate pool estimate from real CDC prevalence when available
    # ------------------------------------------------------------------
    # Published CDC undiagnosis rates (NHANES 2017-2020, CDC Diabetes Statistics 2024):
    #   T2D:             23.1% of total diabetics are undiagnosed
    #   Hypertension:    ~20% are uncontrolled/undiagnosed
    #   Hypothyroidism:  ~50% undiagnosed (estimated, literature range 40-60%)
    #
    # Formula: undiagnosed_pool = population × adult_fraction × diagnosed_rate
    #          × (undiag_frac / (1 - undiag_frac))
    #
    # CDC PLACES reports DIAGNOSED prevalence, so we back-calculate total:
    #   total_T2D = diagnosed / (1 - 0.231)
    #   undiagnosed_T2D = total_T2D × 0.231 = diagnosed × 0.300
    ADULT_FRACTION = 0.78   # ~78% of US county population is 18+ (Census)
    T2D_UNDIAG_MULTIPLIER  = 0.231 / (1 - 0.231)  # ≈ 0.300
    HTN_UNDIAG_MULTIPLIER  = 0.200 / (1 - 0.200)  # ≈ 0.250
    HYPO_PREV_RATE         = 0.047                  # 4.7% general population (ATA estimate)
    HYPO_UNDIAG_MULTIPLIER = 0.500 / (1 - 0.500)  # ≈ 1.000

    if "diabetes_prevalence_pct" in wide.columns:
        pop = wide["population"].fillna(50_000)
        adults = pop * ADULT_FRACTION

        # T2D undiagnosed pool
        t2d_diag_rate = wide["diabetes_prevalence_pct"].fillna(0.113)
        t2d_pool = adults * t2d_diag_rate * T2D_UNDIAG_MULTIPLIER

        # Hypertension undiagnosed pool (if available)
        if "hypertension_prevalence_pct" in wide.columns:
            htn_diag_rate = wide["hypertension_prevalence_pct"].fillna(0.47)
            htn_pool = adults * htn_diag_rate * HTN_UNDIAG_MULTIPLIER
        else:
            htn_pool = adults * 0.47 * HTN_UNDIAG_MULTIPLIER

        # Hypothyroidism (no county-level prevalence available — use national rate)
        hypo_pool = adults * HYPO_PREV_RATE * HYPO_UNDIAG_MULTIPLIER

        real_pool = (t2d_pool + htn_pool + hypo_pool).clip(lower=0).round().astype(int)
        wide["total_estimated_pool"] = real_pool

        log.info(
            f"Pool estimates recalculated from CDC prevalence data. "
            f"Median pool: {real_pool.median():,.0f}; "
            f"Total US undiagnosed estimate: {real_pool.sum():,.0f}"
        )
    else:
        log.info("Using synthetic pool estimates (CDC PLACES not loaded)")

    # ------------------------------------------------------------------
    # Merge 7-dimension scores if available
    # ------------------------------------------------------------------
    dim_scores_path = out_path / "dimension_scores.parquet"
    if dim_scores_path.exists():
        dim_scores = pd.read_parquet(dim_scores_path)
        # Merge dim scores, opportunity fields, and payer/SDoH context columns
        extra_context = [
            "ma_penetration_rate", "medicaid_rate", "commercial_rate",
            "diabetes_prevalence_pct", "obesity_rate_pct", "hypertension_prevalence_pct",
            "poverty_rate", "uninsured_rate", "broadband_access_rate", "median_age",
            "hpsa_flag", "fqhc_present",
        ]
        dim_cols = [c for c in dim_scores.columns if c.startswith("dim_") or
                    c in ("opportunity_score", "opportunity_tier",
                           "recommended_intervention", "priority_rank") or
                    c in extra_context]
        merge_cols = ["county_fips"] + dim_cols
        merge_cols = [c for c in merge_cols if c in dim_scores.columns]
        wide = wide.merge(dim_scores[merge_cols], on="county_fips", how="left")
        log.info(f"Merged 7-dimension scores + payer context ({len(merge_cols)} columns)")
    else:
        log.info("No dimension_scores.parquet found — run without --skip-open-data to generate it.")
        wide["opportunity_score"] = wide["overall_risk_score"]
        wide["opportunity_tier"] = pd.cut(
            wide["opportunity_score"],
            bins=[0, 40, 70, 100],
            labels=["Developing", "Emerging", "Priority"],
            include_lowest=True,
        )
        wide["recommended_intervention"] = "Pharmacy-Based Screening"
        wide["priority_rank"] = wide["opportunity_score"].rank(ascending=False).astype(int)

    # Sort by opportunity score (7-dim composite) if available, else overall_risk_score
    sort_col = "opportunity_score" if "opportunity_score" in wide.columns else "overall_risk_score"
    wide = wide.sort_values(sort_col, ascending=False).reset_index(drop=True)

    # Save outputs
    wide.to_parquet(out_path / "scores.parquet", index=False)
    long_scores.to_parquet(out_path / "scores_long.parquet", index=False)

    # Also save a clean CSV for easy inspection
    export_cols = cfg["output"]["export_columns"]
    # Map config column names to actual column names (flexible)
    available = [c for c in export_cols if c in wide.columns]
    wide[available].to_csv(out_path / "opportunity_table.csv", index=False)

    log.info(f"Scoring complete. Top 5 opportunity counties:")
    log.info(f"\n{wide[['county_name', 'state_name', 'overall_risk_score', 'opportunity_score']].head().to_string(index=False)}")

    return wide


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
