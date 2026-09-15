# PROJECT.md

Master context for `mortgage-risk-platform`. Claude Code reads this file at the start of every session, before doing anything else. It is the single source of truth for scope, architecture, standards and phase boundaries. If something here conflicts with a chat instruction, ask rather than assume.

---

## 1. What this is

A production-grade mortgage credit risk platform: probability of default modelling on real Fannie Mae loan performance data, an IFRS 9 expected credit loss layer on top, and a full model validation pack of the kind a bank's model risk function would demand.

This is a portfolio project targeting Senior ML Engineer and Senior Data Scientist roles in South African banking. It is built to be defended in a technical interview, not to win a leaderboard.

### Repository
`mortgage-risk-platform`

### The decision this system supports
Given a mortgage loan and a point in time, estimate the probability that it enters 90+ days delinquency within the next 12 months, conditional on having survived to that point. Feed that estimate into IFRS 9 staging and expected credit loss calculation for provisioning and portfolio monitoring.

### The user
A credit risk analyst or portfolio manager reviewing book quality, and a model validator challenging the model before it goes live.

### What success looks like
Not a Gini number. Success is a validation report that a model risk function could not dismiss, a pipeline that reproduces exactly, and a documented account of where the model fails.

---

## 2. Non-negotiable principles

These govern every decision. Violating one is a bug even if the code runs.

1. No random splits, ever. This is temporal panel data. Every split is by time or by origination vintage.
2. No leakage. A feature computed at time t uses only information available at time t. When in doubt, write the test first.
3. The simple model is the reference, not the fallback. A WOE scorecard is the regulatory benchmark. The gradient boosting model must beat it convincingly or it does not ship.
4. Monotone constraints are mandatory on FICO, LTV and DTI. A validator will check. A model that says worse FICO implies lower risk is rejected regardless of discrimination.
5. Every number in any document is reproducible from code in this repo. No hand-typed metrics.
6. Report where the model fails. Segment performance, stress windows, calibration drift. A single headline metric is a junior artefact.
7. Honest scoping beats fake scale. We subset the data deliberately and say so. We do not pretend to have processed 300 GB on a laptop.
8. Reject components that are not justified. No Kafka. No feature store. No real-time serving. Batch is correct here and the README says why.

---

## 3. Data

### Primary source
Fannie Mae Single-Family Loan Performance Data.
`https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data`

Real loan-level records from 1999 onward. Single-file format, 108 fields, one row per loan per month. Fannie Mae publishes a glossary and file layout document plus statistical summaries.

HUMAN STEP REQUIRED. This data needs free registration and manual download. Claude Code cannot fetch it. Phase 1 defines exactly which files the human must place in `data/raw/` and halts until they exist. Do not attempt to scrape or bypass this.

### Scope decision
We do not download full history. We take the following acquisition quarters, chosen to span benign, crisis and shock regimes:

| Quarter | Purpose |
| --- | --- |
| 2005Q1, 2005Q3 | Pre-crisis origination, seasons into the crash |
| 2007Q1 | Peak-risk vintage |
| 2012Q1 | Post-crisis tightened underwriting |
| 2016Q1 | Benign, becomes out-of-time test |
| 2018Q1 | Seasons into the 2020 shock |

Six quarters. Each quarter's performance file covers that cohort's full monthly history. This is enough for real out-of-vintage validation and keeps the working set inside laptop and Databricks Free Edition limits.

Record this as ADR-002 with the reasoning, including what we lose by subsetting.

### Macro covariates
FRED (`https://fred.stlouisfed.org`), free API. Series:
- `UNRATE` national unemployment
- `CSUSHPINSA` Case-Shiller national home price index
- `MORTGAGE30US` 30-year fixed mortgage rate

Joined point-in-time to each loan-month. Critical: a loan-month at date d joins the macro value published for d, never a later revision.

### Synthetic fallback
Before real data arrives, Phase 1 builds `src/data/synthetic.py` which generates a structurally identical panel with known ground truth. This lets every downstream phase be developed and tested without the real files, and it gives us fixtures for unit tests. It is not a substitute for the real analysis and must never appear in results.

---

## 4. The modelling problem

### Formulation
Discrete-time hazard, not flat binary classification. For each loan-month observation, model

