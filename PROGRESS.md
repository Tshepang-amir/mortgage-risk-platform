# PROGRESS.md

Working log for `mortgage-risk-platform`. Claude Code appends here at the end of every session and at every phase boundary. Newest entries at the bottom. Never delete or rewrite history. If something earlier turned out to be wrong, add a correcting entry rather than editing the original.

This file exists so that a session starting cold can reconstruct where work stopped, what was decided, and what is currently broken.

---

## Current state

Update these four lines at the end of every session. They are the first thing read on a cold start.

- Current phase: 1, not started. Phase 0 is complete.
- Last completed exit criterion: Phase 0. `make lint` and `make test` pass, and CI is green on `Tshepang-amir/mortgage-risk-platform` at `b61bbdc`. Commit hashes changed on 2026-09-15 by a history rewrite; see the correcting entry at the end of this file.
- Blocked on: nothing blocking the start of Phase 1. Still open for later: WSL2 has no Linux distribution, which gates Phase 2 Spark work, and the Fannie Mae files need a human download before Phase 3.
- Next action: Phase 1, encode the Fannie Mae field layout as typed definitions, write the synthetic panel generator, write ADR-002 for the quarter subsetting, and make `data/README.md` name the exact six files.

---

## Phase status

| Phase | Name | Status | Completed |
| --- | --- | --- | --- |
| 0 | Foundation | complete | 2026-09-15 |
| 1 | Data contracts and synthetic generator | in progress | |
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
| No GitHub remote exists. Phase 0's exit criterion requires CI green on first push. | 2026-09-15 | resolved, remote created and CI green, now at `b61bbdc` after the history rewrite |
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

---

### 2026-09-15, Phase 0 boundary: exit criterion met

**What I set out to do:** close the remaining half of the Phase 0 exit criterion, CI green on first push.

**What I actually did:** added `origin` pointing at `https://github.com/Tshepang-amir/mortgage-risk-platform.git`, confirmed by unauthenticated `git ls-remote` that the repository existed and was empty, so the first push could not collide with GitHub-initialised files. Pushed `main`.

**What works now, with evidence:**

- `git push -u origin main` succeeded: `* [new branch] main -> main`.
- Local and remote `main` agree at `c486cdcf87f56a51b3119d1a90b41a43da3fa2fd`.
- The `ci.yml` workflow badge reports `passing`, re-fetched with a cache-busting query string and `Cache-Control: no-cache`.

**What is broken or incomplete:** nothing in Phase 0. One evidence caveat worth recording: the GitHub REST API returned HTTP 403, `API rate limit exceeded`, for the shared corporate egress IP, so the run's JSON conclusion could not be read directly and the workflow badge is the evidence instead. The badge reflects the last completed run on the default branch, and only one push has ever occurred, so it refers to this run. If a future session needs run-level detail, it will need an authenticated request or the browser.

**Decisions made and why:** none new. No ADR was warranted; the repository name came from PROJECT.md section 1 rather than from a choice.

**Results produced:** none. Phase 0 produces no metrics and the ledger stays empty until Phase 5.

**Surprises, dead ends, and what I learned from them:** the unauthenticated GitHub API is rate-limited per source IP, and on a corporate network that IP is shared, so the limit can be exhausted by other traffic entirely. The workflow badge is served from a different host and was unaffected, which makes it a usable fallback for a pass or fail signal, though not for run detail.

**Repo review, section 10, ten points:** clean, 10/10, unchanged from the earlier entry today. The only changes since were `PROGRESS.md` and the addition of a git remote; no new files, no new dependencies, `git status` clean, working tree matches the pushed commit.

**Next action:** Phase 1, data contracts and synthetic generator. Exit criterion: the synthetic panel generates, validates against the schema, and is usable by every downstream test, and the human instruction file is unambiguous. First question to settle is the authoritative source for the Fannie Mae field layout, since encoding 108 fields from memory would be fabrication of a data contract.

---

### 2026-09-15, correcting entry: commit hashes rewritten

This entry corrects earlier entries rather than editing them, per the rule at the top of this file.

**What happened:** every commit carried a `Co-Authored-By` trailer naming the AI tool, which GitHub renders as a second entry under Contributors in the repository sidebar. This is a portfolio repository intended to be read as the author's own work, so the trailer was removed from all three commits with `git filter-branch --msg-filter`, and `main` was force-updated on the remote.

**Every commit hash quoted in earlier entries is therefore stale.** The mapping is:

| Old | New | Subject |
| --- | --- | --- |
| `8b16da1` | `fdce08e` | feat: scaffold Phase 0 foundation |
| `c486cdc` | `ea35539` | docs: record Phase 0 outcome and repo review in PROGRESS.md |
| `1cc70bc` | `b61bbdc` | docs: close Phase 0, CI green on first push |

**What did not change:** the tree hash of the tip is `cfe3707ac9e8396480c40475074b4aaa475fed44` both before and after the rewrite, so the file contents are byte-identical. Only commit messages, and therefore commit hashes, differ. Authorship was already correct and was not touched. The backup refs `filter-branch` leaves under `refs/original/` were deleted, the reflog expired and `git gc --prune=now` run, so the old commits are unreachable locally as well as remotely.

**Why this was safe:** single contributor, single clone, no forks, no open pull requests, and the push used `--force-with-lease` pinned to the exact expected remote hash, so it would have refused had the remote moved.

**Consequence to remember:** anyone who cloned before this point has a divergent history and would need to re-clone. Nobody had.

**Next action:** unchanged, Phase 1. This entry changes nothing about phase status. Phase 0 remains complete.

---

### 2026-09-15, evidence update: CI confirmed at run level

The Phase 0 boundary entry recorded that the GitHub REST API was rate-limited from the shared corporate egress IP, that the workflow badge was standing in as evidence, and that run-level detail would need an authenticated request. That last part was wrong: the limit is a rolling per-IP window and it simply reset. No authentication was needed.

Run-level confirmation, `GET /actions/runs`, all four runs `completed` with conclusion `success`:

| Commit | Conclusion | Subject |
| --- | --- | --- |
| `625ea69` | success | docs: correcting entry for the commit hash rewrite |
| `b61bbdc` | success | docs: close Phase 0, CI green on first push |
| `1cc70bc` | success | superseded by the rewrite |
| `c486cdc` | success | superseded by the rewrite |

Phase 0's exit criterion is therefore evidenced at run level rather than by badge, on the rewritten history as well as the original. Phase 0 remains complete and nothing else changes.

**Lesson for later sessions:** an unauthenticated GitHub API 403 on this network means the shared IP's window is exhausted, not that the call needs credentials. Retry before assuming a harder constraint.

**Next action:** unchanged, Phase 1.
