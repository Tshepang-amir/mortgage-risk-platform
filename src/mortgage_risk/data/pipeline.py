"""Execute resumable real-data Bronze-to-Gold publication stages."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession

from mortgage_risk.common.spark import build_local_spark
from mortgage_risk.config.gold import FRED_SERIES_IDS
from mortgage_risk.data.bronze import ingest_bronze
from mortgage_risk.data.gold import publish_gold
from mortgage_risk.data.schema import CURRENT_FILE_FIELD_COUNT
from mortgage_risk.data.silver import publish_silver
from mortgage_risk.features.macro import (
    MacroContractError,
    MacroObservation,
    macro_observations_frame,
    parse_fred_initial_releases,
    validate_macro_observations,
)

_RAW_FILENAMES: Final = (
    "2005Q1.csv",
    "2005Q3.csv",
    "2007Q1.csv",
    "2012Q1.csv",
    "2016Q1.csv",
    "2018Q1.csv",
)
_STAGES: Final = ("macro", "bronze", "silver", "gold", "all")


@dataclass(frozen=True, slots=True)
class PipelinePaths:
    """Filesystem locations used by the local real-data pipeline."""

    raw_dir: Path
    external_dir: Path
    delta_dir: Path

    @property
    def raw_files(self) -> tuple[Path, ...]:
        return tuple(self.raw_dir / name for name in _RAW_FILENAMES)

    @property
    def bronze(self) -> Path:
        return self.delta_dir / "bronze"

    @property
    def silver(self) -> Path:
        return self.delta_dir / "silver"

    @property
    def servicer(self) -> Path:
        return self.delta_dir / "servicer"

    @property
    def quarantine(self) -> Path:
        return self.delta_dir / "quarantine" / "silver"

    @property
    def macro(self) -> Path:
        return self.delta_dir / "macro"

    @property
    def gold(self) -> Path:
        return self.delta_dir / "gold"

    @property
    def warehouse(self) -> Path:
        return self.delta_dir / "warehouse"


def load_cached_macro_observations(cache_dir: Path) -> tuple[MacroObservation, ...]:
    """Load and validate all required cached FRED responses."""
    observations: list[MacroObservation] = []
    for series_id in FRED_SERIES_IDS:
        source = cache_dir / f"{series_id}.json"
        if not source.is_file():
            raise FileNotFoundError(source)
        try:
            raw_payload = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MacroContractError(f"invalid JSON cache for {series_id}") from exc
        if not isinstance(raw_payload, Mapping):
            raise MacroContractError(f"FRED cache is not an object for {series_id}")
        payload = cast(Mapping[str, object], raw_payload)
        parsed = parse_fred_initial_releases(series_id, payload)
        if not parsed:
            raise MacroContractError(f"FRED cache has no observations for {series_id}")
        observations.extend(parsed)
    return tuple(observations)


def publish_macro_delta(
    spark: SparkSession,
    cache_dir: Path,
    macro_path: Path,
) -> dict[str, int]:
    """Replace the canonical macro Delta table from validated FRED caches."""
    observations = load_cached_macro_observations(cache_dir)
    frame = macro_observations_frame(spark, observations)
    validate_macro_observations(frame)
    counts = Counter(item.series_id for item in observations)
    (
        frame.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(str(macro_path.resolve()))
    )
    return {series_id: counts[series_id] for series_id in FRED_SERIES_IDS}


def read_delta_pinned(spark: SparkSession, path: Path) -> tuple[DataFrame, int]:
    """Read a Delta table pinned to its current version, returning both.

    The read is pinned with ``versionAsOf`` rather than taking the latest and
    recording the version separately, so the version reported is exactly the
    data that was read and the two cannot drift if anything writes concurrently.
    """
    target = str(path.resolve())
    version_row = DeltaTable.forPath(spark, target).history(1).select("version").first()
    if version_row is None:
        raise MacroContractError(f"Delta table has no committed version: {target}")
    version = int(version_row["version"])
    frame = spark.read.format("delta").option("versionAsOf", version).load(target)
    return frame, version


def run_stage(spark: SparkSession, stage: str, paths: PipelinePaths) -> None:
    """Execute one idempotent publication stage and print its evidence."""
    if stage == "macro":
        counts = publish_macro_delta(spark, paths.external_dir, paths.macro)
        print(f"macro published: {counts}")
        return
    if stage == "bronze":
        bronze_result = ingest_bronze(
            spark,
            paths.raw_files,
            paths.bronze,
            field_count=CURRENT_FILE_FIELD_COUNT,
        )
        print(f"bronze published: {bronze_result}")
        return
    if stage == "silver":
        silver_result = publish_silver(
            spark,
            paths.bronze,
            paths.silver,
            paths.servicer,
            quarantine_path=paths.quarantine,
        )
        print(f"silver published: {silver_result}")
        return
    if stage == "gold":
        silver, silver_version = read_delta_pinned(spark, paths.silver)
        macro, macro_version = read_delta_pinned(spark, paths.macro)
        gold_result = publish_gold(
            spark,
            silver,
            macro,
            paths.gold,
            source_versions={"silver": silver_version, "macro": macro_version},
        )
        print(f"gold published: {gold_result}")
        return
    raise ValueError(f"unsupported pipeline stage: {stage}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run selected real-data publication stages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=_STAGES)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--external-dir", type=Path, default=Path("data/external"))
    parser.add_argument("--delta-dir", type=Path, default=Path("data/delta"))
    arguments = parser.parse_args(argv)
    paths = PipelinePaths(arguments.raw_dir, arguments.external_dir, arguments.delta_dir)

    spark = build_local_spark("mortgage-risk-real-data", paths.warehouse)
    try:
        stages = (
            ("macro", "bronze", "silver", "gold")
            if arguments.stage == "all"
            else (arguments.stage,)
        )
        for stage in stages:
            run_stage(spark, stage, paths)
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
