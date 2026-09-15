# ADR-002: Acquisition Quarter Subset

- **Status:** accepted
- **Date:** 2026-09-15
- **Phase:** 1

## Context

The full Fannie Mae Single-Family Loan Performance dataset is too large for the
laptop-first and Databricks Free Edition constraints in PROJECT.md. The project
still needs enough vintage variation to test benign periods, the financial-crisis
regime, post-crisis underwriting and the 2020 shock.

Fannie Mae publishes one primary dataset file per acquisition quarter. Each file
contains the monthly performance history for that acquisition cohort.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Full history | Maximum sample size and no subsetting judgment | Too large for the target environment; slows every phase before the modelling question is reached |
| Recent-only history | Smaller and easier to download | Misses the pre-crisis and crisis regimes that make mortgage default risk interesting |
| Six regime-spanning quarters | Fits local constraints and keeps crisis, post-crisis and out-of-time cohorts | Loses some seasonality and within-regime variation |

## Decision

Use these six primary acquisition-quarter files:

| Quarter | Role |
| --- | --- |
| 2005Q1 | Pre-crisis origination that seasons into the crash |
| 2005Q3 | Second pre-crisis vintage for within-regime variation |
| 2007Q1 | Peak-risk vintage |
| 2012Q1 | Post-crisis tightened underwriting |
| 2016Q1 | Benign vintage for out-of-time validation |
| 2018Q1 | Vintage that seasons into the 2020 shock |

## Consequences

This keeps the project reproducible on constrained infrastructure while still
testing the modelling stack across distinct credit regimes. The cost is that
reported results are not population-wide Fannie Mae estimates; they are estimates
for a deliberately sampled set of acquisition cohorts. Any headline result must
say that clearly.

Revisit this decision only after Phases 1 to 8 are complete or if the selected
files do not contain enough defaults for stable validation intervals.
