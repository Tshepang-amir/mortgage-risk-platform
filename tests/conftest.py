"""Shared test fixtures backed by deterministic synthetic mortgage data."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pyspark.sql import SparkSession

from mortgage_risk.common.spark import build_local_spark
from mortgage_risk.data.synthetic import SyntheticPanel, generate_synthetic_panel


@pytest.fixture
def synthetic_panel() -> SyntheticPanel:
    """Small panel that downstream tests can reuse without real Fannie Mae files."""
    return generate_synthetic_panel(loan_count=12, max_months=24, seed=20260915)


@pytest.fixture(scope="session")
def spark_session(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SparkSession]:
    """One small Delta-enabled Spark session for integration and DQ tests."""
    warehouse = tmp_path_factory.mktemp("spark-warehouse")
    spark = build_local_spark("mortgage-risk-tests", warehouse)
    yield spark
    spark.stop()
