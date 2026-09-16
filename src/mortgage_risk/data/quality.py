"""Great Expectations gate for the Silver mortgage panel."""

from __future__ import annotations

from dataclasses import dataclass

import great_expectations as gx
from great_expectations.expectations.core.expect_column_values_to_be_between import (
    ExpectColumnValuesToBeBetween,
)
from great_expectations.expectations.core.expect_column_values_to_be_in_set import (
    ExpectColumnValuesToBeInSet,
)
from great_expectations.expectations.core.expect_column_values_to_not_be_null import (
    ExpectColumnValuesToNotBeNull,
)
from great_expectations.expectations.core.expect_compound_columns_to_be_unique import (
    ExpectCompoundColumnsToBeUnique,
)
from great_expectations.expectations.core.expect_table_row_count_to_be_between import (
    ExpectTableRowCountToBeBetween,
)
from pyspark.sql import DataFrame

_ALLOWED_DELINQUENCY_STATUSES = [str(value) for value in range(10)] + ["XX", "RA"]


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    """Compact result returned by the Silver quality gate."""

    success: bool
    evaluated_expectations: int
    failed_expectations: tuple[str, ...]


class DataQualityError(RuntimeError):
    """Raised when an expectation suite blocks layer publication."""

    def __init__(self, report: DataQualityReport) -> None:
        self.report = report
        failures = ", ".join(report.failed_expectations)
        super().__init__(f"Silver data quality gate failed: {failures}")


def silver_expectation_suite() -> gx.ExpectationSuite:
    """Build the executable Silver contract."""
    return gx.ExpectationSuite(
        name="silver_mortgage_panel",
        expectations=[
            ExpectTableRowCountToBeBetween(min_value=1),
            ExpectColumnValuesToNotBeNull(column="LOAN_ID"),
            ExpectColumnValuesToNotBeNull(column="ACT_PERIOD"),
            ExpectColumnValuesToNotBeNull(column="_source_file"),
            ExpectColumnValuesToNotBeNull(column="_source_sha256"),
            ExpectCompoundColumnsToBeUnique(column_list=["LOAN_ID", "ACT_PERIOD"]),
            ExpectColumnValuesToBeBetween(
                column="ORIG_UPB",
                min_value=0,
                strict_min=True,
            ),
            ExpectColumnValuesToBeBetween(
                column="CURRENT_UPB",
                min_value=0,
            ),
            ExpectColumnValuesToBeInSet(
                column="DLQ_STATUS",
                value_set=_ALLOWED_DELINQUENCY_STATUSES,
            ),
        ],
    )


def validate_silver(frame: DataFrame) -> DataQualityReport:
    """Run the Silver suite against a Spark DataFrame and fail loudly."""
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_spark(name="silver_runtime")
    asset = data_source.add_dataframe_asset(name="silver_candidate")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole_candidate")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": frame})
    result = batch.validate(silver_expectation_suite())

    failed_names: list[str] = []
    for expectation_result in result.results:
        if expectation_result.success:
            continue
        config = expectation_result.expectation_config
        failed_names.append("unknown_expectation" if config is None else str(config.type))

    report = DataQualityReport(
        success=bool(result.success),
        evaluated_expectations=len(result.results),
        failed_expectations=tuple(failed_names),
    )
    if not report.success:
        raise DataQualityError(report)
    return report
