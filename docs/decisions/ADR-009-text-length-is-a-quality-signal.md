# ADR-009: Text length is a quality signal, not a structural one

- **Status:** accepted
- **Date:** 2026-09-19
- **Phase:** 1, unblocking real-data work in Phases 2 and 3

## Context

With the 113-field width settled by ADR-008, all six real files parse. Running
the contract against them surfaced a second defect: `SELLER` is published as
`X(50)` in Fannie Mae's glossary, and the real data exceeds it.

A full scan of both name fields across all 45.5 GB:

| Vintage | SELLER | SERVICER |
| --- | --- | --- |
| 2005Q1 | 41 | 42 |
| 2005Q3 | 41 | 43 |
| 2007Q1 | 52 | 42 |
| 2012Q1 | 58 | 41 |
| 2016Q1 | 68 | 52 |
| 2018Q1 | 66 | 66 |

Four of six vintages breach the published length, beginning in 2007Q1. This is
a long-standing divergence between Fannie Mae's data and Fannie Mae's
documentation, not a recent anomaly, and the longest value is a real lender:
`United Shore Financial Services, Llc D/B/A United Wholesale Mortgage`.

Because `_validate_field_value` treated `max_length` as fatal for every field
type, a stale figure in the documentation of a cosmetic field halted ingestion
of otherwise valid loans.

An attempt to measure observed maxima for all 113 positions by scanning the raw
files with `awk` ran for roughly a day without completing: about 114 million
rows times 113 field splits is order 10^10 string operations, single-threaded.
That was the wrong instrument, and abandoning it prompted the better question,
which was not "what are the true maxima" but "why is length fatal at all".

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Widen `SELLER` and `SERVICER` to the observed maximum | Smallest change | Pins the contract to the longest name that happens to exist today; the next vintage or lender renames and it breaks again. Treats the symptom |
| Widen every text field with blanket headroom | Survives new names | Discards the published lengths as information without replacing them with anything; the number becomes arbitrary |
| Drop `max_length` from the schema entirely | Simple | Discards the published contract rather than recording where reality departs from it, and removes the declared figure the quality gate compares against |
| Keep length fatal and quarantine breaching rows | Literal reading of section 8's "fail loud" | Discards valid loans over a field no model uses. Loud about the wrong thing |
| **Split by type: fatal for typed fields, reported for text** | States the rule that over-length matters only where it implies misalignment; moves documentation drift to the layer built to handle it | Two kinds of length check to understand, and the fatal branch is inert today because only text fields declare a length |

## Decision

`max_length` becomes an observation rather than a parse failure.

A correction to an earlier draft of this record, kept because it changes what
the decision means: the branch was first written as "fatal for typed fields,
reported for text", which implied a corruption guard was being preserved. It
was not. `max_length` is populated on **only the 39 text fields**; no `INTEGER`,
`DECIMAL` or `MONTH` field declares one. Numeric widths live in `raw_format`,
for example `9(3)`, and nothing enforces them, so a 40-digit credit score
parses today and did before this change. The type branch therefore guards a
case that does not currently arise. It is kept because it states the intended
rule and will apply the moment a numeric field declares a width, but it is not
load-bearing today and this ADR should not be read as claiming otherwise.

For `STRING` fields, length becomes an observation. `string_length_exceedances`
returns `(column_name, declared_max, observed_length)` for the data quality
suite to gate on at the Bronze to Silver transition, which is where section 8
places value-level quality.

The glossary figures stay in the schema unchanged. They remain the documented
contract; we now record where reality departs from it instead of halting on it.

No parse-time ceiling is added for text. Structural corruption is already
caught more precisely by the exact field-count check: a lost delimiter yields
112 or 114 tokens and fails immediately, so a length cap would add a weaker
duplicate of a check that already exists.

## Consequences

Makes easy: real-data ingestion proceeds, and the divergence becomes a
reportable data quality finding with named fields and observed lengths rather
than a crash. This is a better artefact for the validation pack than a widened
constant would have been, because it is evidence about the source data.

Makes hard: a genuinely corrupt text value now reaches Silver rather than being
stopped at parse. Accepted, because the field-count check already rejects the
structural failure that would produce one, and because no model consumes
`SELLER` or `SERVICER` as a feature.

Reversal cost: low. One branch in `_validate_field_value`.

Revisit trigger: a text field whose length genuinely carries meaning, for
example a fixed-width identifier where over-length would indicate a wrong
record. Such a field should be typed, not left as free text.

Not resolved here, and both are tracked as open questions:

1. Observed maxima for the other text fields are unknown. They will come from
   the Bronze run itself, which reads all six files in Spark and can aggregate
   lengths in the same pass, rather than from another serial scan.
2. Numeric and date widths are declared in `raw_format` and enforced nowhere.
   That is a real gap, and a 40-digit credit score would reach Silver. It is
   deliberately **not** closed here. Imposing a width without evidence that
   real data respects it is precisely what produced the `SELLER` breakage this
   ADR exists to resolve, and the same Bronze aggregation that answers point 1
   will show whether the declared numeric widths hold.
