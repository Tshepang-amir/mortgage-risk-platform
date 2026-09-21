"""Discrete-time logistic hazard model with loan-age splines."""

from __future__ import annotations

from collections.abc import Sequence

from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import SplineTransformer, StandardScaler  # type: ignore[import-untyped]

from mortgage_risk.config.model import RANDOM_SEED, SCORECARD_FEATURES


def build_hazard_model(features: Sequence[str] = SCORECARD_FEATURES) -> Pipeline:
    """Create a discrete-time hazard pipeline before fitting."""
    feature_names = list(features)
    age_column = "SEASONING_MONTHS"
    if age_column not in feature_names:
        raise ValueError(f"hazard features must include {age_column}")
    other_features = [name for name in feature_names if name != age_column]

    age_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("spline", SplineTransformer(n_knots=5, degree=3, include_bias=False)),
            ("scale", StandardScaler()),
        ]
    )
    numeric_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    transformer = ColumnTransformer(
        [
            ("loan_age", age_pipeline, [age_column]),
            ("numeric", numeric_pipeline, other_features),
        ]
    )
    return Pipeline(
        [
            ("features", transformer),
            (
                "logistic",
                LogisticRegression(max_iter=2_000, random_state=RANDOM_SEED),
            ),
        ]
    )
