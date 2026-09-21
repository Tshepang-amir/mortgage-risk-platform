"""WOE scorecard construction with explicit binning and points scaling."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from optbinning import BinningProcess, Scorecard  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

from mortgage_risk.config.model import (
    RANDOM_SEED,
    SCORECARD_FEATURES,
    SCORECARD_MAX_PREBINS,
    SCORECARD_MIN_PREBIN_SIZE,
    SCORECARD_ODDS,
    SCORECARD_PDO,
    SCORECARD_POINTS,
)

MONOTONIC_TRENDS: Final[dict[str, str]] = {
    "CLASSIC_FICO": "descending",
    "OLTV": "ascending",
    "DTI": "ascending",
    "CURRENT_LTV": "ascending",
}


def build_scorecard(features: Sequence[str] = SCORECARD_FEATURES) -> Scorecard:
    """Create the Phase 5 WOE logistic scorecard before fitting."""
    variable_names = list(features)
    missing_monotonic = sorted(set(MONOTONIC_TRENDS).difference(variable_names))
    if missing_monotonic:
        raise ValueError(
            f"scorecard features omit required monotonic variables: {missing_monotonic}"
        )
    fit_params = {
        name: {"monotonic_trend": direction} for name, direction in MONOTONIC_TRENDS.items()
    }

    process = BinningProcess(
        variable_names=variable_names,
        max_n_prebins=SCORECARD_MAX_PREBINS,
        min_prebin_size=SCORECARD_MIN_PREBIN_SIZE,
        binning_fit_params=fit_params,
        n_jobs=1,
    )
    estimator = LogisticRegression(max_iter=2_000, random_state=RANDOM_SEED)
    return Scorecard(
        binning_process=process,
        estimator=estimator,
        scaling_method="pdo_odds",
        scaling_method_params={
            "pdo": SCORECARD_PDO,
            "odds": SCORECARD_ODDS,
            "scorecard_points": SCORECARD_POINTS,
        },
        reverse_scorecard=False,
    )
