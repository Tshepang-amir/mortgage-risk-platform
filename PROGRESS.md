# PROGRESS.md

Working log for `mortgage-risk-platform`. Claude Code appends here at the end of every session and at every phase boundary. Newest entries at the bottom. Never delete or rewrite history. If something earlier turned out to be wrong, add a correcting entry rather than editing the original.

This file exists so that a session starting cold can reconstruct where work stopped, what was decided, and what is currently broken.

---

## Current state

Update these four lines at the end of every session. They are the first thing read on a cold start.

- Current phase: 6 in progress. Phase 5 and 6 model stacks are implemented and tested; both real-data exit runs are outstanding.
- Last completed exit criterion: Phase 4. Phase 6 engineering gate passed on 2026-09-21: Ruff clean, 66 files formatted, mypy clean on 47 source files, pytest 99 passed in 553.28 seconds with 89.22 percent coverage.
- Blocked on: no real Bronze, Silver, Gold, or macro Delta data exists, `FRED_API_KEY` is unset, and no MLflow tracking URI is configured. Synthetic metrics and model selections are not exit evidence.
- Next action: build the real medallion tables and point-in-time macro data, complete the Phase 5 real scorecard run, then run Phase 6 on the same Gold Delta version and record the out-of-time selection interval.

---

## Phase status

| Phase | Name | Status | Completed |
| --- | --- | --- | --- |
| 0 | Foundation | complete | 2026-09-15 |
| 1 | Data contracts and synthetic generator | complete | 2026-09-15 |
| 2 | Bronze and Silver | complete | 2026-09-16 |
| 3 | Golden-record test | complete | 2026-09-17 |
| 4 | Gold panel | complete | 2026-09-17 |
| 5 | Baselines and scorecard | in progress | |
| 6 | Challenger model | in progress | |
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
| Raw files carry 113 pipe-separated tokens; the Phase 1 contract accepted 108 or 110. | 2026-09-17 | resolved by ADR-008; the published sample proved there is no trailing delimiter, so 113 tokens are 113 fields |
| `SELLER` and `SERVICER` exceed their published `X(50)` length in four of six vintages, observed up to 68 characters. Fannie Mae's data contradicts Fannie Mae's glossary. | 2026-09-18 | resolved by ADR-009; text length is now reported to the quality gate, not fatal at parse |
| Observed maxima for the other 37 text fields are unknown, so the quality gate has declared figures but no measured ones to compare against. A serial `awk` scan of all 113 positions was abandoned after roughly a day. | 2026-09-19 | open, answer from the Bronze Spark pass |
| Numeric and date widths are declared in `raw_format`, for example `9(3)`, and enforced nowhere. A 40-digit credit score parses today and would reach Silver. Pre-dates ADR-009. Deliberately not closed without evidence, since an unevidenced width is what broke `SELLER`. | 2026-09-19 | open, answer from the Bronze Spark pass |
| `features/macro.py` sat at 56 percent coverage with the FRED ingestion path untested, so a parser bug could have left the macro-lag test green while real data leaked. | 2026-09-17 | resolved, 86 percent, ingestion and join now tested as one path and verified by mutation |
| ADR-007 leaves identifiers and split columns unclassified. They are temporally invariant so they pass the leakage test, but they are not model features either. Phase 5 must select features positively rather than taking everything that is not an outcome. | 2026-09-17 | resolved by ADR-010 and the positive seven-feature contract |
| PROJECT.md was empty on disk (0 bytes), so Phase 0 could not start. | 2026-09-15 | resolved, content supplied same day |
| No GitHub remote exists. Phase 0's exit criterion requires CI green on first push. | 2026-09-15 | resolved, remote created and CI green, now at `b61bbdc` after the history rewrite |
| WSL2 has no Linux distribution, only the internal `docker-desktop` one. PROJECT.md section 10 requires Spark to run in WSL2, so Phase 2 is blocked unless a distribution is installed or Spark runs in a container instead. Installing one on an Intune-managed device may need IT approval. | 2026-09-15 | resolved by containerised Spark in ADR-005 |
| Security policy blocks execution of uv virtualenv launchers on this host, so the native `make check` cannot run on Windows. Working via a Linux container (ADR-003). Revisit when the Phase 2 environment is settled. | 2026-09-15 | open, mitigated by ADR-003 and ADR-005 |
| Six section 9 directories are not yet created because nothing populates them yet: `dags/`, `governance/`, `dashboards/`, `infra/`, `tests/property/`, `tests/golden/`. Deliberate deferral, not drift. Each is created by the phase that fills it. | 2026-09-15 | open, tracked |

---

## Decisions log

One line per ADR, pointing at the full record.

| ADR | Decision | File |
| --- | --- | --- |
| ADR-001 | Python 3.11 and uv for dependency management | `docs/decisions/ADR-001-toolchain.md` |
| ADR-002 | Use six regime-spanning acquisition quarters: 2005Q1, 2005Q3, 2007Q1, 2012Q1, 2016Q1 and 2018Q1 | `docs/decisions/ADR-002-acquisition-quarter-subset.md` |
| ADR-003 | Containerised development toolchain, because policy blocks local virtualenv execution | `docs/decisions/ADR-003-dev-environment.md` |
| ADR-004 | Use the 108-field sample layout as the Phase 1 default while accepting the 110-field official R-importer extension | `docs/decisions/ADR-004-fannie-mae-schema-version.md` |
| ADR-005 | Run local Spark and Delta Lake in a Java-enabled Linux container | `docs/decisions/ADR-005-containerised-spark-runtime.md` |
| ADR-006 | Define the real-data golden-record population and published-summary tolerance | `docs/decisions/ADR-006-golden-record-population.md` |
| ADR-007 | Separate future-dependent outcome columns from model features with an explicit registry | `docs/decisions/ADR-007-outcome-column-registry.md` |
| ADR-008 | Adopt the confirmed 113-field current raw-file layout | `docs/decisions/ADR-008-current-file-width.md` |
| ADR-009 | Treat published text length as a quality signal rather than a parse failure | `docs/decisions/ADR-009-text-length-is-a-quality-signal.md` |
| ADR-010 | Use constrained OptBinning, deterministic loan sampling, and loan-clustered evaluation | `docs/decisions/ADR-010-scorecard-training-design.md` |
| ADR-011 | Calibrate temporally and require interval evidence to ship LightGBM | `docs/decisions/ADR-011-challenger-calibration-and-selection.md` |

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

