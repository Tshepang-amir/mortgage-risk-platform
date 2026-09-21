"""Ceteris-paribus monotonicity sweeps for probability models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from numpy.typing import NDArray

from mortgage_risk.config.model import (
    CHALLENGER_MONOTONIC_DIRECTIONS,
    SCORECARD_FEATURES,
)

DEFAULT_SWEEP_BOUNDS: Mapping[str, tuple[float, float]] = {
    "CLASSIC_FICO": (500.0, 850.0),
    "OLTV": (20.0, 150.0),
    "DTI": (0.0, 65.0),
    "CURRENT_LTV": (0.0, 200.0),
}


class ProbabilityEstimator(Protocol):
    """Structural interface needed by the sweep validator."""

    def predict_proba(self, x: pd.DataFrame) -> NDArray[np.float64]: ...


class MonotonicityError(AssertionError):
    """Raised when a constrained driver reverses its required risk direction."""


@dataclass(frozen=True, slots=True)
class MonotonicSweep:
    """Observed probability range and worst directional step for one feature."""

    feature: str
    direction: int
    minimum_probability: float
    maximum_probability: float
    worst_violation: float


def evaluate_monotonic_sweeps(
    estimator: ProbabilityEstimator,
    reference: Mapping[str, float],
    *,
    bounds: Mapping[str, tuple[float, float]] = DEFAULT_SWEEP_BOUNDS,
    points: int = 101,
    tolerance: float = 1e-12,
) -> tuple[MonotonicSweep, ...]:
    """Assert constrained predictions are monotone while other values stay fixed."""
    if points < 2:
        raise ValueError("points must be at least two")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    missing_reference = sorted(set(SCORECARD_FEATURES).difference(reference))
    if missing_reference:
        raise ValueError(f"reference is missing model features: {missing_reference}")
    missing_bounds = sorted(set(CHALLENGER_MONOTONIC_DIRECTIONS).difference(bounds))
    if missing_bounds:
        raise ValueError(f"sweep bounds are missing constrained features: {missing_bounds}")

    summaries: list[MonotonicSweep] = []
    for feature, direction in CHALLENGER_MONOTONIC_DIRECTIONS.items():
        lower, upper = bounds[feature]
        if lower >= upper:
            raise ValueError(f"invalid sweep bounds for {feature}: {(lower, upper)}")
        batch = pd.DataFrame([dict(reference)] * points, columns=SCORECARD_FEATURES).astype(
            "float64"
        )
        batch[feature] = np.linspace(lower, upper, points)
        probability = np.asarray(estimator.predict_proba(batch), dtype=np.float64)[:, 1]
        steps = np.diff(probability)
        worst = float(max(0.0, steps.max())) if direction < 0 else float(max(0.0, -steps.min()))
        if worst > tolerance:
            expected = "non-increasing" if direction < 0 else "non-decreasing"
            raise MonotonicityError(
                f"{feature} predictions are not {expected}; worst reversal is {worst:.12g}"
            )
        summaries.append(
            MonotonicSweep(
                feature=feature,
                direction=direction,
                minimum_probability=float(probability.min()),
                maximum_probability=float(probability.max()),
                worst_violation=worst,
            )
        )
    return tuple(summaries)
