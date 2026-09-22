"""Tests for real-data pipeline cache loading and path contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pyspark.sql import SparkSession

from mortgage_risk.config.gold import FRED_SERIES_IDS
from mortgage_risk.data.gold import require_source_versions
from mortgage_risk.data.pipeline import (
    PipelinePaths,
    load_cached_macro_observations,
    run_stage,
)


def test_pipeline_paths_name_every_publication_layer(tmp_path: Path) -> None:
    paths = PipelinePaths(tmp_path / "raw", tmp_path / "external", tmp_path / "delta")

    assert tuple(path.name for path in paths.raw_files) == (
        "2005Q1.csv",
        "2005Q3.csv",
        "2007Q1.csv",
        "2012Q1.csv",
        "2016Q1.csv",
        "2018Q1.csv",
    )
    assert paths.bronze == tmp_path / "delta" / "bronze"
    assert paths.silver == tmp_path / "delta" / "silver"
    assert paths.macro == tmp_path / "delta" / "macro"
    assert paths.gold == tmp_path / "delta" / "gold"


def test_cached_macro_loader_requires_and_labels_every_series(tmp_path: Path) -> None:
    payload = {
        "observations": [{"date": "2015-01-01", "realtime_start": "2015-02-01", "value": "1.25"}]
    }
    for series_id in FRED_SERIES_IDS:
        (tmp_path / f"{series_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    observations = load_cached_macro_observations(tmp_path)

    assert len(observations) == len(FRED_SERIES_IDS)
    assert {item.series_id for item in observations} == set(FRED_SERIES_IDS)


def test_cached_macro_loader_rejects_a_missing_series(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"UNRATE\.json"):
        load_cached_macro_observations(tmp_path)


def test_run_stage_rejects_an_unknown_stage(tmp_path: Path) -> None:
    """The dispatch decides what actually executes, so a typo must not pass silently.

    Spark is never touched: the guard is reached before any stage runs, which is
    what makes this cheap enough to be a unit test.
    """
    paths = PipelinePaths(tmp_path / "raw", tmp_path / "external", tmp_path / "delta")

    with pytest.raises(ValueError, match="unsupported pipeline stage"):
        run_stage(cast(SparkSession, None), "goldd", paths)


def test_source_versions_require_both_inputs() -> None:
    """A Gold build records what it was derived from, or it is not reproducible.

    Section 8 makes Delta time travel the reproducibility mechanism. Recording
    only the version Gold was written at says what was produced, not what it was
    produced from, so an incomplete lineage is refused rather than stored.
    """
    assert require_source_versions({"silver": 3, "macro": 0}) == {"silver": 3, "macro": 0}

    with pytest.raises(ValueError, match="missing source Delta versions"):
        require_source_versions({"silver": 3})

    with pytest.raises(ValueError, match="unexpected source Delta versions"):
        require_source_versions({"silver": 3, "macro": 0, "bronze": 1})

    with pytest.raises(ValueError, match="must be non-negative"):
        require_source_versions({"silver": 3, "macro": -1})
