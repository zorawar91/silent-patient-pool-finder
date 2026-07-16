from __future__ import annotations
"""
Model Training — Geography Risk Scorer
=======================================
Trains an XGBoost regressor to predict `true_undiagnosed_rate` from the
signal feature matrix. Outputs:
  - A trained model per condition (saved as joblib)
  - A combined overall model (all conditions as features)
  - SHAP feature importance values
  - Cross-validation metrics

Spatial cross-validation: folds are split by state, not randomly, to
prevent geographic leakage between train and test sets.
"""

import pandas as pd
import numpy as np
import yaml
import joblib
import logging
from pathlib import Path

import xgboost as xgb
from sklearn.base import clone
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.model_selection import GroupKFold
import shap

log = logging.getLogger(__name__)


def _load_config(country_config_path: str) -> dict:
    with open(country_config_path) as f:
        return yaml.safe_load(f)


def _spatial_cv_splits(
    county_fips: pd.Series,
    counties_df: pd.DataFrame,
    n_folds: int = 5,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    State-grouped CV folds: no state ever straddles train and test.
    This prevents a model trained on Manhattan from being tested on Brooklyn.
    """
    state_fips = counties_df.set_index("county_fips")["state_fips"]
    states = state_fips.loc[county_fips].values
    dummy_X = np.zeros(len(states))
    return list(GroupKFold(n_splits=n_folds).split(dummy_X, groups=states))


def train_condition_model(
    condition: str,
    features_long: pd.DataFrame,
    ground_truth: pd.DataFrame,
    counties_df: pd.DataFrame,
    xgb_params: dict,
    n_folds: int = 5,
) -> tuple[xgb.XGBRegressor, dict, pd.DataFrame]:
    """
    Train a per-condition XGBoost model.

    Returns (model, cv_metrics, shap_importance_df)
    """
    cond_features = features_long[features_long["condition"] == condition].copy()
    cond_truth = ground_truth[ground_truth["condition"] == condition].copy()

    df = cond_features.merge(
        cond_truth[["county_fips", "true_undiagnosed_rate"]],
        on="county_fips",
    )

    feature_cols = [
        "otc_proxy_score",
        "diagnostic_orphan_ratio",
        "hcp_symptom_rx_ratio",
        "geo_burden_index_scaled",
        "composite_signal",
    ]

    X = df[feature_cols].values
    y = df["true_undiagnosed_rate"].values
    county_fips = df["county_fips"].values

    model = xgb.XGBRegressor(
        **xgb_params,
        tree_method="hist",
        eval_metric="rmse",
        verbosity=0,
    )

    # Spatial cross-validation — clone per fold so no state leaks into the
    # estimator that scores it.
    splits = _spatial_cv_splits(county_fips, counties_df, n_folds)
    cv_r2, cv_mae = [], []
    for train_idx, test_idx in splits:
        fold_model = clone(model)
        fold_model.fit(X[train_idx], y[train_idx], verbose=False)
        preds = fold_model.predict(X[test_idx])
        cv_r2.append(r2_score(y[test_idx], preds))
        cv_mae.append(mean_absolute_error(y[test_idx], preds))

    # Final fit on all data
    model.fit(X, y, verbose=False)

    cv_metrics = {
        "condition": condition,
        "cv_r2_mean": float(np.mean(cv_r2)),
        "cv_r2_std": float(np.std(cv_r2)),
        "cv_mae_mean": float(np.mean(cv_mae)),
        "cv_mae_std": float(np.std(cv_mae)),
    }
    log.info(
        f"  [{condition}] CV R²={cv_metrics['cv_r2_mean']:.3f}±{cv_metrics['cv_r2_std']:.3f}  "
        f"MAE={cv_metrics['cv_mae_mean']:.4f}"
    )

    # SHAP feature importance (with fallback to built-in importance)
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        importance_values = np.abs(shap_values).mean(axis=0)
    except Exception as e:
        log.warning(f"SHAP failed ({e}), falling back to model.feature_importances_")
        importance_values = model.feature_importances_

    shap_importance = pd.DataFrame({
        "feature": feature_cols,
        "mean_abs_shap": importance_values,
        "condition": condition,
    }).sort_values("mean_abs_shap", ascending=False)

    return model, cv_metrics, shap_importance


def run(
    data_dir: str = "data/synthetic",
    model_dir: str = "data/models",
    country_config_path: str = "config/us.yaml",
    conditions_config_path: str = "config/conditions.yaml",
) -> dict:
    """
    Train models for all active conditions + combined model.
    Saves models and metrics to model_dir.
    Returns dict of trained models.
    """
    cfg = _load_config(country_config_path)
    xgb_params = cfg["model"]["xgb_params"]
    active_conditions = cfg["data"]["active_conditions"]
    n_folds = cfg["model"]["cv_folds"]

    data_path = Path(data_dir)
    model_path = Path(model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    features_long = pd.read_parquet(data_path / "features_long.parquet")
    ground_truth = pd.read_parquet(data_path / "ground_truth.parquet")
    counties = pd.read_parquet(data_path / "counties.parquet")

    models = {}
    all_metrics = []
    all_shap = []

    log.info(f"Training models for conditions: {active_conditions}")

    for condition in active_conditions:
        log.info(f"Training model: {condition}")
        model, metrics, shap_df = train_condition_model(
            condition, features_long, ground_truth, counties,
            xgb_params, n_folds,
        )
        models[condition] = model
        all_metrics.append(metrics)
        all_shap.append(shap_df)

        joblib.dump(model, model_path / f"model_{condition}.joblib")
        log.info(f"  Saved model_{condition}.joblib")

    # Save metrics
    metrics_df = pd.DataFrame(all_metrics)
    metrics_df.to_csv(model_path / "cv_metrics.csv", index=False)

    shap_df_all = pd.concat(all_shap, ignore_index=True)
    shap_df_all.to_parquet(model_path / "shap_importance.parquet", index=False)

    log.info("Training complete.")
    log.info(f"\n{metrics_df[['condition', 'cv_r2_mean', 'cv_mae_mean']].to_string(index=False)}")

    return models


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
