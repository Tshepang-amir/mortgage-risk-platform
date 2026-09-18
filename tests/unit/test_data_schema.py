"""Tests for the Fannie Mae raw data contract."""

from __future__ import annotations

import pytest

from mortgage_risk.data.schema import (
    CURRENT_FILE_FIELD_COUNT,
    FANNIE_MAE_FIELDS,
    FIELD_BY_COLUMN,
    FORWARD_GLOSSARY_FIELDS,
    OFFICIAL_R_IMPORT_FIELD_COUNT,
    SAMPLE_FILE_FIELD_COUNT,
    FieldType,
    SchemaValidationError,
    field_names,
    split_pipe_row,
    string_length_exceedances,
    validate_raw_values,
)


def test_schema_positions_are_contiguous() -> None:
    """The raw layout is positional, so gaps would be a contract break."""
    assert [field.position for field in FANNIE_MAE_FIELDS] == list(
        range(1, CURRENT_FILE_FIELD_COUNT + 1)
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


def test_current_file_schema_has_113_fields() -> None:
    """The quarterly Primary files emit 113 columns. See ADR-008.

    Confirmed two ways: the published glossary numbers these positions, and the
    published sample yields exactly 108 tokens against a documented 108-field
    layout, which proves Fannie Mae writes no trailing delimiter, so token count
    is field count.
    """
    names = field_names(CURRENT_FILE_FIELD_COUNT)
    assert len(names) == 113
    assert names[:2] == ("POOL_ID", "LOAN_ID")
    assert names[-3:] == (
        "ORIG_CLASSIC_FICO",
        "ISSUANCE_CLASSIC_FICO",
        "CURRENT_CLASSIC_FICO",
    )


def test_classic_fico_fields_are_typed_like_the_other_credit_scores() -> None:
    """Positions 111 to 113 are three-digit scores, as CSCORE_B already is."""
    for column in ("ORIG_CLASSIC_FICO", "ISSUANCE_CLASSIC_FICO", "CURRENT_CLASSIC_FICO"):
        assert FIELD_BY_COLUMN[column].raw_format == "9(3)"
    assert FIELD_BY_COLUMN["ORIG_CLASSIC_FICO"].position == 111
    assert FIELD_BY_COLUMN["ISSUANCE_CLASSIC_FICO"].position == 112
    assert FIELD_BY_COLUMN["CURRENT_CLASSIC_FICO"].position == 113


def test_only_vantagescore_remains_unconfirmed() -> None:
    """Position 114 is in the glossary but in no file we hold, so it stays out.

    ADR-004 refuses unconfirmed positions as raw columns. Accepting 114 would
    make validation reject every real record.
    """
    assert set(FORWARD_GLOSSARY_FIELDS) == {114}


def test_pipe_row_validation_accepts_current_width() -> None:
    """A real-shaped 113-column row validates, blank field 1 included."""
    values = [""] * CURRENT_FILE_FIELD_COUNT
    values[1] = "100023020488"
    values[2] = "082009"
    values[7] = "5.375"
    values[9] = "55000.00"
    values[12] = "240"
    values[13] = "082009"
    values[14] = "102009"
    values[15] = "-1"
    values[39] = "0"
    values[110] = "714"
    line = "|".join(values)

    assert split_pipe_row(line, field_count=CURRENT_FILE_FIELD_COUNT) == tuple(values)


def test_unconfirmed_width_is_still_rejected() -> None:
    """114 columns is not accepted just because the glossary documents it."""
    with pytest.raises(SchemaValidationError, match="unsupported field count"):
        validate_raw_values([""] * 114, field_count=114)


# Real value from 2016Q1, 68 characters against a published X(50). See ADR-009.
_REAL_LONG_SELLER = "United Shore Financial Services, Llc D/B/A United Wholesale Mortgage"


def _current_width_row() -> list[str]:
    values = [""] * CURRENT_FILE_FIELD_COUNT
    values[1] = "100023020488"
    values[2] = "082009"
    return values


def test_over_long_seller_name_still_parses() -> None:
    """Fannie Mae's own data exceeds Fannie Mae's published X(50).

    Four of six vintages breach it from 2007Q1 onward, so halting on it would
    reject valid loans over a field no model consumes.
    """
    declared = FIELD_BY_COLUMN["SELLER"].max_length
    assert declared is not None
    assert len(_REAL_LONG_SELLER) > declared

    values = _current_width_row()
    values[4] = _REAL_LONG_SELLER
    validate_raw_values(values, field_count=CURRENT_FILE_FIELD_COUNT)


def test_over_long_text_is_reported_for_the_quality_gate() -> None:
    """Parsing does not fail, but the divergence must still be visible."""
    values = _current_width_row()
    values[4] = _REAL_LONG_SELLER

    exceedances = string_length_exceedances(values, field_count=CURRENT_FILE_FIELD_COUNT)

    assert exceedances == (("SELLER", 50, len(_REAL_LONG_SELLER)),)


def test_conforming_text_reports_nothing() -> None:
    values = _current_width_row()
    values[4] = "Citimortgage, Inc."

    assert string_length_exceedances(values, field_count=CURRENT_FILE_FIELD_COUNT) == ()


def test_numeric_width_is_declared_but_not_enforced() -> None:
    """Characterisation test for a known gap, not an endorsement of it.

    `max_length` is populated only on the 39 text fields. Numeric and date
    fields carry their width in `raw_format`, for example `9(3)`, and nothing
    checks it, so a 40-digit credit score currently parses. That predates
    ADR-009 and is tracked as an open question in PROGRESS.md, to be closed
    with evidence from the Bronze run rather than by imposing an unevidenced
    constraint, which is what produced the SELLER breakage.

    If someone enforces numeric width, this test should fail and be replaced
    with one asserting the rejection. It exists so that change is deliberate.
    """
    assert FIELD_BY_COLUMN["CSCORE_B"].raw_format == "9(3)"
    assert FIELD_BY_COLUMN["CSCORE_B"].max_length is None

    values = _current_width_row()
    values[23] = "7" * 40
    validate_raw_values(values, field_count=CURRENT_FILE_FIELD_COUNT)


def test_max_length_is_declared_only_on_text_fields() -> None:
    """Pins the fact that makes ADR-009's split a text-only concern."""
    typed_with_length = [
        field.column_name
        for field in FANNIE_MAE_FIELDS
        if field.field_type is not FieldType.STRING and field.max_length is not None
    ]
    assert typed_with_length == []
    assert len([f for f in FANNIE_MAE_FIELDS if f.max_length is not None]) == 39


def test_field_count_still_catches_a_lost_delimiter() -> None:
    """Structural corruption is caught by width, which is why text needs no cap.

    A lost delimiter merges two fields and changes the token count, so the
    exact-width check rejects it before any length rule would matter.
    """
    values = _current_width_row()
    merged = [*values[:4], values[4] + values[5], *values[6:]]

    assert len(merged) == CURRENT_FILE_FIELD_COUNT - 1
    with pytest.raises(SchemaValidationError, match="expected 113 fields"):
        validate_raw_values(merged, field_count=CURRENT_FILE_FIELD_COUNT)
