# ADR-010: Use constrained OptBinning with loan-clustered evaluation

- **Status:** accepted
- **Date:** 2026-09-21
- **Phase:** 5

## Context

Phase 5 requires auditable WOE bins, a points-scaled logistic scorecard, a
marginal baseline, a spline hazard model, and a bootstrap comparison. Gold is a
loan-month table: rows from one loan are dependent, forward labels are not known
for every row, and the real table can be too large for local Pandas fitting.
The run must also remain reproducible from a Delta version.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Hand-written quantile bins and WOE arithmetic | Small dependency surface | Reimplements constrained binning, special-value treatment and score scaling; difficult to validate thoroughly |
| OptBinning with explicit per-feature trends | Established constrained optimizer, inspectable tables, native scorecard scaling | Larger numerical dependency tree; model persistence requires trusted artefacts |
| Fit every Gold row locally | No sampling error | Impractical for tens of gigabytes and encourages memory-dependent runs |
| Random row sample and row bootstrap | Simple | Breaks loan histories across samples and understates uncertainty from repeated loan-months |
| Deterministic loan hash sample and loan-clustered bootstrap | Stable population; retains complete selected histories; uncertainty respects the observation unit | Lower effective sample size and requires reporting the sample rule |

## Decision

Use OptBinning 0.21 with a positive seven-feature contract. Constrain FICO to a
descending event-rate trend and original LTV, DTI, and current LTV to ascending
trends. Keep macro variables and seasoning unconstrained. Scale at 600 points,
50-to-1 odds, and 20 PDO.

Read a named Gold Delta version and select whole loans with a deterministic hash
bucket. Compare scorecard and marginal-baseline Gini with a paired percentile
bootstrap clustered by loan. The real-data phase exit requires the lower 95
percent bound of the Gini improvement to exceed zero.

Fit the monthly hazard only on rows with an observed following month. Persist
the baseline, scorecard, hazard model, scorecard bin table, feature hash, split
contract, metrics, input examples, and signatures in one database-backed MLflow
run.

## Consequences

The bin logic and score scaling are reviewable rather than embedded in custom
arithmetic. Re-running the same Delta version and sampling rule selects the same
loans. Confidence intervals no longer pretend loan-months are independent.

The local fit represents a deterministic subset unless the bucket count is
increased. OptBinning and MLflow add a substantial dependency graph. MLflow
models use cloudpickle because OptBinning is not supported by the safer skops
serializer; model artefacts must therefore be loaded only from the trusted
tracking store.

Revisit the sample fraction if the selected real validation population is too
small for stable intervals, or if distributed scorecard fitting becomes
available without changing the bin semantics.
