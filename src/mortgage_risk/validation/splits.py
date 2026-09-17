"""Deterministic temporal and origination-vintage modelling splits."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as spark_fn

from mortgage_risk.config.gold import (
    OUT_OF_VINTAGE_QUARTERS,
    TRAIN_END,
    VALIDATION_END,
)


class SplitIntegrityError(ValueError):
    """Raised when one loan crosses incompatible modelling partitions."""


def assign_model_splits(panel: DataFrame) -> DataFrame:
    """Assign temporal splits with out-of-vintage holdouts taking precedence."""
    required = {"LOAN_ID", "ACT_PERIOD", "_source_file"}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"panel is missing split columns: {missing}")

    quarter = spark_fn.upper(
        spark_fn.regexp_extract(spark_fn.col("_source_file"), r"^(\d{4}Q[1-4])\.csv$", 1)
    )
    with_quarter = panel.withColumn("ACQUISITION_QUARTER", quarter)
    if with_quarter.where(spark_fn.col("ACQUISITION_QUARTER") == "").limit(1).count() > 0:
        raise SplitIntegrityError("cannot derive acquisition quarter from _source_file")

    temporal_split = (
        spark_fn.when(
            spark_fn.col("ACT_PERIOD") <= spark_fn.lit(TRAIN_END),
            spark_fn.lit("train"),
        )
        .when(
            spark_fn.col("ACT_PERIOD") <= spark_fn.lit(VALIDATION_END),
            spark_fn.lit("validation"),
        )
        .otherwise(spark_fn.lit("out_of_time"))
    )
    with_splits = (
        with_quarter.withColumn("TEMPORAL_SPLIT", temporal_split)
        .withColumn(
            "IS_OUT_OF_VINTAGE",
            spark_fn.col("ACQUISITION_QUARTER").isin(*OUT_OF_VINTAGE_QUARTERS),
        )
        .withColumn(
            "MODELLING_SPLIT",
            spark_fn.when(
                spark_fn.col("IS_OUT_OF_VINTAGE"),
                spark_fn.lit("out_of_vintage"),
            ).otherwise(spark_fn.col("TEMPORAL_SPLIT")),
        )
    )
    assert_split_integrity(with_splits)
    return with_splits


def assert_split_integrity(panel: DataFrame) -> None:
    """Assert that no loan is both training and out-of-vintage."""
    required = {"LOAN_ID", "MODELLING_SPLIT"}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise ValueError(f"panel is missing assigned split columns: {missing}")

    training = panel.where(spark_fn.col("MODELLING_SPLIT") == "train").select("LOAN_ID").distinct()
    out_of_vintage = (
        panel.where(spark_fn.col("MODELLING_SPLIT") == "out_of_vintage")
        .select("LOAN_ID")
        .distinct()
    )
    if training.join(out_of_vintage, "LOAN_ID", "inner").limit(1).count() > 0:
        raise SplitIntegrityError(
            "at least one loan appears in both training and out-of-vintage partitions"
        )
