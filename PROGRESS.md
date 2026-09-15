# PROGRESS.md

Working log for `mortgage-risk-platform`. Claude Code appends here at the end of every session and at every phase boundary. Newest entries at the bottom. Never delete or rewrite history. If something earlier turned out to be wrong, add a correcting entry rather than editing the original.

This file exists so that a session starting cold can reconstruct where work stopped, what was decided, and what is currently broken.

---

## Current state

Update these four lines at the end of every session. They are the first thing read on a cold start.

- Current phase: 0, foundation built, blocked on the CI half of the exit criterion
- Last completed exit criterion: none. `make lint` and `make test` pass, but Phase 0 also requires CI green on first push, and no remote exists yet.
- Blocked on: no GitHub remote. The repository has one local commit (8b16da1) and has never been pushed, so `.github/workflows/ci.yml` has never executed. Creating the remote needs the human. Separately, WSL2 has no Linux distribution installed, which will block Phase 2 Spark work.
- Next action: human creates the GitHub repository and supplies the remote URL. Then push, confirm CI green, and only then start Phase 1.

---

## Phase status

| Phase | Name | Status | Completed |
| --- | --- | --- | --- |
| 0 | Foundation | blocked | |
| 1 | Data contracts and synthetic generator | not started | |
| 2 | Bronze and Silver | not started | |
| 3 | Golden-record test | not started | |
| 4 | Gold panel | not started | |
| 5 | Baselines and scorecard | not started | |
| 6 | Challenger model | not started | |
| 7 | Validation pack | not started | |
| 8 | IFRS 9 ECL layer | not started | |
| 9 | Explainability, fairness, governance | not started | |
| 10 | Orchestration and serving | not started | |
| 11 | Packaging | not started | |

Status values: not started, in progress, blocked, complete.

---

## Key results ledger

Every headline number lands here as soon as it is produced, with the script that produced it. This is the source for README and CV claims. A number not in this table does not go on a CV.

| Metric | Value | Split | Produced by | Date |
| --- | --- | --- | --- | --- |
| | | | | |

---

## Open questions and risks

Things that are unresolved and will bite later if forgotten.

| Item | Raised | Status |
| --- | --- | --- |
| PROJECT.md was empty on disk (0 bytes), so Phase 0 could not start. | 2026-09-15 | resolved, content supplied same day |
| No GitHub remote exists. Phase 0's exit criterion requires CI green on first push, so Phase 0 cannot close until the human creates the repository. | 2026-09-15 | open, blocking Phase 0 |
| WSL2 has no Linux distribution, only the internal `docker-desktop` one. PROJECT.md section 10 requires Spark to run in WSL2, so Phase 2 is blocked unless a distribution is installed or Spark runs in a container instead. Installing one on an Intune-managed device may need IT approval. | 2026-09-15 | open, blocks Phase 2 |
| Security policy blocks execution of uv virtualenv launchers on this host, so the native `make check` cannot run on Windows. Working via a Linux container (ADR-003). Revisit when the Phase 2 environment is settled. | 2026-09-15 | open, mitigated |
| Eight section 9 directories are not yet created because nothing populates them yet: `dags/`, `governance/`, `dashboards/`, `infra/`, `tests/property/`, `tests/integration/`, `tests/data/`, `tests/golden/`. Deliberate deferral, not drift. Each is created by the phase that fills it. | 2026-09-15 | open, tracked |

---

## Decisions log

One line per ADR, pointing at the full record.

| ADR | Decision | File |
| --- | --- | --- |
| ADR-001 | Python 3.11 and uv for dependency management | `docs/decisions/ADR-001-toolchain.md` |
| ADR-002 | Reserved by PROJECT.md section 3 for the acquisition-quarter subsetting decision, written in Phase 1 | not yet written |
| ADR-003 | Containerised development toolchain, because policy blocks local virtualenv execution | `docs/decisions/ADR-003-dev-environment.md` |

---

## Session entries

Use this template for every entry. Be specific. "Worked on features" is useless in three weeks.

```
### YYYY-MM-DD, Phase N

What I set out to do:

What I actually did:

What works now (with evidence, e.g. test names, command output):

What is broken or incomplete:

Decisions made and why:

Results produced (also added to the ledger above):

Surprises, dead ends, and what I learned from them:

Next action:
```

---

---

### 2026-09-15, Phase 0 (second session entry, same day)

**What I set out to do:** PROJECT.md was supplied after the earlier blocked entry. Read it in full, then execute Phase 0: repository structure per section 9, toolchain, pre-commit, Docker Compose skeleton, Makefile, `.env.example`, ADR template, CI workflow. Exit criterion: `make test` and `make lint` pass on an empty codebase, and CI green on first push.

