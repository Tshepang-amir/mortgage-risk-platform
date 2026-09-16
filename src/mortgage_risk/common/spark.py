"""Local Spark session construction with Delta Lake enabled."""

from __future__ import annotations

from pathlib import Path

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession


def build_local_spark(
    app_name: str = "mortgage-risk-platform",
    warehouse_dir: Path | None = None,
) -> SparkSession:
    """Build the small local Spark runtime used by development and tests."""
    builder = (
        SparkSession.builder.master("local[2]")
        .appName(app_name)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.default.parallelism", "2")
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
