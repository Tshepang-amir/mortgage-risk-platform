# ADR-012: Preserve missing pre-archive macro vintages

- **Status:** accepted
- **Date:** 2026-09-22
- **Phase:** 4 real-data publication

## Context

The FRED `output_type=4` pull returns genuine initial releases, but the archive
does not cover the full modelling history for every required series. `UNRATE`
reaches the 2000 observation window, while `MORTGAGE30US` begins in June 2010
and `CSUSHPINSA` begins in October 2014. FRED's series vintage-date endpoint
confirms that these are archive boundaries rather than request or pagination
errors. The selected loan cohorts begin in 2005.

Backfilling those periods with today's revised history would put values into
old loan-months that cannot be shown to have existed then. Substituting CPI is
not an HPI measure, and the alternative national FRED house-price series also
lack pre-2005 vintages. Dropping the crisis cohorts would defeat ADR-002's
regime-spanning sample.

## Decision

Keep the three specified series and their genuine `AVAILABLE_DATE` values.
Before a series' first archived release, publish null macro values and null
HPI-derived current LTV rather than revised or synthetic backfills. The generic
point-in-time join remains strict by default; only Gold construction opts into
pre-archive missingness explicitly. A requested series that is absent from the
archive entirely remains fatal.

The scorecard retains OptBinning's missing bin, the hazard model retains median
imputation, and LightGBM retains native missing-value handling. Real results
must report macro and `CURRENT_LTV` missingness by modelling split.

## Consequences

No future revision enters an earlier loan-month, and the 2005/2007 cohorts stay
in the study. Older rows carry less macro information, so discrimination may be
weaker and missingness can encode calendar regime. Phase 5 and Phase 6 results
must therefore be interpreted with split-level missingness alongside model
metrics. A future source containing authenticated historical releases can fill
the null region through a new Delta version without changing join semantics.
