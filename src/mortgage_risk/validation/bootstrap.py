"""Loan-clustered bootstrap intervals for model discrimination gains."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from sklearn.metrics import roc_auc_score  # type: ignore[import-untyped]

from mortgage_risk.config.model import BOOTSTRAP_ALPHA, BOOTSTRAP_REPLICATES, RANDOM_SEED


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    """Point estimate and percentile interval for a paired Gini difference."""

    estimate: float
    lower: float
    upper: float
    successful_replicates: int


def clustered_gini_difference(
    y_true: ArrayLike,
    candidate_probability: ArrayLike,
    baseline_probability: ArrayLike,
    clusters: ArrayLike,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    alpha: float = BOOTSTRAP_ALPHA,
    seed: int = RANDOM_SEED,
) -> BootstrapInterval:
    """Bootstrap a paired candidate-minus-baseline Gini by loan."""
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")

    target = np.asarray(y_true, dtype=np.int64)
    candidate = np.asarray(candidate_probability, dtype=np.float64)
    baseline = np.asarray(baseline_probability, dtype=np.float64)
    cluster_ids = np.asarray(clusters)
    lengths = {len(target), len(candidate), len(baseline), len(cluster_ids)}
    if len(lengths) != 1 or not lengths or len(target) == 0:
        raise ValueError("all bootstrap inputs must be non-empty and aligned")
    if np.unique(target).size != 2:
        raise ValueError("y_true must contain both classes")

    unique_clusters = np.unique(cluster_ids)
    if unique_clusters.size < 2:
        raise ValueError("clustered bootstrap requires at least two loans")
    rows_by_cluster = {value: np.flatnonzero(cluster_ids == value) for value in unique_clusters}
    generator = np.random.default_rng(seed)
    differences: list[float] = []
    for _ in range(replicates):
        sampled = generator.choice(unique_clusters, size=unique_clusters.size, replace=True)
        row_indices = np.concatenate([rows_by_cluster[value] for value in sampled])
        sampled_target = target[row_indices]
        if np.unique(sampled_target).size != 2:
            continue
        differences.append(
            _gini(sampled_target, candidate[row_indices])
            - _gini(sampled_target, baseline[row_indices])
        )

    minimum_successes = max(10, replicates // 2)
    if len(differences) < minimum_successes:
        raise ValueError("too few valid bootstrap samples contained both classes")
    bounds = np.quantile(np.asarray(differences), [alpha / 2, 1 - alpha / 2])
    return BootstrapInterval(
        estimate=_gini(target, candidate) - _gini(target, baseline),
        lower=float(bounds[0]),
        upper=float(bounds[1]),
        successful_replicates=len(differences),
    )


def _gini(target: ArrayLike, probability: ArrayLike) -> float:
    return float(2.0 * roc_auc_score(target, probability) - 1.0)
