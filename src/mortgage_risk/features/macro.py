"""Point-in-time macro data contracts and joins for the Gold panel."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final, cast

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as spark_fn
from pyspark.sql import types as spark_types

from mortgage_risk.config.gold import FRED_SERIES_IDS

_REQUIRED_MACRO_COLUMNS: Final = frozenset(
    {"SERIES_ID", "OBSERVATION_DATE", "AVAILABLE_DATE", "VALUE"}
)
_PREFIX_PATTERN: Final = re.compile(r"^(?:[A-Z][A-Z0-9]*_)*$")
_FRED_EARLIEST_REALTIME_DATE: Final = "1776-07-04"
_FRED_LATEST_REALTIME_DATE: Final = "9999-12-31"


class MacroContractError(ValueError):
    """Raised when macro vintages cannot support a point-in-time join."""


class MacroCoverageError(MacroContractError):
    """Raised when at least one panel date has no available macro value."""


@dataclass(frozen=True, slots=True)
class MacroObservation:
    """One macro value and the date it first became available."""

    series_id: str
    observation_date: date
    available_date: date
    value: Decimal


def fred_initial_release_parameters(
    series_id: str,
    observation_start: date,
    observation_end: date,
) -> dict[str, str]:
    """Return FRED parameters that request unrevised initial releases."""
    if series_id not in FRED_SERIES_IDS:
        raise ValueError(f"unsupported FRED series: {series_id}")
    if observation_start > observation_end:
        raise ValueError("observation_start must not be after observation_end")
    return {
        "series_id": series_id,
        "file_type": "json",
        "output_type": "4",
        "realtime_start": _FRED_EARLIEST_REALTIME_DATE,
        "realtime_end": _FRED_LATEST_REALTIME_DATE,
        "observation_start": observation_start.isoformat(),
        "observation_end": observation_end.isoformat(),
        "sort_order": "asc",
        "limit": "100000",
    }


def parse_fred_initial_releases(
    series_id: str,
    payload: Mapping[str, object],
) -> tuple[MacroObservation, ...]:
    """Parse a FRED output_type=4 response without accepting missing values."""
    raw_observations = payload.get("observations")
    if not isinstance(raw_observations, list):
        raise MacroContractError("FRED payload has no observations list")

    parsed: list[MacroObservation] = []
    for raw in raw_observations:
        if not isinstance(raw, Mapping):
            raise MacroContractError("FRED observation is not an object")
        observation = cast(Mapping[str, object], raw)
        raw_value = observation.get("value")
        if raw_value == ".":
            continue
        try:
            observation_date = date.fromisoformat(str(observation["date"]))
            available_date = date.fromisoformat(str(observation["realtime_start"]))
            value = Decimal(str(raw_value))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise MacroContractError(f"invalid FRED observation for {series_id}") from exc
        parsed.append(
            MacroObservation(
                series_id=series_id,
                observation_date=observation_date,
                available_date=available_date,
                value=value,
            )
        )
    return tuple(parsed)


def macro_observations_frame(
    spark: SparkSession,
    observations: Sequence[MacroObservation],
) -> DataFrame:
    """Create the canonical Spark macro-vintage frame."""
    schema = spark_types.StructType(
        [
            spark_types.StructField("SERIES_ID", spark_types.StringType(), False),
            spark_types.StructField("OBSERVATION_DATE", spark_types.DateType(), False),
            spark_types.StructField("AVAILABLE_DATE", spark_types.DateType(), False),
            spark_types.StructField("VALUE", spark_types.DecimalType(20, 6), False),
        ]
    )
    rows = [
        (
            observation.series_id,
            observation.observation_date,
            observation.available_date,
            observation.value,
        )
        for observation in observations
    ]
    return spark.createDataFrame(rows, schema)


def validate_macro_observations(macro: DataFrame) -> None:
    """Fail loudly on malformed, unsupported, or duplicate macro vintages."""
    missing = sorted(_REQUIRED_MACRO_COLUMNS.difference(macro.columns))
    if missing:
        raise MacroContractError(f"macro data is missing columns: {missing}")

    invalid = (
        macro.where(
            spark_fn.col("SERIES_ID").isNull()
            | spark_fn.col("OBSERVATION_DATE").isNull()
            | spark_fn.col("AVAILABLE_DATE").isNull()
            | spark_fn.col("VALUE").isNull()
            | ~spark_fn.col("SERIES_ID").isin(*FRED_SERIES_IDS)
        )
        .limit(1)
        .count()
    )
    if invalid:
        raise MacroContractError("macro data contains nulls or unsupported series")

    duplicates = (
        macro.groupBy("SERIES_ID", "OBSERVATION_DATE", "AVAILABLE_DATE")
        .count()
        .where(spark_fn.col("count") > 1)
        .limit(1)
        .count()
    )
    if duplicates:
        raise MacroContractError("macro data contains duplicate vintages")


def join_macro_point_in_time(
    frame: DataFrame,
    macro: DataFrame,
    *,
    as_of_column: str = "ACT_PERIOD",
    series_ids: Sequence[str] = FRED_SERIES_IDS,
    prefix: str = "",
) -> DataFrame:
    """Join the latest macro release available on each panel as-of date."""
    if as_of_column not in frame.columns:
        raise ValueError(f"frame has no as-of column {as_of_column!r}")
    if not series_ids:
        raise ValueError("series_ids must not be empty")
    unsupported = sorted(set(series_ids).difference(FRED_SERIES_IDS))
    if unsupported:
        raise ValueError(f"unsupported FRED series: {unsupported}")
    if _PREFIX_PATTERN.fullmatch(prefix) is None:
        raise ValueError(f"invalid macro output prefix: {prefix!r}")

    validate_macro_observations(macro)
    as_of_dates = (
        frame.select(spark_fn.col(as_of_column).alias("_MACRO_AS_OF_DATE"))
        .where(spark_fn.col("_MACRO_AS_OF_DATE").isNotNull())
        .distinct()
    )
    eligible = as_of_dates.crossJoin(
        spark_fn.broadcast(macro.where(spark_fn.col("SERIES_ID").isin(*series_ids)))
    ).where(
        (spark_fn.col("OBSERVATION_DATE") <= spark_fn.col("_MACRO_AS_OF_DATE"))
        & (spark_fn.col("AVAILABLE_DATE") <= spark_fn.col("_MACRO_AS_OF_DATE"))
    )
    latest_window = Window.partitionBy("_MACRO_AS_OF_DATE", "SERIES_ID").orderBy(
        spark_fn.col("OBSERVATION_DATE").desc(),
        spark_fn.col("AVAILABLE_DATE").desc(),
    )
    latest = (
        eligible.withColumn("_MACRO_RANK", spark_fn.row_number().over(latest_window))
        .where(spark_fn.col("_MACRO_RANK") == 1)
        .drop("_MACRO_RANK")
    )

    expected_count = as_of_dates.count() * len(series_ids)
    actual_count = latest.count()
    if actual_count != expected_count:
        raise MacroCoverageError(
            f"macro coverage incomplete: expected {expected_count} date-series pairs, "
            f"found {actual_count}"
        )

    expressions: list[Column] = []
    for series_id in series_ids:
        matches = spark_fn.col("SERIES_ID") == series_id
        expressions.extend(
            (
                spark_fn.max(spark_fn.when(matches, spark_fn.col("VALUE"))).alias(
                    f"{prefix}{series_id}"
                ),
                spark_fn.max(spark_fn.when(matches, spark_fn.col("OBSERVATION_DATE"))).alias(
                    f"{prefix}{series_id}_OBSERVATION_DATE"
                ),
                spark_fn.max(spark_fn.when(matches, spark_fn.col("AVAILABLE_DATE"))).alias(
                    f"{prefix}{series_id}_AVAILABLE_DATE"
                ),
            )
        )
    wide = latest.groupBy("_MACRO_AS_OF_DATE").agg(*expressions)
    return frame.join(
        wide,
        frame[as_of_column] == wide["_MACRO_AS_OF_DATE"],
        "left",
    ).drop("_MACRO_AS_OF_DATE")
