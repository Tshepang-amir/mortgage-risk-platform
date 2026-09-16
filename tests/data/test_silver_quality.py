"""Great Expectations contract tests for the Silver transition."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from mortgage_risk.data.bronze import ingest_bronze, read_bronze
from mortgage_risk.data.quality import DataQualityError, validate_silver
from mortgage_risk.data.silver import transform_to_silver
from mortgage_risk.data.synthetic import SyntheticPanel, write_synthetic_panel


def test_duplicate_loan_month_fails_silver_gate(
    tmp_path: Path,
    spark_session: SparkSession,
    synthetic_panel: SyntheticPanel,
) -> None:
    raw_path = tmp_path / "duplicate-test.csv"
    bronze_path = tmp_path / "bronze"
    write_synthetic_panel(raw_path, synthetic_panel)
    ingest_bronze(
        spark_session,
        [raw_path],
        bronze_path,
        ingested_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )
    silver = transform_to_silver(read_bronze(spark_session, bronze_path))
    duplicate = silver.unionByName(silver.limit(1))

    with pytest.raises(DataQualityError) as exc_info:
        validate_silver(duplicate)

    assert "expect_compound_columns_to_be_unique" in exc_info.value.report.failed_expectations
