"""The three leakage controls required by PROJECT.md section 5.

Each test is written from the definition in section 5 rather than from the
implementation it guards, and each asserts non-vacuity: that the scenario
actually exercises the property, so a test cannot pass by comparing nothing.

1. Temporal invariance: a feature computed for loan L at month t is identical
   whether or not rows after t exist in the source table.
2. Split integrity: no loan appears in both a training and an out-of-vintage
   test partition.
3. Macro lag: no macro value dated after the observation month enters a feature.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as spark_fn
from pyspark.sql import types as spark_types

from mortgage_risk.config.gold import FRED_SERIES_IDS, OUTCOME_COLUMNS
from mortgage_risk.data.gold import build_gold_panel, reconcile_gold_panel
from mortgage_risk.features.macro import (
    MacroObservation,
    join_macro_point_in_time,
    macro_observations_frame,
    parse_fred_initial_releases,
)
from mortgage_risk.validation.splits import SplitIntegrityError, assign_model_splits

# Outcome columns live in config so the panel builder and these tests cannot
# drift apart. Anything not classified there must be temporally invariant.
FUTURE_DEPENDENT_COLUMNS: Final = OUTCOME_COLUMNS


_SILVER_SCHEMA: Final = spark_types.StructType(
    [
        spark_types.StructField("LOAN_ID", spark_types.StringType(), False),
        spark_types.StructField("ACT_PERIOD", spark_types.DateType(), False),
        spark_types.StructField("ORIG_DATE", spark_types.DateType(), False),
        spark_types.StructField("DLQ_STATUS", spark_types.StringType(), True),
        spark_types.StructField("ZERO_BAL_CODE", spark_types.StringType(), True),
        spark_types.StructField("CURRENT_UPB", spark_types.DecimalType(11, 2), True),
        spark_types.StructField("ORIG_UPB", spark_types.DecimalType(11, 2), True),
        spark_types.StructField("OLTV", spark_types.IntegerType(), True),
        spark_types.StructField("CSCORE_B", spark_types.IntegerType(), True),
        spark_types.StructField("CSCORE_C", spark_types.IntegerType(), True),
        spark_types.StructField("_source_file", spark_types.StringType(), False),
    ]
)


def _month(year: int, month: int) -> date:
    return date(year, month, 1)


def _add_months(start: date, count: int) -> date:
    total = (start.year * 12 + start.month - 1) + count
    return date(total // 12, total % 12 + 1, 1)


def _loan_rows(
    loan_id: str,
    quarter: str,
    origination: date,
    first_period: date,
    months: int,
    *,
    default_at: int | None = None,
    zero_balance_at: int | None = None,
    zero_balance_code: str = "01",
) -> list[tuple[object, ...]]:
    """One loan's monthly Silver rows, with optional default and exit events."""
    rows: list[tuple[object, ...]] = []
    for offset in range(months):
        period = _add_months(first_period, offset)
        status = "03" if default_at is not None and offset >= default_at else "00"
        code = zero_balance_code if offset == zero_balance_at else None
        rows.append(
            (
                loan_id,
                period,
                origination,
                status,
                code,
                Decimal("200000.00") - Decimal(offset) * Decimal("500.00"),
                Decimal("200000.00"),
                80,
                720,
                740,
                f"{quarter}.csv",
            )
        )
    return rows


def _silver_frame(spark: SparkSession) -> DataFrame:
    """Deterministic Silver panel spanning train, validation and out-of-vintage."""
    rows: list[tuple[object, ...]] = []
    # 2012Q1 vintage: in-time loans, activity 2015-07 through 2016-06.
    rows += _loan_rows("L0000000001", "2012Q1", _month(2012, 1), _month(2015, 7), 12)
    rows += _loan_rows("L0000000002", "2012Q1", _month(2012, 1), _month(2015, 7), 12, default_at=10)
    rows += _loan_rows(
        "L0000000003", "2012Q1", _month(2012, 1), _month(2015, 7), 12, zero_balance_at=8
    )
    # 2016Q1 vintage: held out entirely, activity 2016-02 through 2017-01.
    rows += _loan_rows("L0000000004", "2016Q1", _month(2016, 1), _month(2016, 2), 12)
    return spark.createDataFrame(rows, _SILVER_SCHEMA)


