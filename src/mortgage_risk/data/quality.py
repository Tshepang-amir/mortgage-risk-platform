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

# Measured across all 177,385,328 Bronze rows of the six ADR-002 vintages:
# exactly 101 distinct values, being zero-padded "00" through "99" plus "XX".
# The glossary gives no enumeration for position 40, only "the number of months
# the obligor is delinquent" as X(2), so the domain is evidenced rather than
# assumed. The previous set was ["0".."9", "XX", "RA"], which encoded the
# synthetic generator's unpadded output and rejected 95.7 percent of real rows
# because "00" is not "0". "RA" appears nowhere in the real data and is not
# allowed back in on the strength of documentation alone: an unobserved code
# should fail this gate loudly, which is how the mismatch surfaced. See ADR-013.
_ALLOWED_DELINQUENCY_STATUSES = [f"{value:02d}" for value in range(100)] + ["XX"]


@dataclass(frozen=True, slots=True)
class ExpectationFailure:
    """What failed, on which column, and what was actually seen."""

    expectation: str
    column: str | None
    observed_value: str | None
    unexpected_count: int | None
    exception_message: str | None

    def describe(self) -> str:
        target = f"{self.expectation}[{self.column}]" if self.column else self.expectation
        if self.exception_message:
            return f"{target} errored: {self.exception_message}"
        details = []
        if self.observed_value is not None:
            details.append(f"observed={self.observed_value}")
        if self.unexpected_count is not None:
            details.append(f"unexpected_rows={self.unexpected_count}")
        return f"{target} {' '.join(details)}" if details else target


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    """Compact result returned by the Silver quality gate."""

    success: bool
    evaluated_expectations: int
    failed_expectations: tuple[str, ...]
    failures: tuple[ExpectationFailure, ...] = ()

    @property
    def errored(self) -> tuple[ExpectationFailure, ...]:
        """Failures caused by the check itself raising, not by the data.

        An expectation that raised says nothing about the data. Reporting the
        two together invites reading a broken harness as a data finding.
        """
        return tuple(item for item in self.failures if item.exception_message)


class DataQualityError(RuntimeError):
    """Raised when an expectation suite blocks layer publication."""

    def __init__(self, report: DataQualityReport) -> None:
        self.report = report
        if report.failures:
            detail = "; ".join(item.describe() for item in report.failures)
        else:
            detail = ", ".join(report.failed_expectations)
        super().__init__(f"Silver data quality gate failed: {detail}")


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
    failures: list[ExpectationFailure] = []
    for expectation_result in result.results:
        if expectation_result.success:
            continue
        config = expectation_result.expectation_config
        name = "unknown_expectation" if config is None else str(config.type)
        failed_names.append(name)
        kwargs = dict(config.kwargs) if config is not None else {}
        column = kwargs.get("column") or kwargs.get("column_list")
        payload = dict(expectation_result.result or {})
        raised = dict(expectation_result.exception_info or {})
        failures.append(
            ExpectationFailure(
                expectation=name,
                column=None if column is None else str(column),
                observed_value=(
                    None
                    if payload.get("observed_value") is None
                    else str(payload["observed_value"])
                ),
                unexpected_count=(
                    None
                    if payload.get("unexpected_count") is None
                    else int(payload["unexpected_count"])
                ),
                exception_message=(
                    str(raised["exception_message"]) if raised.get("raised_exception") else None
                ),
            )
        )

    report = DataQualityReport(
        success=bool(result.success),
        evaluated_expectations=len(result.results),
        failed_expectations=tuple(failed_names),
        failures=tuple(failures),
    )
    if not report.success:
        raise DataQualityError(report)
    return report
