"""Tests for the Fannie Mae raw data contract."""

from __future__ import annotations

import pytest

from mortgage_risk.data.schema import (
    FANNIE_MAE_FIELDS,
    FIELD_BY_COLUMN,
    OFFICIAL_R_IMPORT_FIELD_COUNT,
    SAMPLE_FILE_FIELD_COUNT,
    SchemaValidationError,
    field_names,
    split_pipe_row,
    validate_raw_values,
)


def test_schema_positions_are_contiguous() -> None:
    """The raw layout is positional, so gaps would be a contract break."""
    assert [field.position for field in FANNIE_MAE_FIELDS] == list(
        range(1, OFFICIAL_R_IMPORT_FIELD_COUNT + 1)
    )


def test_sample_file_schema_has_108_fields() -> None:
    """Phase 1 targets the 108-column sample/release layout."""
    names = field_names(SAMPLE_FILE_FIELD_COUNT)
    assert len(names) == 108
    assert names[:4] == ("POOL_ID", "LOAN_ID", "ACT_PERIOD", "CHANNEL")
    assert names[-3:] == ("ADR_TYPE", "ADR_COUNT", "ADR_UPB")


def test_importer_extension_schema_has_110_fields() -> None:
    """The current official R importer adds two known extension fields."""
    names = field_names(OFFICIAL_R_IMPORT_FIELD_COUNT)
    assert len(names) == 110
    assert names[-2:] == ("PAYMENT_DEFERRAL_MOD_EVENT_FLAG", "INTEREST_BEARING_UPB")


def test_key_modeling_fields_are_typed() -> None:
    """Risk, time and target columns are present before later phases use them."""
    assert FIELD_BY_COLUMN["ACT_PERIOD"].raw_format == "MMYYYY"
    assert FIELD_BY_COLUMN["DLQ_STATUS"].max_length == 2
    assert FIELD_BY_COLUMN["CSCORE_B"].raw_format == "9(3)"
    assert FIELD_BY_COLUMN["OLTV"].raw_format == "9(3)"
    assert FIELD_BY_COLUMN["DTI"].raw_format == "9(2)"


def test_pipe_row_validation_accepts_sample_width() -> None:
    """A headerless pipe row with a blank field 1 still validates at 108 columns."""
    values = [""] * SAMPLE_FILE_FIELD_COUNT
    values[1] = "100023020488"
    values[2] = "082009"
    values[7] = "5.375"
    values[9] = "55000.00"
    values[12] = "240"
    values[13] = "082009"
    values[14] = "102009"
    values[15] = "-1"
    values[39] = "0"
    line = "|".join(values)
    assert split_pipe_row(line) == tuple(values)


def test_validation_rejects_bad_field_count() -> None:
    """A truncated raw row is not silently accepted."""
    with pytest.raises(SchemaValidationError, match="expected 108 fields"):
        validate_raw_values([""] * 107)


def test_validation_rejects_bad_month() -> None:
    """MMYYYY date fields reject impossible calendar months."""
    values = [""] * SAMPLE_FILE_FIELD_COUNT
    values[2] = "132009"
    with pytest.raises(SchemaValidationError, match="ACT_PERIOD"):
        validate_raw_values(values)
