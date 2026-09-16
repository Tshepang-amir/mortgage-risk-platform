"""Contract tests for the Silver loan-servicer SCD Type 2 dimension."""

from __future__ import annotations

from datetime import date

from pyspark.sql import SparkSession

from mortgage_risk.data.silver import build_servicer_dimension


def test_servicer_change_creates_closed_and_current_assignments(
    spark_session: SparkSession,
) -> None:
    silver = spark_session.createDataFrame(
        [
            ("L1", date(2020, 1, 1), "Servicer A"),
            ("L1", date(2020, 2, 1), "Servicer A"),
            ("L1", date(2020, 3, 1), "Servicer B"),
            ("L1", date(2020, 4, 1), "Servicer B"),
        ],
        ["LOAN_ID", "ACT_PERIOD", "SERVICER"],
    )

    rows = (
        build_servicer_dimension(silver)
        .orderBy("EFFECTIVE_FROM")
        .select("SERVICER", "EFFECTIVE_FROM", "EFFECTIVE_TO", "IS_CURRENT")
        .collect()
    )

    assert len(rows) == 2
    assert tuple(rows[0]) == (
        "Servicer A",
        date(2020, 1, 1),
        date(2020, 2, 1),
        False,
    )
    assert tuple(rows[1]) == (
        "Servicer B",
        date(2020, 3, 1),
        None,
        True,
    )
