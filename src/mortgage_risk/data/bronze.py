"""Append-only Bronze ingestion for Fannie Mae raw performance files."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as spark_fn
from pyspark.sql import types as spark_types

from mortgage_risk.data.schema import (
    PIPE_DELIMITER,
    SAMPLE_FILE_FIELD_COUNT,
    field_names,
    fields_for_count,
)


class RawFileContractError(ValueError):
    """Raised when a source file does not match the positional raw contract."""


@dataclass(frozen=True, slots=True)
class BronzeIngestionResult:
    """Counts from one idempotent Bronze ingestion run."""

    ingested_files: tuple[str, ...]
    skipped_files: tuple[str, ...]
    rows_written: int
    final_rows: int


def raw_spark_schema(field_count: int = SAMPLE_FILE_FIELD_COUNT) -> spark_types.StructType:
    """Return an all-string Spark schema for the immutable Bronze layer."""
    fields_for_count(field_count)
    return spark_types.StructType(
        [
            spark_types.StructField(name, spark_types.StringType(), nullable=True)
            for name in field_names(field_count)
        ]
    )


def ingest_bronze(
    spark: SparkSession,
    source_paths: Sequence[Path],
    bronze_path: Path,
    *,
    field_count: int = SAMPLE_FILE_FIELD_COUNT,
    ingested_at: datetime | None = None,
) -> BronzeIngestionResult:
    """Append unseen source files to Bronze and skip exact replays."""
    if not source_paths:
        raise ValueError("source_paths must contain at least one file")

    fields_for_count(field_count)
    timestamp = ingested_at or datetime.now(UTC)
    target = str(bronze_path.resolve())
    ingested: list[str] = []
    skipped: list[str] = []
    rows_written = 0

    for source_path in source_paths:
        source = source_path.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)

        source_hash = _sha256(source)
        if _source_already_ingested(spark, target, source.name, source_hash):
            skipped.append(source.name)
            continue

        row_count = _validate_width(spark, source, field_count)
        frame = (
            spark.read.schema(raw_spark_schema(field_count))
            .option("header", "false")
            .option("sep", PIPE_DELIMITER)
            .option("mode", "FAILFAST")
            .csv(str(source))
            .withColumn("_source_file", spark_fn.lit(source.name))
            .withColumn("_source_path", spark_fn.lit(str(source)))
            .withColumn("_source_sha256", spark_fn.lit(source_hash))
            .withColumn("_source_field_count", spark_fn.lit(field_count))
            .withColumn("_ingested_at", spark_fn.lit(timestamp).cast(spark_types.TimestampType()))
        )
        (frame.write.format("delta").mode("append").option("mergeSchema", "true").save(target))
        ingested.append(source.name)
        rows_written += row_count

    final_rows = _table_row_count(spark, target)
    return BronzeIngestionResult(
        ingested_files=tuple(ingested),
        skipped_files=tuple(skipped),
        rows_written=rows_written,
        final_rows=final_rows,
    )


def read_bronze(spark: SparkSession, bronze_path: Path) -> DataFrame:
    """Read an existing Bronze Delta table."""
    target = str(bronze_path.resolve())
    if not DeltaTable.isDeltaTable(spark, target):
        raise FileNotFoundError(f"Bronze Delta table does not exist: {target}")
    return spark.read.format("delta").load(target)


def _validate_width(spark: SparkSession, source: Path, field_count: int) -> int:
    widths = (
        spark.read.text(str(source))
        .select(
            spark_fn.size(spark_fn.split(spark_fn.col("value"), r"\|", -1)).alias("field_count")
        )
        .groupBy("field_count")
        .count()
        .collect()
    )
    if not widths:
        raise RawFileContractError(f"{source.name} is empty")

    invalid = sorted(
        (int(row["field_count"]), int(row["count"]))
        for row in widths
        if int(row["field_count"]) != field_count
    )
    if invalid:
        raise RawFileContractError(
            f"{source.name} has invalid row widths {invalid}; expected {field_count} fields"
        )
    return sum(int(row["count"]) for row in widths)


def _source_already_ingested(
    spark: SparkSession,
    target: str,
    source_file: str,
    source_hash: str,
) -> bool:
    if not DeltaTable.isDeltaTable(spark, target):
        return False
    return (
        spark.read.format("delta")
        .load(target)
        .where(
            (spark_fn.col("_source_file") == source_file)
            & (spark_fn.col("_source_sha256") == source_hash)
        )
        .limit(1)
        .count()
        > 0
    )


def _table_row_count(spark: SparkSession, target: str) -> int:
    if not DeltaTable.isDeltaTable(spark, target):
        return 0
    return spark.read.format("delta").load(target).count()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
