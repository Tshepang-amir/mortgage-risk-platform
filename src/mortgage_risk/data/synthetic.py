"""Deterministic synthetic Fannie Mae-style loan-month panel generation."""

from __future__ import annotations

import csv
import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Final, Literal, TypeAlias

from mortgage_risk.data.schema import (
    PIPE_DELIMITER,
    SAMPLE_FILE_FIELD_COUNT,
    field_names,
    record_to_values,
    validate_record,
)

SELECTED_ACQUISITION_QUARTERS: Final = (
    "2005Q1",
    "2005Q3",
    "2007Q1",
    "2012Q1",
    "2016Q1",
    "2018Q1",
)
OutcomeType: TypeAlias = Literal["default", "prepaid", "censored"]


@dataclass(frozen=True, slots=True)
class SyntheticLoanOutcome:
    """Ground truth for one synthetic loan, kept outside the raw data schema."""

    loan_id: str
    acquisition_quarter: str
    event_type: OutcomeType
    event_month: int | None
    risk_score: float


@dataclass(frozen=True, slots=True)
class SyntheticPanel:
    """Generated raw rows plus their known loan-level outcomes."""

    rows: tuple[dict[str, str], ...]
    outcomes: Mapping[str, SyntheticLoanOutcome]
    field_count: int = SAMPLE_FILE_FIELD_COUNT


def generate_synthetic_panel(
    loan_count: int = 36,
    max_months: int = 36,
    seed: int = 20260915,
    field_count: int = SAMPLE_FILE_FIELD_COUNT,
) -> SyntheticPanel:
    """Generate a deterministic loan-month panel with known censoring outcomes."""
    if loan_count <= 0:
        raise ValueError("loan_count must be positive")
    if max_months < 12:
        raise ValueError("max_months must be at least 12")

    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    outcomes: dict[str, SyntheticLoanOutcome] = {}

    for loan_index in range(loan_count):
        quarter = SELECTED_ACQUISITION_QUARTERS[loan_index % len(SELECTED_ACQUISITION_QUARTERS)]
        loan = _sample_loan(rng, loan_index, quarter)
        outcome = _sample_outcome(rng, loan)
        outcomes[loan.loan_id] = outcome

        months_observed = outcome.event_month if outcome.event_month is not None else max_months
        months_observed = min(months_observed, max_months)
        for month_index in range(months_observed):
            row = _loan_month_record(loan, outcome, month_index, field_count)
            validate_record(row, field_count=field_count)
            rows.append(row)

    return SyntheticPanel(rows=tuple(rows), outcomes=outcomes, field_count=field_count)


