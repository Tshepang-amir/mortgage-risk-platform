# ADR-008: Adopt the 113-field raw layout, amending ADR-004

- **Status:** accepted; amends ADR-004, which remains the record of why the narrower widths were adopted first
- **Date:** 2026-09-18
- **Phase:** 1, unblocking real-data work in Phases 2 and 3

## Context

ADR-004 encoded the 108-field sample layout plus the two official R-importer
extension fields, and deliberately withheld judgement on the rest:

> Positions 111 to 114 are documented as forward glossary fields but are not
> accepted as raw-file columns until the sample file or official importer
> confirms that shape.

The six real quarterly files arrived on 2026-09-17 and every record carries 113
pipe-separated tokens, so ingestion could not run. Two readings were possible
from the data alone, and they are byte-indistinguishable: 113 real fields, or
112 fields followed by a trailing delimiter. An off-by-one would have shifted
every column while still parsing cleanly.

## Evidence

**The published sample file settles the delimiter question.** Fannie Mae's
public sample, the file ADR-004 named as one of its two triggers, yields
exactly 108 tokens under the same split, against a documented 108-field layout.
Had records carried a trailing delimiter it would yield 109. Fannie Mae emits
none, so token count equals field count and the real files hold 113 fields.

**The published glossary names every position.** The combined glossary
spreadsheet documents 114 positions. Positions 109 to 114 are:

| Position | Field | Present in our files |
| --- | --- | --- |
| 109 | Payment Deferral Modification Event Indicator | yes |
| 110 | Interest Bearing UPB | yes |
| 111 | Origination Classic FICO | yes, populated |
| 112 | Issuance Classic FICO | yes, empty throughout |
| 113 | Current Classic FICO | yes, empty throughout |
| 114 | Origination VantageScore 4.0 | no, not yet emitted |

**The raw files agree with that mapping independently.** Scanning about 1.1
million rows across four vintages before the glossary was consulted:

- Position 1 is present and empty in every row, consistent with Reference Pool
  ID, which is populated only for CRT deals.
- Position 111 is populated and rises with vintage: 1,353 of 200,000 rows in
  2012Q1, 4,120 of 300,000 in 2016Q1, 5,921 of 300,000 in 2018Q1. Classic FICO
  at origination becoming more widely reported over time is what that looks
  like.
- Positions 112 and 113 are empty in every row inspected, consistent with
  issuance and current Classic FICO not being backfilled for these vintages.

The data-side observations were made before the glossary was read, so the
agreement is corroboration rather than confirmation bias.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Treat as 112 fields plus a trailing delimiter | Would have matched a common CSV convention | Contradicted by the sample file; would silently shift positions 109 onward |
| Accept 113 and encode positions 111 to 113 | Matches the glossary, the sample-derived delimiter rule, and the observed population pattern | Column names for 111 to 113 must be derived, as no official short name is published |
| Encode all 114 glossary positions | Future-proof against the next release | Position 114 is not in any file we hold, so validation would reject every real record. ADR-004's discipline of accepting only confirmed widths still applies |
| Widen validation to accept any width | Unblocks immediately | Discards the contract. The width check is what surfaced this in minutes rather than as misaligned columns in Silver |

## Decision

Add `CURRENT_FILE_FIELD_COUNT = 113` and include it in
`SUPPORTED_FIELD_COUNTS`. Encode positions 111 to 113 as real fields typed as
three-digit integers, mirroring the existing `CSCORE_B` credit-score
convention. Leave position 114 in `FORWARD_GLOSSARY_FIELDS`, unaccepted, on
exactly the grounds ADR-004 set out.

Fannie Mae publishes no short column name for positions 111 to 113, so the
names `ORIG_CLASSIC_FICO`, `ISSUANCE_CLASSIC_FICO` and `CURRENT_CLASSIC_FICO`
are derived from the glossary labels. They are ours, not Fannie Mae's, which is
recorded here so nobody later mistakes them for official identifiers.

## Consequences

Makes easy: real-data Bronze and Silver runs, and with them the Phase 2
real-data quality evidence that has been outstanding since the files arrived.

Makes hard: nothing immediately. Note that 112 and 113 are empty in every
vintage held, so they are structurally present but carry no signal for this
subset; any model use of Classic FICO must rely on position 111.

Reversal cost: low. The change is one constant and three field definitions.

Revisit trigger: position 114 appearing in a future release, or a width other
than 108, 110 or 113 arriving. Either fails the contract loudly, which is the
intended behaviour and how this amendment came about.

## Note on ADR-004

ADR-004 is not superseded. Its reasoning held, and its explicit refusal to
accept unconfirmed positions is what turned a layout change into a contract
question answered with evidence in an afternoon, rather than a silent
corruption of every column from position 109 onward.
