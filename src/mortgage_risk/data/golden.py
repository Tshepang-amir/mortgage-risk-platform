"""Fannie Mae acquisition-summary reproduction and golden-record checks."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, cast

from pyspark.sql import Column, DataFrame, Row, Window
from pyspark.sql import functions as spark_fn

FANNIE_PRIMARY_SUMMARY_URL: Final = (
    "https://capitalmarkets.fanniemae.com/media/document/pdf/"
    "FNMA_SF_Loan_Performance_Stat_Summary_Primary.pdf"
)
FANNIE_PRIMARY_SUMMARY_SHA256: Final = (
    "0d4b36c43a0d49bd8e6b11fca0162e117220c447f57fa41da4b119e7e655fbfc"
)

_REQUIRED_COLUMNS: Final = frozenset(
    {
        "LOAN_ID",
        "ACT_PERIOD",
        "ORIG_DATE",
        "ORIG_UPB",
        "ORIG_RATE",
        "OLTV",
        "OCLTV",
        "DTI",
        "CSCORE_B",
        "CSCORE_C",
    }
)
_QUARTER_PATTERN: Final = re.compile(r"^(\d{4}Q[1-4])(?:\.csv)?$", re.IGNORECASE)
_FULL_PUBLICATION_QUARTERS: Final = tuple(
    f"{year}Q{quarter}"
    for year in range(2000, 2027)
    for quarter in range(1, 5)
    if (year, quarter) <= (2026, 1)
)


class GoldenRecordError(RuntimeError):
    """Base error for an invalid or mismatched golden-record comparison."""


class PopulationMismatchError(GoldenRecordError):
    """Raised before comparison when actual and published populations differ."""


class SummaryMismatchError(GoldenRecordError):
    """Raised when compatible populations produce different summary values."""


@dataclass(frozen=True, slots=True)
class AcquisitionSummaryRow:
    """One displayed row from Fannie Mae's acquisition summary."""

    origination_year: str
    loan_count: int
    total_original_upb_millions: Decimal
    average_original_upb: Decimal
    classic_fico: Decimal
    oltv: Decimal
    ocltv: Decimal
    dti: Decimal
    note_rate: Decimal


@dataclass(frozen=True, slots=True)
class SummaryTolerance:
    """Absolute tolerances implied by the published table's display precision."""

    total_original_upb_millions: Decimal = Decimal("0.5")
    average_original_upb: Decimal = Decimal("0.5")
    classic_fico: Decimal = Decimal("0.5")
    ratio: Decimal = Decimal("0.05")
    note_rate: Decimal = Decimal("0.05")


DEFAULT_SUMMARY_TOLERANCE: Final = SummaryTolerance()


@dataclass(frozen=True, slots=True)
class PublishedSummaryReference:
    """Versioned external reference and the population it describes."""

    title: str
    source_url: str
    source_sha256: str
    acquisition_quarters: tuple[str, ...]
    rows: tuple[AcquisitionSummaryRow, ...]


@dataclass(frozen=True, slots=True)
class GoldenRecordResult:
    """Evidence returned after a successful external comparison."""

    compared_rows: int
    observed_acquisition_quarters: tuple[str, ...]
    source_sha256: str


FANNIE_PRIMARY_JULY_2026: Final = PublishedSummaryReference(
    title="Fannie Mae Statistical Summary Tables: July 2026",
    source_url=FANNIE_PRIMARY_SUMMARY_URL,
    source_sha256=FANNIE_PRIMARY_SUMMARY_SHA256,
    acquisition_quarters=_FULL_PUBLICATION_QUARTERS,
    rows=(
        AcquisitionSummaryRow(
            "2005",
            1_446_003,
            Decimal("252235"),
            Decimal("174436"),
            Decimal("721"),
            Decimal("69.7"),
            Decimal("71.7"),
            Decimal("37.6"),
            Decimal("5.8"),
        ),
        AcquisitionSummaryRow(
            "2007",
            1_252_409,
            Decimal("245723"),
            Decimal("196200"),
            Decimal("719"),
            Decimal("72.2"),
            Decimal("74.3"),
            Decimal("38.9"),
            Decimal("6.3"),
        ),
        AcquisitionSummaryRow(
            "2012",
            2_680_144,
            Decimal("608112"),
            Decimal("226895"),
            Decimal("766"),
            Decimal("68.9"),
            Decimal("70.2"),
            Decimal("31.1"),
            Decimal("3.6"),
        ),
        AcquisitionSummaryRow(
            "2016",
            2_353_822,
            Decimal("555054"),
            Decimal("235810"),
            Decimal("752"),
            Decimal("73.6"),
            Decimal("74.3"),
            Decimal("33.5"),
            Decimal("3.7"),
        ),
        AcquisitionSummaryRow(
            "2018",
            1_787_453,
            Decimal("419624"),
            Decimal("234761"),
            Decimal("743"),
            Decimal("77.8"),
            Decimal("78.3"),
            Decimal("37.6"),
            Decimal("4.8"),
        ),
        AcquisitionSummaryRow(
            "Total",
            57_864_281,
            Decimal("12724660"),
            Decimal("219905"),
            Decimal("747"),
            Decimal("71.9"),
            Decimal("72.7"),
            Decimal("34.6"),
            Decimal("4.7"),
        ),
    ),
)


