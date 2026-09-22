"""Gold loan-month survival panel construction and Delta publication."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as spark_fn
from pyspark.sql import types as spark_types

from mortgage_risk.config.gold import (
    DEFAULT_DELINQUENCY_THRESHOLD,
    DEFAULT_HORIZON_MONTHS,
)
from mortgage_risk.features.macro import join_macro_point_in_time
from mortgage_risk.validation.splits import assign_model_splits

_SURVIVAL_COLUMNS: Final = frozenset({"LOAN_ID", "ACT_PERIOD", "DLQ_STATUS", "ZERO_BAL_CODE"})
_FEATURE_COLUMNS: Final = frozenset(
    {
        "ACT_PERIOD",
        "ORIG_DATE",
        "CURRENT_UPB",
        "ORIG_UPB",
        "OLTV",
        "CSCORE_B",
        "CSCORE_C",
    }
)
_PREPAYMENT_CODE: Final = "01"
_REPURCHASE_CODE: Final = "06"


class GoldReconciliationError(RuntimeError):
    """Raised when Gold row counts do not match at-risk Silver months."""


@dataclass(frozen=True, slots=True)
class GoldReconciliation:
    """Per-publication row-count evidence."""

    loan_count: int
    silver_rows: int
    gold_rows: int
    terminal_or_post_exit_rows: int


@dataclass(frozen=True, slots=True)
class GoldPublicationResult:
    """Published Gold counts, its Delta version, and the versions it was built from."""

    reconciliation: GoldReconciliation
    delta_version: int
    source_versions: Mapping[str, int]


_REQUIRED_SOURCE_VERSIONS: Final = frozenset({"silver", "macro"})


def require_source_versions(source_versions: Mapping[str, int]) -> Mapping[str, int]:
    """Validate the input Delta versions a Gold build is derived from.

    Section 8 makes Delta time travel the reproducibility mechanism. Recording
    only the version Gold was written at leaves the build irreproducible: it
    says what was produced, not what it was produced from.
    """
    missing = sorted(_REQUIRED_SOURCE_VERSIONS.difference(source_versions))
    if missing:
        raise ValueError(f"missing source Delta versions: {missing}")
    unexpected = sorted(set(source_versions).difference(_REQUIRED_SOURCE_VERSIONS))
    if unexpected:
        raise ValueError(f"unexpected source Delta versions: {unexpected}")
    negative = sorted(name for name, version in source_versions.items() if version < 0)
    if negative:
        raise ValueError(f"source Delta versions must be non-negative: {negative}")
    return dict(source_versions)


def build_survival_panel(
    silver: DataFrame,
    *,
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
    delinquency_threshold: int = DEFAULT_DELINQUENCY_THRESHOLD,
) -> DataFrame:
    """Create at-risk loan-month rows with hazard and 12-month labels."""
    if horizon_months <= 0:
        raise ValueError("horizon_months must be positive")
    if delinquency_threshold <= 0:
        raise ValueError("delinquency_threshold must be positive")
    _require_columns(silver, _SURVIVAL_COLUMNS, "survival")

    marked = _with_survival_markers(silver, delinquency_threshold)
    horizon_end = spark_fn.add_months(spark_fn.col("ACT_PERIOD"), horizon_months)
    default_within_horizon = (
        spark_fn.col("FIRST_D90_DATE").isNotNull()
        & (spark_fn.col("FIRST_D90_DATE") > spark_fn.col("ACT_PERIOD"))
        & (spark_fn.col("FIRST_D90_DATE") <= horizon_end)
    )
    known_through = spark_fn.when(
        spark_fn.col("FIRST_CENSOR_DATE").isNull(),
        spark_fn.col("LAST_OBSERVED_DATE"),
    ).otherwise(
        spark_fn.least(
            spark_fn.col("LAST_OBSERVED_DATE"),
            spark_fn.col("FIRST_CENSOR_DATE"),
        )
    )

    at_risk = (
        marked.where(spark_fn.col("_IS_AT_RISK"))
        .withColumn("HORIZON_END_DATE", horizon_end)
        .withColumn(
            "DEFAULT_NEXT_MONTH",
            (
                spark_fn.col("FIRST_D90_DATE") == spark_fn.add_months(spark_fn.col("ACT_PERIOD"), 1)
            ).cast(spark_types.IntegerType()),
        )
        .withColumn(
            "DEFAULT_IN_12M",
            spark_fn.when(default_within_horizon, spark_fn.lit(1))
            .when(known_through >= horizon_end, spark_fn.lit(0))
            .otherwise(spark_fn.lit(None).cast(spark_types.IntegerType())),
        )
        .withColumn(
            "LABEL_OBSERVED_12M",
            spark_fn.col("DEFAULT_IN_12M").isNotNull(),
        )
        .drop("_IS_AT_RISK")
    )
    at_risk_window = Window.partitionBy("LOAN_ID")
    order = Window.partitionBy("LOAN_ID").orderBy("ACT_PERIOD")
    return (
        at_risk.withColumn(
            "AT_RISK_OBSERVED_MONTHS",
            spark_fn.count(spark_fn.lit(1)).over(at_risk_window),
        )
        .withColumn("AT_RISK_MONTH_NUMBER", spark_fn.row_number().over(order))
        .orderBy("LOAN_ID", "ACT_PERIOD")
    )


def engineer_loan_features(panel: DataFrame) -> DataFrame:
    """Add row-local features that cannot depend on future loan observations."""
    _require_columns(panel, _FEATURE_COLUMNS, "feature")
    original_upb = spark_fn.col("ORIG_UPB").cast("double")
    current_upb = spark_fn.col("CURRENT_UPB").cast("double")
    oltv = spark_fn.col("OLTV").cast("double")
    original_property_value = spark_fn.when(
        oltv > 0,
        original_upb / (oltv / spark_fn.lit(100.0)),
    )
    classic_fico = (
        spark_fn.when(spark_fn.col("CSCORE_B").isNull(), spark_fn.col("CSCORE_C"))
        .when(spark_fn.col("CSCORE_C").isNull(), spark_fn.col("CSCORE_B"))
        .otherwise(spark_fn.least("CSCORE_B", "CSCORE_C"))
    )
    return (
        panel.withColumn(
            "SEASONING_MONTHS",
            spark_fn.floor(
                spark_fn.months_between(
                    spark_fn.col("ACT_PERIOD"),
                    spark_fn.col("ORIG_DATE"),
                )
            ).cast(spark_types.IntegerType()),
        )
        .withColumn("CLASSIC_FICO", classic_fico)
        .withColumn("ORIGINAL_PROPERTY_VALUE", original_property_value)
        .withColumn(
            "CURRENT_LTV_UNINDEXED",
            spark_fn.when(
                spark_fn.col("ORIGINAL_PROPERTY_VALUE") > 0,
                current_upb / spark_fn.col("ORIGINAL_PROPERTY_VALUE") * 100.0,
            ),
        )
    )


def add_hpi_adjusted_current_ltv(panel: DataFrame) -> DataFrame:
    """Estimate current LTV using only HPI values available at each as-of date."""
    required = {"CURRENT_UPB", "ORIGINAL_PROPERTY_VALUE", "CSUSHPINSA", "ORIG_CSUSHPINSA"}
    _require_columns(panel, required, "current-LTV")
    estimated_value = (
        spark_fn.col("ORIGINAL_PROPERTY_VALUE")
        * spark_fn.col("CSUSHPINSA").cast("double")
        / spark_fn.col("ORIG_CSUSHPINSA").cast("double")
    )
    return panel.withColumn("ESTIMATED_CURRENT_PROPERTY_VALUE", estimated_value).withColumn(
        "CURRENT_LTV",
        spark_fn.when(
            estimated_value > 0,
            spark_fn.col("CURRENT_UPB").cast("double") / estimated_value * 100.0,
        ),
    )


def build_gold_panel(silver: DataFrame, macro: DataFrame) -> DataFrame:
    """Build the labelled, point-in-time-correct Gold modelling panel."""
    survival = build_survival_panel(silver)
    featured = engineer_loan_features(survival)
    with_current_macro = join_macro_point_in_time(featured, macro, allow_pre_archive_missing=True)
    with_origination_hpi = join_macro_point_in_time(
        with_current_macro,
        macro,
        as_of_column="ORIG_DATE",
        series_ids=("CSUSHPINSA",),
        prefix="ORIG_",
        allow_pre_archive_missing=True,
    )
    with_current_ltv = add_hpi_adjusted_current_ltv(with_origination_hpi)
    return assign_model_splits(with_current_ltv)


def reconcile_gold_panel(silver: DataFrame, gold: DataFrame) -> GoldReconciliation:
    """Prove that Gold has exactly one row per at-risk Silver loan-month."""
    _require_columns(silver, _SURVIVAL_COLUMNS, "survival")
    _require_columns(gold, {"LOAN_ID", "ACT_PERIOD"}, "Gold reconciliation")

    expected = (
        _with_survival_markers(silver, DEFAULT_DELINQUENCY_THRESHOLD)
        .where(spark_fn.col("_IS_AT_RISK"))
        .groupBy("LOAN_ID")
        .agg(spark_fn.count(spark_fn.lit(1)).alias("EXPECTED_ROWS"))
    )
    actual = gold.groupBy("LOAN_ID").agg(spark_fn.count(spark_fn.lit(1)).alias("ACTUAL_ROWS"))
    mismatch = (
        expected.join(actual, "LOAN_ID", "full")
        .where(
            spark_fn.coalesce("EXPECTED_ROWS", spark_fn.lit(-1))
            != spark_fn.coalesce("ACTUAL_ROWS", spark_fn.lit(-1))
        )
        .limit(1)
        .count()
    )
    if mismatch:
        raise GoldReconciliationError(
            "Gold rows do not equal at-risk observed months for every loan"
        )

    silver_rows = silver.count()
    gold_rows = gold.count()
    return GoldReconciliation(
        loan_count=gold.select("LOAN_ID").distinct().count(),
        silver_rows=silver_rows,
        gold_rows=gold_rows,
        terminal_or_post_exit_rows=silver_rows - gold_rows,
    )


def publish_gold(
    spark: SparkSession,
    silver: DataFrame,
    macro: DataFrame,
    gold_path: Path,
    *,
    source_versions: Mapping[str, int],
) -> GoldPublicationResult:
    """Build, reconcile, and overwrite the derived Gold Delta table."""
    recorded_sources = require_source_versions(source_versions)
    candidate = build_gold_panel(silver, macro)
    reconciliation = reconcile_gold_panel(silver, candidate)
    target = str(gold_path.resolve())
    (
        candidate.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(target)
    )
    version_row = DeltaTable.forPath(spark, target).history(1).select("version").first()
    if version_row is None:
        raise GoldReconciliationError("Gold Delta table has no committed version")
    return GoldPublicationResult(
        reconciliation=reconciliation,
        delta_version=int(version_row["version"]),
        source_versions=recorded_sources,
    )


def _with_survival_markers(
    silver: DataFrame,
    delinquency_threshold: int,
) -> DataFrame:
    loan_window = Window.partitionBy("LOAN_ID").rowsBetween(
        Window.unboundedPreceding,
        Window.unboundedFollowing,
    )
    ordered_loan_window = (
        Window.partitionBy("LOAN_ID")
        .orderBy("ACT_PERIOD")
        .rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)
    )
    numeric_status = spark_fn.when(
        spark_fn.col("DLQ_STATUS").rlike(r"^\d+$"),
        spark_fn.col("DLQ_STATUS").cast(spark_types.IntegerType()),
    )
    is_default = numeric_status >= delinquency_threshold
    is_censor = spark_fn.col("ZERO_BAL_CODE").isNotNull() & (
        spark_fn.trim(spark_fn.col("ZERO_BAL_CODE")) != ""
    )
    marked = (
        silver.withColumn("_IS_DEFAULT_EVENT", is_default)
        .withColumn("_IS_CENSOR_EVENT", is_censor)
        .withColumn(
            "_RAW_FIRST_D90_DATE",
            spark_fn.min(
                spark_fn.when(spark_fn.col("_IS_DEFAULT_EVENT"), spark_fn.col("ACT_PERIOD"))
            ).over(loan_window),
        )
        .withColumn(
            "FIRST_CENSOR_DATE",
            spark_fn.min(
                spark_fn.when(spark_fn.col("_IS_CENSOR_EVENT"), spark_fn.col("ACT_PERIOD"))
            ).over(loan_window),
        )
        .withColumn(
            "FIRST_CENSOR_CODE",
            spark_fn.first(
                spark_fn.when(
                    spark_fn.col("_IS_CENSOR_EVENT"),
                    spark_fn.col("ZERO_BAL_CODE"),
                ),
                ignorenulls=True,
            ).over(ordered_loan_window),
        )
        .withColumn(
            "LAST_OBSERVED_DATE",
            spark_fn.max("ACT_PERIOD").over(loan_window),
        )
        .withColumn(
            "SOURCE_OBSERVED_MONTHS",
            spark_fn.count(spark_fn.lit(1)).over(loan_window),
        )
    )
    effective_default = spark_fn.when(
        spark_fn.col("_RAW_FIRST_D90_DATE").isNotNull()
        & (
            spark_fn.col("FIRST_CENSOR_DATE").isNull()
            | (spark_fn.col("_RAW_FIRST_D90_DATE") <= spark_fn.col("FIRST_CENSOR_DATE"))
        ),
        spark_fn.col("_RAW_FIRST_D90_DATE"),
    )
    with_exit = (
        marked.withColumn("FIRST_D90_DATE", effective_default)
        .withColumn(
            "EXIT_DATE",
            spark_fn.when(
                spark_fn.col("FIRST_D90_DATE").isNull(),
                spark_fn.col("FIRST_CENSOR_DATE"),
            )
            .when(
                spark_fn.col("FIRST_CENSOR_DATE").isNull(),
                spark_fn.col("FIRST_D90_DATE"),
            )
            .otherwise(spark_fn.least("FIRST_D90_DATE", "FIRST_CENSOR_DATE")),
        )
        .withColumn(
            "EXIT_TYPE",
            spark_fn.when(
                spark_fn.col("FIRST_D90_DATE").isNotNull(),
                spark_fn.lit("default"),
            )
            .when(
                spark_fn.col("FIRST_CENSOR_CODE") == _PREPAYMENT_CODE,
                spark_fn.lit("prepaid"),
            )
            .when(
                spark_fn.col("FIRST_CENSOR_CODE") == _REPURCHASE_CODE,
                spark_fn.lit("repurchased"),
            )
            .when(
                spark_fn.col("FIRST_CENSOR_DATE").isNotNull(),
                spark_fn.lit("other_exit"),
            )
            .otherwise(spark_fn.lit("right_censored")),
        )
    )
    return with_exit.withColumn(
        "_IS_AT_RISK",
        spark_fn.col("EXIT_DATE").isNull()
        | (spark_fn.col("ACT_PERIOD") < spark_fn.col("EXIT_DATE")),
    ).drop(
        "_IS_DEFAULT_EVENT",
        "_IS_CENSOR_EVENT",
        "_RAW_FIRST_D90_DATE",
    )


def _require_columns(frame: DataFrame, required: set[str] | frozenset[str], label: str) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"{label} data is missing columns: {missing}")
