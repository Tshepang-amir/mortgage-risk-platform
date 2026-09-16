"""End-to-end Bronze and Silver behavior on the synthetic raw contract."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import types as spark_types

from mortgage_risk.data.bronze import ingest_bronze, read_bronze
from mortgage_risk.data.silver import publish_silver
from mortgage_risk.data.synthetic import SyntheticPanel, write_synthetic_panel


def test_bronze_replay_and_silver_publication_are_idempotent(
    tmp_path: Path,
    spark_session: SparkSession,
    synthetic_panel: SyntheticPanel,
) -> None:
    raw_path = tmp_path / "2005Q1.csv"
    bronze_path = tmp_path / "bronze"
    silver_path = tmp_path / "silver"
    servicer_path = tmp_path / "servicer"
    write_synthetic_panel(raw_path, synthetic_panel)

    timestamp = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    first = ingest_bronze(
        spark_session,
        [raw_path],
        bronze_path,
        ingested_at=timestamp,
    )
    replay = ingest_bronze(
        spark_session,
        [raw_path],
        bronze_path,
        ingested_at=timestamp,
    )

    assert first.ingested_files == ("2005Q1.csv",)
    assert first.rows_written == len(synthetic_panel.rows)
    assert replay.ingested_files == ()
    assert replay.skipped_files == ("2005Q1.csv",)
    assert replay.final_rows == first.final_rows

    bronze = read_bronze(spark_session, bronze_path)
    assert isinstance(bronze.schema["LOAN_ID"].dataType, spark_types.StringType)
    assert bronze.where("_source_sha256 IS NULL OR _ingested_at IS NULL").count() == 0

    first_publish = publish_silver(
        spark_session,
        bronze_path,
        silver_path,
        servicer_path,
    )
    replay_publish = publish_silver(
        spark_session,
        bronze_path,
        silver_path,
        servicer_path,
    )

    expected_silver_rows = len(
        {(row["LOAN_ID"], row["ACT_PERIOD"]) for row in synthetic_panel.rows}
    )
    assert first_publish.silver_rows == expected_silver_rows
    assert replay_publish.silver_rows == first_publish.silver_rows
    assert first_publish.quality.success
    assert first_publish.quality.evaluated_expectations == 9

    silver = spark_session.read.format("delta").load(str(silver_path))
    assert isinstance(silver.schema["ACT_PERIOD"].dataType, spark_types.DateType)
    assert isinstance(silver.schema["ORIG_UPB"].dataType, spark_types.DecimalType)
    minimum_upb = silver.agg({"CURRENT_UPB": "min"}).first()
    assert minimum_upb is not None
    assert minimum_upb[0] >= Decimal("0")
    channel_labels = {
        row["CHANNEL_LABEL"] for row in silver.select("CHANNEL_LABEL").distinct().collect()
    }
    assert channel_labels <= {
        "Broker",
        "Correspondent",
        "Retail",
    }

    servicer = spark_session.read.format("delta").load(str(servicer_path))
    assert servicer.count() == len(synthetic_panel.outcomes)
    assert servicer.where("IS_CURRENT = true").count() == len(synthetic_panel.outcomes)
    assert servicer.where("LOAN_SERVICER_KEY IS NULL").count() == 0
