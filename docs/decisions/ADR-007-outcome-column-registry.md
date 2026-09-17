# ADR-007: Separate outcome columns from features by explicit registry

- **Status:** accepted
- **Date:** 2026-09-17
- **Phase:** 4

## Context

The Gold panel is one flat table. It carries model features, join keys, split
assignments, the forward-looking labels, and survival bookkeeping side by side,
with nothing in the schema distinguishing them.

Writing the temporal-invariance test in section 5 surfaced the risk concretely.
Withholding rows after a cutoff changed three columns that were not labels and
were not obviously outcomes:

| Column | Full build | Rows after cutoff withheld |
| --- | --- | --- |
| `SOURCE_OBSERVED_MONTHS` | 12 | 2 |
| `EXIT_DATE` | 2016-05-01 | null |
| `EXIT_TYPE` | `default` | `right_censored` |

All three are legitimate: survival framing needs a loan's terminal event to
build labels and handle censoring correctly. The danger is not that they exist,
it is that nothing stops Phase 5 selecting them. `EXIT_TYPE` is a restatement
of the answer and `SOURCE_OBSERVED_MONTHS` encodes how long the loan survived.
A model trained on either would score near-perfectly and mean nothing, and the
failure would look like success, which is the worst kind.

PROJECT.md rule 2 requires the leakage test before the feature it guards. The
panel code was written first in an earlier session, so this decision is being
made after the fact. That is recorded honestly rather than papered over.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Naming convention, for example an `OUTCOME_` prefix | Self-describing at the call site; no registry to maintain | Renames every label column, breaking Phase 3 work and the published Delta schema; a convention is not enforced by anything, so it degrades the moment someone forgets |
| Separate labels into their own table, joined on demand | Strongest possible separation; impossible to select by accident | A join on every training run; complicates Delta versioning and reconciliation, whose whole point is one row per at-risk loan-month; disproportionate at this scale |
| Explicit registry in `config/gold.py`, asserted by test | One source of truth shared by builder and tests; costs nothing at runtime; the test turns an unclassified lookahead column into a failure rather than a silent feature | Requires a human to classify each new column, and the registry can drift if the test is weak |
| Leave the distinction implicit, document it in prose | No code change | Exactly the status quo that nearly shipped three unclassified lookahead columns |

## Decision

Add `OUTCOME_COLUMNS` to `src/mortgage_risk/config/gold.py` as the single
registry of columns that depend on observations after a row's own month or that
exist only to construct the label.

The leakage test asserts a **subset** property, not a fixed exclusion list: the
set of columns whose values change when future rows are withheld must be a
subset of `OUTCOME_COLUMNS`. The drift objection is answered by the shape of the
assertion. A new column carrying lookahead fails the suite until somebody
classifies it deliberately, so the registry cannot silently fall behind the
panel.

## Consequences

Makes easy: Phase 5 has an unambiguous, machine-readable answer to "which
columns may a model see". The rule is enforced by a test rather than by prose in
a document nobody rereads.

Makes hard: adding a genuinely future-dependent column now requires an explicit
entry. That friction is the intended effect.

Reversal cost: low. The registry is one frozenset and the test is one
assertion; moving to separate tables later remains open.

Revisit trigger: Phase 5 selecting features. If the modelling code needs more
than this binary split, for example distinguishing join keys and split
assignments from true features, promote the registry to a fuller column-role
mapping rather than adding a second ad hoc set.

Not resolved here: identifiers such as `LOAN_ID` and split assignments such as
`MODELLING_SPLIT` are temporally invariant and therefore pass the leakage test,
but they are not model features either. Phase 5 must still choose features
positively rather than by taking everything that is not an outcome.