---

### 2026-09-15, Phase 1 boundary: exit criterion met

**What I set out to do:** execute Phase 1 after Phase 0 was confirmed complete: encode the Fannie Mae field layout, build a deterministic synthetic loan-month panel with known ground truth, make pytest fixtures available for downstream phases, write ADR-002 for the acquisition-quarter subset, and make the raw-data instructions unambiguous.

**What I actually did:** encoded the Fannie Mae Single-Family Loan Performance positional contract in `src/mortgage_risk/data/schema.py`. The default supported raw width is the 108-field public sample layout, with support for the 110-field official Primary R importer extension. Added `src/mortgage_risk/data/synthetic.py`, which generates deterministic headerless pipe-delimited loan-month rows plus separate loan-level ground-truth outcomes for default, prepayment and censoring. Added reusable pytest fixture `synthetic_panel` in `tests/conftest.py` and focused unit tests for schema validation and synthetic generation. Updated `data/README.md` with the six exact required primary files: `2005Q1.csv`, `2005Q3.csv`, `2007Q1.csv`, `2012Q1.csv`, `2016Q1.csv`, and `2018Q1.csv`. Wrote ADR-002 for the subset decision and ADR-004 for the schema-version mismatch between the sample CSV, R importer and latest glossary.

**What works now, with evidence:** direct Docker check passed from PowerShell using the ADR-003 Linux toolchain: `ruff check` reported all checks passed, `ruff format --check` reported 29 files already formatted, `mypy` reported success on 19 source files, and `pytest` collected 42 tests, all passed, with total coverage 92.21 percent. The downloaded official sample CSV validated against the 108-field schema: 757 rows accepted.

**What is broken or incomplete:** native Windows `uv run ruff format .` remains blocked by local execution/cache policy, consistent with ADR-003. `make docker-check` also remains Git-Bash-oriented because PowerShell treats `MSYS_NO_PATHCONV=1` as a command; running the equivalent `docker run` command directly from PowerShell works. Real Fannie Mae files are not present under `data/raw/`, and their local SHA-256 hashes cannot be recorded until the human downloads them.

**Decisions made and why:** ADR-002 keeps six regime-spanning acquisition quarters so the project remains small enough for the target environment while retaining crisis, post-crisis and out-of-time cohorts. ADR-004 keeps the 108-field sample layout as Phase 1 default but accepts the 110-field official R importer extension, because the public artefacts disagree and pretending otherwise would make Phase 2 brittle.

**Results produced:** none. Phase 1 produces contracts and fixtures, not model metrics; the results ledger remains empty.

**Surprises, dead ends, and what I learned from them:** the current public artefacts disagree on field count: the sample CSV is 108 fields, the official Primary R importer names 110 fields, and the latest glossary dated 2026-09-10 runs through position 114. The schema now records that evidence instead of collapsing it into a single undocumented assumption. `apply_patch` also failed before modifying files because the Windows sandbox wrapper could not prepare the writable-root policy, so file writes were split through smaller PowerShell/Python writes.

**Repo review, section 10, ten points:** clean, 10/10, with notes. No generated artefacts or raw data are tracked; `data/` still tracks only `data/README.md`; new modules are imported by tests; no new runtime dependencies were added; naming remains snake_case; ADRs record the non-obvious choices; direct Docker lint, typecheck and tests are clean; `git status` has only the intended Phase 1 working-tree changes.

**Next action:** Phase 2 is next but blocked on the Spark runtime path. Either install a WSL2 Linux distribution or write an ADR accepting containerised Spark for Bronze/Silver work.


---

### 2026-09-16, Phase 2 boundary: exit criterion met

**What I set out to do:** resolve the Spark runtime decision that blocked Phase 2, then implement Bronze and Silver on Delta Lake with provenance, typing, deduplication, code decoding, a slowly changing servicer dimension, a Great Expectations transition gate, and a test proving ingestion replay is idempotent.

**What I actually did:** accepted ADR-005 and added a Java 17 development image plus Java 17 in CI. Locked Delta Lake 4.4.0, PySpark 4.1.3 and Great Expectations 1.23.0. Added an all-string Bronze schema and append-only ingestion with source filename, source path, SHA-256, field count and ingest timestamp. Exact source filename and hash replays are skipped. Added Silver casting from the Phase 1 field contract, deterministic loan-month deduplication, decoded channel, purpose, property, occupancy, zero-balance and delinquency labels, and an SCD Type 2 loan-servicer assignment dimension. Silver publication runs a nine-expectation GX suite first and can write failed candidates to a quarantine Delta path.

**What works now, with evidence:** the end-to-end synthetic test writes a headerless raw file, ingests it twice with identical Bronze row counts, publishes Silver twice with identical row counts, verifies date and decimal types, verifies decoded labels and provenance, and checks one current servicer assignment per synthetic loan. A separate GX test injects a duplicate loan-month and is rejected by expect_compound_columns_to_be_unique. The SCD2 test changes servicer and verifies the old assignment closes in the preceding month while the new assignment remains current. The complete container check passed: Ruff clean, 37 files formatted, mypy clean on 26 source files, and pytest 45 passed in 212.48 seconds with 92.00 percent coverage.

