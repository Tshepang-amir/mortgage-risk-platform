# PROGRESS.md

Working log for `mortgage-risk-platform`. Claude Code appends here at the end of every session and at every phase boundary. Newest entries at the bottom. Never delete or rewrite history. If something earlier turned out to be wrong, add a correcting entry rather than editing the original.

This file exists so that a session starting cold can reconstruct where work stopped, what was decided, and what is currently broken.

---

## Current state

Update these four lines at the end of every session. They are the first thing read on a cold start.

- Current phase: 0 (not started, BLOCKED)
- Last completed exit criterion: none
- Blocked on: PROJECT.md is empty (0 bytes on disk). It is the specification and the standard; without it there is no Phase 0 exit criterion, no section 9 layout, no section 10 hygiene checklist, and no section 11 phase order. No code can be written.
- Next action: user to supply the content of PROJECT.md. Nothing else can proceed.

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
| PROJECT.md is empty on disk (0 bytes). Spec, exit criteria, section 9 layout, section 10 hygiene checklist and section 11 phase order are all unavailable. | 2026-09-15 | open, blocking |
| Once PROJECT.md is restored, confirm it is the intended final version and not a truncated draft, before any code is written against it. | 2026-09-15 | open |

---

## Decisions log

One line per ADR, pointing at the full record.

| ADR | Decision | File |
| --- | --- | --- |
| | | |

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

### Example entry, delete once real work begins

### 2026-01-01, Phase 0

What I set out to do: initialise the repository skeleton and get CI green.

What I actually did: created `pyproject.toml` with ruff, mypy and pytest config; added pre-commit with detect-secrets; scaffolded `src/mortgage_risk/` package layout; wrote a placeholder test; added `.github/workflows/ci.yml` running lint, type check and tests on push.

What works now: `make lint` passes with 0 ruff errors. `make test` passes 1 placeholder test. CI green on first push, run link in commit.

What is broken or incomplete: Docker Compose file is a skeleton only, no services defined yet. Makefile has targets for lint and test but not yet for spark or airflow.

Decisions made and why: chose `uv` over `pip-tools` for dependency management because it resolves faster and the lockfile is simpler to read in review. Recorded as ADR-001.

Results produced: none yet, no models trained.

Surprises: mypy strict mode flagged a large number of issues in the empty package due to missing stubs for pyspark. Set `ignore_missing_imports` for pyspark specifically rather than loosening strictness globally. Noted in ADR-001.

Next action: Phase 1, encode the Fannie Mae 108-field schema and write `data/README.md` with exact download instructions for the six quarters.
---

### 2026-09-15, Phase 0

What I set out to do: read PROJECT.md and PROGRESS.md, state the Phase 0 exit criterion and plan, then initialise the repository skeleton and .gitignore per section 9 and section 10.

What I actually did: read both files. PROJECT.md is present on disk but empty, 0 bytes. Searched the machine for any other copy: Desktop, Downloads, Documents, both OneDrive roots. Found two unrelated specs (`Desktop/project/PROJECT_CONTEXT.md`, an IndabaX health-QA hackathon; `Downloads/PROJECT_STATE.md` and `OneDrive - Zutari/Marine Project/PROJECT_STATE.md`, a Cape Town marine outfalls pipeline). No copy of the mortgage specification exists anywhere I can reach. There is no git history to recover it from; the directory is not a repository.

Stopped without writing code and recorded the block here, per operating rule 8.

What works now: nothing. No repository, no package, no tests. The directory contains only Project.md (empty) and Progress.md.

What is broken or incomplete: everything downstream of the specification. Specifically unavailable and not inferable:
- Section 11, the phase order and the exit criterion for each phase. PROGRESS.md gives phase *names* only. A name is not an exit criterion.
- Section 9, the repository layout. Phase 0 scaffolds this, so guessing it guarantees drift that rule 9 forbids.
- Section 10, repository hygiene and the ten-point repo review that must be run and reported at the end of every session.
- Data contracts, the Fannie Mae field schema and which six quarters are in scope.
- Model specification: hazard horizon, WOE binning rules, the bootstrap comparison procedure that decides whether LightGBM ships.
- IFRS 9 staging rules and ECL specification.
- Validation pack contents and thresholds.

Decisions made and why: did not scaffold anything, not even .gitignore or `git init`. Phase 0's entire content is conformance to sections 9 and 10, which I do not have. A scaffold built on a guessed layout would have to be torn down and would put unreviewed drift into the repository's first commit. The instruction to start Phase 0 conflicts with PROJECT.md being unreadable, and PROJECT.md governs, so I stopped and asked as instructed. No ADR written: this is a missing input, not a decision between defensible options.

Results produced: none. Ledger unchanged and correctly empty.

Surprises, dead ends, and what I learned from them: the file exists with a plausible name and a recent timestamp, so a cold start that trusted the directory listing rather than the byte count would have read silence as "no constraints" and invented a specification. Worth guarding: a zero-byte spec should fail loudly, not quietly.

Next action: user supplies the content of PROJECT.md. On receipt, re-read it in full, restate Phase 0's exit criterion from section 11 and the layout from section 9, confirm the plan, then execute Phase 0 including .gitignore before the first commit.