**What I actually did:** built the whole Phase 0 scaffold and committed it as `8b16da1`. Renamed `Project.md`/`Progress.md` to the uppercase names section 9 specifies. Wrote `.gitignore` before `git init`, covering every artefact class in section 10 point 1 and the data rules in point 2, so no cache or data file has ever been staged. Created the `src/mortgage_risk/` package with all eleven section 9 subpackages. Configured ruff (line length 100, including `ANN` so section 10's type-hint requirement is enforced rather than merely stated), mypy in strict mode, and pytest with a 70 percent coverage floor. Added pre-commit with `detect-secrets` and a generated `.secrets.baseline`. Wrote `docker-compose.yml` with the Postgres and MLflow services from section 8. Wrote `ci.yml` running lint, type check, structure assertion and tests on `ubuntu-latest`.

Rather than a placeholder test, the test suite is a structure assertion: it checks that every file and subpackage section 9 requires exists, imports each subpackage, and asserts the section 10 hygiene rules against `git ls-files` so that a committed cache, a committed data file or a committed `.env` fails CI instead of relying on someone noticing in review.

**What works now, with evidence:**

- `make docker-check` is green end to end: `ruff check` "All checks passed!", `ruff format --check` "22 files already formatted", `mypy` "Success: no issues found in 14 source files", `pytest` "30 passed in 13.23s", coverage 100 percent against a 70 percent floor.
- `pre-commit run --all-files`: 10 hooks Passed, nbstripout Skipped with no notebooks to check.
- `docker compose config --quiet` validates; services declared are `postgres` and `mlflow`.
- `git status` clean, one commit on `main`.

**What is broken or incomplete:**

- **CI has never run.** There is no GitHub remote, so the second half of the Phase 0 exit criterion is unmet. Phase 0 is therefore not closed and Phase 1 has not been started.
- **The native `make check` cannot run on this host.** Windows execution policy blocks uv's virtualenv launchers. `make docker-check` runs the identical commands in Linux. See ADR-003.
- **WSL2 has no Linux distribution.** Section 10 requires Spark in WSL2. This blocks Phase 2, not Phase 0.
- Eight section 9 directories are not yet created, listed in the open questions table. Deliberate: each is created by the phase that populates it, and git cannot track an empty directory.

**Decisions made and why:**

- **ADR-001**, Python 3.11 and uv. 3.11 rather than the host's 3.12 because it is compatible with both the Spark 3.5 and Spark 4.x lines, so it removes a class of Phase 2 risk at no cost now.
- **ADR-003**, containerised toolchain. Forced by measurement, not preference: virtualenv launchers were blocked in the project directory, `%LOCALAPPDATA%` and `%TEMP%` alike, so relocating the environment was ruled out empirically before any other option was considered. No attempt was made to circumvent the control.
- ADR-002 is left unwritten and reserved: section 3 assigns that number to the acquisition-quarter subsetting decision in Phase 1.
- Dropped the `no-commit-to-branch` pre-commit hook. It would have blocked every commit to `main` in a solo trunk-based repository and forced habitual `--no-verify`, which is worse than not having the hook.
- Runtime `dependencies` in `pyproject.toml` is deliberately empty. Section 10 point 8 requires that nothing is listed that is not imported, so libraries are added in the phase that first imports them.

**Results produced:** none. Phase 0 produces no metrics, and nothing has been added to the results ledger. The first entries arrive in Phase 5.

**Surprises, dead ends, and what I learned from them:**

- The venv block presented as a plain `Access is denied`, which reads like a file permission problem. File ACLs granted FullControl, so it was an execution policy. Checking the ACL first would have wasted less time than assuming.
- Relocating the virtualenv was the obvious fix and was wrong. Testing three locations before committing to a design turned a plausible guess into a fact, and changed the decision.
- `detect-secrets` shells out to `git` to enumerate files, so it failed on the slim image for the same reason three hygiene tests were silently skipping there. One root cause, two symptoms, and the skip was the more dangerous of the two because it was quiet. Those tests now fail rather than skip when `CI` is set, so they cannot pass by not running in the place where they are the gate.
- Git Bash rewrote the container-side path `/w` into `W:/`, so `make docker-check` worked only with `MSYS_NO_PATHCONV=1`. Set inside the Makefile rather than documented as a prefix to remember.
- `pre-commit` normalised `PROJECT.md` and `PROGRESS.md` from CRLF to LF and added a trailing newline. Since PROJECT.md is the specification, I verified before accepting it: `git diff --ignore-cr-at-eol --ignore-all-space` on both files is empty, so no content changed. Added `.gitattributes` with `* text=auto eol=lf` so this cannot recur on every commit.

**Repo review, section 10, ten points:** clean, 10/10, with two notes.

1. No generated artefacts committed: pass, no tracked path matches any banned pattern.
2. No data in git: pass, `data/README.md` is the only tracked path under `data/`.
3. No dead files: pass. An automated substring scan flagged `docs/decisions/adr-template.md` on "temp" inside "template"; false positive, the ADR template is required by Phase 0.
4. No orphan modules: pass, all 12 files under `src/` are imported by `tests/unit/test_repo_structure.py`.
5. No empty directories or stale placeholders: pass.
6. Structure matches section 9: pass for everything created, 17 of 25 directories present, no file outside the section 9 tree. The eight absent directories are a deliberate deferral recorded in open questions, not drift.
7. Notebooks stay scratch: pass, none committed, `nbstripout` configured.
8. Dependencies are real: pass, runtime deps empty by design, all six dev deps invoked by the Makefile, pre-commit or CI.
9. Naming consistent: pass, all modules snake_case.
10. `git status` clean: pass.

**Next action:** blocked on the human. Create the GitHub repository and give me the remote URL, then I push, confirm CI green, and close Phase 0. Phase 1 will not be started before that. The WSL2 distribution question should be settled in parallel, since it gates Phase 2.