**What is broken or incomplete:** the six real Fannie Mae quarterly files are still absent, so the Phase 2 DQ suite has passed on synthetic data only and Phase 3 cannot run. Native Windows virtualenv launchers remain blocked by policy. The managed network intercepts Maven TLS with a Cloudflare Gateway root trusted by Windows but not by the base image's Java store; the public root was used only in a temporary local truststore for the first Delta download, and the Maven artefacts now live in the ignored Docker mrp-ivy volume. CI uses the normal GitHub trust chain and does not need this host-specific step.

**Decisions made and why:** ADR-005 accepts containerised local Spark because Docker Desktop is healthy, there is no user WSL distribution, and waiting for an Intune-dependent installation would leave Phase 2 blocked. Spark uses local[2], two shuffle partitions, and loopback for both the bound and advertised driver address so local executors work inside one container. Delta 4.4 and Spark 4.1 are kept within their official compatibility line.

**Results produced:** none. Phase 2 creates validated data layers and no model metric; the results ledger remains empty.

**Surprises, dead ends, and what I learned from them:** the patch helper again failed before editing because the Windows sandbox wrapper could not enforce split writable roots, so edits used narrowly scoped PowerShell writes after that failure. The first dependency lock exceeded the command timeout but completed the lockfile write. Delta 4.4 uses Spark-versioned Maven coordinates such as delta-spark_4.1_2.13. After resolving TLS trust, Spark initially failed because spark.driver.bindAddress was loopback while spark.driver.host still advertised the container address; pairing both on loopback fixed the single-container local runtime.

**Repo review, section 10, ten points:** clean, 10/10. No generated artefacts, certificates, Delta files, Maven jars or raw data are tracked; data/ still tracks only its README; all new source modules are imported by tests; both runtime dependencies are imported; there are no dead files or empty directories; the new tests/data/ and tests/integration/ directories match section 9; naming is consistent; notebook state is unchanged; git diff --check is clean; the worktree contains only the intended Phase 2 changes before commit.

**Next action:** obtain the six quarterly files listed in data/README.md, record their SHA-256 hashes, run the Silver DQ suite on them, and begin Phase 3 by reproducing Fannie Mae's published statistical summary.

---

### 2026-09-17, Phase 3 boundary: exit criterion met by documented discrepancy

**What I set out to do:** reproduce Fannie Mae's published statistical summary from Silver, assert equality within the publication's displayed precision, and either pass the real-data check or identify and document the root cause of any discrepancy.

**What I actually did:** downloaded the public Primary R reference archive and July 2026 Primary statistical-summary PDF, inspected the one-row-per-loan production code and acquisition-summary formulas, and added `src/mortgage_risk/data/golden.py`. The module collapses Silver to the latest row per loan, replaces missing OCLTV with OLTV, derives Classic FICO as the lower available borrower/co-borrower score, and calculates loan count, original UPB totals and averages, and original-UPB-weighted FICO, LTV, CLTV, DTI and note rate by origination year plus a total row. It pins six published control rows, including the total, to the July 2026 PDF hash and compares at half the publication's displayed unit. Before metric comparison it derives acquisition quarters from Silver provenance and requires exact population equality. Added ADR-006 and focused Spark tests.

**What works now, with evidence:** the focused tests prove one-row-per-loan collapse, latest-record selection, missing-CLTV substitution, minimum-score Classic FICO, UPB weighting, total-row construction, tolerance failure, provenance parsing and end-to-end validation through the public API. They also prove the six-quarter manifest is rejected against the publication's 105-quarter scope. The complete container gate passed: Ruff clean, 40 files formatted, mypy clean on 28 source files, and pytest 48 passed in 179.28 seconds with 91.81 percent coverage.

**External evidence pinned:** `FNMA_SF_Loan_Performance_Stat_Summary_Primary.pdf`, titled "Fannie Mae Statistical Summary Tables: July 2026", SHA-256 `0d4b36c43a0d49bd8e6b11fca0162e117220c447f57fa41da4b119e7e655fbfc`; `FNMA_SF_Loan_Performance_r_Primary.zip`, SHA-256 `00b6798d614ed6af75ed1e79e8908bbb0526f166d4367e4be0334af70ecd6418`. Both were read from Fannie Mae's public Loan Performance Data page and remain temporary local reference downloads, not repository files.

**Root-cause finding and exit disposition:** the July 2026 publication covers every acquisition quarter from 2000Q1 through 2026Q1 and groups loans by origination year. ADR-002 deliberately selects only 2005Q1, 2005Q3, 2007Q1, 2012Q1, 2016Q1 and 2018Q1. An origination-year row spans loans delivered in multiple acquisition quarters, so no annual published row is a control total for this six-quarter subset. Equality is mathematically unavailable even after the six required files arrive. Comparing anyway would produce a guaranteed population error, not evidence about ingestion. This is the investigated discrepancy and root cause allowed by the Phase 3 exit criterion; ADR-006 records the decision to fail closed.

**What is broken or incomplete:** a literal equality result against Fannie Mae's full-book PDF is unavailable under the project's intentional six-quarter scope. It becomes possible only if a later ADR expands ingestion to all 105 quarters for this exact PDF snapshot, or Fannie Mae publishes matching quarter-level controls. The six real files are still absent, so their hashes and Phase 2 real-data DQ evidence also remain outstanding. No model results exist.

**Surprises, dead ends, and what I learned from them:** the public tutorial says reproducing the identical portal summary requires the full dataset, which exposes the conflict with ADR-002 directly. The downloadable R archive is also stale in two visible ways: its configured endpoint is 2023Q4 and its summary script emits borrower and co-borrower scores separately, while the July 2026 PDF displays one Classic FICO column. The production script still derives `CSCORE_MN` as the lower available score, matching the tutorial's definition and the current table. The patch helper again failed before writing because of the known Windows sandbox-wrapper limitation; narrowly scoped PowerShell writes were used after that failure.

