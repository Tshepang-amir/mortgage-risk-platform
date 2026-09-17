# ADR-006: Golden-record population must match the publication

- **Status:** accepted
- **Date:** 2026-09-17
- **Phase:** 3

## Context

PROJECT.md asks Phase 3 to reproduce Fannie Mae's published statistical
summary from Silver. The July 2026 Primary statistical summary covers loans
acquired from January 2000 through March 2026. ADR-002 deliberately limits this
project to six acquisition quarters: 2005Q1, 2005Q3, 2007Q1, 2012Q1, 2016Q1
and 2018Q1.

The published rows are grouped by origination year, not acquisition quarter.
Loans originated in a given year can appear in several acquisition-quarter
files. Therefore an annual published row cannot be reconstructed from one or
two selected acquisition quarters, and a difference is expected rather than a
pipeline defect. Fannie Mae's tutorial also says the identical-summary check
requires the full dataset.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Compare the six-quarter summary with the published annual rows | Superficially satisfies the requested test shape | Produces guaranteed false failures and confuses population difference with ingestion error |
| Download every quarter from 2000Q1 through 2026Q1 | Permits a like-for-like external check | Reverses ADR-002, exceeds the deliberate laptop scope, and still requires the human-controlled download |
| Reproduce the method and fail closed on population mismatch | Preserves the useful calculation, makes invalid comparisons impossible, and states the limitation honestly | The external equality assertion remains unavailable for the scoped dataset |

## Decision

Implement Fannie Mae's acquisition-summary method from Silver: one latest row
per loan, missing OCLTV replaced with OLTV, minimum borrower/co-borrower Classic
FICO, and original-UPB-weighted averages. Pin the July 2026 published values and
source PDF hash in code.

Before comparing metrics, require exact equality between the acquisition
quarters represented by Silver provenance and the publication's 2000Q1 to
2026Q1 population. The six-quarter project scope must raise a population
mismatch; it must never report a misleading golden-record failure or pass.

## Consequences

The summary transformation and tolerance logic are fully testable on synthetic
Silver data, while the incompatible external comparison fails with its root
cause. Phase 3 closes under its documented-discrepancy exit path rather than by
claiming an equality that cannot hold.

Revisit only if a future scope decision supplies every acquisition quarter for
the exact publication snapshot, or Fannie Mae publishes quarter-level control
totals matching ADR-002's six files. A new PDF release must be treated as a new
reference with a new hash and acquisition-period boundary.
