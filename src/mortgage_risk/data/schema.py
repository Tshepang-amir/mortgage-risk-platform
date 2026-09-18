"""Fannie Mae Single-Family Loan Performance data contracts.

The raw quarterly files are pipe-delimited and have no header row. Field
positions are therefore part of the contract, not a convenience.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Final, TypeAlias

PIPE_DELIMITER: Final = "|"
SCHEMA_SOURCE_URL: Final = (
    "https://capitalmarkets.fanniemae.com/resources/file/credit-risk/pdf/"
    "crt-file-layout-and-glossary.pdf"
)
SCHEMA_SOURCE_DATE: Final = "2026-09-10"
SAMPLE_FILE_FIELD_COUNT: Final = 108
OFFICIAL_R_IMPORT_FIELD_COUNT: Final = 110
# Width actually emitted by the quarterly Primary files, confirmed against the
# real 2005Q1 to 2018Q1 downloads and the published glossary. See ADR-008.
CURRENT_FILE_FIELD_COUNT: Final = 113
LATEST_GLOSSARY_POSITION_COUNT: Final = 114
SUPPORTED_FIELD_COUNTS: Final = (
    SAMPLE_FILE_FIELD_COUNT,
    OFFICIAL_R_IMPORT_FIELD_COUNT,
    CURRENT_FILE_FIELD_COUNT,
)
FORWARD_GLOSSARY_FIELDS: Final[Mapping[int, str]] = MappingProxyType(
    {
        114: "Origination VantageScore 4.0",
    }
)


class FieldType(Enum):
    """Logical type used for raw field validation."""

    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    MONTH = "month"


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    """One positional field in the Fannie Mae raw file layout."""

    position: int
    display_name: str
    column_name: str
    field_type: FieldType
    raw_format: str
    max_length: int | None
    scale: int
    single_family_applicable: bool


class SchemaValidationError(ValueError):
    """Raised when a raw row does not satisfy the positional schema."""


SchemaRow: TypeAlias = tuple[int, str, str, FieldType, str, int | None, int, bool]
_SCHEMA_ROWS: Final[tuple[SchemaRow, ...]] = (
    (
        1,
        "Reference Pool ID",
        "POOL_ID",
        FieldType.STRING,
        "X(4)",
        4,
        0,
        False,
    ),
    (
        2,
        "Loan Identifier",
        "LOAN_ID",
        FieldType.STRING,
        "X(12)",
        12,
        0,
        True,
    ),
    (
        3,
        "Monthly Reporting Period",
        "ACT_PERIOD",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        4,
        "Channel",
        "CHANNEL",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        5,
        "Seller Name",
        "SELLER",
        FieldType.STRING,
        "X(50)",
        50,
        0,
        True,
    ),
    (
        6,
        "Servicer Name",
        "SERVICER",
        FieldType.STRING,
        "X(50)",
        50,
        0,
        True,
    ),
    (
        7,
        "Master Servicer",
        "MASTER_SERVICER",
        FieldType.STRING,
        "X(10)",
        10,
        0,
        False,
    ),
    (
        8,
        "Original Interest Rate",
        "ORIG_RATE",
        FieldType.DECIMAL,
        "9(2).999",
        None,
        3,
        True,
    ),
    (
        9,
        "Current Interest Rate",
        "CURR_RATE",
        FieldType.DECIMAL,
        "9(2).999",
        None,
        3,
        True,
    ),
    (
        10,
        "Original UPB",
        "ORIG_UPB",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        11,
        "UPB at Issuance",
        "ISSUANCE_UPB",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        12,
        "Current Actual UPB",
        "CURRENT_UPB",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        13,
        "Original Loan Term",
        "ORIG_TERM",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        14,
        "Origination Date",
        "ORIG_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        15,
        "First Payment Date",
        "FIRST_PAY",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        16,
        "Loan Age",
        "LOAN_AGE",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        17,
        "Remaining Months to Legal Maturity",
        "REM_MONTHS",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        18,
        "Remaining Months To Maturity",
        "ADJ_REM_MONTHS",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        19,
        "Maturity Date",
        "MATR_DT",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        20,
        "Original Loan to Value Ratio (LTV)",
        "OLTV",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        21,
        "Original Combined Loan to Value Ratio (CLTV)",
        "OCLTV",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        22,
        "Number of Borrowers",
        "NUM_BO",
        FieldType.INTEGER,
        "9(2)",
        None,
        0,
        True,
    ),
    (
        23,
        "Debt-To-Income (DTI)",
        "DTI",
        FieldType.INTEGER,
        "9(2)",
        None,
        0,
        True,
    ),
    (
        24,
        "Borrower Credit Score at Origination",
        "CSCORE_B",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        25,
        "Co-Borrower Credit Score at Origination",
        "CSCORE_C",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        26,
        "First Time Home Buyer Indicator",
        "FIRST_FLAG",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        27,
        "Loan Purpose",
        "PURPOSE",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        28,
        "Property Type",
        "PROP",
        FieldType.STRING,
        "X(2)",
        2,
        0,
        True,
    ),
    (
        29,
        "Number of Units",
        "NO_UNITS",
        FieldType.INTEGER,
        "9(1)",
        None,
        0,
        True,
    ),
    (
        30,
        "Occupancy Status",
        "OCC_STAT",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        31,
        "Property State",
        "STATE",
        FieldType.STRING,
        "X(2)",
        2,
        0,
        True,
    ),
    (
        32,
        "Metropolitan Statistical Area (MSA) or Metropolitan Statistical Division Area (MSDA)",
        "MSA",
        FieldType.STRING,
        "X(5)",
        5,
        0,
        True,
    ),
    (
        33,
        "Zip Code Short",
        "ZIP",
        FieldType.STRING,
        "X(3)",
        3,
        0,
        True,
    ),
    (
        34,
        "Mortgage Insurance Percentage",
        "MI_PCT",
        FieldType.DECIMAL,
        "9(3).99",
        None,
        2,
        True,
    ),
    (
        35,
        "Amortization Type",
        "PRODUCT",
        FieldType.STRING,
        "X(3)",
        3,
        0,
        True,
    ),
    (
        36,
        "Prepayment Penalty Indicator",
        "PPMT_FLG",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        37,
        "Interest Only Loan Indicator",
        "IO",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        38,
        "Interest Only First Principal And Interest Payment Date",
        "FIRST_PAY_IO",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        39,
        "Months to Amortization",
        "MNTHS_TO_AMTZ_IO",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        40,
        "Current Loan Delinquency Status",
        "DLQ_STATUS",
        FieldType.STRING,
        "X(2)",
        2,
        0,
        True,
    ),
    (
        41,
        "Loan Payment History",
        "PMT_HISTORY",
        FieldType.STRING,
        "X(48)",
        48,
        0,
        True,
    ),
    (
        42,
        "Modification Flag",
        "MOD_FLAG",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        43,
        "Mortgage Insurance Cancellation Indicator",
        "MI_CANCEL_FLAG",
        FieldType.STRING,
        "X (2)",
        2,
        0,
        False,
    ),
    (
        44,
        "Zero Balance Code",
        "ZERO_BAL_CODE",
        FieldType.STRING,
        "X(3)",
        3,
        0,
        True,
    ),
    (
        45,
        "Zero Balance Effective Date",
        "ZB_DTE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        46,
        "UPB at the Time of Removal",
        "LAST_UPB",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        47,
        "Repurchase Date",
        "RPRCH_DTE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        False,
    ),
    (
        48,
        "Scheduled Principal Current",
        "CURR_SCHD_PRNCPL",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        49,
        "Total Principal Current",
        "TOT_SCHD_PRNCPL",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        50,
        "Unscheduled Principal Current",
        "UNSCHD_PRNCPL_CURR",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        51,
        "Last Paid Installment Date",
        "LAST_PAID_INSTALLMENT_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        52,
        "Foreclosure Date",
        "FORECLOSURE_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        53,
        "Disposition Date",
        "DISPOSITION_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        True,
    ),
    (
        54,
        "Foreclosure Costs",
        "FORECLOSURE_COSTS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        55,
        "Property Preservation and Repair Costs",
        "PROPERTY_PRESERVATION_AND_REPAIR_COSTS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        56,
        "Asset Recovery Costs",
        "ASSET_RECOVERY_COSTS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        57,
        "Miscellaneous Holding Expenses and Credits",
        "MISCELLANEOUS_HOLDING_EXPENSES_AND_CREDITS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        58,
        "Associated Taxes for Holding Property",
        "ASSOCIATED_TAXES_FOR_HOLDING_PROPERTY",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        59,
        "Net Sales Proceeds",
        "NET_SALES_PROCEEDS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        60,
        "Credit Enhancement Proceeds",
        "CREDIT_ENHANCEMENT_PROCEEDS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        61,
        "Repurchase Make Whole Proceeds",
        "REPURCHASES_MAKE_WHOLE_PROCEEDS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        62,
        "Other Foreclosure Proceeds",
        "OTHER_FORECLOSURE_PROCEEDS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        63,
        "Modification-Related Non-Interest Bearing UPB",
        "NON_INTEREST_BEARING_UPB",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        64,
        "Principal Forgiveness Amount",
        "PRINCIPAL_FORGIVENESS_AMOUNT",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        65,
        "Original List Start Date",
        "ORIGINAL_LIST_START_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        False,
    ),
    (
        66,
        "Original List Price",
        "ORIGINAL_LIST_PRICE",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        67,
        "Current List Start Date",
        "CURRENT_LIST_START_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        False,
    ),
    (
        68,
        "Current List Price",
        "CURRENT_LIST_PRICE",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        69,
        "Borrower Credit Score At Issuance",
        "ISSUE_SCOREB",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        False,
    ),
    (
        70,
        "Co-Borrower Credit Score At Issuance",
        "ISSUE_SCOREC",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        False,
    ),
    (
        71,
        "Borrower Credit Score Current",
        "CURR_SCOREB",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        False,
    ),
    (
        72,
        "Co-Borrower Credit Score Current",
        "CURR_SCOREC",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        False,
    ),
    (
        73,
        "Mortgage Insurance Type",
        "MI_TYPE",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        74,
        "Servicing Activity Indicator",
        "SERV_IND",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        75,
        "Current Period Modification Loss Amount",
        "CURRENT_PERIOD_MODIFICATION_LOSS_AMOUNT",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        76,
        "Cumulative Modification Loss Amount",
        "CUMULATIVE_MODIFICATION_LOSS_AMOUNT",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        77,
        "Current Period Credit Event Net Gain or Loss",
        "CURRENT_PERIOD_CREDIT_EVENT_NET_GAIN_OR_LOSS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        78,
        "Cumulative Credit Event Net Gain or Loss",
        "CUMULATIVE_CREDIT_EVENT_NET_GAIN_OR_LOSS",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        79,
        "Special Eligibility Program",
        "HOMEREADY_PROGRAM_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        80,
        "Foreclosure Principal Write-off Amount",
        "FORECLOSURE_PRINCIPAL_WRITE_OFF_AMOUNT",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        81,
        "Relocation Mortgage Indicator",
        "RELOCATION_MORTGAGE_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        82,
        "Zero Balance Code Change Date",
        "ZERO_BALANCE_CODE_CHANGE_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        False,
    ),
    (
        83,
        "Loan Holdback Indicator",
        "LOAN_HOLDBACK_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        False,
    ),
    (
        84,
        "Loan Holdback Effective Date",
        "LOAN_HOLDBACK_EFFECTIVE_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        False,
    ),
    (
        85,
        "Delinquent Accrued Interest",
        "DELINQUENT_ACCRUED_INTEREST",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        86,
        "Property Valuation Method",
        "PROPERTY_INSPECTION_WAIVER_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        87,
        "High Balance Loan Indicator",
        "HIGH_BALANCE_LOAN_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        88,
        "ARM Initial Fixed-Rate Period <= 5 YR Indicator",
        "ARM_5_YR_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        False,
    ),
    (
        89,
        "ARM Product Type",
        "ARM_PRODUCT_TYPE",
        FieldType.STRING,
        "X(100)",
        100,
        0,
        False,
    ),
    (
        90,
        "Initial Fixed-Rate Period",
        "MONTHS_UNTIL_FIRST_PAYMENT_RESET",
        FieldType.INTEGER,
        "9(4)",
        None,
        0,
        False,
    ),
    (
        91,
        "Interest Rate Adjustment Frequency",
        "MONTHS_BETWEEN_SUBSEQUENT_PAYMENT_RESET",
        FieldType.INTEGER,
        "9(4)",
        None,
        0,
        False,
    ),
    (
        92,
        "Next Interest Rate Adjustment Date",
        "INTEREST_RATE_CHANGE_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        False,
    ),
    (
        93,
        "Next Payment Change Date",
        "PAYMENT_CHANGE_DATE",
        FieldType.MONTH,
        "MMYYYY",
        None,
        0,
        False,
    ),
    (
        94,
        "Index",
        "ARM_INDEX",
        FieldType.STRING,
        "X(100)",
        100,
        0,
        False,
    ),
    (
        95,
        "ARM Cap Structure",
        "ARM_CAP_STRUCTURE",
        FieldType.STRING,
        "X(10)",
        10,
        0,
        False,
    ),
    (
        96,
        "Initial Interest Rate Cap Up Percent",
        "INITIAL_INTEREST_RATE_CAP",
        FieldType.DECIMAL,
        "9(2).9999",
        None,
        4,
        False,
    ),
    (
        97,
        "Periodic Interest Rate Cap Up Percent",
        "PERIODIC_INTEREST_RATE_CAP",
        FieldType.DECIMAL,
        "9(2).9999",
        None,
        4,
        False,
    ),
    (
        98,
        "Lifetime Interest Rate Cap Up Percent",
        "LIFETIME_INTEREST_RATE_CAP",
        FieldType.DECIMAL,
        "9(2).9999",
        None,
        4,
        False,
    ),
    (
        99,
        "Mortgage Margin",
        "MARGIN",
        FieldType.DECIMAL,
        "9(2).9999",
        None,
        4,
        False,
    ),
    (
        100,
        "ARM Balloon Indicator",
        "BALLOON_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        False,
    ),
    (
        101,
        "ARM Plan Number",
        "PLAN_NUMBER",
        FieldType.INTEGER,
        "9(4)",
        None,
        0,
        False,
    ),
    (
        102,
        "Borrower Assistance Plan",
        "FORBEARANCE_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        103,
        "High Loan to Value (HLTV) Refinance Option Indicator",
        "HIGH_LOAN_TO_VALUE_HLTV_REFINANCE_OPTION_INDICATOR",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        104,
        "Deal Name",
        "DEAL_NAME",
        FieldType.STRING,
        "X(200)",
        200,
        0,
        False,
    ),
    (
        105,
        "Repurchase Make Whole Proceeds Flag",
        "RE_PROCS_FLAG",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        106,
        "Alternative Delinquency Resolution",
        "ADR_TYPE",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        107,
        "Alternative Delinquency Resolution Count",
        "ADR_COUNT",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        108,
        "Total Deferral Amount",
        "ADR_UPB",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        True,
    ),
    (
        109,
        "Payment Deferral Modification Event Indicator",
        "PAYMENT_DEFERRAL_MOD_EVENT_FLAG",
        FieldType.STRING,
        "X(1)",
        1,
        0,
        True,
    ),
    (
        110,
        "Interest Bearing UPB",
        "INTEREST_BEARING_UPB",
        FieldType.DECIMAL,
        "9(10).99",
        None,
        2,
        False,
    ),
    (
        111,
        "Origination Classic FICO",
        "ORIG_CLASSIC_FICO",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        112,
        "Issuance Classic FICO",
        "ISSUANCE_CLASSIC_FICO",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
    (
        113,
        "Current Classic FICO",
        "CURRENT_CLASSIC_FICO",
        FieldType.INTEGER,
        "9(3)",
        None,
        0,
        True,
    ),
)
FANNIE_MAE_FIELDS: Final[tuple[FieldDefinition, ...]] = tuple(
    FieldDefinition(*row) for row in _SCHEMA_ROWS
)
FIELD_BY_COLUMN: Final[Mapping[str, FieldDefinition]] = MappingProxyType(
    {field.column_name: field for field in FANNIE_MAE_FIELDS}
)


def fields_for_count(field_count: int = SAMPLE_FILE_FIELD_COUNT) -> tuple[FieldDefinition, ...]:
    """Return the positional fields for a supported raw-file width."""
    if field_count not in SUPPORTED_FIELD_COUNTS:
        raise SchemaValidationError(
            f"unsupported field count {field_count}; expected one of {SUPPORTED_FIELD_COUNTS}"
        )
    return FANNIE_MAE_FIELDS[:field_count]


def field_names(field_count: int = SAMPLE_FILE_FIELD_COUNT) -> tuple[str, ...]:
    """Return stable column names in raw file order."""
    return tuple(field.column_name for field in fields_for_count(field_count))


def split_pipe_row(line: str, field_count: int = SAMPLE_FILE_FIELD_COUNT) -> tuple[str, ...]:
    """Split and validate one raw pipe-delimited record."""
    values = tuple(line.rstrip("\r\n").split(PIPE_DELIMITER))
    validate_raw_values(values, field_count=field_count)
    return values


def record_to_values(
    record: Mapping[str, str], field_count: int = SAMPLE_FILE_FIELD_COUNT
) -> tuple[str, ...]:
    """Convert a named record to positional values and validate it."""
    names = field_names(field_count)
    names_set = set(names)
    extra = sorted(set(record) - names_set)
    missing = [name for name in names if name not in record]
    if missing or extra:
        raise SchemaValidationError(
            f"record keys do not match schema; missing={missing}, extra={extra}"
        )
    values = tuple(record[name] for name in names)
    validate_raw_values(values, field_count=field_count)
    return values


def validate_record(record: Mapping[str, str], field_count: int = SAMPLE_FILE_FIELD_COUNT) -> None:
    """Validate a named raw record against the positional field contract."""
    record_to_values(record, field_count=field_count)


def validate_raw_values(values: Sequence[str], field_count: int = SAMPLE_FILE_FIELD_COUNT) -> None:
    """Validate positional raw values against length and field-level types."""
    fields = fields_for_count(field_count)
    if len(values) != len(fields):
        raise SchemaValidationError(f"expected {len(fields)} fields, got {len(values)}")
    for field, value in zip(fields, values, strict=True):
        _validate_field_value(field, value)


def string_length_exceedances(
    values: Sequence[str], field_count: int = SAMPLE_FILE_FIELD_COUNT
) -> tuple[tuple[str, int, int], ...]:
    """Report text fields longer than the glossary declares.

    Returned as (column_name, declared_max, observed_length) for the data
    quality suite to gate on. These are observations, not parse failures: see
    ADR-009 for why an over-long name does not invalidate a record.
    """
    exceedances: list[tuple[str, int, int]] = []
    for field, value in zip(fields_for_count(field_count), values, strict=True):
        if field.field_type is not FieldType.STRING or field.max_length is None:
            continue
        if value and len(value) > field.max_length:
            exceedances.append((field.column_name, field.max_length, len(value)))
    return tuple(exceedances)


def _validate_field_value(field: FieldDefinition, value: str) -> None:
    if value == "":
        return
    # Length is fatal only where exceeding it means the row is misaligned. A
    # 40-character FICO is corruption; a 68-character seller name is Fannie
    # Mae's published length being out of date. ADR-009.
    if (
        field.max_length is not None
        and field.field_type is not FieldType.STRING
        and len(value) > field.max_length
    ):
        raise SchemaValidationError(
            f"{field.column_name} exceeds max length {field.max_length}: {value!r}"
        )
    if field.field_type is FieldType.INTEGER:
        _validate_integer(field, value)
    elif field.field_type is FieldType.DECIMAL:
        _validate_decimal(field, value)
    elif field.field_type is FieldType.MONTH:
        _validate_month(field, value)


def _validate_integer(field: FieldDefinition, value: str) -> None:
    try:
        int(value)
    except ValueError as exc:
        raise SchemaValidationError(f"{field.column_name} must be an integer: {value!r}") from exc


def _validate_decimal(field: FieldDefinition, value: str) -> None:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise SchemaValidationError(f"{field.column_name} must be decimal: {value!r}") from exc
    if not parsed.is_finite():
        raise SchemaValidationError(f"{field.column_name} must be finite decimal: {value!r}")
    exponent = parsed.as_tuple().exponent
    if not isinstance(exponent, int):
        raise SchemaValidationError(f"{field.column_name} must be finite decimal: {value!r}")
    places = abs(exponent) if exponent < 0 else 0
    if places > field.scale:
        raise SchemaValidationError(
            f"{field.column_name} has {places} decimal places; max is {field.scale}"
        )


def _validate_month(field: FieldDefinition, value: str) -> None:
    if len(value) != 6 or not value.isdigit():
        raise SchemaValidationError(f"{field.column_name} must use MMYYYY format: {value!r}")
    try:
        datetime.strptime(value, "%m%Y")
    except ValueError as exc:
        raise SchemaValidationError(f"{field.column_name} is not a valid month: {value!r}") from exc
