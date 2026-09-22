"""Tests for authenticated FRED downloads and validated cache publication."""

from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from mortgage_risk.data import fred_ingestion


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _payload() -> dict[str, object]:
    return {
        "observations": [{"date": "2015-09-01", "realtime_start": "2015-10-02", "value": "5.1"}]
    }


def test_fetch_uses_point_in_time_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_url = ""

    def fake_urlopen(url: str, *, timeout: float) -> _Response:
        nonlocal captured_url
        captured_url = url
        assert timeout == 12.0
        return _Response(json.dumps(_payload()).encode())

    monkeypatch.setattr(fred_ingestion, "urlopen", fake_urlopen)

    fred_ingestion.fetch_fred_initial_releases(
        "secret-key",
        "UNRATE",
        date(2015, 1, 1),
        date(2015, 12, 1),
        timeout_seconds=12.0,
    )

    query = parse_qs(urlparse(captured_url).query)
    assert query["api_key"] == ["secret-key"]
    assert query["output_type"] == ["4"]
    assert query["realtime_start"] == ["1776-07-04"]
    assert query["realtime_end"] == ["9999-12-31"]


def test_cache_is_written_only_after_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        fred_ingestion,
        "fetch_fred_initial_releases",
        lambda *_args, **_kwargs: _payload(),
    )

    result = fred_ingestion.cache_fred_initial_releases(
        "secret-key",
        "UNRATE",
        date(2015, 1, 1),
        date(2015, 12, 1),
        tmp_path,
    )

    assert result.observation_count == 1
    assert result.first_observation_date == date(2015, 9, 1)
    assert result.last_available_date == date(2015, 10, 2)
    assert json.loads(result.path.read_text(encoding="utf-8")) == _payload()
    assert not (tmp_path / ".UNRATE.json.tmp").exists()


def test_api_error_payload_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_url: str, *, timeout: float) -> _Response:
        assert timeout == 60.0
        return _Response(b'{"error_code": 400, "error_message": "Bad Request"}')

    monkeypatch.setattr(fred_ingestion, "urlopen", fake_urlopen)

    with pytest.raises(fred_ingestion.FredApiError, match="API error 400"):
        fred_ingestion.fetch_fred_initial_releases(
            "secret-key",
            "UNRATE",
            date(2015, 1, 1),
            date(2015, 12, 1),
        )


def test_configured_key_falls_back_to_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("FRED_API_KEY=secret-key\n", encoding="utf-8")

    assert fred_ingestion.configured_api_key(env_file) == "secret-key"
