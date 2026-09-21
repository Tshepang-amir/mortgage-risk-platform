"""Monotone-constrained LightGBM challenger construction."""

from __future__ import annotations

from collections.abc import Sequence

from lightgbm import LGBMClassifier

from mortgage_risk.config.model import (
    CHALLENGER_LEARNING_RATE,
    CHALLENGER_MAX_DEPTH,
    CHALLENGER_MIN_CHILD_SAMPLES,
    CHALLENGER_MONOTONIC_DIRECTIONS,
    CHALLENGER_N_ESTIMATORS,
    CHALLENGER_NUM_LEAVES,
    RANDOM_SEED,
    SCORECARD_FEATURES,
)


def monotonic_constraints(features: Sequence[str] = SCORECARD_FEATURES) -> tuple[int, ...]:
    """Return LightGBM constraints in the exact feature order."""
    feature_names = tuple(features)
    missing = sorted(set(CHALLENGER_MONOTONIC_DIRECTIONS).difference(feature_names))
    if missing:
        raise ValueError(f"challenger features omit required monotonic variables: {missing}")
    return tuple(CHALLENGER_MONOTONIC_DIRECTIONS.get(name, 0) for name in feature_names)


def build_challenger(features: Sequence[str] = SCORECARD_FEATURES) -> LGBMClassifier:
    """Create the deterministic binary LightGBM challenger before fitting."""
    constraints = monotonic_constraints(features)
    return LGBMClassifier(
        objective="binary",
        n_estimators=CHALLENGER_N_ESTIMATORS,
        learning_rate=CHALLENGER_LEARNING_RATE,
        num_leaves=CHALLENGER_NUM_LEAVES,
        max_depth=CHALLENGER_MAX_DEPTH,
        min_child_samples=CHALLENGER_MIN_CHILD_SAMPLES,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        monotone_constraints=constraints,
        monotone_constraints_method="intermediate",
        deterministic=True,
        force_col_wise=True,
        random_state=RANDOM_SEED,
        n_jobs=1,
        verbosity=-1,
    )
