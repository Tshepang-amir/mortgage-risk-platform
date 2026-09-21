# Phase 6 challenger methodology

## Model and target

The challenger estimates `DEFAULT_IN_12M` on the same at-risk loan-month rows
and seven-feature contract as the WOE scorecard. It uses LightGBM's binary
objective so its probabilities, Gini, and calibration are directly comparable
with the scorecard. A Poisson objective is not used because the target is a
binary event indicator rather than a count or exposure-rate response.

The fixed first-pass configuration is deliberately modest: 300 trees, learning
rate 0.05, 15 leaves, maximum depth 5, minimum 50 rows per leaf, row and feature
subsampling, and L2 regularization. The random seed, one-thread execution,
column-wise learner, and deterministic mode make repeated local fits stable.
No random split or hyperparameter search is used.

## Monotonic constraints

Constraints are passed in the exact feature order used for fitting:

| Feature | Constraint | Required relationship |
| --- | ---: | --- |
| `CLASSIC_FICO` | -1 | Higher FICO cannot increase predicted default risk |
| `OLTV` | +1 | Higher original LTV cannot reduce predicted default risk |
| `DTI` | +1 | Higher DTI cannot reduce predicted default risk |
| `CURRENT_LTV` | +1 | Higher current LTV cannot reduce predicted default risk |
| `SEASONING_MONTHS` | 0 | Unconstrained |
| `UNRATE` | 0 | Unconstrained |
| `MORTGAGE30US` | 0 | Unconstrained |

LightGBM's `intermediate` monotonic method is used because the basic method can
over-constrain the trees, while the advanced method adds complexity without
real-data evidence that it is needed. Configuration is not treated as proof:
the fitted model is scored over ceteris-paribus synthetic sweeps spanning FICO,
original LTV, DTI, and current LTV. Any directional reversal fails the run.

## Temporal calibration and evaluation

Both the scorecard reference and raw challenger are fitted only on `train`.
The already-fitted challenger is wrapped in scikit-learn's `FrozenEstimator`
and sigmoid-calibrated on `validation`, so calibration cannot refit its trees.
The calibrated model must pass the same monotonic sweeps; this catches a
pathological calibrator that reverses model ordering.

Model selection happens only on `out_of_time`. Ranking and calibration are
assessed separately:

- scorecard, raw-challenger, and calibrated-challenger AUC/Gini measure ranking;
- raw and calibrated Brier scores measure probability calibration;
- calibrated challenger minus scorecard Gini is bootstrapped in paired samples
  clustered by `LOAN_ID`.

The challenger ships only when the lower 95 percent bound of that Gini
improvement is above zero. Otherwise the scorecard ships, including when the
point estimate is positive but inconclusive. Out-of-vintage evaluation remains
untouched for the broader Phase 7 validation pack.

## Tracking and evidence

One MLflow run records the Gold Delta version, feature hash, ordered monotonic
constraints, temporal split roles, ranking and Brier metrics, bootstrap interval,
monotonic sweep results, feature importance, fitted raw and calibrated models,
the scorecard comparator, signatures, input examples, and a generated model
selection JSON artifact.

Synthetic tests establish that the implementation and guards work. They do not
decide which model ships. Phase 6 remains open until the run is executed on a
real Gold Delta version and the resulting decision is written to `PROGRESS.md`.

## References

- LightGBM parameter reference: <https://lightgbm.readthedocs.io/en/latest/Parameters.html>
- LightGBM `LGBMClassifier`: <https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMClassifier.html>
- scikit-learn calibration: <https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html>
- scikit-learn `FrozenEstimator`: <https://scikit-learn.org/stable/modules/generated/sklearn.frozen.FrozenEstimator.html>
