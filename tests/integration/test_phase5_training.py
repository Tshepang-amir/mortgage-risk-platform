"""End-to-end synthetic training, extraction, and MLflow tracking tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import mlflow
import pandas as pd  # type: ignore[import-untyped]
from pyspark.sql import SparkSession

from mortgage_risk.config.model import SCORECARD_FEATURES
from mortgage_risk.models.training import collect_model_frame, train_and_track_phase5


def _training_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split, count, year in (("train", 120, 2015), ("validation", 100, 2017)):
        for index in range(count):
            event = index % 4 == 0
            activity = date(year, index % 12 + 1, 1)
            rows.append(
                {
                    "LOAN_ID": f"{split[:1].upper()}{index:05d}",
                    "ACT_PERIOD": activity,
                    "LAST_OBSERVED_DATE": activity + timedelta(days=32),
                    "MODELLING_SPLIT": split,
                    "LABEL_OBSERVED_12M": True,
                    "CLASSIC_FICO": 620 + index % 7 if event else 760 + index % 7,
                    "OLTV": 96 + index % 3 if event else 70 + index % 3,
                    "DTI": 48 + index % 2 if event else 27 + index % 2,
                    "CURRENT_LTV": 108 + index % 4 if event else 64 + index % 4,
                    "SEASONING_MONTHS": index % 7,
                    "UNRATE": 4.0 + (index % 8) / 10,
                    "MORTGAGE30US": 3.0 + (index % 10) / 10,
                    "DEFAULT_IN_12M": int(event),
                    "DEFAULT_NEXT_MONTH": int(index % 5 == 0),
                }
            )
    return pd.DataFrame(rows)


def test_collect_model_frame_samples_whole_loans(spark_session: SparkSession) -> None:
    frame = _training_frame().head(12)
    gold = spark_session.createDataFrame(frame)

    collected = collect_model_frame(gold, sample_buckets=1, sample_keep=1)

    assert len(collected) == len(frame)
    assert tuple(name for name in SCORECARD_FEATURES if name in collected) == SCORECARD_FEATURES
    assert collected[["LOAN_ID", "ACT_PERIOD"]].equals(
        collected[["LOAN_ID", "ACT_PERIOD"]].sort_values(["LOAN_ID", "ACT_PERIOD"])
    )


def test_train_and_track_phase5_records_reproducibility_contract(tmp_path: Path) -> None:
    tracking_uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
    client = mlflow.MlflowClient(tracking_uri=tracking_uri)
    client.create_experiment(
        "phase5-test",
        artifact_location=(tmp_path / "artifacts").as_uri(),
    )
    result = train_and_track_phase5(
        _training_frame(),
        gold_delta_version=7,
        tracking_uri=tracking_uri,
        experiment_name="phase5-test",
        bootstrap_replicates=50,
    )

    run = client.get_run(result.run_id)
    artifact_paths = {item.path for item in client.list_artifacts(result.run_id)}

    assert run.data.params["gold_delta_version"] == "7"
    assert run.data.params["feature_list_hash"] == result.feature_list_hash
    assert (
        run.data.metrics["validation_scorecard_auc"] > run.data.metrics["validation_baseline_auc"]
    )
    assert result.metrics.gini_improvement.estimate > 0
    assert run.data.metrics["validation_gini_improvement_ci_lower"] == (
        result.metrics.gini_improvement.lower
    )
    assert {"contracts", "scorecard"}.issubset(artifact_paths)
