# ADR-011: Calibrate temporally and require interval evidence to ship LightGBM

- **Status:** accepted
- **Date:** 2026-09-21
- **Phase:** 6

## Context

The production challenger must preserve economically sensible risk directions,
produce calibrated probabilities for later IFRS 9 use, and beat the scorecard
convincingly rather than merely produce a higher point estimate. Random
cross-validation would violate the panel's temporal structure. Calibration also
needs data unseen during tree fitting, while the out-of-time split must remain
available for model selection.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Binary LightGBM objective | Matches the 12-month binary label and scorecard probabilities directly | Does not model exposure counts, which are not the response here |
| Poisson objective | Natural for counts and rates | Target is not a count; complicates probability interpretation and comparison |
| Basic monotonic method | Fastest and strict | Can over-constrain trees and lose useful interactions |
| Intermediate monotonic method | Strict directions with less over-constraint and little added cost | Slightly slower than basic |
| Advanced monotonic method | Most flexible constrained trees | Extra runtime and complexity without evidence it is needed |
| Isotonic calibration | Flexible non-parametric mapping | Can overfit smaller or sparse-default calibration samples |
| Sigmoid calibration | Stable two-parameter mapping; suitable for imbalanced probabilities | Cannot correct arbitrary calibration shapes |
| Select on point-estimate Gini | Simple | Treats sampling noise as evidence and encourages forcing a win |
| Select on clustered interval | Accounts for repeated loan-months and uncertainty | More conservative; may retain the scorecard despite a positive point estimate |

## Decision

Use LightGBM's binary objective with the `intermediate` monotonic method. Apply
constraints of -1 for FICO, +1 for original LTV, DTI, and current LTV, and zero
for the remaining features. Assert the fitted raw model and final calibrated
model over ceteris-paribus sweeps.

Fit trees on `train`, sigmoid calibration on `validation` using a
`FrozenEstimator`, and compare the calibrated challenger with a train-fitted
scorecard on `out_of_time`. Bootstrap paired Gini differences by loan. Select
the challenger only when the lower 95 percent bound is above zero; otherwise
select the scorecard. Record raw and calibrated Brier scores separately from
ranking metrics.

## Consequences

Calibration and model selection consume distinct temporal periods and cannot
silently refit the challenger. The monotonicity requirement applies to the
model actually used for probabilities, not merely to constructor parameters.
An inconclusive challenger result has an explicit outcome: the scorecard ships.

Validation data is now dedicated to probability calibration after Phase 5
scorecard assessment. Out-of-time data is used for the Phase 6 selection
decision, while out-of-vintage remains independent for Phase 7. The fixed
first-pass hyperparameters avoid tuning leakage but may leave challenger
performance on the table; any later tuning protocol requires a new ADR and a
time-respecting inner split.

Revisit sigmoid versus isotonic only when the real validation sample size and
calibration curve demonstrate that the extra flexibility is supportable.
