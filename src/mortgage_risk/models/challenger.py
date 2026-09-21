"""Phase 6 LightGBM training, calibration, comparison, and tracking."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

import mlflow
import mlflow.lightgbm
import mlflow.sklearn
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from mlflow.models import infer_signature
from numpy.typing import ArrayLike
from sklearn.calibration import CalibratedClassifierCV  # type: ignore[import-untyped]
from sklearn.frozen import FrozenEstimator  # type: ignore[import-untyped]
from sklearn.metrics import brier_score_loss, roc_auc_score  # type: ignore[import-untyped]

from mortgage_risk.config.model import (
    BOOTSTRAP_REPLICATES,
    CHALLENGER_CALIBRATION_METHOD,
    CHALLENGER_EXPERIMENT_NAME,
    CHALLENGER_MONOTONIC_DIRECTIONS,
    SCORECARD_FEATURES,
    SCORECARD_TARGET,
)
from mortgage_risk.models.gbm import build_challenger, monotonic_constraints
from mortgage_risk.models.scorecard import build_scorecard
from mortgage_risk.models.training import feature_list_hash
from mortgage_risk.validation.bootstrap import BootstrapInterval, clustered_gini_difference
from mortgage_risk.validation.monotonicity import MonotonicSweep, evaluate_monotonic_sweeps

_REQUIRED_COLUMNS: Final = frozenset(
    {
        "LOAN_ID",
        "MODELLING_SPLIT",
        "LABEL_OBSERVED_12M",
        SCORECARD_TARGET,
        *SCORECARD_FEATURES,
    }
)


@dataclass(frozen=True, slots=True)
class ChallengerMetrics:
    """Out-of-time ranking and calibration evidence for model selection."""

    scorecard_auc: float
    scorecard_gini: float
    challenger_raw_auc: float
    challenger_raw_gini: float
    challenger_calibrated_auc: float
    challenger_calibrated_gini: float
    challenger_raw_brier: float
    challenger_calibrated_brier: float
    gini_improvement: BootstrapInterval

    @property
    def calibration_brier_change(self) -> float:
        """Return calibrated minus raw Brier; negative means improvement."""
        return self.challenger_calibrated_brier - self.challenger_raw_brier


@dataclass(frozen=True, slots=True)
class ChallengerTrainingResult:
    """Tracked Phase 6 challenger run and evidence-based selection."""

    run_id: str
    gold_delta_version: int
    feature_list_hash: str
    metrics: ChallengerMetrics
    monotonic_sweeps: tuple[MonotonicSweep, ...]

    @property
    def selected_model(self) -> str:
        """Ship the challenger only when its entire Gini interval is positive."""
        return "challenger" if self.metrics.gini_improvement.lower > 0 else "scorecard"


def train_and_track_challenger(
    frame: pd.DataFrame,
    *,
    gold_delta_version: int,
    tracking_uri: str | None = None,
    experiment_name: str = CHALLENGER_EXPERIMENT_NAME,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> ChallengerTrainingResult:
    """Fit, calibrate, compare, and track the Phase 6 challenger."""
    if gold_delta_version < 0:
        raise ValueError("gold_delta_version must be non-negative")
    _validate_frame(frame)
    features = list(SCORECARD_FEATURES)
    training = _labelled_split(frame, "train")
    calibration = _labelled_split(frame, "validation")
    out_of_time = _labelled_split(frame, "out_of_time")

    x_train, y_train = _model_xy(training, features)
    x_calibration, y_calibration = _model_xy(calibration, features)
    x_out_of_time, y_out_of_time = _model_xy(out_of_time, features)

    scorecard = build_scorecard()
    scorecard.fit(x_train, y_train)
    challenger = build_challenger()
    challenger.fit(x_train, y_train)

    calibrated = CalibratedClassifierCV(
        estimator=FrozenEstimator(challenger),
        method=CHALLENGER_CALIBRATION_METHOD,
    )
    calibrated.fit(x_calibration, y_calibration)
    reference = {name: float(x_train[name].median()) for name in SCORECARD_FEATURES}
    sweeps = evaluate_monotonic_sweeps(calibrated, reference)

    scorecard_probability = np.asarray(scorecard.predict_proba(x_out_of_time))[:, 1]
    raw_probability = np.asarray(challenger.predict_proba(x_out_of_time))[:, 1]
    calibrated_probability = np.asarray(calibrated.predict_proba(x_out_of_time))[:, 1]
    interval = clustered_gini_difference(
        y_out_of_time,
        calibrated_probability,
        scorecard_probability,
        out_of_time["LOAN_ID"].to_numpy(),
        replicates=bootstrap_replicates,
    )

    scorecard_auc = _auc(y_out_of_time, scorecard_probability)
    raw_auc = _auc(y_out_of_time, raw_probability)
    calibrated_auc = _auc(y_out_of_time, calibrated_probability)
    metrics = ChallengerMetrics(
        scorecard_auc=scorecard_auc,
        scorecard_gini=_gini_from_auc(scorecard_auc),
        challenger_raw_auc=raw_auc,
        challenger_raw_gini=_gini_from_auc(raw_auc),
        challenger_calibrated_auc=calibrated_auc,
        challenger_calibrated_gini=_gini_from_auc(calibrated_auc),
        challenger_raw_brier=float(brier_score_loss(y_out_of_time, raw_probability)),
        challenger_calibrated_brier=float(brier_score_loss(y_out_of_time, calibrated_probability)),
        gini_improvement=interval,
    )
    feature_hash = feature_list_hash(SCORECARD_FEATURES)
    selection = "challenger" if interval.lower > 0 else "scorecard"

    if tracking_uri is not None:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=f"challenger-gold-v{gold_delta_version}") as run:
        _log_contract(
            frame=frame,
            gold_delta_version=gold_delta_version,
            feature_hash=feature_hash,
            metrics=metrics,
            sweeps=sweeps,
            selection=selection,
        )
        example = x_train.head(5)
        mlflow.lightgbm.log_model(
            challenger,
            name="challenger_raw",
            serialization_format="cloudpickle",
            signature=infer_signature(example, challenger.predict_proba(example)),
            input_example=example,
        )
        mlflow.sklearn.log_model(
            calibrated,
            name="challenger_calibrated",
            serialization_format="cloudpickle",
            signature=infer_signature(example, calibrated.predict_proba(example)),
            input_example=example,
            pyfunc_predict_fn="predict_proba",
        )
        mlflow.sklearn.log_model(
            scorecard,
            name="scorecard_reference",
            serialization_format="cloudpickle",
            signature=infer_signature(example, scorecard.predict_proba(example)),
            input_example=example,
            pyfunc_predict_fn="predict_proba",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            importance_path = root / "feature-importance.csv"
            pd.DataFrame(
                {
                    "feature": list(SCORECARD_FEATURES),
                    "gain": challenger.booster_.feature_importance(importance_type="gain"),
                }
            ).sort_values("gain", ascending=False).to_csv(importance_path, index=False)
            scorecard_path = root / "scorecard-bins.csv"
            scorecard.table(style="detailed").to_csv(scorecard_path, index=False)
            mlflow.log_artifact(str(importance_path), artifact_path="challenger")
            mlflow.log_artifact(str(scorecard_path), artifact_path="scorecard-reference")
        run_id = str(run.info.run_id)

    return ChallengerTrainingResult(
        run_id=run_id,
        gold_delta_version=gold_delta_version,
        feature_list_hash=feature_hash,
        metrics=metrics,
        monotonic_sweeps=sweeps,
    )


def _validate_frame(frame: pd.DataFrame) -> None:
    missing = sorted(_REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"challenger frame is missing columns: {missing}")
    if frame.empty:
        raise ValueError("challenger frame must not be empty")


def _labelled_split(frame: pd.DataFrame, split: str) -> pd.DataFrame:
    selected = frame.loc[
        (frame["MODELLING_SPLIT"] == split)
        & frame["LABEL_OBSERVED_12M"].astype(bool)
        & frame[SCORECARD_TARGET].notna()
    ].copy()
    classes = set(selected[SCORECARD_TARGET].dropna().astype(int).unique())
    if classes != {0, 1}:
        raise ValueError(f"{split} split must contain both classes for {SCORECARD_TARGET}")
    return selected


def _model_xy(
    frame: pd.DataFrame, features: list[str]
) -> tuple[pd.DataFrame, np.ndarray[tuple[int], np.dtype[np.int64]]]:
    x = frame.loc[:, features].astype("float64")
    y = frame[SCORECARD_TARGET].astype(int).to_numpy(dtype=np.int64)
    return x, y


def _auc(target: ArrayLike, probability: ArrayLike) -> float:
    return float(roc_auc_score(target, probability))


def _gini_from_auc(auc: float) -> float:
    return 2.0 * auc - 1.0


def _log_contract(
    *,
    frame: pd.DataFrame,
    gold_delta_version: int,
    feature_hash: str,
    metrics: ChallengerMetrics,
    sweeps: tuple[MonotonicSweep, ...],
    selection: str,
) -> None:
    constraints = monotonic_constraints()
    mlflow.log_params(
        {
            "gold_delta_version": gold_delta_version,
            "feature_list_hash": feature_hash,
            "target": SCORECARD_TARGET,
            "calibration_method": CHALLENGER_CALIBRATION_METHOD,
            "calibration_split": "validation",
            "evaluation_split": "out_of_time",
            "monotonic_constraints": json.dumps(constraints),
        }
    )
    mlflow.log_metrics(
        {
            "oot_scorecard_auc": metrics.scorecard_auc,
            "oot_scorecard_gini": metrics.scorecard_gini,
            "oot_challenger_raw_auc": metrics.challenger_raw_auc,
            "oot_challenger_raw_gini": metrics.challenger_raw_gini,
            "oot_challenger_calibrated_auc": metrics.challenger_calibrated_auc,
            "oot_challenger_calibrated_gini": metrics.challenger_calibrated_gini,
            "oot_challenger_raw_brier": metrics.challenger_raw_brier,
            "oot_challenger_calibrated_brier": metrics.challenger_calibrated_brier,
            "oot_calibration_brier_change": metrics.calibration_brier_change,
            "oot_gini_improvement": metrics.gini_improvement.estimate,
            "oot_gini_improvement_ci_lower": metrics.gini_improvement.lower,
            "oot_gini_improvement_ci_upper": metrics.gini_improvement.upper,
            "bootstrap_successful_replicates": metrics.gini_improvement.successful_replicates,
        }
    )
    mlflow.log_dict(
        {
            "features": list(SCORECARD_FEATURES),
            "feature_list_hash": feature_hash,
            "monotonic_directions": CHALLENGER_MONOTONIC_DIRECTIONS,
        },
        "contracts/challenger-features.json",
    )
    mlflow.log_dict(
        {
            "calibration_split": "validation",
            "evaluation_split": "out_of_time",
            "row_counts": {
                str(name): int(count)
                for name, count in frame["MODELLING_SPLIT"].value_counts().sort_index().items()
            },
        },
        "contracts/challenger-splits.json",
    )
    mlflow.log_dict(
        {"sweeps": [asdict(sweep) for sweep in sweeps]},
        "validation/monotonic-sweeps.json",
    )
    mlflow.log_dict(
        {
            "selected_model": selection,
            "rule": "select challenger only when lower 95% Gini-improvement bound is above zero",
            "gini_improvement": asdict(metrics.gini_improvement),
        },
        "validation/model-selection.json",
    )
