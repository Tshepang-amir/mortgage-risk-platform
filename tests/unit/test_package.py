"""Smoke tests for the installed package."""

from __future__ import annotations

import mortgage_risk


def test_version_is_exposed() -> None:
    """The package exposes a version string, so the build is not broken."""
    assert isinstance(mortgage_risk.__version__, str)
    assert mortgage_risk.__version__.count(".") == 2