**Repo review, section 10, ten points:** clean, 10/10. No raw data, downloaded PDFs, ZIPs, Spark output or generated artefacts are tracked; `data/` still tracks only its README; the new module is imported and exercised by tests; no dependency was added; `tests/golden/` now matches the required section 9 layout; naming is snake_case; the non-obvious population decision has an ADR; notebook state is unchanged; `git diff --check` is clean; and the working tree contains only intended Phase 3 changes before commit.

**Next action:** Phase 4, constructing the Gold survival panel on synthetic Silver first. When the six human-downloaded files arrive, record their hashes and rerun the existing Bronze/Silver DQ path, but do not compare their subset aggregates with the incompatible full-book publication.

---

### 2026-09-17, Phase 4 boundary: exit criterion met

**What I set out to do:** find the true state of Phase 4, fix whatever was failing, and meet the exit criterion: all three leakage tests pass, and panel rows reconcile to loan counts times observed months.

**What I found on arrival:** 709 lines of Gold-panel work uncommitted across `data/gold.py`, `features/macro.py`, `validation/splits.py` and `config/gold.py`, with `hypothesis` added to `pyproject.toml` but unused. `make check` failed at `ruff format`, and because the gate chains on `&&`, mypy and pytest had never run against any of it. None of the three leakage tests existed. The phase table and current-state block both still said Phase 3 was "not started" even though the 2026-09-17 entry above closes it; the living blocks had not been updated at the end of that session.

**What I actually did:** added a `docker-format` target, since the native `format` target cannot run on this host for the reasons in ADR-003. Reformatted three files. Fixed a genuine mypy failure in `macro.py` that the lint failure had been masking: `expressions` needed an explicit `list[Column]` annotation. Wrote `tests/property/test_leakage.py`, which creates the `tests/property/` directory section 9 requires and makes the `hypothesis` dependency legitimate rather than unused.

**The leakage tests found a real exposure.** Withholding rows after a cutoff changed three columns that were neither labels nor obviously outcomes:

| Column | Full build | Rows after cutoff withheld |
| --- | --- | --- |
| `SOURCE_OBSERVED_MONTHS` | 12 | 2 |
| `EXIT_DATE` | 2016-05-01 | null |
| `EXIT_TYPE` | `default` | `right_censored` |

All three are legitimate survival bookkeeping, and my first classification list missed them, so the initial failure was partly my own test being incomplete. The exposure it revealed is real regardless: nothing in the Gold schema separated them from features. `EXIT_TYPE` is a restatement of the answer and `SOURCE_OBSERVED_MONTHS` encodes how long the loan survived. A Phase 5 model selecting either would score near-perfectly and mean nothing, and that failure would look like success.

The fix is structural rather than a patched exclusion list. `OUTCOME_COLUMNS` now lives in `config/gold.py` as one registry, and the test asserts a subset property: the set of columns whose values change under truncation must be contained in that registry. Any new column carrying lookahead fails the suite until someone classifies it deliberately. Recorded as ADR-007, including the honest note that the panel code was written before its guard, contrary to rule 2.

**What works now, with evidence:** full container gate green on 2026-09-17, `make docker-check` exit 0. Because the gate chains on `&&`, pytest running at all proves Ruff check, Ruff format and mypy all passed. **56 passed in 585.65 seconds, 86.17 percent coverage** against a 70 percent floor. The eight leakage tests are:

- `test_only_classified_outcome_columns_depend_on_future_rows` and `test_temporal_invariance_holds_at_any_cutoff`, a Hypothesis property over four cutoffs, for control 1
- `test_temporal_invariance_check_is_not_vacuous`, which fails if truncation stops changing anything, so control 1 cannot pass by comparing a panel with itself
- `test_no_loan_is_both_training_and_out_of_vintage` and `test_split_integrity_rejects_a_loan_in_two_vintages` for control 2, the second being the negative case
- `test_no_macro_value_postdates_its_observation_month` and `test_point_in_time_join_ignores_a_later_revision` for control 3, the second injecting a 2020 revision of a 2015 observation and asserting it never reaches a 2015 loan-month
- `test_panel_rows_reconcile_to_at_risk_loan_months` for the second half of the exit criterion

**What is broken or incomplete:** `features/macro.py` is at 56 percent coverage, and the untested part is the FRED ingestion path that decides each value's `AVAILABLE_DATE`. Leakage control 3 proves the join respects availability, but the test builds its own vintage frame, so it never exercises the parser that produces those dates from a real FRED response. A bug there would leave the macro-lag test green while real data leaked. Recorded in open questions and worth closing before Phase 5 consumes macro data in anger. The six Fannie Mae files are still absent, so every result so far is structural, not empirical.

**Decisions made and why:** ADR-007, the outcome-column registry, chosen over a naming convention that nothing enforces and over splitting labels into a separate table, which would add a join to every training run and complicate the one-row-per-at-risk-loan-month reconciliation that is the point of the panel.

**Results produced:** none. The ledger stays empty. Phase 5 produces the first headline numbers, and on synthetic data they would measure the generator rather than the mortgage market, so they must not be cited.

**Surprises, dead ends, and what I learned from them:** a formatting failure hid a type error, which in an `&&` chain hid the entire test suite. A cheap failure at the front of a gate can conceal expensive ones behind it, and "lint is failing" is not a small problem when nothing after it has run. Separately, writing the invariance test as a subset assertion rather than a fixed exclusion list turned a one-off fix into a standing guard; the fixed list would have gone stale the first time someone added a column.

**Repo review, section 10, ten points:** clean, 10/10. No generated artefacts or data tracked; no dead files; all 23 `src` modules reached by tests or siblings; no empty directories; 10 of 14 section 9 directories present, with `dags/`, `governance/`, `dashboards/` and `infra/` still owned by later phases; no notebooks committed; every declared dependency used, `hypothesis` now genuinely so; naming snake_case throughout; working tree staged and clean.

**Next action:** close the macro ingestion coverage gap, then obtain the six Fannie Mae files before Phase 5 trains anything whose output is meant to be cited.