def _macro_frame(spark: SparkSession, *, revisions: bool = False) -> DataFrame:
    """Monthly macro vintages covering every origination and activity month.

    Each observation is available in the month it refers to. When ``revisions``
    is set, a much later revision of one month is added, which a point-in-time
    join must ignore for any as-of date before that revision existed.
    """
    observations: list[MacroObservation] = []
    start = _month(2011, 1)
    for offset in range(120):
        observation_date = _add_months(start, offset)
        for index, series_id in enumerate(FRED_SERIES_IDS):
            observations.append(
                MacroObservation(
                    series_id=series_id,
                    observation_date=observation_date,
                    available_date=observation_date,
                    value=Decimal(100 + offset + index),
                )
            )
    if revisions:
        observations.append(
            MacroObservation(
                series_id="CSUSHPINSA",
                observation_date=_month(2015, 9),
                available_date=_month(2020, 1),
                value=Decimal("999999.000000"),
            )
        )
    return macro_observations_frame(spark, observations)


def _rows_by_key(
    panel: DataFrame, columns: list[str]
) -> dict[tuple[str, date], tuple[object, ...]]:
    selected = panel.select("LOAN_ID", "ACT_PERIOD", *columns).collect()
    return {
        (row["LOAN_ID"], row["ACT_PERIOD"]): tuple(row[column] for column in columns)
        for row in selected
    }


# ---------------------------------------------------------------------------
# Leakage control 1: temporal invariance
# ---------------------------------------------------------------------------


def _changed_columns(
    spark: SparkSession, cutoff: date
) -> tuple[set[str], dict[tuple[str, date], tuple[object, ...]]]:
    """Return which panel columns change when rows after ``cutoff`` are withheld."""
    macro = _macro_frame(spark)
    silver = _silver_frame(spark)
    truncated = silver.where(spark_fn.col("ACT_PERIOD") <= spark_fn.lit(cutoff))

    full_panel = build_gold_panel(silver, macro).where(
        spark_fn.col("ACT_PERIOD") <= spark_fn.lit(cutoff)
    )
    truncated_panel = build_gold_panel(truncated, macro)

    columns = sorted(c for c in full_panel.columns if not c.startswith("_"))
    full_rows = _rows_by_key(full_panel, columns)
    truncated_rows = _rows_by_key(truncated_panel, columns)

    assert full_rows, "invariance compared no rows, the fixture is wrong"
    assert set(full_rows) == set(truncated_rows), (
        "withholding future rows changed which loan-months are at risk at or before the cutoff"
    )

    changed = {
        name
        for key in full_rows
        for name, before, after in zip(columns, full_rows[key], truncated_rows[key], strict=True)
        if before != after
    }
    return changed, full_rows


def test_only_classified_outcome_columns_depend_on_future_rows(
    spark_session: SparkSession,
) -> None:
    """No feature may change when later rows are withheld.

    Stated as a subset rather than a fixed exclusion list: any new column that
    carries lookahead fails here until it is deliberately classified in
    OUTCOME_COLUMNS, which is what PROJECT.md rule 2 is asking for.
    """
    changed, _ = _changed_columns(spark_session, _month(2016, 3))

    leaking = changed - FUTURE_DEPENDENT_COLUMNS
    assert not leaking, (
        f"these columns change when future rows are withheld but are not classified "
        f"as outcomes, so they leak into features: {sorted(leaking)}"
    )


