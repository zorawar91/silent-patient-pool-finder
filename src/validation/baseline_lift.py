from __future__ import annotations
"""
Baseline-Lift Validation — Part III of the SPPF methodology.
=============================================================
Answers the only question a technical reviewer ultimately asks: does the
7-dimension composite beat a naive ranking any analyst could build in a
spreadsheet, out of time, on public data?

Design (temporal out-of-time, no look-ahead in the score):
  1. FROZEN SCORE — rebuild the composite using ONLY the earlier CDC PLACES
     vintage (2022 release / 2020 BRFSS): diabetes, hypertension, and obesity
     prevalence are swapped to their *_prior values, and the YoY trend columns
     are dropped (they encode the future). All single-vintage sources
     (ACS, CMS, CHR, HRSA, USDA) are held fixed.
  2. NAIVE BASELINES — (a) the spec's baseline: population x prior diabetes
     prevalence (the "biggest pool" spreadsheet ranking); (b) prior prevalence
     alone (guards against the strawman objection that (a) is unit-mismatched
     with a per-capita outcome).
  3. REALIZED OUTCOME — change in diagnosed prevalence between PLACES
     vintages (2020 -> 2022 BRFSS), T2D primary, HTN secondary. Counties with
     a real hidden pool should surface more diagnoses in the next vintage.

Metrics per Part III.1: Spearman rho, Kendall tau, Precision@20 (share of a
score's top-20 counties landing in the top tercile of realized outcome), and
AUC (top tercile vs rest). Every metric is reported as LIFT over the naive
baseline with a paired-bootstrap two-sided p-value (2,000 resamples).

Honesty notes (report alongside any quoted number):
  - Rising diagnosed prevalence conflates surfacing of hidden cases with true
    burden growth; this test shows predictive structure, NOT causal effect.
  - Non-PLACES covariates are 2022-vintage (single release available) — a
    mild look-ahead shared equally by composite and baselines.
  - Prior prevalence appears in the frozen score and in the outcome delta
    (regression-to-mean structure); both composite and baselines share it.

Run:  python3 src/validation/baseline_lift.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scipy import stats
from sklearn.metrics import roc_auc_score

from src.features.dimension_scorer import compute_all_dimensions

N_BOOT = 2_000
SEED = 42
TOP_K = 20


def build_frozen_prior_composite(panel: pd.DataFrame) -> pd.Series:
    """Recompute the composite from the prior PLACES vintage only."""
    prior = panel.copy()
    prior["diabetes_prevalence_pct"]     = prior["diabetes_prev_prior"]
    prior["hypertension_prevalence_pct"] = prior["htn_prev_prior"]
    prior["obesity_rate_pct"]            = prior["obesity_prev_prior"]
    # Trend columns encode the later vintage — the frozen score must not see them.
    prior = prior.drop(columns=[c for c in ["diabetes_trend", "htn_trend"] if c in prior.columns])
    scored = compute_all_dimensions(prior)
    return scored["opportunity_score"]


def _metrics(score: np.ndarray, outcome: np.ndarray) -> dict:
    """The four Part III.1 metrics for one score vector vs one outcome."""
    rho, _ = stats.spearmanr(score, outcome)
    tau, _ = stats.kendalltau(score, outcome)
    top_tercile = outcome >= np.quantile(outcome, 2 / 3)
    top_k_idx = np.argsort(-score)[:TOP_K]
    precision = float(top_tercile[top_k_idx].mean())
    auc = float(roc_auc_score(top_tercile, score))
    return {"spearman_rho": rho, "kendall_tau": tau,
            f"precision_at_{TOP_K}": precision, "auc_top_tercile": auc}


def _bootstrap_lift_p(sppf: np.ndarray, naive: np.ndarray, outcome: np.ndarray,
                      n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Paired bootstrap: resample counties, recompute metric lift, two-sided p."""
    rng = np.random.default_rng(seed)
    n = len(outcome)
    diffs: dict[str, list[float]] = {}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        m_s = _metrics(sppf[idx], outcome[idx])
        m_n = _metrics(naive[idx], outcome[idx])
        for k in m_s:
            diffs.setdefault(k, []).append(m_s[k] - m_n[k])
    out = {}
    for k, d in diffs.items():
        d = np.asarray(d)
        p = 2 * min((d <= 0).mean(), (d >= 0).mean())
        out[k] = {"p": min(max(p, 1 / n_boot), 1.0),
                  "ci_low": float(np.percentile(d, 2.5)),
                  "ci_high": float(np.percentile(d, 97.5))}
    return out


def run() -> pd.DataFrame:
    panel = pd.read_parquet("data/scored/dimension_scores.parquet")

    frozen = build_frozen_prior_composite(panel)

    results = []
    for cond, prior_col, cur_col in [
        ("t2d", "diabetes_prev_prior", "diabetes_prevalence_pct"),
        ("htn", "htn_prev_prior",      "hypertension_prevalence_pct"),
    ]:
        mask = panel[prior_col].notna() & panel[cur_col].notna()
        df = panel[mask]
        outcome = (df[cur_col] - df[prior_col]).values * 100  # pp change
        sppf = frozen[mask].values

        baselines = {
            "pop_x_prev": (df["population"] * df[prior_col]).values,
            "prev_only":  df[prior_col].values,
        }
        for base_name, naive in baselines.items():
            m_s = _metrics(sppf, outcome)
            m_n = _metrics(naive, outcome)
            boot = _bootstrap_lift_p(sppf, naive, outcome)
            for metric in m_s:
                results.append({
                    "condition": cond, "baseline": base_name, "metric": metric,
                    "naive": round(m_n[metric], 4), "sppf": round(m_s[metric], 4),
                    "lift": round(m_s[metric] - m_n[metric], 4),
                    "ci_low": round(boot[metric]["ci_low"], 4),
                    "ci_high": round(boot[metric]["ci_high"], 4),
                    "p": boot[metric]["p"], "n": int(mask.sum()),
                })
    return pd.DataFrame(results)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    table = run()
    out_path = Path("data/scored/validation_baseline_lift.csv")
    table.to_csv(out_path, index=False)
    pd.set_option("display.width", 160)
    print(table.to_string(index=False))
    print(f"\nSaved -> {out_path}")
