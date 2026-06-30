"""
Feature Engineering — Signal Computation
=========================================
Reads the raw synthetic (or real) data tables and computes a feature matrix
per county × condition. This is the input to the ML scoring model.

Four signals are computed per county × condition:
  1. otc_proxy_score          (0-1)  — OTC co-purchase proxy
  2. diagnostic_orphan_ratio  (0-1)  — Lab tests without follow-up Rx
  3. hcp_symptom_rx_ratio     (0-1)  — Symptom-adjacent Rx share
  4. geo_burden_index_scaled  (0-1)  — Epidemiological gap (scaled)

These are combined into a `composite_signal` (weighted sum, per country config)
and a wide feature matrix suitable for XGBoost training.
"""

import pandas as pd
import numpy as np
import yaml
from pathlib import Path
import logging

log = logging.getLogger(__name__)


def _load_config(country_config_path: str, conditions_config_path: str) -> tuple[dict, dict]:
    with open(country_config_path) as f:
        country = yaml.safe_load(f)
    with open(conditions_config_path) as f:
        conditions = yaml.safe_load(f)["conditions"]
    return country, conditions


def build_feature_matrix(
    data_dir: str = "data/synthetic",
    country_config_path: str = "config/us.yaml",
    conditions_config_path: str = "config/conditions.yaml",
) -> pd.DataFrame:
    """
    Load raw signal tables → compute normalized features → return feature matrix.

    Returns
    -------
    pd.DataFrame with columns:
        county_fips, condition,
        otc_proxy_score, diagnostic_orphan_ratio, hcp_symptom_rx_ratio,
        geo_burden_index_scaled, composite_signal,
        [plus raw signal columns for interpretability]
    """
    country_cfg, conditions = _load_config(country_config_path, conditions_config_path)
    weights = country_cfg["signals"]

    data_path = Path(data_dir)

    # Load raw tables
    otc = pd.read_parquet(data_path / "otc_signals.parquet")
    labs = pd.read_parquet(data_path / "lab_signals.parquet")
    hcp = pd.read_parquet(data_path / "hcp_signals.parquet")
    geo = pd.read_parquet(data_path / "geo_burden.parquet")

    # Merge on county_fips × condition
    features = (
        otc[["county_fips", "condition", "otc_proxy_score", "otc_units_per_1k"]]
        .merge(
            labs[["county_fips", "condition", "diagnostic_orphan_ratio",
                  "labs_ordered_per_1k", "labs_with_no_followup_rx_per_1k"]],
            on=["county_fips", "condition"],
        )
        .merge(
            hcp[["county_fips", "condition", "hcp_symptom_rx_ratio",
                 "hcp_count", "symptom_rx_per_hcp", "chronic_rx_per_hcp"]],
            on=["county_fips", "condition"],
        )
        .merge(
            geo[["county_fips", "condition", "geo_burden_index",
                 "prevalence_prior", "rx_penetration_rate"]],
            on=["county_fips", "condition"],
        )
    )

    # Scale geo_burden_index to [0, 1] (it's a ratio, can be > 1)
    max_burden = features["geo_burden_index"].quantile(0.99)
    features["geo_burden_index_scaled"] = (
        features["geo_burden_index"].clip(upper=max_burden) / max_burden
    )

    # Composite weighted signal (0-1)
    features["composite_signal"] = (
        weights["otc_proxy_weight"]          * features["otc_proxy_score"]
        + weights["diagnostic_orphan_weight"] * features["diagnostic_orphan_ratio"]
        + weights["hcp_symptom_weight"]       * features["hcp_symptom_rx_ratio"]
        + weights["geo_burden_weight"]         * features["geo_burden_index_scaled"]
    )

    log.info(
        f"Feature matrix built: {len(features):,} rows × "
        f"{len(features.columns)} columns"
    )
    return features


def build_wide_feature_matrix(
    features: pd.DataFrame,
    conditions: list[str] | None = None,
) -> pd.DataFrame:
    """
    Pivot the long feature matrix (county × condition) into wide format
    (one row per county, columns = signal_condition).

    This is what the XGBoost model trains on — one row per county,
    features from all conditions together.
    """
    if conditions is not None:
        features = features[features["condition"].isin(conditions)]

    signal_cols = [
        "otc_proxy_score",
        "diagnostic_orphan_ratio",
        "hcp_symptom_rx_ratio",
        "geo_burden_index_scaled",
        "composite_signal",
    ]

    wide = features.pivot_table(
        index="county_fips",
        columns="condition",
        values=signal_cols,
        aggfunc="first",
    )
    # Flatten MultiIndex columns: signal_condition
    wide.columns = [f"{sig}__{cond}" for sig, cond in wide.columns]
    wide = wide.reset_index()

    log.info(f"Wide feature matrix: {len(wide):,} counties × {len(wide.columns)} features")
    return wide


def get_per_condition_features(features: pd.DataFrame, condition: str) -> pd.DataFrame:
    """Return feature matrix filtered to a single condition."""
    return features[features["condition"] == condition].copy()


def run(
    data_dir: str = "data/synthetic",
    country_config_path: str = "config/us.yaml",
    conditions_config_path: str = "config/conditions.yaml",
    output_dir: str = "data/synthetic",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build and save feature matrices. Returns (long_features, wide_features).
    """
    features = build_feature_matrix(data_dir, country_config_path, conditions_config_path)
    wide = build_wide_feature_matrix(features)

    out = Path(output_dir)
    features.to_parquet(out / "features_long.parquet", index=False)
    wide.to_parquet(out / "features_wide.parquet", index=False)
    log.info(f"Features saved to {out}")

    return features, wide


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