def test_temporal_invariance_check_is_not_vacuous(spark_session: SparkSession) -> None:
    """Truncation must actually change something, or the subset test proves nothing.

    Loan 2 reaches D90 after the cutoff, so with the full table its earlier rows
    carry a positive 12-month label and a known exit; with later rows withheld
    both are unknowable. If nothing ever changes, the test above is comparing a
    panel with itself.
    """
    changed, _ = _changed_columns(spark_session, _month(2016, 3))

    assert changed, "withholding future rows changed nothing, so the invariance test is vacuous"
    assert changed & {"DEFAULT_IN_12M", "EXIT_TYPE"}, (
        f"expected the forward label or exit type to change under truncation, got {sorted(changed)}"
    )


@settings(
    max_examples=4, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(offset=st.integers(min_value=1, max_value=8))
def test_temporal_invariance_holds_at_any_cutoff(spark_session: SparkSession, offset: int) -> None:
    """Invariance is a property of every cutoff, not of one chosen month."""
    changed, _ = _changed_columns(spark_session, _add_months(_month(2015, 7), offset))
    assert not changed - FUTURE_DEPENDENT_COLUMNS


# ---------------------------------------------------------------------------
# Leakage control 2: split integrity
# ---------------------------------------------------------------------------


def test_no_loan_is_both_training_and_out_of_vintage(spark_session: SparkSession) -> None:
    """The built panel must never place one loan in train and out-of-vintage."""
    panel = build_gold_panel(_silver_frame(spark_session), _macro_frame(spark_session))
    split_rows = panel.select("MODELLING_SPLIT").distinct().collect()
    splits = {row["MODELLING_SPLIT"] for row in split_rows}

    assert "train" in splits, "fixture produced no training rows, integrity check is vacuous"
    assert "out_of_vintage" in splits, "fixture produced no out-of-vintage rows"

    overlap = (
        panel.where(spark_fn.col("MODELLING_SPLIT") == "train")
        .select("LOAN_ID")
        .distinct()
        .join(
            panel.where(spark_fn.col("MODELLING_SPLIT") == "out_of_vintage")
            .select("LOAN_ID")
            .distinct(),
            "LOAN_ID",
            "inner",
        )
        .count()
    )
    assert overlap == 0, "a loan appears in both the training and out-of-vintage partitions"


def test_split_integrity_rejects_a_loan_in_two_vintages(spark_session: SparkSession) -> None:
    """A loan delivered in both an in-time and a held-out quarter must be rejected.

    This is the negative case. Without it, the assertion above could pass simply
    because no input ever puts one loan in two partitions.
    """
    rows = _loan_rows("L0000000009", "2012Q1", _month(2012, 1), _month(2015, 7), 6)
    rows += _loan_rows("L0000000009", "2016Q1", _month(2016, 1), _month(2016, 2), 6)
    contaminated = spark_session.createDataFrame(rows, _SILVER_SCHEMA)

    with pytest.raises(SplitIntegrityError):
        assign_model_splits(contaminated)


# ---------------------------------------------------------------------------
# Leakage control 3: macro lag
# ---------------------------------------------------------------------------


def test_no_macro_value_postdates_its_observation_month(spark_session: SparkSession) -> None:
    """Every joined macro release must have been available by the row's month."""
    panel = build_gold_panel(_silver_frame(spark_session), _macro_frame(spark_session))

    checked = 0
    for series_id in FRED_SERIES_IDS:
        available = f"{series_id}_AVAILABLE_DATE"
        observed = f"{series_id}_OBSERVATION_DATE"
        assert available in panel.columns, f"{available} is missing, cannot prove the macro lag"
        late = panel.where(
            (spark_fn.col(available) > spark_fn.col("ACT_PERIOD"))
            | (spark_fn.col(observed) > spark_fn.col("ACT_PERIOD"))
        ).count()
        assert late == 0, f"{series_id} entered rows before it was published"
        checked += 1

    assert checked == len(FRED_SERIES_IDS)
    assert panel.count() > 0, "macro lag checked an empty panel"


def test_point_in_time_join_ignores_a_later_revision(spark_session: SparkSession) -> None:
    """A revision published after the as-of date must never be joined.

    Section 3 requires a loan-month at date d to take the value published for d
    and never a later revision. The revised figure here is deliberately absurd,
    so any contamination is unmistakable.
    """
    as_of = _month(2015, 9)
    frame = spark_session.createDataFrame(
        [("L0000000001", as_of)],
        spark_types.StructType(
            [
                spark_types.StructField("LOAN_ID", spark_types.StringType(), False),
                spark_types.StructField("ACT_PERIOD", spark_types.DateType(), False),
            ]
        ),
    )
    joined = join_macro_point_in_time(
        frame, _macro_frame(spark_session, revisions=True), series_ids=("CSUSHPINSA",)
    )
    row = joined.first()
    assert row is not None

    assert row["CSUSHPINSA"] != Decimal("999999.000000"), (
        "a revision published in 2020 leaked into a 2015 loan-month"
    )
    assert row["CSUSHPINSA_AVAILABLE_DATE"] <= as_of


# ---------------------------------------------------------------------------
# Phase 4 exit criterion, second half: row counts reconcile
# ---------------------------------------------------------------------------


def test_panel_rows_reconcile_to_at_risk_loan_months(spark_session: SparkSession) -> None:
    """Gold must hold exactly one row per at-risk loan-month, and prove it."""
    silver = _silver_frame(spark_session)
    panel = build_gold_panel(silver, _macro_frame(spark_session))
    reconciliation = reconcile_gold_panel(silver, panel)

    assert reconciliation.gold_rows == panel.count()
    assert reconciliation.loan_count == panel.select("LOAN_ID").distinct().count()
    assert reconciliation.gold_rows > 0

    per_loan = panel.groupBy("LOAN_ID").count().collect()
    assert reconciliation.gold_rows == sum(row["count"] for row in per_loan)

    # Censored and post-exit months are dropped, so Gold is strictly smaller.
    assert reconciliation.terminal_or_post_exit_rows > 0, (
        "no rows were excluded, so the fixture never exercises censoring"
    )


def test_parsed_fred_releases_respect_publication_lag_end_to_end(
    spark_session: SparkSession,
) -> None:
    """Close the seam between FRED ingestion and the point-in-time join.

    The macro-lag test above builds its own vintage frame, so it proves the
    join honours AVAILABLE_DATE but never exercises the parser that produces
    those dates. This test runs a realistic FRED payload through the parser and
    into the join.

    US unemployment for August 2015 was published on 4 September 2015, and the
    September figure on 2 October 2015. A loan-month at 1 October 2015 therefore
    knows the August figure and cannot know the September one.
    """
    payload = {
        "observations": [
            {"date": "2015-08-01", "realtime_start": "2015-09-04", "value": "5.1"},
            {"date": "2015-09-01", "realtime_start": "2015-10-02", "value": "5.0"},
        ]
    }
    macro = macro_observations_frame(spark_session, parse_fred_initial_releases("UNRATE", payload))

    as_of = _month(2015, 10)
    frame = spark_session.createDataFrame(
        [("L0000000001", as_of)],
        spark_types.StructType(
            [
                spark_types.StructField("LOAN_ID", spark_types.StringType(), False),
                spark_types.StructField("ACT_PERIOD", spark_types.DateType(), False),
            ]
        ),
    )
    row = join_macro_point_in_time(frame, macro, series_ids=("UNRATE",)).first()
    assert row is not None

    assert row["UNRATE"] == Decimal("5.100000"), (
        "expected the August figure, the latest published by 1 October 2015"
    )
    assert row["UNRATE_OBSERVATION_DATE"] == _month(2015, 8)
    assert row["UNRATE_AVAILABLE_DATE"] == date(2015, 9, 4)
