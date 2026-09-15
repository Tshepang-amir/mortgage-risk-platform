# data/

Nothing in this directory is committed except this README and small test
fixtures under 100 KB. See `.gitignore` and PROJECT.md section 10 point 2.

| Path | Contents | Source |
| --- | --- | --- |
| `data/raw/` | Fannie Mae Single-Family Loan Performance files, as downloaded | Human download, see below |
| `data/external/` | Cached FRED macro series pulls | `UNRATE`, `CSUSHPINSA`, `MORTGAGE30US` |
| `data/fixtures/` | Small synthetic fixtures used by tests | Generated, Phase 1 |
| `data/delta/` | Local Delta Lake tables, Bronze through Gold | Generated, Phase 2 onward |

## Fannie Mae data requires a human download

The loan performance data needs free registration and a manual download.
It cannot be fetched programmatically, and no attempt is made to scrape it.

<https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data>

**The exact file manifest — which six acquisition quarters, their filenames,
and the checksums to verify them against — is defined in Phase 1.** Do not
place files here yet; Phase 1 will name precisely what is needed and halt until
those files exist.
