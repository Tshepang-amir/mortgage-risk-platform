# Phase 5 scorecard methodology

## Purpose and target

The scorecard estimates `DEFAULT_IN_12M` for an at-risk loan-month. Training
uses only Gold rows assigned to `train` where `LABEL_OBSERVED_12M` is true.
Evaluation uses the equivalent rows in `validation`; out-of-time and
out-of-vintage rows remain untouched for later independent validation.

The implementation selects these seven features positively rather than taking
every non-outcome Gold column:

| Feature | Role | Binning constraint |
| --- | --- | --- |
| `CLASSIC_FICO` | Lower of borrower and co-borrower FICO | Event rate descending |
| `OLTV` | Original loan-to-value ratio | Event rate ascending |
| `DTI` | Debt-to-income ratio | Event rate ascending |
| `CURRENT_LTV` | Point-in-time HPI-adjusted current LTV | Event rate ascending |
| `SEASONING_MONTHS` | Loan age at the as-of month | Automatic |
| `UNRATE` | Latest unemployment release available at the as-of month | Automatic |
| `MORTGAGE30US` | Latest mortgage-rate release available at the as-of month | Automatic |

The explicit list is checked against the Phase 4 outcome-column registry before
Gold is collected. Identifier, split, censoring, and outcome columns therefore
cannot enter the model through a broad exclusion rule.

## Binning and score scaling

OptBinning performs supervised optimal binning and transforms each variable to
weight of evidence (WOE). Each variable has at most 12 prebins and every prebin
contains at least 3 percent of the training observations. Missing values retain
OptBinning's dedicated missing bin. The four directional constraints in the
table encode expected risk ordering; no direction is forced on macro variables
or seasoning because their relationship can vary across the mortgage cycle.

A logistic regression is fitted to the WOE values. The score is scaled to 600
points at odds of 50 to 1, with 20 points to double the odds. The fitted bin
table is logged as `scorecard/scorecard-bins.csv` in the MLflow run so every
boundary, WOE value, event rate, and point allocation can be reviewed.

## Baseline and hazard model

The comparison baseline is the smoothed marginal 12-month default rate by
`SEASONING_MONTHS`. An unseen loan age falls back to the training portfolio
rate. This is intentionally simple and establishes whether borrower, leverage,
and macro information improve discrimination beyond loan age alone.

The separate discrete-time hazard model estimates `DEFAULT_NEXT_MONTH`. Loan
age enters through cubic B-splines; all other scorecard features enter linearly
after median imputation and standardization. A row is eligible only when its
next month is observed (`ACT_PERIOD < LAST_OBSERVED_DATE`). The final
right-censored month is never relabelled as a known non-event.

## Reproducibility and evaluation

Each run reads one explicit Gold Delta `versionAsOf`. Loans are retained by a
deterministic `xxhash64(LOAN_ID)` bucket rule, so every month for a selected loan
is kept and repeated runs select the same population. The default sample is 20
of 10,000 buckets (0.2 percent) to keep local WOE fitting tractable; a production
run may increase it explicitly.

MLflow records the Delta version, ordered feature-list SHA-256, split boundaries,
split row counts, validation AUC and Gini, the bootstrap interval, fitted models,
input examples, and signatures. Scorecard improvement is candidate Gini minus
baseline Gini. Its 95 percent percentile interval is paired and clustered by
`LOAN_ID`, preserving within-loan dependence. Phase 5 closes only if the lower
bound is above zero on real validation data. Synthetic test results prove the
pipeline mechanics and are not model-performance evidence.


## References

- OptBinning scorecard API: <https://gnpalencia.org/optbinning/scorecard.html>
- OptBinning binning-process API: <https://gnpalencia.org/optbinning/binning_process.html>
- MLflow Tracking: <https://mlflow.org/docs/latest/ml/tracking>
- MLflow model signatures: <https://mlflow.org/docs/latest/model/signatures/>
