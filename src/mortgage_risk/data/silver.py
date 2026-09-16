"""Typed, deduplicated Silver tables derived from immutable Bronze data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as spark_fn
from pyspark.sql import types as spark_types

from mortgage_risk.data.bronze import read_bronze
from mortgage_risk.data.quality import DataQualityError, DataQualityReport, validate_silver
from mortgage_risk.data.schema import FANNIE_MAE_FIELDS, FieldType

_CODE_LABELS: Final[dict[str, dict[str, str]]] = {
    "CHANNEL": {
        "B": "Broker",
        "C": "Correspondent",
        "R": "Retail",
    },
    "PURPOSE": {
        "C": "Cash-out refinance",
        "P": "Purchase",
        "R": "Rate-term refinance",
        "U": "Unknown",
    },
    "PROP": {
        "CO": "Condominium",
        "CP": "Cooperative",
        "MH": "Manufactured housing",
        "PU": "Planned unit development",
        "SF": "Single-family",
    },
    "OCC_STAT": {
        "I": "Investment",
        "P": "Primary residence",
        "S": "Second home",
        "U": "Unknown",
    },
    "ZERO_BAL_CODE": {
        "01": "Prepaid or matured",
        "02": "Third-party sale",
        "03": "Short sale",
        "06": "Repurchased",
        "09": "Deed-in-lieu",
        "15": "Note sale",
        "16": "Reperforming loan sale",
    },
}

_DELINQUENCY_LABELS: Final[dict[str, str]] = {
    "0": "Current",
    "1": "30 days delinquent",
    "2": "60 days delinquent",
    "3": "90 days delinquent",
    "4": "120 days delinquent",
    "5": "150 days delinquent",
    "6": "180+ days delinquent",
    "7": "180+ days delinquent",
    "8": "180+ days delinquent",
    "9": "180+ days delinquent",
    "RA": "REO acquisition",
    "XX": "Unknown",
}


@dataclass(frozen=True, slots=True)
class SilverPublicationResult:
    """Counts and quality evidence for one Silver publication."""

    silver_rows: int
    servicer_rows: int
    quality: DataQualityReport


def transform_to_silver(bronze: DataFrame) -> DataFrame:
    """Type raw columns, retain provenance, decode codes and deduplicate keys."""
    typed = bronze
    for field in FANNIE_MAE_FIELDS:
        name = field.column_name
        if name not in typed.columns:
            continue
        if field.field_type is FieldType.INTEGER:
            typed = typed.withColumn(name, spark_fn.col(name).cast(spark_types.IntegerType()))
        elif field.field_type is FieldType.DECIMAL:
            typed = typed.withColumn(
                name, spark_fn.col(name).cast(spark_types.DecimalType(20, field.scale))
            )
        elif field.field_type is FieldType.MONTH:
            typed = typed.withColumn(name, spark_fn.to_date(spark_fn.col(name), "MMyyyy"))

    for column_name, labels in _CODE_LABELS.items():
        typed = typed.withColumn(f"{column_name}_LABEL", _decode(column_name, labels))
    typed = typed.withColumn(
        "DLQ_STATUS_LABEL",
        _decode("DLQ_STATUS", _DELINQUENCY_LABELS),
    )

    latest = Window.partitionBy("LOAN_ID", "ACT_PERIOD").orderBy(
        spark_fn.col("_ingested_at").desc(),
        spark_fn.col("_source_sha256").desc(),
    )
    return (
        typed.withColumn("_dedupe_rank", spark_fn.row_number().over(latest))
        .where(spark_fn.col("_dedupe_rank") == 1)
        .drop("_dedupe_rank")
    )


def build_servicer_dimension(silver: DataFrame) -> DataFrame:
    """Build SCD Type 2 loan-servicer assignments from monthly observations."""
    order = Window.partitionBy("LOAN_ID").orderBy("ACT_PERIOD")
    cumulative = order.rowsBetween(Window.unboundedPreceding, Window.currentRow)

    assignments = (
        silver.select("LOAN_ID", "ACT_PERIOD", "SERVICER")
        .where(
            spark_fn.col("LOAN_ID").isNotNull()
            & spark_fn.col("ACT_PERIOD").isNotNull()
            & spark_fn.col("SERVICER").isNotNull()
        )
        .withColumn("_previous_servicer", spark_fn.lag("SERVICER").over(order))
        .withColumn(
            "_new_assignment",
            spark_fn.when(
                spark_fn.col("_previous_servicer").isNull()
                | (spark_fn.col("_previous_servicer") != spark_fn.col("SERVICER")),
                spark_fn.lit(1),
            ).otherwise(spark_fn.lit(0)),
        )
        .withColumn("_assignment_number", spark_fn.sum("_new_assignment").over(cumulative))
    )

    spells = assignments.groupBy("LOAN_ID", "_assignment_number").agg(
        spark_fn.first("SERVICER").alias("SERVICER"),
        spark_fn.min("ACT_PERIOD").alias("EFFECTIVE_FROM"),
    )
    spell_order = Window.partitionBy("LOAN_ID").orderBy("EFFECTIVE_FROM")
    with_end = spells.withColumn(
        "_next_effective_from",
        spark_fn.lead("EFFECTIVE_FROM").over(spell_order),
    )
    return (
        with_end.withColumn(
            "EFFECTIVE_TO",
            spark_fn.add_months(spark_fn.col("_next_effective_from"), -1),
        )
        .withColumn("IS_CURRENT", spark_fn.col("_next_effective_from").isNull())
        .withColumn(
            "LOAN_SERVICER_KEY",
            spark_fn.sha2(
                spark_fn.concat_ws(
                    "|",
                    spark_fn.col("LOAN_ID"),
                    spark_fn.col("SERVICER"),
                    spark_fn.date_format(spark_fn.col("EFFECTIVE_FROM"), "yyyy-MM-dd"),
                ),
                256,
            ),
        )
        .select(
            "LOAN_SERVICER_KEY",
            "LOAN_ID",
            "SERVICER",
            "EFFECTIVE_FROM",
            "EFFECTIVE_TO",
            "IS_CURRENT",
        )
    )


def publish_silver(
    spark: SparkSession,
    bronze_path: Path,
    silver_path: Path,
    servicer_path: Path,
    *,
    quarantine_path: Path | None = None,
) -> SilverPublicationResult:
    """Validate first, then replace the derived Silver Delta tables."""
    candidate = transform_to_silver(read_bronze(spark, bronze_path))
    try:
        quality = validate_silver(candidate)
    except DataQualityError:
        if quarantine_path is not None:
            (
                candidate.write.format("delta")
                .mode("overwrite")
                .option("overwriteSchema", "true")
                .save(str(quarantine_path.resolve()))
            )
        raise

    dimension = build_servicer_dimension(candidate)
    silver_rows = candidate.count()
    servicer_rows = dimension.count()

    (
        candidate.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(str(silver_path.resolve()))
    )
    (
        dimension.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(str(servicer_path.resolve()))
    )
    return SilverPublicationResult(
        silver_rows=silver_rows,
        servicer_rows=servicer_rows,
        quality=quality,
    )


def _decode(column_name: str, labels: dict[str, str]) -> Column:
    entries: list[Column] = []
    for code, label in labels.items():
        entries.extend((spark_fn.lit(code), spark_fn.lit(label)))
    lookup = spark_fn.create_map(*entries)
    value = spark_fn.col(column_name)
    return spark_fn.when(
        value.isNull(), spark_fn.lit(None).cast(spark_types.StringType())
    ).otherwise(
        spark_fn.coalesce(
            spark_fn.element_at(lookup, value),
            spark_fn.concat(spark_fn.lit("Unmapped ("), value, spark_fn.lit(")")),
        )
    )
