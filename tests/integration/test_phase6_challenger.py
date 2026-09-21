"""End-to-end Phase 6 calibration, comparison, and MLflow tracking test."""

from __future__ import annotations

from pathlib import Path

import mlflow
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pytest

from mortgage_risk.models.challenger import train_and_track_challenger


def _challenger_frame() -> pd.DataFrame:
    generator = np.random.default_rng(20260921)
    rows: list[dict[str, object]] = []
    for split, count in (("train", 240), ("validation", 160), ("out_of_time", 180)):
        fico = generator.uniform(520, 830, count)
        oltv = generator.uniform(45, 120, count)
        dti = generator.uniform(10, 60, count)
        current_ltv = generator.uniform(30, 160, count)
        seasoning = generator.integers(0, 120, count)
        unemployment = generator.uniform(3, 10, count)
        mortgage_rate = generator.uniform(2, 8, count)
        logit = (
            -2.2
            + (700 - fico) * 0.012
            + (oltv - 80) * 0.025
            + (dti - 35) * 0.025
            + (current_ltv - 80) * 0.012
            + (unemployment - 5) * 0.12
            + ((current_ltv > 105) & (unemployment > 6)) * 0.8
        )
        probability = 1.0 / (1.0 + np.exp(-logit))
        target = generator.binomial(1, probability)
        for index in range(count):
            rows.append(
                {
                    "LOAN_ID": f"{split[:1].upper()}{index:06d}",
                    "MODELLING_SPLIT": split,
                    "LABEL_OBSERVED_12M": True,
                    "CLASSIC_FICO": fico[index],
                    "OLTV": oltv[index],
                    "DTI": dti[index],
                    "CURRENT_LTV": current_ltv[index],
                    "SEASONING_MONTHS": seasoning[index],
                    "UNRATE": unemployment[index],
                    "MORTGAGE30US": mortgage_rate[index],
                    "DEFAULT_IN_12M": int(target[index]),
                }
            )
    return pd.DataFrame(rows)


def test_challenger_run_tracks_temporal_calibration_and_selection(tmp_path: Path) -> None:
    tracking_uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
    client = mlflow.MlflowClient(tracking_uri=tracking_uri)
    client.create_experiment(
        "phase6-test",
        artifact_location=(tmp_path / "artifacts").as_uri(),
    )

    result = train_and_track_challenger(
        _challenger_frame(),
        gold_delta_version=11,
        tracking_uri=tracking_uri,
        experiment_name="phase6-test",
        bootstrap_replicates=50,
    )

    run = client.get_run(result.run_id)
    artifact_paths = {item.path for item in client.list_artifacts(result.run_id)}

    assert run.data.params["gold_delta_version"] == "11"
    assert run.data.params["calibration_split"] == "validation"
    assert run.data.params["evaluation_split"] == "out_of_time"
    assert run.data.params["monotonic_constraints"] == "[-1, 1, 1, 1, 0, 0, 0]"
    assert result.metrics.challenger_calibrated_auc == pytest.approx(
        result.metrics.challenger_raw_auc
    )
    assert run.data.metrics["oot_calibration_brier_change"] == pytest.approx(
        result.metrics.calibration_brier_change
    )
    expected_selection = "challenger" if result.metrics.gini_improvement.lower > 0 else "scorecard"
    assert result.selected_model == expected_selection
    assert all(sweep.worst_violation == 0 for sweep in result.monotonic_sweeps)
    assert {
        "challenger",
        "contracts",
        "scorecard-reference",
        "validation",
    }.issubset(artifact_paths)
