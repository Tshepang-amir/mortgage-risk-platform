# ADR-005: Containerised Spark runtime on the Windows host

- **Status:** accepted
- **Date:** 2026-09-15
- **Phase:** 2

## Context

PROJECT.md specifies local Spark in WSL2 because native Windows Spark is not a
supported development path. At the start of Phase 2, `wsl -l -v` shows only
Docker Desktop's internal `docker-desktop` distribution. There is no user Linux
distribution, while Docker Desktop is installed and healthy. Installing a WSL2
distribution on this Intune-managed device may require IT approval.

Spark also requires Java. The existing Python development image has no Java
runtime, so it cannot execute the Phase 2 integration tests unchanged.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Wait for a WSL2 Linux distribution | Matches PROJECT.md literally; best local edit-test loop | Blocks Phase 2 on an external approval with no known date |
| Run Spark in a Java-enabled Linux container | Available now; Linux matches CI; stays outside native Windows Spark; reuses the established ADR-003 path | Docker bind mounts and JVM startup make tests slower; Maven artefacts need network access on first run |
| Run Spark natively on Windows | No container build | Explicitly rejected by PROJECT.md; AppLocker already blocks the Python virtualenv launchers |

## Decision

Run local Spark 4 and Delta Lake 4 in the project development container. Extend
the image with OpenJDK 17, and install the same Java version in CI. Keep Spark
configured for a small local worker count and shuffle partition count so the
laptop remains within the memory constraint called out in PROJECT.md.

This supersedes ADR-003's deliberate deferral of the Phase 2 Spark decision; it
does not change ADR-003's diagnosis of the Windows execution policy.

## Consequences

Phase 2 can proceed without native Windows Spark or an IT dependency, and local
tests exercise the same Linux, Java, Python and dependency lock as CI. The first
Spark run must download Delta's JVM artefacts from Maven, and tests carry JVM
startup cost. A WSL2 distribution can later run the same `make check` commands
without changing pipeline code or table formats.

Revisit when a managed WSL2 distribution is available, or if container memory
pressure prevents the six-quarter workload from completing. The fallback is to
reduce the quarter set through a new ADR before tuning executor settings.
