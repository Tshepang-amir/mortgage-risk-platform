"""Assert the repository matches PROJECT.md section 9 and stays hygienic.

This is the structure assertion that `make check` runs. It exists so that
layout drift and committed build artefacts fail CI instead of being caught by
eye during review, which PROJECT.md section 10 makes a standing obligation.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Files section 9 requires to exist at this phase. Documents owned by later
# phases (docs/architecture.md, governance/*) are asserted by those phases.
REQUIRED_FILES = [
    "PROJECT.md",
    "PROGRESS.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "Makefile",
    "docker-compose.yml",
    ".pre-commit-config.yaml",
    ".secrets.baseline",
    ".env.example",
    ".gitignore",
    "data/README.md",
    "notebooks/README.md",
    "docs/decisions/adr-template.md",
    ".github/workflows/ci.yml",
]

# The src/mortgage_risk subpackages named in section 9.
REQUIRED_SUBPACKAGES = [
    "config",
    "data",
    "features",
    "models",
    "validation",
    "ifrs9",
    "explain",
    "fairness",
    "serve",
    "monitoring",
    "common",
]

# Section 10 point 1: these must never be tracked by git.
BANNED_PATH_FRAGMENTS = [
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".ipynb_checkpoints",
    "spark-warehouse",
    "metastore_db",
    "derby.log",
    "mlruns/",
    ".coverage",
    "htmlcov/",
    ".egg-info",
]

BANNED_SUFFIXES = [".pyc", ".parquet", ".delta", ".DS_Store"]

# Section 10 point 2: no data in git beyond the README and small fixtures.
FIXTURE_SIZE_LIMIT_BYTES = 100 * 1024


def _tracked_files() -> list[str]:
    """Return git-tracked paths.

    Skips locally when git is genuinely absent, for example inside the slim
    dev container. Under CI it fails instead, so the hygiene assertions can
    never pass by silently not running where they are the actual gate.
    """
    git = shutil.which("git")
    if git is None:
        message = "git is not available, so repository hygiene cannot be checked"
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    try:
        result = subprocess.run(
            [git, "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
        pytest.fail(f"git ls-files failed: {exc}")
    return [line for line in result.stdout.splitlines() if line]


@pytest.mark.parametrize("relative_path", REQUIRED_FILES)
def test_required_file_exists(relative_path: str) -> None:
    """Every file PROJECT.md section 9 requires at this phase is present."""
    assert (REPO_ROOT / relative_path).is_file(), (
        f"{relative_path} is required by PROJECT.md section 9 but is missing"
    )


@pytest.mark.parametrize("subpackage", REQUIRED_SUBPACKAGES)
def test_subpackage_is_importable(subpackage: str) -> None:
    """Each section 9 subpackage exists and imports cleanly.

    This also discharges section 10 point 4: these modules are imported by a
    test, so none of them is an orphan.
    """
    module = importlib.import_module(f"mortgage_risk.{subpackage}")
    assert module.__doc__, f"mortgage_risk.{subpackage} has no docstring"


def test_no_build_artefacts_are_tracked() -> None:
    """Section 10 point 1: no generated artefacts committed."""
    offenders = [
        path
        for path in _tracked_files()
        if any(fragment in path for fragment in BANNED_PATH_FRAGMENTS)
        or any(path.endswith(suffix) for suffix in BANNED_SUFFIXES)
    ]
    assert not offenders, f"generated artefacts are tracked by git: {offenders}"


def test_no_data_is_tracked() -> None:
    """Section 10 point 2: data/ holds only its README and small fixtures."""
    offenders = []
    for path in _tracked_files():
        if not path.startswith("data/"):
            continue
        if path == "data/README.md":
            continue
        size = (REPO_ROOT / path).stat().st_size
        if not path.startswith("data/fixtures/") or size > FIXTURE_SIZE_LIMIT_BYTES:
            offenders.append(f"{path} ({size} bytes)")
    assert not offenders, f"data must not be committed: {offenders}"


def test_no_env_file_is_tracked() -> None:
    """Section 10: no secrets in the repo, .env.example only."""
    offenders = [
        path
        for path in _tracked_files()
        if Path(path).name.startswith(".env") and Path(path).name != ".env.example"
    ]
    assert not offenders, f"environment files must not be committed: {offenders}"