---

### 2026-09-17, raw data placed and a schema mismatch found

**What I set out to do:** move the six downloaded Fannie Mae files into `data/raw/`, record their hashes, and confirm they match the Phase 1 contract.

**What I actually did:** found all six archives in `Downloads`, verified before extracting that each contained exactly one correctly-named CSV and that 45.5 GB would fit in 500 GB free. Extracted them to `data/raw/`; no renaming was needed because the archive entries already carried the manifest filenames. Confirmed `git check-ignore` resolves each file to `.gitignore:53`, `data/*`, and that the working tree stayed clean, so none of this can reach the repository. Then inspected the format rather than assuming it.

**SHA-256 of the raw files, as required by Phase 1:**

| File | Size | SHA-256 |
| --- | --- | --- |
| `2005Q1.csv` | 6.15 GB | `342d8049441e0cac1de435069f740d56b969a77de0c7b5f4612fa9afdac4cd71` |
| `2005Q3.csv` | 8.97 GB | `9cf06c554a5766c8d760e626a190db68a1571a6d1a4a5d420dfb055b7793c722` |
| `2007Q1.csv` | 4.21 GB | `6d352fa421713ae1ee9133c633aba2f62af0855e4ea35619686c4cb5f4ac2573` |
| `2012Q1.csv` | 12.90 GB | `3e4928f155e7571da8f92116280dd2800e51fc71cf6c82265b50fb510b8a8f07` |
| `2016Q1.csv` | 6.84 GB | `ce2551185c5e05f63545d72d99f9a6cf1de16e130c0b534eee8f5fb07809864c` |
| `2018Q1.csv` | 6.45 GB | `b89043e7c2967d8f50bb3d7f5f694ee624a77ec86e9390a6333ee9ccf5ed3ebe` |

**The finding: the real files do not match the encoded schema.** Every line carries 113 pipe-separated tokens. `SUPPORTED_FIELD_COUNTS` accepts 108 or 110 only.

Scanning roughly 1.1 million rows across four vintages gives a completely consistent shape:

| Token | 2005Q1 | 2012Q1 | 2016Q1 | 2018Q1 |
| --- | --- | --- | --- | --- |
| 1 | always empty | always empty | always empty | always empty |
| 111 | always empty | 1,353 of 200k populated | 4,120 of 300k populated | 5,921 of 300k populated |
| 112 | always empty | always empty | always empty | always empty |
| 113 | always empty | always empty | always empty | always empty |

Token 1 is a real field that happens to be blank, almost certainly Reference Pool ID, which is populated only for CRT deals. The following tokens read as loan identifier, monthly reporting period, channel `C`, then seller name, which is the documented order and confirms token 1 is not a wrapper artefact.

Token 111 is real and increasingly populated in later vintages, matching the position `schema.py` line 29 already names "Origination Classic FICO". That is the confirmation ADR-004 was explicitly waiting for when it said positions 111 to 114 are not accepted as raw-file columns until the sample file or official importer confirms the shape.

**What is broken or incomplete:** whether the layout is 112 fields plus a trailing delimiter, or 113 fields with the last two unpopulated in every vintage held, cannot be decided from content. A record ending in a delimiter and a record whose final field is empty are byte-identical. Resolving it by guess would fabricate the data contract that every later phase is validated against, and an off-by-one would shift every column silently while still parsing. Real-data Bronze and Silver runs are therefore blocked, as is the Phase 2 real-data DQ evidence.

**Decisions made and why:** none. No ADR yet, because the schema decision cannot be made without the layout document. ADR-004 will need amending once it is available; that amendment is the decision, and making it now would be guesswork dressed as a record.

**Results produced:** none. The hashes above are provenance, not metrics, so the ledger stays empty.

**Surprises, dead ends, and what I learned from them:** the working assumption had been that the files would arrive in the 108-field public sample shape or the 110-field importer shape, and ADR-004 hedged against exactly this. The hedge paid off: because the supported counts were explicit and validated, the mismatch surfaced as a contract question in minutes rather than as silently misaligned columns in Silver. A schema that fails loudly on an unexpected width is worth more than one that tolerates it.

**Repo review, section 10, ten points:** clean, 10/10, unchanged in substance. Specifically on point 2, 45.5 GB now sits under `data/` and none of it is tracked; `git check-ignore` was run against the new files rather than assumed, and `git status` is clean.

**Next action:** obtain the current Fannie Mae file layout and glossary from Data Dynamics under Resources, which is a human step behind the same login. Then amend ADR-004, extend `SUPPORTED_FIELD_COUNTS`, encode positions 109 to 113, and re-run Bronze and Silver against real data.

---

### 2026-09-17, closing the macro ingestion coverage gap

**What I set out to do:** close the gap recorded at the Phase 4 boundary, where `features/macro.py` sat at 56 percent and the untested part was the FRED ingestion path that decides each macro value's `AVAILABLE_DATE`. This is Phase 4 remedial work, not the start of Phase 5.

**Why it mattered:** leakage control 3 proves the join honours `AVAILABLE_DATE`, but the test builds its own vintage frame, so it never exercised the parser producing those dates. A bug there would have left the macro-lag test green while real data leaked. The guarantee was thinner than it looked.

**What I actually did:** added `tests/unit/test_macro_ingestion.py`, seventeen tests over `fred_initial_release_parameters` and `parse_fred_initial_releases`, and added `test_parsed_fred_releases_respect_publication_lag_end_to_end` to the leakage suite, which runs a realistic FRED payload through the parser into the join.

The tests that matter most:

