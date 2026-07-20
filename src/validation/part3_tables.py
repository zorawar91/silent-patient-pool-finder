from __future__ import annotations
"""
Part III validation tables — computes every number for the methodology doc.
============================================================================
Produces the values for all five Part III tables (III.1–III.5) from data
already in the repo, per the doc's reader's note: "Populate from the
validation scripts before presenting; do not enter numbers by hand."

  III.1  Baseline lift vs realized outcome  (delegates to baseline_lift.py)
  III.2  Temporal out-of-time cohorts + coherence of the frozen ranking
  III.3  External held-out source: CHR premature death (YPLL) — a severity
         measure never used by any of the seven dimensions (verified: only
         chr_poor_health_pct appears in the scorer, and only as a coverage
         marker). USRDS row stays pending until that source is ingested.
  III.4  Incremental value over SDoH: does the Diagnosis Gap dimension add
         predictive signal for the held-out severity measure beyond an
         SDoH+Access baseline?
  III.5  Weight stability: Monte Carlo perturbation of all seven weights.

Run:  python3 src/validation/part3_tables.py
Writes data/scored/validation_part3.json and prints every table.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scipy import stats
from sklearn.linear_model import LinearRegression

from src.features.dimension_scorer import DIM_ORDER, load_weights, recompute_composite
from src.validation.baseline_lift import build_frozen_prior_composite, run as run_baseline_lift

SEED = 42
N_MC = 2_000
TOP_K = 20

SDOH_DIMS = ["dim_social_determinants", "dim_access_to_care"]
GAP_DIM = "dim_diagnosis_gap"
ALL_DIMS = [f"dim_{k}" for k in DIM_ORDER]


def table_III2(panel: pd.DataFrame, frozen: pd.Series) -> dict:
    """Cohort table: realized Δ diagnosed T2D prevalence (pp) by frozen-score
    cohort, vs the same-size cohorts of the naive pop×prev ranking, plus the
    overall temporal-coherence stats of the frozen vs current ranking."""
    mask = panel["diabetes_prev_prior"].notna()
    df = panel[mask].copy()
    df["frozen"] = frozen[mask]
    df["naive"] = df["population"] * df["diabetes_prev_prior"]
    df["delta_pp"] = (df["diabetes_prevalence_pct"] - df["diabetes_prev_prior"]) * 100

    def _cohorts(score_col):
        r = df[score_col].rank(pct=True)
        return {
            "top_decile":    df[r >= 0.9],
            "middle_tier":   df[(r >= 0.1) & (r < 0.9)],
            "bottom_decile": df[r < 0.1],
        }

    frozen_c, naive_c = _cohorts("frozen"), _cohorts("naive")
    rows = {}
    for name in frozen_c:
        fc, nc = frozen_c[name], naive_c[name]
        rho, _ = stats.spearmanr(fc["frozen"], fc["delta_pp"])
        rows[name] = {
            "n": int(len(fc)),
            "mean_delta_pp": round(float(fc["delta_pp"].mean()), 3),
            "baseline_cohort_delta_pp": round(float(nc["delta_pp"].mean()), 3),
            "spearman_within": round(float(rho), 3),
        }

    coh_rho, _ = stats.spearmanr(df["frozen"], df["opportunity_score"])
    coh_tau, _ = stats.kendalltau(df["frozen"], df["opportunity_score"])
    r_f = df["frozen"].rank(ascending=False)
    r_c = df["opportunity_score"].rank(ascending=False)
    top50 = len(set(r_f.nsmallest(50).index) & set(r_c.nsmallest(50).index)) / 50
    return {"cohorts": rows, "coherence": {
        "spearman_rho": round(float(coh_rho), 3),
        "kendall_tau": round(float(coh_tau), 3),
        "top50_overlap": round(top50, 3), "n": int(mask.sum())}}


def table_III3(panel: pd.DataFrame) -> dict:
    """Held-out severity: CHR premature death (YPLL/100k), never an input."""
    mask = panel["chr_premature_death"].notna()
    df = panel[mask]
    held = df["chr_premature_death"].values
    sppf = df["opportunity_score"].values
    naive = (df["population"] * df["diabetes_prevalence_pct"]).values
    rho_s, p_s = stats.spearmanr(sppf, held)
    rho_n, _ = stats.spearmanr(naive, held)
    return {"chr_premature_death": {
        "geo_level": "county", "n": int(mask.sum()),
        "sppf_rho": round(float(rho_s), 3), "sppf_p": float(p_s),
        "baseline_rho": round(float(rho_n), 3),
        "lift": round(float(rho_s - rho_n), 3)}}


def table_III4(panel: pd.DataFrame) -> dict:
    """Incremental value of the Diagnosis Gap dimension over an SDoH+Access
    baseline, predicting the held-out severity measure (III.3)."""
    mask = panel["chr_premature_death"].notna()
    df = panel[mask]
    y = df["chr_premature_death"].values

    def _r2(cols_or_score):
        X = (df[cols_or_score].values if isinstance(cols_or_score, list)
             else np.asarray(cols_or_score).reshape(-1, 1))
        return float(LinearRegression().fit(X, y).score(X, y))

    r2_sdoh = _r2(SDOH_DIMS)
    r2_sdoh_gap = _r2(SDOH_DIMS + [GAP_DIM])
    r2_full = _r2(ALL_DIMS)

    # Partial correlation of Dx Gap with outcome, controlling SDoH+Access
    Xc = df[SDOH_DIMS].values
    res_y = y - LinearRegression().fit(Xc, y).predict(Xc)
    g = df[GAP_DIM].values
    res_g = g - LinearRegression().fit(Xc, g).predict(Xc)
    pr, pp = stats.pearsonr(res_g, res_y)
    return {
        "sdoh_only_r2": round(r2_sdoh, 3),
        "sdoh_plus_gap_r2": round(r2_sdoh_gap, 3),
        "delta_r2_gap": round(r2_sdoh_gap - r2_sdoh, 3),
        "full_composite_r2": round(r2_full, 3),
        "delta_r2_full_vs_sdoh": round(r2_full - r2_sdoh, 3),
        "partial_corr_gap": round(float(pr), 3),
        "partial_p": float(pp), "n": int(mask.sum()),
    }


def table_III5(panel: pd.DataFrame) -> dict:
    """Monte Carlo weight perturbation. Stable core = counties in the top-20
    in >=90% of draws."""
    rng = np.random.default_rng(SEED)
    base_w = load_weights()
    base = recompute_composite(panel, base_w)
    base_top = set(base.nlargest(TOP_K).index)

    out = {}
    for pct in (0.10, 0.25):
        retention, taus = [], []
        appear = {}
        for _ in range(N_MC):
            w = {k: base_w[k] * (1 + rng.uniform(-pct, pct)) for k in base_w}
            s = recompute_composite(panel, w)
            top = set(s.nlargest(TOP_K).index)
            retention.append(len(top & base_top) / TOP_K)
            taus.append(stats.kendalltau(base.values, s.values)[0])
            for i in top:
                appear[i] = appear.get(i, 0) + 1
        stable_core = sum(1 for v in appear.values() if v >= 0.9 * N_MC)
        out[f"pm{int(pct*100)}"] = {
            "draws": N_MC,
            "top20_retention_pct": round(100 * float(np.mean(retention)), 1),
            "kendall_tau_vs_base": round(float(np.mean(taus)), 4),
            "stable_core_counties": int(stable_core),
        }
    return out


def main() -> dict:
    panel = pd.read_parquet("data/scored/dimension_scores.parquet")
    frozen = build_frozen_prior_composite(panel)

    results = {
        "III.1_baseline_lift": run_baseline_lift().to_dict(orient="records"),
        "III.2_temporal": table_III2(panel, frozen),
        "III.3_held_out": table_III3(panel),
        "III.4_incremental": table_III4(panel),
        "III.5_weight_stability": table_III5(panel),
    }
    out = Path("data/scored/validation_part3.json")
    out.write_text(json.dumps(results, indent=2))
    print(json.dumps({k: v for k, v in results.items() if k != "III.1_baseline_lift"}, indent=2))
    print(f"\nSaved -> {out}")
    return results


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    main()
