"""Focused arithmetic and fitting tests for the Phase 5 estimators."""

from __future__ import annotations

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pytest

from mortgage_risk.config.model import SCORECARD_FEATURES
from mortgage_risk.models.baseline import MarginalRateBaseline
from mortgage_risk.models.hazard import build_hazard_model
from mortgage_risk.models.scorecard import MONOTONIC_TRENDS, build_scorecard
from mortgage_risk.validation.bootstrap import clustered_gini_difference


def _features(rows: int = 80) -> pd.DataFrame:
    index = np.arange(rows)
    event = index % 4 == 0
    return pd.DataFrame(
        {
            "CLASSIC_FICO": np.where(event, 620, 760) + index % 7,
            "OLTV": np.where(event, 96, 70) + index % 3,
            "DTI": np.where(event, 48, 27) + index % 2,
            "CURRENT_LTV": np.where(event, 108, 64) + index % 4,
            "SEASONING_MONTHS": index % 60,
            "UNRATE": 4.0 + (index % 8) / 10,
            "MORTGAGE30US": 3.0 + (index % 10) / 10,
        }
    )


def test_marginal_baseline_smooths_age_rates_and_uses_global_fallback() -> None:
    x = pd.DataFrame({"SEASONING_MONTHS": [1, 1, 2, 2]})
    model = MarginalRateBaseline(smoothing=2.0).fit(x, np.asarray([1, 1, 0, 0]))

    probabilities = model.predict_proba(pd.DataFrame({"SEASONING_MONTHS": [1, 2, 99]}))[:, 1]

    assert probabilities == pytest.approx([0.75, 0.25, 0.5])


def test_scorecard_declares_monotonic_woe_rules_and_pdo_scaling() -> None:
    scorecard = build_scorecard()
    params = scorecard.get_params(deep=False)
    process_params = params["binning_process"].get_params()

    assert params["scaling_method"] == "pdo_odds"
    assert params["scaling_method_params"] == {
        "pdo": 20,
        "odds": 50,
        "scorecard_points": 600,
    }
    for feature, trend in MONOTONIC_TRENDS.items():
        assert process_params["binning_fit_params"][feature]["monotonic_trend"] == trend


def test_scorecard_rejects_a_feature_set_without_required_monotonic_drivers() -> None:
    with pytest.raises(ValueError, match="CLASSIC_FICO"):
        build_scorecard(("SEASONING_MONTHS",))


def test_hazard_pipeline_fits_spline_age_and_returns_probabilities() -> None:
    x = _features()
    target = (np.arange(len(x)) % 5 == 0).astype(int)
    model = build_hazard_model().fit(x, target)

    probabilities = model.predict_proba(x.head(6))

    assert probabilities.shape == (6, 2)
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert list(x.columns) == list(SCORECARD_FEATURES)


def test_clustered_bootstrap_reports_reproducible_gini_gain() -> None:
    target = np.asarray([0, 1] * 30)
    candidate = np.where(target == 1, 0.9, 0.1)
    baseline = np.full(len(target), 0.5)
    clusters = np.asarray([f"L{index:03d}" for index in range(len(target))])

    first = clustered_gini_difference(
        target,
        candidate,
        baseline,
        clusters,
        replicates=100,
        seed=17,
    )
    second = clustered_gini_difference(
        target,
        candidate,
        baseline,
        clusters,
        replicates=100,
        seed=17,
    )

    assert first == second
    assert first.estimate == pytest.approx(1.0)
    assert first.lower > 0
    assert first.successful_replicates == 100


def test_clustered_bootstrap_rejects_a_single_class() -> None:
    with pytest.raises(ValueError, match="both classes"):
        clustered_gini_difference(
            [0, 0],
            [0.1, 0.2],
            [0.1, 0.1],
            ["A", "B"],
            replicates=10,
        )