P(default in months t+1 to t+12 | loan survived to month t)

The unit of observation is the loan-month, not the loan. A loan contributes one row per month it remains in the panel and exits when it defaults, prepays or reaches the observation window end.

This framing matters. It handles censoring correctly, it lets loan age enter as a covariate, and it is how mortgage risk is actually modelled. Flat classification on loan-level rows is the junior version.

### Default definition
D90+: current loan delinquency status reaches 90 days or more past due. Record the exact field and code mapping from the Fannie Mae glossary in `docs/data-dictionary.md`. Also handle the competing exits: prepayment and repurchase are censoring events, not negatives.

### Models to build, in this order

| # | Model | Role |
| --- | --- | --- |
| 1 | Marginal rate by loan age | Naive baseline. Everything must beat this. |
| 2 | WOE-binned logistic scorecard | Regulatory reference model. Interpretable, points-based. |
| 3 | Discrete-time hazard logistic with loan-age splines | Correct statistical form, still interpretable. |
| 4 | LightGBM with monotone constraints, Poisson or binary objective | Production challenger. |
| 5 | Optional: competing risks separating prepayment from default | Only if phases 1 to 8 are complete and time allows. |

Model 4 must beat model 2 on out-of-time Gini by a margin whose bootstrap confidence interval excludes zero. If it does not, model 2 ships and we write that up. Choosing the simpler model on evidence is a stronger result than forcing the complex one.

### Monotone constraint directions
- FICO at origination: higher score, lower default hazard (negative)
- Original LTV and current LTV: higher LTV, higher hazard (positive)
- DTI at origination: higher DTI, higher hazard (positive)

Encode these explicitly in the LightGBM `monotone_constraints` parameter and assert them in a test by scoring synthetic monotone sweeps.

---

## 5. Validation strategy

This is the centrepiece of the project. It gets more care than the modelling.

### Splits
| Split | Definition |
| --- | --- |
| Train | Origination quarters 2005Q1, 2005Q3, 2007Q1, 2012Q1; loan-months up to 2015-12 |
| Validation | Same vintages, loan-months 2016-01 to 2017-12 |
| Out-of-time test | Loan-months 2018-01 onward, all vintages |
| Out-of-vintage test | 2016Q1 and 2018Q1 vintages held out entirely from training |

Out-of-vintage is the harder and more informative test. A model that generalises across time but not across underwriting cohorts is not deployable.

### Stress windows
Evaluate separately and report as its own table section:
- 2008-01 to 2010-12, the financial crisis
- 2020-03 to 2020-12, the pandemic shock and forbearance period

Note explicitly that 2020 forbearance distorts the delinquency signal. Handling this honestly, rather than silently, is a senior detail.

### Metrics and why each one
| Metric | Reason |
| --- | --- |
| Gini / AUC with bootstrap CI | Discrimination. A point estimate without an interval is not a result. |
| KS statistic | Industry standard in credit scorecards. |
| Calibration by decile, and by vintage | IFRS 9 ECL depends on absolute probability levels, not ranking. |
| Brier score and Brier skill score against the base rate | Brier alone is misread at low prevalence. Always report skill relative to the marginal rate. |
| PSI on the score distribution | Population stability across vintages and time. |
| CSI per feature | Characteristic stability. Identifies which driver shifted. |
| Default rate: predicted vs actual by segment | The plot a validator asks for first. |
| Performance by LTV band, FICO band, loan age, geography, vintage | A single headline number hides the failure mode. |

### Leakage controls
Three tests that must exist and must pass:
1. Temporal invariance: a feature value computed for loan L at month t is identical whether or not rows after t exist in the source table.
2. Split integrity: no loan appears in both a training and an out-of-vintage test partition.
3. Macro lag: no macro value dated after the observation month enters any feature.

---

## 6. IFRS 9 expected credit loss layer

Sits on top of the PD model. Converts a hazard into a provision.

### Components
- PD: 12-month and lifetime, derived from the hazard model by chaining monthly survival probabilities.
- LGD: loss given default. Derive empirically from the Fannie Mae loss fields where available; otherwise use a documented, simple assumption and label it as such. Do not invent a sophisticated LGD model.
- EAD: exposure at default, approximated by current unpaid principal balance.

