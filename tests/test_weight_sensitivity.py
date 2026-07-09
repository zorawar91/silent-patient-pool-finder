"""Weight sensitivity helpers — recompute + stability metrics."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.dimension_scorer import (
    DIM_ORDER, rank_stability, recompute_composite,
)

RNG = np.random.default_rng(3)


def _dims(n=500) -> pd.DataFrame:
    return pd.DataFrame({f"dim_{k}": RNG.uniform(0, 100, n) for k in DIM_ORDER})


def test_default_weights_reproduce_composite():
    df = _dims()
    weights = {"disease_burden": .20, "diagnosis_gap": .25, "access_to_care": .15,
               "social_determinants": .15, "payer_landscape": .10,
               "commercial_readiness": .10, "trajectory": .05}
    manual = sum(df[f"dim_{k}"] * w for k, w in weights.items())
    out = recompute_composite(df, weights)
    assert np.allclose(out, manual)


def test_weights_are_normalised():
    """Raw slider ints (20, 25, …) must give the same result as fractions."""
    df = _dims()
    frac = recompute_composite(df, {k: w for k, w in zip(
        DIM_ORDER, [.20, .25, .15, .15, .10, .10, .05])})
    ints = recompute_composite(df, {k: w for k, w in zip(
        DIM_ORDER, [20, 25, 15, 15, 10, 10, 5])})
    assert np.allclose(frac, ints)


def test_all_zero_weights_raise():
    with pytest.raises(ValueError):
        recompute_composite(_dims(), {k: 0 for k in DIM_ORDER})


def test_identical_scores_perfect_stability():
    df = _dims()
    w = {k: 1 for k in DIM_ORDER}
    s = recompute_composite(df, w)
    stab = rank_stability(s, s.copy())
    assert stab["spearman"] == pytest.approx(1.0)
    assert stab["top_overlap"] == 1.0
    assert stab["max_jump"] == 0


def test_perturbed_weights_detect_movement():
    df = _dims()
    base = recompute_composite(df, {k: w for k, w in zip(
        DIM_ORDER, [20, 25, 15, 15, 10, 10, 5])})
    extreme = recompute_composite(df, {k: w for k, w in zip(
        DIM_ORDER, [0, 0, 0, 0, 0, 0, 100])})   # trajectory-only
    stab = rank_stability(base, extreme)
    assert stab["spearman"] < 0.9          # ranking should visibly shift
    assert stab["top_overlap"] < 1.0