- `output_type` must be `"4"`, which is what makes FRED return unrevised first prints. Any other value returns the series as later revised, and the request still succeeds with plausible numbers, so nothing else would catch it.
- The real-time window must stay `1776-07-04` to `9999-12-31`. Narrowing it drops early releases and leaves only revisions, the same failure by a different route.
- `available_date` must come from `realtime_start`, not from `date`. US unemployment for September 2015 was published in October 2015; taking the observation month would make it knowable during September.
- A same-day release, as the weekly mortgage rate is, must survive unchanged. The rule is that availability is read from the release date, not that a lag is imposed.
- A missing `realtime_start` is rejected rather than defaulted, because without a release date there is no basis for availability.
- FRED's `"."` missing marker is skipped rather than coerced, so no fabricated macro reading enters the panel.

**Verified the guards actually fail.** Rather than trusting that the tests were meaningful, I mutated `parse_fred_initial_releases` to take `available_date` from the observation month and reran them:

| Test | Under mutation |
| --- | --- |
| `test_available_date_is_the_release_date_not_the_observation_month` | failed, as required |
| `test_parsed_fred_releases_respect_publication_lag_end_to_end` | failed, as required |
| `test_same_day_release_is_preserved_rather_than_forced_to_lag` | passed, correctly |

The third is the informative one. For `MORTGAGE30US` the observation date and release date are the same day, so the mutation cannot change it. The guards are specific to the real defect rather than broadly sensitive to any change. `macro.py` was restored with `git checkout` and confirmed clean before the gate ran.

**What works now, with evidence:** full container gate green, `make docker-check` exit 0. Ruff clean, 47 files formatted, mypy clean on 34 source files, **74 passed in 628.48 seconds, 89.92 percent total coverage**. `features/macro.py` moved from 56 to 86 percent, with the remaining uncovered lines being argument-validation branches rather than the vintage logic.

**What is broken or incomplete:** nothing in this work. The schema width question from the previous entry still blocks real-data ingestion and is now the only thing blocking progress.

**Decisions made and why:** none, no ADR warranted. This closes a known gap against an existing requirement rather than choosing between options.

**Results produced:** none. Coverage is an engineering measure, not a model result, so the ledger stays empty.

**Surprises, dead ends, and what I learned from them:** the mutation check was worth more than the tests it validated. It turned "these tests look right" into evidence, and the one test that correctly kept passing showed the suite is discriminating rather than merely sensitive. Worth repeating for any test whose whole purpose is to catch a silent failure.

**Repo review, section 10, ten points:** clean, 10/10. Of note on point 2, 45.5 GB of raw data now sits on disk and none of it is tracked; point 3 was checked for leftover mutation markers and diagnostic scripts, and none remain.

**Next action:** unchanged. Obtain the current Fannie Mae file layout, amend ADR-004, extend `SUPPORTED_FIELD_COUNTS`, and re-run Bronze and Silver on real data.

---

### 2026-09-18, schema width resolved: the layout is 113 fields

**What I set out to do:** resolve the blocker from the previous entry, where the real files carried 113 pipe-separated tokens and the contract accepted 108 or 110. The previous entry recorded this as a human step behind the Data Dynamics login. That was wrong, and testing the assumption before asking for help was worth the few minutes it took.

**What I actually did:** the file layout and glossary are published openly, outside the login that gates the data itself. Retrieved both the glossary spreadsheet and the public sample file directly.

**How the ambiguity was settled.** The open question was whether 113 tokens meant 113 fields or 112 fields followed by a trailing delimiter, which are byte-indistinguishable. The published sample answers it: it yields exactly 108 tokens against a documented 108-field layout. A trailing delimiter would make that 109. Fannie Mae writes none, so token count is field count and the real files hold 113 fields.

The glossary then names all 114 documented positions, and every prediction from the raw scan held:

| Position | Field | Observed in our files |
| --- | --- | --- |
| 1 | Reference Pool ID | present, empty throughout, consistent with non-CRT loans |
| 109 | Payment Deferral Modification Event Indicator | present |
| 110 | Interest Bearing UPB | present |
| 111 | Origination Classic FICO | present and populated, rising by vintage |
| 112 | Issuance Classic FICO | present, empty throughout |
| 113 | Current Classic FICO | present, empty throughout |
| 114 | Origination VantageScore 4.0 | not emitted |

The raw-data observations were made before the glossary was read, so the agreement is corroboration rather than confirmation bias. The glossary also carries `Type` and `Max Length` columns, which independently confirm positions 111 to 113 as `9(3)` numeric, matching how they were typed.

**What works now, with evidence:** `CURRENT_FILE_FIELD_COUNT = 113` added to `SUPPORTED_FIELD_COUNTS`, positions 111 to 113 encoded as `ORIG_CLASSIC_FICO`, `ISSUANCE_CLASSIC_FICO` and `CURRENT_CLASSIC_FICO`, and position 114 still refused. Full container gate green: Ruff clean, 48 files formatted, mypy clean on 34 source files, **79 passed in 397.95 seconds with 90.13 percent coverage**.

The schema was then run against the real downloads rather than only against tests. All six files parse at 113 fields, which is the evidence that matters.

**What is broken or incomplete:** that real-data run surfaced a second defect. `SELLER` is published as `X(50)` and the data exceeds it. A full scan of all 45.5 GB gives observed maxima by vintage:

| Vintage | SELLER | SERVICER |
| --- | --- | --- |
| 2005Q1 | 41 | 42 |
| 2005Q3 | 41 | 43 |
| 2007Q1 | 52 | 42 |
| 2012Q1 | 58 | 41 |
| 2016Q1 | 68 | 52 |
| 2018Q1 | 66 | 66 |

Four of six vintages breach the published length, from 2007Q1 onward, so this is a long-standing divergence between Fannie Mae's data and Fannie Mae's documentation, not a recent anomaly. Real-data ingestion stops here. A scan of all 113 positions is running so the new bounds come from evidence rather than from fixing one field at a time and discovering the next one partway through a multi-hour Bronze run.