### Staging
| Stage | Criterion | ECL |
| --- | --- | --- |
| 1 | No significant increase in credit risk since origination | 12-month ECL |
| 2 | Significant increase in credit risk, not yet impaired | Lifetime ECL |
| 3 | Credit-impaired | Lifetime ECL |

Define the significant-increase trigger explicitly, for example a relative PD increase threshold plus a 30-days-past-due backstop. Document the choice and its sensitivity in `docs/ifrs9-methodology.md`.

### Output
A portfolio ECL figure by vintage and by stage, with a sensitivity table showing how ECL moves under the stress windows. This is the artefact that makes the project bank-native.

---

## 7. Explainability, fairness and governance

### Reason codes
SHAP values on the production model mapped to a ranked list of adverse-action style reason codes. Each code is a plain-language sentence a credit officer could use. The mapping table lives in `governance/reason_codes.md`. This is explainability with a regulatory purpose, not a feature importance plot.

### Fairness and proxy discrimination
Fannie Mae data does not contain protected attributes, which is itself the point. Analyse geography-adjacent and income-adjacent features as proxies: state, MSA, loan purpose, occupancy, property type. Report performance and approval-equivalent rates across geographic segments and discuss what could not be tested and why.

Reference the known result that fairness through unawareness fails, since ZIP-adjacent features carry protected-class signal. Cite Hurlin, Perignon and Saurin (2022) in the write-up.

### South African regulatory framing
The README and governance docs must frame the work against the regime the target employers operate under:
- National Credit Act 34 of 2005: affordability assessment and reckless lending provisions.
- IFRS 9: the impairment model implemented in Phase 7.
- POPIA: data handling, minimisation, and why this project uses US public data rather than local personal data.
- Note that the EU AI Act classifies creditworthiness evaluation of natural persons as high-risk under Annex III point 5(b), with Chapter III obligations now applying from 2 December 2027 following Regulation (EU) 2026/1744. Verify currency before quoting.

Two or three sentences each. This costs nothing and is noticed immediately.

### Governance artefacts required
| File | Contents |
| --- | --- |
| `governance/validation_report.md` | SR 11-7 structure: conceptual soundness, outcomes analysis, ongoing monitoring |
| `governance/model_card.md` | Intended use, data, metrics by segment, limitations, out-of-scope uses |
| `governance/data_card.md` | Provenance, subsetting decision, known quality issues, licence |
| `governance/reason_codes.md` | SHAP to adverse-action mapping |
| `governance/monitoring_policy.md` | PSI and CSI thresholds, recalibrate vs retrain triggers, owners |
| `governance/rollback_runbook.md` | Step-by-step model and pipeline rollback |
| `docs/ifrs9-methodology.md` | Staging rules, PD term structure, LGD and EAD assumptions |

---

## 8. Architecture

### Data platform
Medallion on Delta Lake.

| Layer | Contents | Key property |
| --- | --- | --- |
| Bronze | Raw acquisition and performance files as landed, plus ingest timestamp and source filename | Append-only, immutable, never edited |
| Silver | Typed, deduplicated, validated, with codes decoded to labels and a slowly-changing servicer dimension | Schema-enforced, contract-tested |
| Gold | Loan-month panel with point-in-time macro joins, engineered features, and the labelled modelling dataset | Point-in-time correct, reproducible by Delta version |

Delta time travel is the reproducibility mechanism. Every MLflow run logs the Delta table version it trained on.

### Processing
PySpark for Bronze to Gold. Local Spark inside WSL2 for development, Databricks Free Edition for larger passes. Pandas or Polars only downstream of Gold, on the sampled modelling frame.

### Orchestration
Airflow in Docker Compose. Two DAGs:
- `ingest_loan_performance`: monthly ingestion, file-availability sensor, idempotent MERGE into Delta, DQ gates, SLA miss alerting.
- `backfill_loan_performance`: replays any historical month range. This exists to demonstrate backfill reasoning, which is the part interviewers probe.

Idempotency is a hard requirement. Running the same month twice must not duplicate rows. Write the test that proves it.

### Experiment tracking
Self-hosted MLflow backed by Postgres and local artifact storage, via Docker Compose. Every run logs: Delta version, feature list hash, split definition, all metrics including segment breakdowns, the validation report artefact, and the model with a signature.

