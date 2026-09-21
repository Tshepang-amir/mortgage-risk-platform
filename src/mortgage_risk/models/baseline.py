"""Marginal default-rate baseline by loan seasoning month."""

from __future__ import annotations

from typing import Self

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from numpy.typing import ArrayLike, NDArray
from sklearn.base import BaseEstimator, ClassifierMixin  # type: ignore[import-untyped]


class MarginalRateBaseline(ClassifierMixin, BaseEstimator):  # type: ignore[misc]
    """Smoothed marginal event rate indexed by loan age."""

    def __init__(self, age_column: str = "SEASONING_MONTHS", smoothing: float = 20.0) -> None:
        self.age_column = age_column
        self.smoothing = smoothing

    def fit(self, x: pd.DataFrame, y: ArrayLike) -> Self:
        """Estimate a smoothed event rate for every observed loan age."""
        if self.smoothing < 0:
            raise ValueError("smoothing must be non-negative")
        ages = self._ages(x)
        target = np.asarray(y, dtype=np.int64)
        if target.ndim != 1 or len(target) != len(ages):
            raise ValueError("y must be one-dimensional and aligned with x")
        if not np.isin(target, (0, 1)).all():
            raise ValueError("y must contain only binary values")
        if len(target) == 0:
            raise ValueError("cannot fit an empty baseline")

        self.classes_ = np.asarray([0, 1], dtype=np.int64)
        self.global_rate_ = float(target.mean())
        grouped = pd.DataFrame({"age": ages, "target": target}).groupby("age")["target"]
        events = grouped.sum()
        counts = grouped.count()
        rates = (events + self.smoothing * self.global_rate_) / (counts + self.smoothing)
        self.age_rates_ = {float(age): float(rate) for age, rate in rates.items()}
        return self

    def predict_proba(self, x: pd.DataFrame) -> NDArray[np.float64]:
        """Return class probabilities, falling back to the portfolio rate."""
        if not hasattr(self, "global_rate_"):
            raise RuntimeError("baseline must be fitted before prediction")
        rates = np.asarray(
            [self.age_rates_.get(float(age), self.global_rate_) for age in self._ages(x)],
            dtype=np.float64,
        )
        return np.column_stack((1.0 - rates, rates)).astype(np.float64, copy=False)

    def _ages(self, x: pd.DataFrame) -> NDArray[np.float64]:
        if self.age_column not in x.columns:
            raise ValueError(f"x is missing age column: {self.age_column}")
        ages = pd.to_numeric(x[self.age_column], errors="coerce")
        if ages.isna().any():
            raise ValueError(f"{self.age_column} must not contain missing values")
        return np.asarray(ages, dtype=np.float64)
