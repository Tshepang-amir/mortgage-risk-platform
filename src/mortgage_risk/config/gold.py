"""Phase 4 Gold-panel constants and temporal split boundaries."""

from datetime import date
from typing import Final

DEFAULT_HORIZON_MONTHS: Final = 12
DEFAULT_DELINQUENCY_THRESHOLD: Final = 3
TRAIN_END: Final = date(2015, 12, 1)
VALIDATION_END: Final = date(2017, 12, 1)
OUT_OF_VINTAGE_QUARTERS: Final = frozenset({"2016Q1", "2018Q1"})
FRED_SERIES_IDS: Final = ("UNRATE", "CSUSHPINSA", "MORTGAGE30US")

# Gold columns whose value depends on observations after the row's own month,
# or which exist only to construct the label. None may ever be used as a model
# feature: EXIT_TYPE and DEFAULT_IN_12M are restatements of the answer, and
# SOURCE_OBSERVED_MONTHS encodes how long the loan survived.
#
# The leakage tests assert that the set of columns which change when future
# rows are withheld is a subset of this one, so any new column carrying
# lookahead fails the suite until it is classified here deliberately.
OUTCOME_COLUMNS: Final = frozenset(
    {
        "AT_RISK_OBSERVED_MONTHS",
        "DEFAULT_IN_12M",
        "DEFAULT_NEXT_MONTH",
        "EXIT_DATE",
        "EXIT_TYPE",
        "FIRST_CENSOR_CODE",
        "FIRST_CENSOR_DATE",
        "FIRST_D90_DATE",
        "HORIZON_END_DATE",
        "LABEL_OBSERVED_12M",
        "LAST_OBSERVED_DATE",
        "SOURCE_OBSERVED_MONTHS",
    }
)
