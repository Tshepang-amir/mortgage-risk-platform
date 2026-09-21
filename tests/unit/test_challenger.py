"""Constraint and monotonicity tests for the Phase 6 challenger."""

from __future__ import annotations

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pytest
from numpy.typing import NDArray

from mortgage_risk.config.model import SCORECARD_FEATURES
from mortgage_risk.models.gbm import build_challenger, monotonic_constraints
from mortgage_risk.validation.monotonicity import (
    MonotonicityError,
    evaluate_monotonic_sweeps,
)


def _features(rows: int = 300) -> pd.DataFrame:
    generator = np.random.default_rng(20260921)
    return pd.DataFrame(
        {
            "CLASSIC_FICO": generator.uniform(520, 830, rows),
            "OLTV": generator.uniform(45, 120, rows),
            "DTI": generator.uniform(10, 60, rows),
            "CURRENT_LTV": generator.uniform(30, 160, rows),
            "SEASONING_MONTHS": generator.integers(0, 120, rows),
            "UNRATE": generator.uniform(3, 10, rows),
            "MORTGAGE30US": generator.uniform(2, 8, rows),
        }
    ).astype("float64")


def _target(x: pd.DataFrame) -> NDArray[np.int64]:
    risk = (
        (700 - x["CLASSIC_FICO"]) * 0.012
        + (x["OLTV"] - 80) * 0.035
        + (x["DTI"] - 35) * 0.035
        + (x["CURRENT_LTV"] - 80) * 0.02
    )
    return np.asarray(risk.to_numpy() > np.median(risk), dtype=np.int64)


def test_challenger_constraints_follow_feature_order() -> None:
    assert monotonic_constraints() == (-1, 1, 1, 1, 0, 0, 0)
    assert len(monotonic_constraints()) == len(SCORECARD_FEATURES)


def test_challenger_declares_deterministic_monotone_parameters() -> None:
    params = build_challenger().get_params()

    assert params["objective"] == "binary"
    assert params["monotone_constraints"] == (-1, 1, 1, 1, 0, 0, 0)
    assert params["monotone_constraints_method"] == "intermediate"
    assert params["deterministic"] is True
    assert params["n_jobs"] == 1


def test_fitted_challenger_passes_ceteris_paribus_monotonic_sweeps() -> None:
    x = _features()
    model = build_challenger().fit(x, _target(x))
    reference = {name: float(x[name].median()) for name in SCORECARD_FEATURES}

    sweeps = evaluate_monotonic_sweeps(model, reference, points=51)

    assert {sweep.feature for sweep in sweeps} == {
        "CLASSIC_FICO",
        "OLTV",
        "DTI",
        "CURRENT_LTV",
    }
    assert all(sweep.worst_violation == 0 for sweep in sweeps)


class _InvertedFicoEstimator:
    def predict_proba(self, x: pd.DataFrame) -> NDArray[np.float64]:
        probability = np.clip((x["CLASSIC_FICO"].to_numpy() - 500.0) / 350.0, 0.0, 1.0)
        return np.column_stack((1.0 - probability, probability)).astype(np.float64)


def test_monotonicity_guard_rejects_a_reversed_fico_relationship() -> None:
    reference = dict.fromkeys(SCORECARD_FEATURES, 1.0)

    with pytest.raises(MonotonicityError, match="CLASSIC_FICO"):
        evaluate_monotonic_sweeps(_InvertedFicoEstimator(), reference, points=20)


def test_constraint_builder_rejects_missing_required_driver() -> None:
    with pytest.raises(ValueError, match="DTI"):
        monotonic_constraints(("CLASSIC_FICO", "OLTV", "CURRENT_LTV"))
