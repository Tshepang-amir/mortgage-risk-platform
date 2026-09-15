"""Shared test fixtures backed by deterministic synthetic mortgage data."""

from __future__ import annotations

import pytest

from mortgage_risk.data.synthetic import SyntheticPanel, generate_synthetic_panel


@pytest.fixture
def synthetic_panel() -> SyntheticPanel:
    """Small panel that downstream tests can reuse without real Fannie Mae files."""
    return generate_synthetic_panel(loan_count=12, max_months=24, seed=20260915)
