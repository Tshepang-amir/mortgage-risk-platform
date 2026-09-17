"""Golden-record acquisition summary behavior."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import types as spark_types

from mortgage_risk.data.golden import (
    FANNIE_PRIMARY_JULY_2026,
    AcquisitionSummaryRow,
    PopulationMismatchError,
    PublishedSummaryReference,
    SummaryMismatchError,
    collect_summary_rows,
    compare_summary_rows,
    observed_acquisition_quarters,
    require_population_match,
    summarize_acquisition,
    validate_published_summary,
)
from mortgage_risk.data.synthetic import SELECTED_ACQUISITION_QUARTERS


def test_acquisition_summary_uses_one_row_per_loan_and_upb_weights(
    spark_session: SparkSession,
) -> None:
    silver = _silver_fixture(spark_session)

    rows = collect_summary_rows(summarize_acquisition(silver))

    expected = AcquisitionSummaryRow(
        origination_year="2005",
        loan_count=2,
        total_original_upb_millions=Decimal("0.0004"),
        average_original_upb=Decimal("200"),
        classic_fico=Decimal("732.5"),
        oltv=Decimal("65"),
        ocltv=Decimal("68.75"),
        dti=Decimal("37.5"),
        note_rate=Decimal("4.25"),
    )
    expected_total = AcquisitionSummaryRow(
        origination_year="Total",
        loan_count=expected.loan_count,
        total_original_upb_millions=expected.total_original_upb_millions,
        average_original_upb=expected.average_original_upb,
        classic_fico=expected.classic_fico,
        oltv=expected.oltv,
        ocltv=expected.ocltv,
        dti=expected.dti,
        note_rate=expected.note_rate,
    )

    assert compare_summary_rows(rows, (expected, expected_total)) == 2
    assert observed_acquisition_quarters(silver) == ("2005Q1",)
    reference = PublishedSummaryReference(
        title="Synthetic acquisition control",
        source_url="test fixture",
        source_sha256="synthetic-sha256",
        acquisition_quarters=("2005Q1",),
        rows=(expected, expected_total),
    )
    result = validate_published_summary(silver, reference)
    assert result.compared_rows == 2
    assert result.observed_acquisition_quarters == ("2005Q1",)
    assert result.source_sha256 == "synthetic-sha256"


def test_comparison_rejects_values_outside_display_tolerance(
    spark_session: SparkSession,
) -> None:
    rows = collect_summary_rows(summarize_acquisition(_silver_fixture(spark_session)))
    expected = rows["2005"]
    outside_tolerance = AcquisitionSummaryRow(
        expected.origination_year,
        expected.loan_count,
        expected.total_original_upb_millions,
        expected.average_original_upb,
        expected.classic_fico,
        expected.oltv,
        expected.ocltv,
        expected.dti,
        expected.note_rate + Decimal("0.051"),
    )

    with pytest.raises(SummaryMismatchError, match="note_rate"):
        compare_summary_rows(rows, (outside_tolerance,))


def test_scoped_manifest_is_not_the_published_full_book_population() -> None:
    assert len(FANNIE_PRIMARY_JULY_2026.acquisition_quarters) == 105
    with pytest.raises(PopulationMismatchError, match="observed=6 quarters, expected=105"):
        require_population_match(
            SELECTED_ACQUISITION_QUARTERS,
            FANNIE_PRIMARY_JULY_2026.acquisition_quarters,
        )


def _silver_fixture(spark: SparkSession) -> DataFrame:
    schema = spark_types.StructType(
        [
            spark_types.StructField("LOAN_ID", spark_types.StringType(), False),
            spark_types.StructField("ACT_PERIOD", spark_types.DateType(), False),
            spark_types.StructField("ORIG_DATE", spark_types.DateType(), False),
            spark_types.StructField("ORIG_UPB", spark_types.DecimalType(20, 2), False),
            spark_types.StructField("ORIG_RATE", spark_types.DecimalType(20, 3), False),
            spark_types.StructField("OLTV", spark_types.IntegerType(), False),
            spark_types.StructField("OCLTV", spark_types.IntegerType(), True),
            spark_types.StructField("DTI", spark_types.IntegerType(), False),
            spark_types.StructField("CSCORE_B", spark_types.IntegerType(), False),
            spark_types.StructField("CSCORE_C", spark_types.IntegerType(), True),
            spark_types.StructField("_source_file", spark_types.StringType(), False),
        ]
    )
    return spark.createDataFrame(
        [
            (
                "L1",
                date(2005, 3, 1),
                date(2005, 1, 1),
                Decimal("100.00"),
                Decimal("5.000"),
                80,
                None,
                30,
                700,
                None,
                "2005Q1.csv",
            ),
            (
                "L1",
                date(2005, 4, 1),
                date(2005, 1, 1),
                Decimal("100.00"),
                Decimal("5.000"),
                80,
                None,
                30,
                710,
                None,
                "2005Q1.csv",
            ),
            (
                "L2",
                date(2005, 3, 1),
                date(2005, 2, 1),
                Decimal("300.00"),
                Decimal("4.000"),
                60,
                65,
                40,
                760,
                740,
                "2005Q1.csv",
            ),
        ],
        schema,
    )