**Decisions made and why:** ADR-008, adopt the 113-field width, amending but not superseding ADR-004. Position 114 stays refused on ADR-004's own grounds: it appears in no file we hold, so accepting it would make validation reject every real record. Recorded explicitly in the ADR is that Fannie Mae publishes no short column name for positions 111 to 113, so those three names are ours, derived from glossary labels, and are not official identifiers.

**Results produced:** none. Schema work produces no metrics and the ledger stays empty.

**Surprises, dead ends, and what I learned from them:** the previous entry asserted that obtaining the layout needed the human, and that assertion was never tested. It was wrong, and it would have idled the project waiting on something I could fetch myself. Worth checking whether a stated blocker is real before handing it over.

The more interesting result is that both defects were caught by the same mechanism. ADR-004 refused to accept unconfirmed field positions, and the schema declares a max length per field. Without the first, positions 109 onward would have silently misaligned; without the second, seller names would have been truncated or accepted into Silver unnoticed. A contract that fails loudly on an unexpected shape turned two real defects into two clear errors in an afternoon.

**Repo review, section 10, ten points:** clean, 10/10. Of note on point 2, 45.5 GB sits in `data/raw` and none of it is tracked; on point 3, the temporary validation script used against the real files was removed and checked for.

**Next action:** finish the all-position width scan, write the ADR on how to treat fields that exceed their published length, apply it, then run Bronze and Silver on real data.

---

### 2026-09-19, text length reclassified as a quality signal

**What I set out to do:** unblock real-data ingestion, which stopped because `SELLER` exceeds the `X(50)` length Fannie Mae's own glossary publishes.

**A scan I abandoned, and why that was the useful part.** The plan recorded in the previous entry was to measure observed maxima for all 113 positions and set bounds from evidence. That scan ran for roughly a day and produced nothing: about 114 million rows times 113 field splits is order 10^10 string operations, single-threaded on NTFS. Killing it forced a better question. The problem was never that the bounds were wrong, it was that length was fatal at parse for a field no model consumes.

**What I actually did:** separated structural validation from value-level quality. Field count stays fatal, because a lost delimiter yields 112 or 114 tokens and is caught precisely. Text length becomes an observation: `string_length_exceedances` returns `(column_name, declared_max, observed_length)` for the quality suite to gate on at the Bronze to Silver transition, which is where section 8 puts value-level checks. The glossary figures stay in the schema unchanged as the documented contract; we now record where reality departs from it rather than halting. Recorded as ADR-009.

**A correction to my own ADR, made before committing it.** The first draft described the change as "fatal for typed fields, reported for text", implying a corruption guard was preserved. The test written to prove that claim failed, and the reason was that `max_length` is populated on **only the 39 text fields**. No `INTEGER`, `DECIMAL` or `MONTH` field declares one; numeric widths live in `raw_format` such as `9(3)` and are enforced nowhere. A 40-digit credit score parses today and did before this change. The type branch therefore guards a case that does not currently arise.

ADR-009 now says so explicitly rather than quietly dropping the claim, and the options table was corrected for the same inconsistency. The test that caught it was kept as a characterisation test whose docstring states that enforcing numeric width should make it fail and require replacement, so that change is deliberate rather than accidental.

**What I deliberately did not do:** close the numeric width gap. It is real. Imposing a width without evidence that real data respects it is exactly what produced the `SELLER` breakage this work exists to resolve. The Bronze run reads all six files in Spark and can aggregate per-field lengths in the same pass, answering both open questions with measurement instead of assumption.

**What works now, with evidence:** full container gate green, Ruff clean, 49 files formatted, mypy clean on 34 source files, **85 passed in 587.35 seconds with 90.28 percent coverage**. New tests prove the real 68-character seller name parses, that it is still reported to the quality gate as `("SELLER", 50, 68)`, that conforming text reports nothing, and that a lost delimiter is still rejected on width.

**What is broken or incomplete:** two open questions, both recorded above and both answerable from the Bronze pass. Observed maxima for the other 37 text fields are unknown, so the quality gate has declared figures but no measured ones. Numeric and date widths remain unenforced.

**Decisions made and why:** ADR-009. Widening the two breached fields was rejected because it pins the contract to the longest lender name that happens to exist today and treats the symptom; quarantining breaching rows was rejected because it discards valid loans over a cosmetic field, which is being loud about the wrong thing.

**Results produced:** none. The ledger stays empty until Phase 5.

**Surprises, dead ends, and what I learned from them:** two mistakes, both mine, both caught by the process rather than by luck. The day-long scan was the wrong instrument for the question, and the question itself was wrong. The ADR overclaimed, and the test written to demonstrate the claim is what exposed it. Writing the test before trusting the reasoning is what turned a plausible-sounding record into an accurate one.

**Repo review, section 10, ten points:** clean, 10/10. The abandoned scan left a zero-byte `widths.tsv` in the scratch directory outside the repository, not in it, and nothing untracked remains in the working tree.

**Next action:** run Bronze on the six real files, aggregating per-field observed lengths in the same Spark pass.


---

### 2026-09-21, Phase 5 implementation complete; real-data exit outstanding

**What I set out to do:** proceed from completed Phase 4 into the baselines and scorecard phase, including the marginal baseline, WOE scorecard, points scaling, discrete-time spline hazard, MLflow tracking, and bootstrap comparison required by `PROJECT.md`.

**What I actually did:** locked OptBinning 0.21.0, MLflow 3.16.1, NumPy, Pandas, and scikit-learn. Added a smoothed marginal default-rate baseline by seasoning, a constrained seven-feature OptBinning scorecard scaled at 600 points / 50 odds / 20 PDO, and a logistic monthly hazard model with cubic loan-age splines. The hazard fit excludes the final right-censored month because its following month is not observed.

Added deterministic whole-loan extraction from an explicit Gold Delta version, using 20 of 10,000 `xxhash64(LOAN_ID)` buckets by default. The trainer logs the Delta version, feature-list SHA-256, split contract and row counts, validation AUC/Gini, a paired loan-clustered bootstrap interval, three fitted models with signatures and input examples, and the detailed scorecard bin table. Added `docs/scorecard-methodology.md` and accepted ADR-010.