Model registry with aliases. A model reaches `production` only after the validation notebook passes and a human sets the alias. Automated promotion is explicitly not built here, and the README says why that differs from the fraud platform.

### Serving
Batch scoring job producing a scored portfolio table in Delta, plus a small FastAPI read API exposing portfolio ECL and segment risk. A Streamlit page for the validator view: calibration curves, PSI trend, ECL by stage and vintage.

Say in the README that real-time serving is not justified for monthly portfolio rescoring. That sentence is the point.

### Monitoring
Lighter than the fraud platform, and correctly so.
- Vintage-level PSI on the scoring population
- CSI per feature
- Calibration drift as new performance months land
- Pipeline health: run duration, row counts per layer, data freshness, DQ pass rate
- Grafana board fed by Prometheus, or by a simple metrics table if Prometheus proves disproportionate. Decide and record as an ADR.

### Data quality
Great Expectations or Pandera suites gating each layer transition. Failures quarantine the batch and halt the DAG. Fail loud, never silently coerce.

### Golden-record test
Fannie Mae publishes statistical summaries of the dataset. Build a test that reproduces their published summary figures from our pipeline and asserts equality within tolerance. This validates the entire ingestion path against an external source of truth. It is a small piece of work with a disproportionate credibility payoff.

---

## 9. Repository layout

```
mortgage-risk-platform/
├── PROJECT.md                   # this file
├── PROGRESS.md                  # session log, Claude Code appends here
├── README.md                    # recruiter-facing, written last
├── pyproject.toml
├── Makefile
├── docker-compose.yml
├── .pre-commit-config.yaml
├── .env.example
│
├── data/
│   ├── raw/                     # gitignored, human places files here
│   ├── external/                # FRED pulls, cached
│   └── README.md                # exactly which files, where to get them
│
├── src/mortgage_risk/
│   ├── config/                  # typed settings, no magic numbers in code
│   ├── data/
│   │   ├── schemas.py           # Fannie Mae 108-field layout, typed
│   │   ├── synthetic.py         # structurally identical generator
│   │   ├── bronze.py
│   │   ├── silver.py
│   │   └── gold.py              # loan-month panel construction
│   ├── features/                # WOE binning, engineered features, macro joins
│   ├── models/
│   │   ├── baseline.py
│   │   ├── scorecard.py         # WOE + logistic
│   │   ├── hazard.py            # discrete-time hazard
│   │   └── gbm.py               # LightGBM with monotone constraints
│   ├── validation/
│   │   ├── splits.py
│   │   ├── metrics.py           # Gini, KS, PSI, CSI, Brier skill
│   │   ├── calibration.py
│   │   ├── stability.py
│   │   └── bootstrap.py
│   ├── ifrs9/
│   │   ├── pd_term_structure.py
│   │   ├── lgd.py
│   │   ├── ead.py
│   │   └── staging.py
│   ├── explain/                 # SHAP, reason code mapping
│   ├── fairness/                # proxy analysis
│   ├── serve/                   # batch scorer, FastAPI read API
│   ├── monitoring/              # PSI jobs, calibration drift
│   └── common/                  # logging, config, spark session, io
│
├── dags/
│   ├── ingest_loan_performance.py
│   └── backfill_loan_performance.py
│
├── tests/
│   ├── unit/
│   ├── property/                # Hypothesis: leakage and money invariants
│   ├── integration/             # end-to-end on synthetic data
│   ├── data/                    # Great Expectations suites
│   └── golden/                  # Fannie Mae published summary reproduction
│
├── notebooks/                   # exploration only, never the source of truth
│   └── README.md                # says exactly that
│
├── governance/                  # see section 7
├── docs/
│   ├── architecture.md
│   ├── data-dictionary.md
│   ├── evaluation.md
│   ├── ifrs9-methodology.md
│   └── decisions/               # ADR-001 onward
│
├── dashboards/                  # Streamlit validator view
├── infra/                       # Terraform, if deployed
└── .github/workflows/
    ├── ci.yml
    ├── data-quality.yml
    └── train.yml
```

---

## 10. Engineering standards

Non-negotiable, enforced in CI.

