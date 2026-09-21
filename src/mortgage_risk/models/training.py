"""Phase 5 extraction, model fitting, evaluation, and MLflow tracking."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from mlflow.models import infer_signature
from numpy.typing import ArrayLike
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as spark_fn
from sklearn.metrics import roc_auc_score  # type: ignore[import-untyped]

from mortgage_risk.config.gold import OUTCOME_COLUMNS, TRAIN_END, VALIDATION_END
from mortgage_risk.config.model import (
    BOOTSTRAP_REPLICATES,
    HAZARD_TARGET,
    MLFLOW_EXPERIMENT_NAME,
    MODEL_SAMPLE_BUCKETS,
    MODEL_SAMPLE_KEEP,
    SCORECARD_FEATURES,
    SCORECARD_TARGET,
)
from mortgage_risk.models.baseline import MarginalRateBaseline
from mortgage_risk.models.hazard import build_hazard_model
from mortgage_risk.models.scorecard import build_scorecard
from mortgage_risk.validation.bootstrap import BootstrapInterval, clustered_gini_difference

_EXTRACTION_COLUMNS: Final = (
    "LOAN_ID",
    "ACT_PERIOD",
    "LAST_OBSERVED_DATE",
    "MODELLING_SPLIT",
    "LABEL_OBSERVED_12M",
    *SCORECARD_FEATURES,
    SCORECARD_TARGET,
    HAZARD_TARGET,
)


@dataclass(frozen=True, slots=True)
class Phase5Metrics:
    """Validation metrics and the paired model-improvement interval."""

    baseline_auc: float
    baseline_gini: float
    scorecard_auc: float
    scorecard_gini: float
    hazard_auc: float
    gini_improvement: BootstrapInterval


@dataclass(frozen=True, slots=True)
class Phase5TrainingResult:
    """Tracked Phase 5 model run."""

    run_id: str
    gold_delta_version: int
    feature_list_hash: str
    metrics: Phase5Metrics

    @property
    def scorecard_beats_baseline(self) -> bool:
        """Require the entire paired 95% interval to be above zero."""
        return self.metrics.gini_improvement.lower > 0


def load_gold_model_frame(
    spark: SparkSession,
    gold_path: Path,
    gold_delta_version: int,
    *,
    sample_buckets: int = MODEL_SAMPLE_BUCKETS,
    sample_keep: int = MODEL_SAMPLE_KEEP,
) -> pd.DataFrame:
    """Read one immutable Gold Delta version into a deterministic loan sample."""
    if gold_delta_version < 0:
        raise ValueError("gold_delta_version must be non-negative")
    gold = (
        spark.read.format("delta")
        .option("versionAsOf", gold_delta_version)
        .load(str(gold_path.resolve()))
    )
    return collect_model_frame(
        gold,
        sample_buckets=sample_buckets,
        sample_keep=sample_keep,
    )


def collect_model_frame(
    gold: DataFrame,
    *,
    sample_buckets: int = MODEL_SAMPLE_BUCKETS,
    sample_keep: int = MODEL_SAMPLE_KEEP,
) -> pd.DataFrame:
    """Collect a deterministic loan-level hash sample from Gold."""
    if sample_buckets <= 0 or not 0 < sample_keep <= sample_buckets:
        raise ValueError("sample_keep must be between one and sample_buckets")
    missing = sorted(set(_EXTRACTION_COLUMNS).difference(gold.columns))
    if missing:
        raise ValueError(f"Gold data is missing model columns: {missing}")
    leaking_features = sorted(set(SCORECARD_FEATURES).intersection(OUTCOME_COLUMNS))
    if leaking_features:
        raise ValueError(f"configured model features include outcomes: {leaking_features}")

    sampled = gold.where(
        spark_fn.pmod(spark_fn.xxhash64("LOAN_ID"), spark_fn.lit(sample_buckets)) < sample_keep
    )
    return sampled.select(*_EXTRACTION_COLUMNS).orderBy("LOAN_ID", "ACT_PERIOD").toPandas()


def train_and_track_phase5(
    frame: pd.DataFrame,
    *,
    gold_delta_version: int,
    tracking_uri: str | None = None,
    experiment_name: str = MLFLOW_EXPERIMENT_NAME,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> Phase5TrainingResult:
    """Fit all Phase 5 models and log one reproducible MLflow run."""
    _validate_training_frame(frame)
    features = list(SCORECARD_FEATURES)
    training = frame.loc[
        (frame["MODELLING_SPLIT"] == "train")
        & frame["LABEL_OBSERVED_12M"].astype(bool)
        & frame[SCORECARD_TARGET].notna()
    ].copy()
    validation = frame.loc[
        (frame["MODELLING_SPLIT"] == "validation")
        & frame["LABEL_OBSERVED_12M"].astype(bool)
        & frame[SCORECARD_TARGET].notna()
    ].copy()
    _require_binary_split(training, SCORECARD_TARGET, "training")
    _require_binary_split(validation, SCORECARD_TARGET, "validation")

    x_train = training.loc[:, features].astype("float64")
    y_train = training[SCORECARD_TARGET].astype(int).to_numpy()
    x_validation = validation.loc[:, features].astype("float64")
    y_validation = validation[SCORECARD_TARGET].astype(int).to_numpy()

    baseline = MarginalRateBaseline().fit(x_train, y_train)
    scorecard = build_scorecard()
    scorecard.fit(x_train, y_train)
    baseline_probability = baseline.predict_proba(x_validation)[:, 1]
    scorecard_probability = np.asarray(scorecard.predict_proba(x_validation))[:, 1]
    interval = clustered_gini_difference(
        y_validation,
        scorecard_probability,
        baseline_probability,
        validation["LOAN_ID"].to_numpy(),
        replicates=bootstrap_replicates,
    )

    hazard_training = _observed_hazard_rows(frame, "train")
    hazard_validation = _observed_hazard_rows(frame, "validation")
    _require_binary_split(hazard_training, HAZARD_TARGET, "hazard training")
    _require_binary_split(hazard_validation, HAZARD_TARGET, "hazard validation")
    hazard = build_hazard_model()
    hazard_x_train = hazard_training.loc[:, features].astype("float64")
    hazard_x_validation = hazard_validation.loc[:, features].astype("float64")
    hazard.fit(
        hazard_x_train,
        hazard_training[HAZARD_TARGET].astype(int).to_numpy(),
    )
    hazard_probability = hazard.predict_proba(hazard_x_validation)[:, 1]

    baseline_auc = _auc(y_validation, baseline_probability)
    scorecard_auc = _auc(y_validation, scorecard_probability)
    metrics = Phase5Metrics(
        baseline_auc=baseline_auc,
        baseline_gini=2.0 * baseline_auc - 1.0,
        scorecard_auc=scorecard_auc,
        scorecard_gini=2.0 * scorecard_auc - 1.0,
        hazard_auc=_auc(
            hazard_validation[HAZARD_TARGET].astype(int).to_numpy(),
            hazard_probability,
        ),
        gini_improvement=interval,
    )
    feature_hash = feature_list_hash(SCORECARD_FEATURES)

    if tracking_uri is not None:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=f"gold-v{gold_delta_version}") as run:
        _log_run_contract(
            frame=frame,
            gold_delta_version=gold_delta_version,
            feature_hash=feature_hash,
            metrics=metrics,
        )
        example = x_train.head(5)
        mlflow.sklearn.log_model(
            baseline,
            name="marginal_baseline",
            serialization_format="cloudpickle",
            signature=infer_signature(example, baseline.predict_proba(example)),
            input_example=example,
            pyfunc_predict_fn="predict_proba",
        )
        mlflow.sklearn.log_model(
            scorecard,
            name="scorecard",
            serialization_format="cloudpickle",
            signature=infer_signature(example, scorecard.predict_proba(example)),
            input_example=example,
            pyfunc_predict_fn="predict_proba",
        )
        hazard_example = hazard_x_train.head(5)
        mlflow.sklearn.log_model(
            hazard,
            name="hazard",
            serialization_format="cloudpickle",
            signature=infer_signature(hazard_example, hazard.predict_proba(hazard_example)),
            input_example=hazard_example,
            pyfunc_predict_fn="predict_proba",
        )
        with tempfile.TemporaryDirectory() as directory:
            table_path = Path(directory) / "scorecard-bins.csv"
            scorecard.table(style="detailed").to_csv(table_path, index=False)
            mlflow.log_artifact(str(table_path), artifact_path="scorecard")
        run_id = str(run.info.run_id)

    return Phase5TrainingResult(
        run_id=run_id,
        gold_delta_version=gold_delta_version,
        feature_list_hash=feature_hash,
        metrics=metrics,
    )


def feature_list_hash(features: tuple[str, ...]) -> str:
    """Hash an ordered feature contract for run-to-run comparison."""
    payload = json.dumps(list(features), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _observed_hazard_rows(frame: pd.DataFrame, split: str) -> pd.DataFrame:
    activity = pd.to_datetime(frame["ACT_PERIOD"])
    last_observed = pd.to_datetime(frame["LAST_OBSERVED_DATE"])
    return frame.loc[
        (frame["MODELLING_SPLIT"] == split)
        & frame[HAZARD_TARGET].notna()
        & (activity < last_observed)
    ].copy()


def _validate_training_frame(frame: pd.DataFrame) -> None:
    missing = sorted(set(_EXTRACTION_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"training frame is missing columns: {missing}")
    if frame.empty:
        raise ValueError("training frame must not be empty")


def _require_binary_split(frame: pd.DataFrame, target: str, label: str) -> None:
    if frame.empty or set(frame[target].dropna().astype(int).unique()) != {0, 1}:
        raise ValueError(f"{label} split must contain both classes for {target}")


def _auc(target: ArrayLike, probability: ArrayLike) -> float:
    return float(roc_auc_score(target, probability))


def _log_run_contract(
    *,
    frame: pd.DataFrame,
    gold_delta_version: int,
    feature_hash: str,
    metrics: Phase5Metrics,
) -> None:
    mlflow.log_params(
        {
            "gold_delta_version": gold_delta_version,
            "feature_list_hash": feature_hash,
            "scorecard_target": SCORECARD_TARGET,
            "hazard_target": HAZARD_TARGET,
            "train_end": TRAIN_END.isoformat(),
            "validation_end": VALIDATION_END.isoformat(),
        }
    )
    mlflow.log_metrics(
        {
            "validation_baseline_auc": metrics.baseline_auc,
            "validation_baseline_gini": metrics.baseline_gini,
            "validation_scorecard_auc": metrics.scorecard_auc,
            "validation_scorecard_gini": metrics.scorecard_gini,
            "validation_hazard_auc": metrics.hazard_auc,
            "validation_gini_improvement": metrics.gini_improvement.estimate,
            "validation_gini_improvement_ci_lower": metrics.gini_improvement.lower,
            "validation_gini_improvement_ci_upper": metrics.gini_improvement.upper,
            "bootstrap_successful_replicates": metrics.gini_improvement.successful_replicates,
        }
    )
    split_counts = {
        str(name): int(count)
        for name, count in frame["MODELLING_SPLIT"].value_counts().sort_index().items()
    }
    mlflow.log_dict(
        {
            "features": list(SCORECARD_FEATURES),
            "feature_list_hash": feature_hash,
        },
        "contracts/features.json",
    )
    mlflow.log_dict(
        {
            "train_end": TRAIN_END.isoformat(),
            "validation_end": VALIDATION_END.isoformat(),
            "precedence": "out_of_vintage before temporal split",
            "row_counts": split_counts,
        },
        "contracts/splits.json",
    )