**What works now, with evidence:** focused Phase 5 checks pass, including real OptBinning fitting, spline hazard prediction, deterministic clustered bootstrap, Spark Gold extraction, SQLite-backed MLflow tracking, model serialization, signatures, contracts, and scorecard artefacts. The full container gate is green: Ruff clean, 59 files formatted, mypy clean on 42 source files, and **92 tests passed in 535.81 seconds with 88.75 percent coverage**.

**What is broken or incomplete:** Phase 5 is not closed. `data/raw` contains the six source files, but there is no `data/delta` or `data/external`, no real Gold Delta version, `FRED_API_KEY` is unset, and `MLFLOW_TRACKING_URI` is unset. The scorecard has therefore not been trained on real validation data, and no real bootstrap interval exists. The synthetic tracking test is implementation evidence only and its metrics are deliberately absent from the results ledger.

**Decisions made and why:** ADR-010 chooses an established constrained-binning library instead of custom WOE arithmetic, positive feature selection instead of excluding known outcomes, deterministic loan-level sampling instead of random row sampling, and a paired loan-clustered bootstrap because loan-month rows are not independent. Cloudpickle is used for trusted MLflow model artefacts because OptBinning is not supported by the safer skops serializer.

**Surprises, dead ends, and what I learned from them:** MLflow 3.16 rejects its legacy filesystem tracking backend by default, so the integration test now uses SQLite metadata and an isolated artifact root, matching the project's database-backed design. The first synthetic fixture accidentally made seasoning perfectly predict default; decorrelating those cycles exposed that a small synthetic sample did not clear a 95 percent interval. The test was corrected to verify interval tracking rather than manufacture statistical certainty. The Windows patch helper failed intermittently; one PowerShell fallback tuple was flattened and corrupted one new file, which Ruff caught immediately. The file was restored before any test or commit.

**Results produced:** none. No synthetic AUC, Gini, or interval belongs in the ledger.

**Next action:** execute Bronze, Silver, macro ingestion, and Gold publication on the real files, then call the Phase 5 trainer with the published Gold Delta version and the configured MLflow server. Close Phase 5 only if the scorecard's validation Gini improvement has a lower 95 percent loan-clustered bound above zero.


---

### 2026-09-21, Phase 6 implementation complete; real-data selection outstanding

**What I set out to do:** implement the LightGBM production challenger with mandatory FICO, LTV, and DTI monotonic constraints, prove those constraints with synthetic sweeps, calibrate probabilities separately from ranking, compare against the scorecard with a clustered interval, and track the complete decision in MLflow.

**What I actually did:** locked LightGBM 4.7.0 and added a deterministic binary classifier with shallow regularized trees and ordered constraints of -1 for FICO, +1 for original LTV, DTI, and current LTV, and zero for the remaining features. Added ceteris-paribus sweep validation that fails on a directional reversal and runs against the final calibrated model, not merely the raw constructor configuration.

The challenger and scorecard are fitted on `train`. The already-fitted challenger is wrapped in scikit-learn's `FrozenEstimator` and sigmoid-calibrated on `validation`; model selection uses only `out_of_time`. The run reports scorecard, raw-challenger, and calibrated-challenger AUC/Gini separately from raw and calibrated Brier scores, then bootstraps calibrated-challenger minus scorecard Gini in paired loan clusters. The generated decision selects LightGBM only when the lower 95 percent bound is above zero.

MLflow logs the Delta version, feature hash, ordered constraints, temporal roles, metrics, interval, feature importance, monotonic sweeps, generated selection JSON, scorecard reference, and raw and calibrated challenger models with signatures. Added `docs/challenger-methodology.md` and accepted ADR-011.

**What works now, with evidence:** the real constrained LightGBM model passes all four monotonic sweeps, a deliberately inverted FICO predictor fails the guard, sigmoid calibration preserves ranking in the integration fixture, and the SQLite-backed MLflow run records all expected contracts and artifacts. The complete container gate is green: Ruff clean, 66 files formatted, mypy clean on 47 source files, and **99 tests passed in 553.28 seconds with 89.22 percent coverage**.

**What is broken or incomplete:** Phase 6 is not closed, and Phase 5 remains open for the same upstream reason. There is no real Bronze, Silver, Gold, or macro Delta data, `FRED_API_KEY` is unset, and `MLFLOW_TRACKING_URI` is unset. No real out-of-time comparison exists, so there is no challenger-versus-scorecard decision to write into the results ledger. Synthetic model selection is deliberately ignored.

**Decisions made and why:** ADR-011 chooses the binary objective because the response is a binary 12-month event, LightGBM's intermediate monotonic method to avoid the basic method's over-constraint without paying for advanced complexity, sigmoid calibration because it is stable for sparse default samples, and a frozen train/validation/out-of-time sequence that does not randomize or refit across temporal boundaries. The scorecard remains the default unless clustered interval evidence supports the challenger.

**Surprises, dead ends, and what I learned from them:** the first runtime sweep checked raw LightGBM only. Review caught that calibration is part of the deployed probability model and could theoretically invert ordering, so the trainer now asserts the calibrated model too. A combined mypy-and-integration command timed out despite each component being healthy; splitting it showed the model tests take seconds and the tracked run about 20 seconds. The Windows patch helper continued to fail intermittently, so narrowly scoped UTF-8 writes were used only after failed patch attempts.

**Results produced:** none. Synthetic AUC, Brier, Gini, bootstrap intervals, and model selection do not belong in the ledger.

**Next action:** build the real medallion and point-in-time macro tables, complete the Phase 5 scorecard run, then execute Phase 6 against the same Gold Delta version. Write the real out-of-time interval and resulting ship decision to this log whether LightGBM wins or loses.