- Python 3.11 or 3.12. Type hints on every public function. `mypy` clean.
- `ruff` for lint and format, zero errors.
- `pre-commit` configured and installed, including `detect-secrets`.
- `pytest` with meaningful tests, not coverage theatre. Target 70 percent on `src/`, but a test that asserts a real invariant beats five that assert a getter.
- Hypothesis property tests for: leakage invariance, monotone constraint behaviour, money and rate arithmetic, WOE binning stability.
- No secrets in the repo. `.env.example` only.
- No magic numbers in logic. Thresholds live in `src/mortgage_risk/config/`.
- Every non-obvious decision becomes an ADR in `docs/decisions/`.
- Conventional commits. Small, reviewable commits with real messages.
- Notebooks are scratch. Anything that matters gets moved into `src/`.

### Repository hygiene

The repo is a deliverable in its own right. A recruiter or interviewer will browse it, and clutter reads as carelessness. Keep it clean continuously, not in a cleanup pass at the end.

At the end of every working session, before updating PROGRESS.md, run a repo review and fix anything that fails:

1. No generated artefacts committed. `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.ipynb_checkpoints`, `*.pyc`, `.DS_Store`, `spark-warehouse/`, `metastore_db/`, `derby.log`, `mlruns/`, `.coverage`, `htmlcov/`, `dist/`, `build/`, `*.egg-info`. All gitignored from Phase 0, never committed.
2. No data in git. Everything under `data/` is ignored except `data/README.md` and small test fixtures under 100 KB. Delta tables, Parquet, CSV, checkpoints stay out.
3. No dead files. Scratch scripts, `test2.py`, `old_`, `_backup`, `copy of`, commented-out blocks kept "just in case". Delete them. Git history is the backup.
4. No orphan modules. Every file in `src/` is imported by something or tested by something. If neither, either wire it in or remove it.
5. No empty directories left behind after refactors, and no placeholder files that no longer serve a purpose.
6. Structure matches PROJECT.md section 9. If a file has drifted into the wrong package, move it. If PROJECT.md is genuinely wrong, say so and propose a change rather than diverging silently.
7. Notebooks stay scratch. Anything a result depends on lives in `src/`. Strip notebook outputs before committing.
8. Dependencies are real. Nothing in `pyproject.toml` that is not imported. Remove experiments that did not survive.
9. Naming is consistent. `snake_case` modules, no abbreviations that need a glossary, no mixed conventions across packages.
10. `git status` is clean at the end of a session. Nothing untracked that should be committed, nothing committed that should be ignored.

Add a `make clean` target that removes local caches and build artefacts, and a `make check` target that runs lint, type check, tests and a structure assertion in one command. Run `make check` before every commit.

Report the outcome of the repo review in the PROGRESS.md session entry. One line if clean, a list of what was fixed if not.

### Environment notes
- Windows host: run all Spark work inside WSL2. Native Windows Spark wastes days on winutils and path length. VS Code WSL extension makes this transparent.
- Docker Desktop with the WSL2 backend.
- Spark is memory-bound on a laptop. If passes fail on memory, reduce the quarter set before tuning executor config, and record the decision.
- Databricks Free Edition limits: serverless only, small clusters, one SQL warehouse at 2X-Small, max 5 concurrent job tasks, one active pipeline per type, no GPUs, restricted outbound network, no R or Scala. Exceeding quota shuts down compute for the rest of the day. Plan in small batches.

---

## 11. Phases

Each phase has an exit criterion. Do not start the next phase until the current one is met and PROGRESS.md is updated. If a phase cannot be completed, write why in PROGRESS.md and stop rather than working around it.

### Phase 0: Foundation
Repo structure, `pyproject.toml`, pre-commit, ruff, mypy, pytest skeleton, Docker Compose skeleton, Makefile, `.env.example`, ADR template, PROGRESS.md initialised, empty CI workflow that runs lint and tests.
Exit: `make test` and `make lint` pass on an empty codebase. CI green on first push.

### Phase 1: Data contracts and synthetic generator
Fannie Mae 108-field schema encoded as typed definitions. `data/README.md` naming the exact six quarterly files and where the human gets them. Synthetic panel generator producing the identical schema with known ground truth. Test fixtures built from synthetic data.
Exit: synthetic panel generates, validates against schema, and is usable by every downstream test. Human instruction file is unambiguous.

