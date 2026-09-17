"""Tests for the FRED ingestion path that decides when a macro value existed.

Leakage control 3 in `tests/property/test_leakage.py` proves the join respects
`AVAILABLE_DATE`. It cannot prove those dates are right, because it builds its
own vintage frame. These tests cover the code that derives them from a FRED
response, which is where a point-in-time bug would survive that control.

The governing requirement is PROJECT.md section 3: a loan-month at date d joins
the macro value published for d, never a later revision.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mortgage_risk.features.macro import (
    MacroContractError,
    fred_initial_release_parameters,
    parse_fred_initial_releases,
)


def _payload(*observations: dict[str, str]) -> dict[str, Any]:
    return {"observations": list(observations)}


# ---------------------------------------------------------------------------
# Request parameters
# ---------------------------------------------------------------------------


def test_parameters_request_initial_releases_only() -> None:
    """`output_type=4` is what makes FRED return unrevised first prints.

    Any other output type returns the series as later revised, which would put
    numbers into a loan-month that nobody could have known at the time. This is
    asserted explicitly because the failure is silent: the request still
    succeeds and the values still look plausible.
    """
    parameters = fred_initial_release_parameters("UNRATE", date(2015, 1, 1), date(2018, 12, 1))

    assert parameters["output_type"] == "4"
    assert parameters["series_id"] == "UNRATE"
    assert parameters["observation_start"] == "2015-01-01"
    assert parameters["observation_end"] == "2018-12-01"


def test_parameters_span_the_whole_realtime_window() -> None:
    """The real-time window must not clip the vintage history.

    Narrowing it would drop early releases and leave only later revisions,
    which is the same failure as requesting the wrong output type.
    """
    parameters = fred_initial_release_parameters("CSUSHPINSA", date(2005, 1, 1), date(2005, 3, 1))

    assert parameters["realtime_start"] == "1776-07-04"
    assert parameters["realtime_end"] == "9999-12-31"


def test_parameters_reject_an_unsupported_series() -> None:
    with pytest.raises(ValueError, match="unsupported FRED series"):
        fred_initial_release_parameters("GDP", date(2015, 1, 1), date(2015, 2, 1))


def test_parameters_reject_a_reversed_window() -> None:
    with pytest.raises(ValueError, match="must not be after"):
        fred_initial_release_parameters("UNRATE", date(2018, 1, 1), date(2015, 1, 1))


def test_parameters_accept_a_single_month_window() -> None:
    """Start equal to end is a legitimate one-month request, not a reversal."""
    parameters = fred_initial_release_parameters("UNRATE", date(2015, 6, 1), date(2015, 6, 1))

    assert parameters["observation_start"] == parameters["observation_end"] == "2015-06-01"


# ---------------------------------------------------------------------------
# Response parsing: where AVAILABLE_DATE comes from
# ---------------------------------------------------------------------------


def test_available_date_is_the_release_date_not_the_observation_month() -> None:
    """The single property the whole macro-lag guarantee rests on.

    US unemployment for September 2015 was first published in October 2015. If
    `available_date` were taken from `date` rather than `realtime_start`, the
    September figure would appear knowable during September, and every
    downstream point-in-time join would silently leak.
    """
    payload = _payload(
        {"date": "2015-09-01", "realtime_start": "2015-10-02", "value": "5.1"},
    )

    (observation,) = parse_fred_initial_releases("UNRATE", payload)

    assert observation.observation_date == date(2015, 9, 1)
    assert observation.available_date == date(2015, 10, 2)
    assert observation.available_date > observation.observation_date


def test_same_day_release_is_preserved_rather_than_forced_to_lag() -> None:
    """Not every series lags. The weekly mortgage rate prints the same day.

    The rule is that availability is taken from the release date, not that a
    lag is imposed, so a same-day release must survive parsing unchanged.
    """
    payload = _payload(
        {"date": "2015-09-03", "realtime_start": "2015-09-03", "value": "3.89"},
    )

    (observation,) = parse_fred_initial_releases("MORTGAGE30US", payload)

    assert observation.available_date == observation.observation_date == date(2015, 9, 3)


def test_value_keeps_decimal_precision() -> None:
    """Rates are parsed as Decimal, so no binary-float drift enters a money path."""
    payload = _payload(
        {"date": "2015-09-01", "realtime_start": "2015-10-02", "value": "175.123456"},
    )

    (observation,) = parse_fred_initial_releases("CSUSHPINSA", payload)

    assert observation.value == Decimal("175.123456")
    assert isinstance(observation.value, Decimal)


def test_series_id_is_carried_through_from_the_request() -> None:
    """FRED's payload does not name the series, so the caller's label must stick."""
    payload = _payload({"date": "2015-09-01", "realtime_start": "2015-10-02", "value": "5.1"})

    (observation,) = parse_fred_initial_releases("UNRATE", payload)

    assert observation.series_id == "UNRATE"


def test_observations_are_returned_in_payload_order() -> None:
    payload = _payload(
        {"date": "2015-07-01", "realtime_start": "2015-08-07", "value": "5.3"},
        {"date": "2015-08-01", "realtime_start": "2015-09-04", "value": "5.1"},
        {"date": "2015-09-01", "realtime_start": "2015-10-02", "value": "5.0"},
    )

    observations = parse_fred_initial_releases("UNRATE", payload)

    assert [o.observation_date for o in observations] == [
        date(2015, 7, 1),
        date(2015, 8, 1),
        date(2015, 9, 1),
    ]


# ---------------------------------------------------------------------------
# Response parsing: malformed input must fail loudly
# ---------------------------------------------------------------------------


def test_missing_value_marker_is_skipped_not_coerced() -> None:
    """FRED writes "." for a value it has no figure for.

    Skipping is correct; coercing it to zero would put a fabricated macro
    reading into the panel. Section 8 requires failing loud over silently
    coercing, and here the loud outcome is a coverage error later rather than
    a plausible wrong number now.
    """
    payload = _payload(
        {"date": "2015-08-01", "realtime_start": "2015-09-04", "value": "."},
        {"date": "2015-09-01", "realtime_start": "2015-10-02", "value": "5.1"},
    )

    observations = parse_fred_initial_releases("UNRATE", payload)

    assert len(observations) == 1
    assert observations[0].observation_date == date(2015, 9, 1)


def test_payload_without_an_observations_list_is_rejected() -> None:
    with pytest.raises(MacroContractError, match="no observations list"):
        parse_fred_initial_releases("UNRATE", {"error_code": 400})


def test_observation_that_is_not_an_object_is_rejected() -> None:
    with pytest.raises(MacroContractError, match="not an object"):
        parse_fred_initial_releases("UNRATE", {"observations": ["2015-09-01"]})


def test_missing_realtime_start_is_rejected() -> None:
    """Without a release date there is no basis for availability, so refuse it."""
    with pytest.raises(MacroContractError, match="invalid FRED observation"):
        parse_fred_initial_releases("UNRATE", _payload({"date": "2015-09-01", "value": "5.1"}))


def test_malformed_date_is_rejected() -> None:
    with pytest.raises(MacroContractError, match="invalid FRED observation"):
        parse_fred_initial_releases(
            "UNRATE",
            _payload({"date": "September 2015", "realtime_start": "2015-10-02", "value": "5.1"}),
        )


def test_non_numeric_value_is_rejected() -> None:
    with pytest.raises(MacroContractError, match="invalid FRED observation"):
        parse_fred_initial_releases(
            "UNRATE",
            _payload({"date": "2015-09-01", "realtime_start": "2015-10-02", "value": "n/a"}),
        )


def test_empty_observation_list_parses_to_nothing() -> None:
    """An empty response is not malformed; it produces no vintages."""
    assert parse_fred_initial_releases("UNRATE", _payload()) == ()