def write_synthetic_panel(path: Path, panel: SyntheticPanel) -> None:
    """Write a headerless pipe-delimited synthetic raw file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=PIPE_DELIMITER, lineterminator="\n")
        for row in panel.rows:
            writer.writerow(record_to_values(row, field_count=panel.field_count))


def iter_pipe_rows(panel: SyntheticPanel) -> Iterable[tuple[str, ...]]:
    """Yield positional raw rows for tests or small fixture writers."""
    for row in panel.rows:
        yield record_to_values(row, field_count=panel.field_count)


@dataclass(frozen=True, slots=True)
class _SyntheticLoan:
    loan_id: str
    quarter: str
    acquisition_month: date
    origination_month: date
    first_payment_month: date
    maturity_month: date
    original_upb: Decimal
    original_rate: Decimal
    original_term: int
    ltv: int
    cltv: int
    dti: int
    borrower_score: int
    coborrower_score: int | None
    borrowers: int
    channel: str
    purpose: str
    property_type: str
    occupancy: str
    state: str
    msa: str
    zip3: str
    mi_pct: Decimal
    risk_score: float


def _sample_loan(rng: random.Random, loan_index: int, quarter: str) -> _SyntheticLoan:
    acquisition_month = _quarter_start(quarter)
    origination_month = _add_months(acquisition_month, -1 * rng.randint(1, 3))
    first_payment_month = _add_months(origination_month, 2)
    original_term = rng.choice((180, 240, 360))
    maturity_month = _add_months(first_payment_month, original_term - 1)
    ltv = rng.randint(55, 97)
    cltv = min(105, ltv + rng.choice((0, 0, 5, 10)))
    dti = rng.randint(18, 50)
    borrower_score = rng.randint(610, 810)
    borrowers = rng.choice((1, 1, 2, 2))
    coborrower_score = rng.randint(620, 820) if borrowers == 2 else None
    original_upb = _money(rng.randrange(80_000, 650_000, 5_000))
    original_rate = _rate(rng.uniform(2.75, 7.25))
    crisis = 0.35 if quarter in {"2005Q1", "2005Q3", "2007Q1"} else 0.0
    risk_score = (
        ((ltv - 55) / 42 * 0.35)
        + ((dti - 18) / 32 * 0.25)
        + ((810 - borrower_score) / 200 * 0.30)
        + crisis
    )
    return _SyntheticLoan(
        loan_id=f"SYN{loan_index + 1:09d}",
        quarter=quarter,
        acquisition_month=acquisition_month,
        origination_month=origination_month,
        first_payment_month=first_payment_month,
        maturity_month=maturity_month,
        original_upb=original_upb,
        original_rate=original_rate,
        original_term=original_term,
        ltv=ltv,
        cltv=cltv,
        dti=dti,
        borrower_score=borrower_score,
        coborrower_score=coborrower_score,
        borrowers=borrowers,
        channel=rng.choice(("R", "C", "B")),
        purpose=rng.choice(("P", "R", "C")),
        property_type=rng.choice(("SF", "CO", "PU")),
        occupancy=rng.choice(("P", "P", "P", "S", "I")),
        state=rng.choice(("CA", "FL", "GA", "IL", "NY", "OH", "TX", "WA")),
        msa=rng.choice(("00000", "12060", "16980", "19100", "31080", "35620")),
        zip3=f"{rng.randint(100, 999)}",
        mi_pct=Decimal("30.00") if ltv > 80 else Decimal("0.00"),
        risk_score=risk_score,
    )


def _sample_outcome(rng: random.Random, loan: _SyntheticLoan) -> SyntheticLoanOutcome:
    default_threshold = 0.62
    prepay_threshold = 0.26
    draw = rng.random()
    if loan.risk_score > default_threshold and draw < 0.75:
        event_type: OutcomeType = "default"
        event_month = rng.randint(13, 32)
    elif loan.risk_score < prepay_threshold and draw < 0.70:
        event_type = "prepaid"
        event_month = rng.randint(18, 34)
    else:
        event_type = "censored"
        event_month = None
    return SyntheticLoanOutcome(
        loan_id=loan.loan_id,
        acquisition_quarter=loan.quarter,
        event_type=event_type,
        event_month=event_month,
        risk_score=round(loan.risk_score, 6),
    )


def _loan_month_record(
    loan: _SyntheticLoan,
    outcome: SyntheticLoanOutcome,
    month_index: int,
    field_count: int,
) -> dict[str, str]:
    record = dict.fromkeys(field_names(field_count), "")
    reporting_month = _add_months(loan.acquisition_month, month_index)
    scheduled_principal = loan.original_upb / Decimal(loan.original_term)
    current_upb = max(Decimal("0.00"), loan.original_upb - (scheduled_principal * month_index))
    total_principal = scheduled_principal if month_index > 0 else Decimal("0.00")
    is_event_month = outcome.event_month == month_index + 1

    delinquency = "00"
    zero_balance_code = ""
    zero_balance_date = ""
    removal_upb = ""
    last_paid_installment = _format_month(reporting_month)
    if outcome.event_type == "default" and outcome.event_month is not None:
        months_to_default = outcome.event_month - month_index - 1
        if months_to_default <= 0:
            delinquency = "03"
            last_paid_installment = _format_month(_add_months(reporting_month, -3))
        elif months_to_default == 1:
            delinquency = "02"
        elif months_to_default == 2:
            delinquency = "01"
    if is_event_month and outcome.event_type == "prepaid":
        zero_balance_code = "01"
        zero_balance_date = _format_month(reporting_month)
        removal_upb = _format_money(current_upb)
        current_upb = Decimal("0.00")
    elif is_event_month and outcome.event_type == "default":
        removal_upb = _format_money(current_upb)

    record.update(
        {
            "LOAN_ID": loan.loan_id,
            "ACT_PERIOD": _format_month(reporting_month),
            "CHANNEL": loan.channel,
            "SELLER": "Synthetic Seller",
            "SERVICER": "Synthetic Servicer",
            "ORIG_RATE": _format_rate(loan.original_rate),
            "CURR_RATE": _format_rate(loan.original_rate),
            "ORIG_UPB": _format_money(loan.original_upb),
            "CURRENT_UPB": _format_money(current_upb),
            "ORIG_TERM": str(loan.original_term),
            "ORIG_DATE": _format_month(loan.origination_month),
            "FIRST_PAY": _format_month(loan.first_payment_month),
            "LOAN_AGE": str(month_index),
            "REM_MONTHS": str(max(0, loan.original_term - month_index)),
            "ADJ_REM_MONTHS": str(max(0, loan.original_term - month_index)),
            "MATR_DT": _format_month(loan.maturity_month),
            "OLTV": str(loan.ltv),
            "OCLTV": str(loan.cltv),
            "NUM_BO": str(loan.borrowers),
            "DTI": str(loan.dti),
            "CSCORE_B": str(loan.borrower_score),
            "CSCORE_C": "" if loan.coborrower_score is None else str(loan.coborrower_score),
            "FIRST_FLAG": "Y" if loan.purpose == "P" and loan.borrower_score < 700 else "N",
            "PURPOSE": loan.purpose,
            "PROP": loan.property_type,
            "NO_UNITS": "1",
            "OCC_STAT": loan.occupancy,
            "STATE": loan.state,
            "MSA": loan.msa,
            "ZIP": loan.zip3,
            "MI_PCT": _format_money(loan.mi_pct),
            "PRODUCT": "FRM",
            "PPMT_FLG": "N",
            "IO": "N",
            "DLQ_STATUS": delinquency,
            "PMT_HISTORY": _payment_history(month_index, delinquency),
            "MOD_FLAG": "N",
            "ZERO_BAL_CODE": zero_balance_code,
            "ZB_DTE": zero_balance_date,
            "LAST_UPB": removal_upb,
            "TOT_SCHD_PRNCPL": _format_money(total_principal),
            "LAST_PAID_INSTALLMENT_DATE": last_paid_installment,
            "MI_TYPE": "1" if loan.mi_pct > 0 else "",
            "SERV_IND": "N",
            "HOMEREADY_PROGRAM_INDICATOR": "7",
            "FORECLOSURE_PRINCIPAL_WRITE_OFF_AMOUNT": "",
            "RELOCATION_MORTGAGE_INDICATOR": "N",
            "PROPERTY_INSPECTION_WAIVER_INDICATOR": "",
            "HIGH_BALANCE_LOAN_INDICATOR": "N",
            "FORBEARANCE_INDICATOR": "N",
            "HIGH_LOAN_TO_VALUE_HLTV_REFINANCE_OPTION_INDICATOR": "N",
            "RE_PROCS_FLAG": "N",
            "ADR_TYPE": "7",
            "ADR_COUNT": "0",
            "ADR_UPB": "0.00",
        }
    )
    if field_count >= 110:
        record["PAYMENT_DEFERRAL_MOD_EVENT_FLAG"] = "7"
        record["INTEREST_BEARING_UPB"] = _format_money(current_upb)
    return record


def _quarter_start(quarter: str) -> date:
    year = int(quarter[:4])
    quarter_index = int(quarter[-1])
    return date(year, ((quarter_index - 1) * 3) + 1, 1)


def _add_months(value: date, months: int) -> date:
    zero_based_month = value.month - 1 + months
    return date(value.year + zero_based_month // 12, zero_based_month % 12 + 1, 1)


def _format_month(value: date) -> str:
    return f"{value.month:02d}{value.year:04d}"


def _format_money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _format_rate(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _money(value: int) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _rate(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _payment_history(month_index: int, delinquency: str) -> str:
    history = ["0"] * min(24, month_index + 1)
    history[-1] = delinquency
    return "".join(history)
