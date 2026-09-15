# ADR-001: Python 3.11 and uv for dependency management

- **Status:** accepted
- **Date:** 2026-09-15
- **Phase:** 0

## Context

PROJECT.md section 10 requires "Python 3.11 or 3.12" without choosing between
them, and requires a reproducible, lockfile-backed environment without naming a
tool. Both are live decisions at Phase 0 because they are expensive to change
once Spark, Delta and MLflow pin transitive dependencies.

Facts known at the time of writing:

- The Windows host has Python 3.12.10 and `uv` 0.11.25 already installed.
- Spark work runs inside WSL2 (section 10, environment notes), so the host
  Python version does not constrain the project version.
- The binding compatibility constraint is PySpark plus `delta-spark`, not the
  application code. Python 3.11 is supported by both the Spark 3.5 line and the
  Spark 4.x line; 3.12 is supported only by the newer line.
- Databricks Free Edition (section 10) is serverless, so its runtime Python
  version is not under our control and is a further reason to sit on the
  version with the widest support surface.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Python 3.12 | Already on the host, no download; newer stdlib | Narrows the viable PySpark/`delta-spark` matrix to the newest line only; a Phase 2 incompatibility would force a rebuild of the environment |
| Python 3.11 | Compatible with both Spark lines and every current Databricks runtime; removes a class of Phase 2 risk at zero cost now | uv must fetch an interpreter the host does not have |
| `uv` | Fast resolution, single lockfile, manages the interpreter itself, already installed | Younger tool than the alternatives |
| Poetry | Mature, widely known | Slower resolution; separate interpreter management |
| `pip-tools` | Minimal, closest to plain pip | Multiple requirements files; no interpreter management |

## Decision

Python 3.11, pinned in `pyproject.toml` as `requires-python = ">=3.11,<3.12"`.
`uv` for dependency resolution, locking and interpreter management, with
`uv.lock` committed.

## Consequences

Makes easy: a single `make install` reproduces the environment on Windows, in
WSL2 and in CI from one lockfile, with uv fetching 3.11 wherever it is absent.

Makes hard: nothing at present. Python 3.12-only syntax is unavailable, which
costs nothing in this codebase.

Reversal cost: low while dependencies are empty, rising once Spark and Delta
are pinned in Phase 2. Changing the Python version after Phase 2 means a full
re-resolve and re-verification of the Spark stack.

Revisit trigger: if a required Phase 2 dependency drops 3.11 support, or if
Databricks Free Edition's serverless runtime moves to a version that makes 3.11
artifacts incompatible.
