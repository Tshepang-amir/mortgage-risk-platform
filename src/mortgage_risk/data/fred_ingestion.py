"""Download and cache point-in-time FRED macro vintages."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from json import JSONDecodeError
from pathlib import Path
from typing import Final, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from mortgage_risk.config.gold import FRED_SERIES_IDS
from mortgage_risk.features.macro import (
    MacroObservation,
    fred_initial_release_parameters,
    parse_fred_initial_releases,
)

FRED_OBSERVATIONS_URL: Final = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_OBSERVATION_START: Final = date(2000, 1, 1)


class FredApiError(RuntimeError):
    """Raised when FRED cannot return a valid observations payload."""


@dataclass(frozen=True, slots=True)
class FredCacheResult:
    """Metadata for one validated cached FRED series."""

    series_id: str
    path: Path
    observation_count: int
    first_observation_date: date
    last_observation_date: date
    last_available_date: date


def fetch_fred_initial_releases(
    api_key: str,
    series_id: str,
    observation_start: date,
    observation_end: date,
    *,
    timeout_seconds: float = 60.0,
) -> dict[str, object]:
    """Fetch one FRED series and validate its point-in-time observations."""
    if not api_key:
        raise ValueError("FRED_API_KEY is empty")

    parameters = fred_initial_release_parameters(series_id, observation_start, observation_end)
    parameters["api_key"] = api_key
    request_url = f"{FRED_OBSERVATIONS_URL}?{urlencode(parameters)}"

    try:
        with urlopen(request_url, timeout=timeout_seconds) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise FredApiError(f"FRED request failed for {series_id}: HTTP {exc.code}") from exc
    except (URLError, TimeoutError, JSONDecodeError, OSError) as exc:
        raise FredApiError(f"FRED request failed for {series_id}") from exc

    if not isinstance(payload, dict):
        raise FredApiError(f"FRED returned a non-object payload for {series_id}")
    typed_payload = cast(dict[str, object], payload)
    if "error_code" in typed_payload:
        code = typed_payload.get("error_code")
        raise FredApiError(f"FRED returned API error {code} for {series_id}")

    parse_fred_initial_releases(series_id, typed_payload)
    return typed_payload


def cache_fred_initial_releases(
    api_key: str,
    series_id: str,
    observation_start: date,
    observation_end: date,
    output_dir: Path,
    *,
    timeout_seconds: float = 60.0,
) -> FredCacheResult:
    """Download, validate, and atomically cache one FRED response."""
    payload = fetch_fred_initial_releases(
        api_key,
        series_id,
        observation_start,
        observation_end,
        timeout_seconds=timeout_seconds,
    )
    observations = parse_fred_initial_releases(series_id, payload)
    if not observations:
        raise FredApiError(f"FRED returned no usable observations for {series_id}")

    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{series_id}.json"
    temporary = output_dir / f".{series_id}.json.tmp"
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return _cache_result(series_id, target, observations)


def download_fred_series(
    api_key: str,
    observation_start: date,
    observation_end: date,
    output_dir: Path,
    *,
    series_ids: Sequence[str] = FRED_SERIES_IDS,
    timeout_seconds: float = 60.0,
) -> tuple[FredCacheResult, ...]:
    """Download all configured macro series into the external-data cache."""
    return tuple(
        cache_fred_initial_releases(
            api_key,
            series_id,
            observation_start,
            observation_end,
            output_dir,
            timeout_seconds=timeout_seconds,
        )
        for series_id in series_ids
    )


def configured_api_key(env_file: Path = Path(".env")) -> str:
    """Read FRED_API_KEY from the process environment or a local env file."""
    process_value = os.environ.get("FRED_API_KEY", "").strip()
    if process_value:
        return process_value
    if env_file.is_file():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            name, separator, value = raw_line.partition("=")
            if separator and name.strip() == "FRED_API_KEY":
                configured = value.strip().strip('"').strip("'")
                if configured:
                    return configured
    raise FredApiError("FRED_API_KEY is not configured")


def _cache_result(
    series_id: str,
    path: Path,
    observations: Sequence[MacroObservation],
) -> FredCacheResult:
    return FredCacheResult(
        series_id=series_id,
        path=path,
        observation_count=len(observations),
        first_observation_date=min(item.observation_date for item in observations),
        last_observation_date=max(item.observation_date for item in observations),
        last_available_date=max(item.available_date for item in observations),
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Run the FRED cache ingestion command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=_parse_date, default=DEFAULT_OBSERVATION_START)
    parser.add_argument("--end", type=_parse_date, default=date.today())
    parser.add_argument("--output-dir", type=Path, default=Path("data/external"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    arguments = parser.parse_args(argv)

    results = download_fred_series(
        configured_api_key(arguments.env_file),
        arguments.start,
        arguments.end,
        arguments.output_dir,
    )
    for result in results:
        print(
            f"{result.series_id}: {result.observation_count} observations, "
            f"{result.first_observation_date} to {result.last_observation_date}, "
            f"latest release {result.last_available_date}, cached at {result.path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
