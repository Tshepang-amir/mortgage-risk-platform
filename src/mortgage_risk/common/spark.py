"""Local Spark session construction with Delta Lake enabled."""

from __future__ import annotations

from pathlib import Path

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession


def build_local_spark(
    app_name: str = "mortgage-risk-platform",
    warehouse_dir: Path | None = None,
    *,
    cores: int = 2,
    shuffle_partitions: int = 2,
) -> SparkSession:
    """Build the local Spark runtime.

    The defaults are sized for the synthetic test fixtures, where two shuffle
    partitions keep suites fast. Real-data runs must raise
    ``shuffle_partitions``: at two partitions a 177 million row shuffle has to
    hold roughly 88 million rows per partition, which exhausts the heap
    whatever its size.

    Driver heap cannot be set here. PySpark launches the JVM before this
    builder runs, so ``spark.driver.memory`` set as config is silently ignored;
    the launcher reads the ``SPARK_DRIVER_MEMORY`` environment variable
    instead. `effective_driver_memory` reports what was actually granted.
    """
    if cores < 1:
        raise ValueError("cores must be at least 1")
    if shuffle_partitions < 1:
        raise ValueError("shuffle_partitions must be at least 1")
    builder = (
        SparkSession.builder.master(f"local[{cores}]")
        .appName(app_name)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        .config("spark.default.parallelism", str(cores))
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    if warehouse_dir is not None:
        builder = builder.config(
            "spark.sql.warehouse.dir",
            str(warehouse_dir.resolve()),
        )

    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def effective_driver_memory(spark: SparkSession) -> str:
    """Report the driver heap Spark actually granted.

    Worth logging on real runs: a silently defaulted 1g heap looks identical to
    a configured one until a shuffle fails.
    """
    return str(spark.sparkContext.getConf().get("spark.driver.memory", "1g (default)"))
