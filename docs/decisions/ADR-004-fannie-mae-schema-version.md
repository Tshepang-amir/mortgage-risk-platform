# ADR-004: Fannie Mae Schema Version

- **Status:** accepted
- **Date:** 2026-09-15
- **Phase:** 1

## Context

PROJECT.md names the Fannie Mae Single-Family Loan Performance layout as a
108-field schema. During Phase 1, the official public artefacts did not fully
agree:

| Artefact checked | Observed layout |
| --- | --- |
| Fannie Mae sample CSV linked from the loan performance page | 108 pipe-delimited fields |
| Fannie Mae Primary R importer linked from the same page | 110 named fields |
| Fannie Mae CRT glossary and file layout dated 2026-09-10 | Positions through 114 |

The new glossary positions include credit-score modernization fields that are not
yet reflected consistently in the sample CSV and R importer.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Encode only 108 fields | Matches PROJECT.md and the sample CSV | Phase 2 could fail when real files follow the newer R importer |
| Encode all 114 glossary positions | Most forward-looking | Would claim a physical raw-file shape not evidenced by the sample or importer |
| Encode 108 as the Phase 1 default and accept the 110 importer extension | Matches the explicit phase exit while preparing for the known current extension | Leaves positions 111 to 114 as documented forward drift |

## Decision

Encode the 108-field sample layout as the Phase 1 default schema and also encode
the two official R-importer extension fields at positions 109 and 110. Validation
supports both 108 and 110 columns. Positions 111 to 114 are documented as
forward glossary fields but are not accepted as raw-file columns until the sample
file or official importer confirms that shape.

## Consequences

Synthetic fixtures remain identical to the Phase 1 108-field release contract.
Phase 2 ingestion can accept real files that already include the 109 and 110
fields. If Fannie Mae updates the sample or importer to 114 fields, the schema
will need one small additive update rather than a redesign.
