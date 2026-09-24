# ADR-013: Measure the delinquency status domain, and bind the generator to it

- **Status:** accepted
- **Date:** 2026-09-23
- **Phase:** 2 real-data publication

## Context

The Silver quality gate rejected the real panel. The first report named nine
failed expectations with no detail, which read like the data violating nine
contracts at once. It was not. Eight expectations pass on real data. Exactly
one fails:

```
expect_column_values_to_be_in_set[DLQ_STATUS]
  49,297 of 50,000 unexpected (98.59 per cent)
  observed values: "00", "00", "00", ...
```

The allowed set was `[str(v) for v in range(10)] + ["XX", "RA"]`, so `"0"` but
not `"00"`. Fannie Mae writes the field zero-padded. Since `DLQ_STATUS` is
`X(2)` holding "the number of months the obligor is delinquent", two-digit
values such as `"12"` were equally excluded.

The set had been calibrated against `synthetic.py`, which emitted unpadded
`"0"` to `"3"`. The contract therefore encoded the generator's behaviour rather
than the source data's, passed every synthetic test, and rejected 95.7 per cent
of real rows on first contact.

Two supporting facts shaped the decision. The glossary gives **no enumeration**
for position 40, only the description and `X(2)`, so there is no published value
set to adopt. And `gold.py` matches `^\d+$` before casting, so `"03"` and `"3"`
both parse: the hazard logic was never affected, only the gate.

## Evidence

Measured over all **177,385,328** Bronze rows of the six ADR-002 vintages:

| Property | Value |
| --- | --- |
| Distinct values | 101 |
| Numeric | `"00"` to `"99"`, zero-padded, exactly 100 values |
| Non-numeric | `"XX"` only |
| `"00"` share | 95.71 per cent |
| `"XX"` share | 0.88 per cent |
| `"RA"` | absent |

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Widen the set to include `"00"` | One-line fix | Treats the symptom. `"12"` and the rest would still be rejected, and the generator stays divergent |
| Accept any two-character value | Never fails again | Discards the gate. A corrupted column would pass |
| Drop the expectation | Simple | Removes the check that found the defect |
| **Measure the domain, correct the set, and bind the generator to it** | Contract reflects the source; divergence becomes impossible to reintroduce silently | Requires a full scan, and pins the set to six vintages |
| Also restore `"RA"` on documentation | Guards a possible future code | Not observed in 177 million rows. Allowing unevidenced values is how this defect arose |

## Decision

Set the allowed domain to zero-padded `"00"` through `"99"` plus `"XX"`, as
measured, and record the measurement in the code so the figure is traceable.

Fix `synthetic.py` to emit the same zero-padded format. Fixing only the
expectation would leave the generator producing a value domain the real data
does not contain, and every downstream test would keep exercising it.

Add `test_generated_delinquency_statuses_satisfy_the_silver_contract`, which
asserts the generator's output is a subset of the allowed set. This ties the two
together so a future divergence fails in seconds rather than after a two and a
half hour Silver build. Verified by mutation: reverting the generator to
unpadded output makes the test fail and name the offending values.

`"RA"` is **not** allowed back on the strength of documentation alone. An
unobserved code should fail this gate loudly, which is precisely how the
mismatch was caught.

## Consequences

Makes easy: Silver publication proceeds, and the contract now describes the
source rather than the fixture.

Makes hard: a seventh vintage introducing a new code fails the gate. That is
intended. The remedy is to measure and extend deliberately, as here.

Reversal cost: low, one constant and one generator branch.

Revisit trigger: ingesting vintages outside ADR-002's six, where the domain must
be re-measured rather than assumed to hold.

## What this says about the synthetic strategy

Phase 1's exit criterion was a synthetic panel "structurally identical" to the
real files. It satisfied the schema's widths and types, and was still wrong
about a value domain, which no structural check could catch. Synthetic data
validates plumbing, not semantics. Where a contract encodes a value domain, it
must be derived from the source or from published documentation, never from the
generator, and the two should be tied together by a test.