def summarize_acquisition(silver: DataFrame) -> DataFrame:
    """Reproduce the published acquisition summary from typed Silver rows."""
    missing = sorted(_REQUIRED_COLUMNS.difference(silver.columns))
    if missing:
        raise ValueError(f"Silver data is missing acquisition-summary columns: {missing}")

    latest = Window.partitionBy("LOAN_ID").orderBy(spark_fn.col("ACT_PERIOD").desc())
    loan_level = (
        silver.withColumn("_golden_rank", spark_fn.row_number().over(latest))
        .where(spark_fn.col("_golden_rank") == 1)
        .drop("_golden_rank")
        .withColumn("ORIGINATION_YEAR", spark_fn.date_format("ORIG_DATE", "yyyy"))
        .withColumn("_GOLDEN_OCLTV", spark_fn.coalesce("OCLTV", "OLTV"))
        .withColumn(
            "_GOLDEN_CLASSIC_FICO",
            spark_fn.when(spark_fn.col("CSCORE_B").isNull(), spark_fn.col("CSCORE_C"))
            .when(spark_fn.col("CSCORE_C").isNull(), spark_fn.col("CSCORE_B"))
            .otherwise(spark_fn.least("CSCORE_B", "CSCORE_C")),
        )
        .where(spark_fn.col("ORIGINATION_YEAR").isNotNull())
    )

    grouped = loan_level.groupBy("ORIGINATION_YEAR").agg(*_summary_expressions())
    total = loan_level.agg(*_summary_expressions()).withColumn(
        "ORIGINATION_YEAR", spark_fn.lit("Total")
    )
    return grouped.unionByName(total).orderBy(
        spark_fn.when(spark_fn.col("ORIGINATION_YEAR") == "Total", 1).otherwise(0),
        "ORIGINATION_YEAR",
    )


def observed_acquisition_quarters(silver: DataFrame) -> tuple[str, ...]:
    """Read acquisition-quarter scope from immutable Silver provenance."""
    if "_source_filename" not in silver.columns:
        raise ValueError("Silver data has no _source_filename provenance column")

    quarters: set[str] = set()
    for row in silver.select("_source_filename").distinct().collect():
        source_filename = cast(str | None, row["_source_filename"])
        match = _QUARTER_PATTERN.fullmatch(source_filename or "")
        if match is None:
            raise ValueError(f"cannot derive acquisition quarter from {source_filename!r}")
        quarters.add(match.group(1).upper())
    return tuple(sorted(quarters))


def require_population_match(
    observed_quarters: Iterable[str], expected_quarters: Iterable[str]
) -> tuple[str, ...]:
    """Fail closed unless the actual and published acquisition scopes are equal."""
    observed = frozenset(observed_quarters)
    expected = frozenset(expected_quarters)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise PopulationMismatchError(
            "golden-record populations differ: "
            f"observed={len(observed)} quarters, expected={len(expected)} quarters, "
            f"missing={missing}, extra={extra}"
        )
    return tuple(sorted(observed))


def collect_summary_rows(summary: DataFrame) -> dict[str, AcquisitionSummaryRow]:
    """Collect the small aggregate table into typed rows for comparison."""
    result: dict[str, AcquisitionSummaryRow] = {}
    for row in summary.collect():
        converted = _from_spark_row(row)
        result[converted.origination_year] = converted
    return result