### Phase 2: Bronze and Silver
Bronze ingestion as landed with provenance columns. Silver: typing, deduplication, code decoding, servicer dimension, Great Expectations suite gating the transition. Idempotency proven by test.
Exit: running ingestion twice produces identical row counts. DQ suite passes on synthetic and, once available, on real data.

### Phase 3: Golden-record test
Reproduce Fannie Mae's published statistical summary from the Silver layer. Assert equality within documented tolerance.
Exit: the test passes on real data, or the discrepancy is investigated and documented in PROGRESS.md with a root cause.

### Phase 4: Gold panel
Loan-month panel construction. Survival framing with correct censoring for prepayment and repurchase. Point-in-time FRED macro joins. Loan age, seasoning, current LTV derivation. The three leakage tests.
Exit: all three leakage tests pass. Panel row counts reconcile to loan counts times observed months.

### Phase 5: Baselines and scorecard
Marginal hazard baseline. WOE binning with documented bin logic. Logistic scorecard with points scaling. Discrete-time hazard logistic with loan-age splines. MLflow tracking from this phase onward, logging Delta version.
Exit: scorecard trained, tracked, and beating the marginal baseline on the validation split with a reported bootstrap interval.

### Phase 6: Challenger model
LightGBM with monotone constraints on FICO, LTV, DTI. Monotonicity asserted by test on synthetic sweeps. Calibration applied and assessed separately from ranking.
Exit: challenger trained and tracked. A written decision in PROGRESS.md on whether it beats the scorecard, with the bootstrap interval as evidence. Either outcome is acceptable. Fabricating a win is not.

### Phase 7: Validation pack
All splits evaluated. Stress windows evaluated separately. Full metric suite including segment breakdowns. Calibration curves by decile and vintage. PSI and CSI. `docs/evaluation.md` generated from code.
Exit: every number in `docs/evaluation.md` is produced by a script in the repo. No hand-typed figures.

### Phase 8: IFRS 9 ECL layer
PD term structure from chained survival. LGD derived or documented as an assumption. EAD from current UPB. Staging rules with a documented significant-increase trigger. Portfolio ECL by vintage and stage. Sensitivity under stress windows.
Exit: ECL table produced and reconciled. `docs/ifrs9-methodology.md` complete.

### Phase 9: Explainability, fairness, governance
SHAP reason codes mapped to adverse-action language. Proxy discrimination analysis across geographic and loan-characteristic segments. All seven governance documents written, each grounded in results from earlier phases.
Exit: validation report complete in SR 11-7 structure. Every claim in it traceable to a script output.

### Phase 10: Orchestration and serving
Airflow ingestion DAG and backfill DAG. Idempotent MERGE. SLA alerting. Batch scoring job. FastAPI read API. Streamlit validator dashboard. Monitoring jobs for PSI and calibration drift.
Exit: backfill DAG replays a historical month range and produces identical output to the original run.

### Phase 11: Packaging
README with a results scorecard at the top, architecture diagram, how to run, limitations, and the South African regulatory framing. Demo recording. Final ADR review.
Exit: a stranger can clone the repo and reproduce the headline numbers from the README instructions alone.

---

## 12. How Claude Code works in this repo

1. Read PROJECT.md at the start of every session. Read PROGRESS.md to find where work stopped.
2. State which phase you are in and what the exit criterion is before writing code.
3. Work in small, committed increments. Run lint and tests before every commit.
4. Update PROGRESS.md at the end of every working session and at every phase boundary, using the template in that file.
5. When a decision has more than one defensible option, write an ADR and state the reasoning. Do not silently pick.
6. When blocked on something only the human can do, such as downloading the Fannie Mae files, stop and say so clearly in PROGRESS.md. Do not work around it with fabricated data presented as real.
7. Never write a metric into a document by hand. Documents are generated or quote script output.
8. If a result is disappointing, report it. A model that loses to the scorecard is a finding, not a failure.

### Definition of done for any task
- Code written, typed, linted, tested
- Tests assert behaviour that would actually break
- Decisions recorded where non-obvious
- Repo review from section 10 run and clean
- PROGRESS.md updated, including the repo review outcome
- Nothing hand-typed that should be generated
