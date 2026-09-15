"""Tests for deterministic synthetic panel generation."""

from __future__ import annotations

from pathlib import Path

from mortgage_risk.data.schema import SAMPLE_FILE_FIELD_COUNT, split_pipe_row
from mortgage_risk.data.synthetic import (
    SELECTED_ACQUISITION_QUARTERS,
    SyntheticPanel,
    generate_synthetic_panel,
    iter_pipe_rows,
    write_synthetic_panel,
)


def test_synthetic_panel_matches_raw_schema(synthetic_panel: SyntheticPanel) -> None:
    """Every generated row is the exact Phase 1 raw file width."""
    rows = list(iter_pipe_rows(synthetic_panel))
    assert rows
    assert {len(row) for row in rows} == {SAMPLE_FILE_FIELD_COUNT}


def test_synthetic_panel_is_deterministic() -> None:
    """A stable seed gives stable fixtures for downstream tests."""
    first = generate_synthetic_panel(loan_count=8, max_months=18, seed=7)
    second = generate_synthetic_panel(loan_count=8, max_months=18, seed=7)
    assert first.rows == second.rows
    assert first.outcomes == second.outcomes


def test_synthetic_panel_has_known_ground_truth_events() -> None:
    """The generator creates defaults, prepayments and censored observations."""
    panel = generate_synthetic_panel(loan_count=36, max_months=36, seed=20260915)
    event_types = {outcome.event_type for outcome in panel.outcomes.values()}
    assert event_types == {"default", "prepaid", "censored"}
    default_ids = {
        outcome.loan_id for outcome in panel.outcomes.values() if outcome.event_type == "default"
    }
    default_rows = [row for row in panel.rows if row["LOAN_ID"] in default_ids]
    assert any(row["DLQ_STATUS"] == "3" for row in default_rows)


def test_synthetic_panel_spans_selected_quarters() -> None:
    """The six scoped acquisition quarters are represented in fixture metadata."""
    panel = generate_synthetic_panel(loan_count=12, max_months=12, seed=11)
    assert {outcome.acquisition_quarter for outcome in panel.outcomes.values()} == set(
        SELECTED_ACQUISITION_QUARTERS
    )


def test_synthetic_panel_writes_headerless_pipe_file(tmp_path: Path) -> None:
    """Fixture files can be materialised for ingestion tests without real data."""
    panel = generate_synthetic_panel(loan_count=3, max_months=12, seed=5)
    output_path = tmp_path / "synthetic.csv"
    write_synthetic_panel(output_path, panel)
    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert lines
    assert not lines[0].startswith("POOL_ID")
    assert len(split_pipe_row(lines[0])) == SAMPLE_FILE_FIELD_COUNT
