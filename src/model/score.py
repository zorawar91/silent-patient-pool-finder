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

    # Add estimated undiagnosed pool from ground truth
    pool_by_county = (
        ground_truth.groupby("county_fips")["estimated_undiagnosed_pool"]
        .sum()
        .reset_index()
        .rename(columns={"estimated_undiagnosed_pool": "total_estimated_pool"})
    )
    wide = wide.merge(pool_by_county, on="county_fips", how="left")

    # Sort by overall risk score
    wide = wide.sort_values("overall_risk_score", ascending=False).reset_index(drop=True)

    # Save outputs
    wide.to_parquet(out_path / "scores.parquet", index=False)
    long_scores.to_parquet(out_path / "scores_long.parquet", index=False)

    # Also save a clean CSV for easy inspection
    export_cols = cfg["output"]["export_columns"]
    # Map config column names to actual column names (flexible)
    available = [c for c in export_cols if c in wide.columns]
    wide[available].to_csv(out_path / "opportunity_table.csv", index=False)

    log.info(f"Scoring complete. Top 5 opportunity counties:")
    log.info(f"\n{wide[['county_name', 'state_name', 'overall_risk_score']].head().to_string(index=False)}")

    return wide


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
