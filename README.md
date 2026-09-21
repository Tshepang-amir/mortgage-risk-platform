# mortgage-risk-platform

Mortgage credit risk on Fannie Mae loan performance data: a discrete-time
hazard probability-of-default model, an IFRS 9 expected credit loss layer, and
a model validation pack of the kind a bank's model risk function would demand.

**Status: Phase 4 of 11 complete; Phase 5 and 6 implementations are in progress.**
The Gold survival panel and leakage controls are complete. The baseline, WOE
scorecard, spline hazard model, constrained LightGBM challenger, temporal
calibration, clustered comparison, and MLflow tracking paths are implemented
and tested, but no model has been trained on real Gold data and no results have
been produced.
This README is recruiter-facing and is written properly in Phase 11,
once there are numbers to put at the top of it.

- [PROJECT.md](PROJECT.md) is the specification and the standard.
- [PROGRESS.md](PROGRESS.md) is the working log and the current state of play.

## Quick start

```bash
make install   # create the virtualenv and install dependencies
make hooks     # install pre-commit hooks
make check     # lint, type check, structure assertion, tests
```

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11.

On a managed Windows host where security policy blocks execution of virtualenv
launchers, run the same checks in a Linux container instead:

```bash
make docker-check
```

Both run identical commands. The Docker image includes Java 17 for Spark and
persists the local Maven cache between runs. See
[ADR-005](docs/decisions/ADR-005-containerised-spark-runtime.md) for the Spark
runtime decision, [ADR-003](docs/decisions/ADR-003-dev-environment.md) for the
managed-host constraint, and [ADR-001](docs/decisions/ADR-001-toolchain.md) for
the Python and uv choice.
