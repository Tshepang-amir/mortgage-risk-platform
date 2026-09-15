# ADR-003: Containerised development toolchain on the Windows host

- **Status:** accepted for Phases 0 and 1; the Phase 2 Spark environment is deliberately left open
- **Date:** 2026-09-15
- **Phase:** 0

## Context

PROJECT.md section 10 says Spark work runs inside WSL2 on Windows hosts. Phase
0 needs no Spark, so the expectation was that the Python toolchain would run
natively on Windows for the foundation phase. It does not.

Measured on this host during Phase 0:

- `uv sync` resolves and installs correctly, and the uv-managed interpreter at
  `AppData\Roaming\uv\python\cpython-3.11-...\python.exe` executes normally.
- Every executable inside a created virtualenv (`\.venv\Scripts\*.exe`) fails
  with `Access is denied (os error 5)`. These are uv's small unsigned
  trampoline binaries.
- The block is not path-specific. A virtualenv created under the project
  directory, under `%LOCALAPPDATA%`, and under `%TEMP%` all fail identically.
- File ACLs grant the user FullControl, so this is an execution policy, not a
  permissions problem. The device is Intune-managed with AppLocker enforced.
  Windows Defender Controlled Folder Access is in audit mode and is not the
  cause.
- Docker Desktop is installed and healthy, with a Linux engine on the WSL2
  backend.
- WSL2 itself has no Linux distribution installed. Only the internal
  `docker-desktop` utility distribution is present, which is not a development
  environment.

This is a corporate security control. It is not something to work around, and
no attempt was made to do so.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Relocate the virtualenv | Would have been a one-line change | Ruled out by measurement: blocked in every location tested |
| Run the toolchain in a Linux container | Works today with no IT involvement; Docker is already in the stack for MLflow and Airflow; matches the `ubuntu-latest` CI runner, so local and CI results agree | Slower loop than native; the slim image has no `git`, so three hygiene tests skip locally |
| Install a WSL2 Linux distribution | What PROJECT.md section 10 already mandates for Spark; native speed; `git` present | Needs `wsl --install`, which on an Intune-managed device is likely to need IT approval. Cannot be assumed available |
| Request an AppLocker exception for uv trampolines | Restores the native Windows loop | Slow to obtain, may be refused, and leaves Phase 2 Spark on Windows, which section 10 explicitly warns against |

## Decision

For Phases 0 and 1, run the toolchain in a Linux container via `make
docker-check`. The native `make check` target is kept unchanged and remains the
correct entry point in CI, in WSL2, and on any unrestricted host. The container
is a way to run the same commands, not a different build.

The Phase 2 Spark environment is **not** decided here. It is recorded as an
open question in PROGRESS.md because it depends on whether a WSL2 distribution
can be installed on this device, which is not something this project can settle
on its own.

## Consequences

Makes easy: Phase 0 and Phase 1 proceed today with no IT dependency, and local
results match CI because both run Linux.

Makes hard: the edit-test loop is slower, and `git`-dependent hygiene tests skip
in the slim image. That skip is mitigated by failing rather than skipping when
`CI` is set, so the assertions cannot silently not run where they are the gate.

Reversal cost: near zero. The Makefile targets are the same commands; choosing
WSL2 later means running `make check` instead of `make docker-check`.

Revisit trigger: a WSL2 distribution becoming available, or Phase 2 beginning,
whichever comes first. Spark under Docker Desktop on Windows is viable but
memory-constrained, and section 10 already flags Spark as memory-bound on a
laptop.