def compare_summary_rows(
    actual: Mapping[str, AcquisitionSummaryRow],
    expected: Iterable[AcquisitionSummaryRow],
    tolerance: SummaryTolerance = DEFAULT_SUMMARY_TOLERANCE,
) -> int:
    """Compare aggregate rows at the precision displayed by Fannie Mae."""
    mismatches: list[str] = []
    compared = 0
    for expected_row in expected:
        actual_row = actual.get(expected_row.origination_year)
        if actual_row is None:
            mismatches.append(f"{expected_row.origination_year}: row missing")
            continue
        compared += 1
        if actual_row.loan_count != expected_row.loan_count:
            mismatches.append(
                f"{expected_row.origination_year}.loan_count: "
                f"actual={actual_row.loan_count}, expected={expected_row.loan_count}"
            )
        checks = (
            ("total_original_upb_millions", tolerance.total_original_upb_millions),
            ("average_original_upb", tolerance.average_original_upb),
            ("classic_fico", tolerance.classic_fico),
            ("oltv", tolerance.ratio),
            ("ocltv", tolerance.ratio),
            ("dti", tolerance.ratio),
            ("note_rate", tolerance.note_rate),
        )
        for metric, allowed_difference in checks:
            actual_value = cast(Decimal, getattr(actual_row, metric))
            expected_value = cast(Decimal, getattr(expected_row, metric))
            if abs(actual_value - expected_value) > allowed_difference:
                mismatches.append(
                    f"{expected_row.origination_year}.{metric}: "
                    f"actual={actual_value}, expected={expected_value}, "
                    f"tolerance={allowed_difference}"
                )

    if mismatches:
        raise SummaryMismatchError("; ".join(mismatches))
    return compared


def validate_published_summary(
    silver: DataFrame,
    reference: PublishedSummaryReference = FANNIE_PRIMARY_JULY_2026,
    tolerance: SummaryTolerance = DEFAULT_SUMMARY_TOLERANCE,
) -> GoldenRecordResult:
    """Validate Silver against a publication only when populations are identical."""
    quarters = require_population_match(
        observed_acquisition_quarters(silver), reference.acquisition_quarters
    )
    actual = collect_summary_rows(summarize_acquisition(silver))
    compared = compare_summary_rows(actual, reference.rows, tolerance)
    return GoldenRecordResult(compared, quarters, reference.source_sha256)


def _summary_expressions() -> tuple[Column, ...]:
    return (
        spark_fn.count(spark_fn.lit(1)).alias("LOAN_COUNT"),
        (spark_fn.sum("ORIG_UPB") / spark_fn.lit(1_000_000)).alias("TOTAL_ORIGINAL_UPB_MILLIONS"),
        spark_fn.avg("ORIG_UPB").alias("AVERAGE_ORIGINAL_UPB"),
        _weighted_average("_GOLDEN_CLASSIC_FICO").alias("CLASSIC_FICO"),
        _weighted_average("OLTV").alias("OLTV"),
        _weighted_average("_GOLDEN_OCLTV").alias("OCLTV"),
        _weighted_average("DTI").alias("DTI"),
        _weighted_average("ORIG_RATE").alias("NOTE_RATE"),
    )


def _weighted_average(column_name: str) -> Column:
    value = spark_fn.col(column_name).cast("double")
    weight = spark_fn.col("ORIG_UPB").cast("double")
    usable = value.isNotNull() & weight.isNotNull()
    return spark_fn.sum(spark_fn.when(usable, value * weight)) / spark_fn.sum(
        spark_fn.when(usable, weight)
    )


def _from_spark_row(row: Row) -> AcquisitionSummaryRow:
    return AcquisitionSummaryRow(
        origination_year=cast(str, row["ORIGINATION_YEAR"]),
        loan_count=cast(int, row["LOAN_COUNT"]),
        total_original_upb_millions=_as_decimal(row["TOTAL_ORIGINAL_UPB_MILLIONS"]),
        average_original_upb=_as_decimal(row["AVERAGE_ORIGINAL_UPB"]),
        classic_fico=_as_decimal(row["CLASSIC_FICO"]),
        oltv=_as_decimal(row["OLTV"]),
        ocltv=_as_decimal(row["OCLTV"]),
        dti=_as_decimal(row["DTI"]),
        note_rate=_as_decimal(row["NOTE_RATE"]),
    )


def _as_decimal(value: object) -> Decimal:
    if value is None:
        raise GoldenRecordError("published acquisition metric unexpectedly evaluated to null")
    return Decimal(str(value))
