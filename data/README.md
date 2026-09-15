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

## Phase 1 raw file manifest

Download the **Primary dataset** quarterly files from Data Dynamics after
registration and accepting Fannie Mae's terms:

<https://datadynamics.fanniemae.com/data-dynamics/#/reportMenu;category=HP>

Place exactly these files in `data/raw/`, keeping the filenames unchanged:

| Acquisition quarter | Required filename | Purpose |
| --- | --- | --- |
| 2005Q1 | `2005Q1.csv` | Pre-crisis origination that seasons into the crash |
| 2005Q3 | `2005Q3.csv` | Second pre-crisis vintage for within-regime variation |
| 2007Q1 | `2007Q1.csv` | Peak-risk vintage |
| 2012Q1 | `2012Q1.csv` | Post-crisis tightened underwriting |
| 2016Q1 | `2016Q1.csv` | Benign vintage for out-of-time validation |
| 2018Q1 | `2018Q1.csv` | Vintage that seasons into the 2020 shock |

Expected raw format: headerless pipe-delimited text, one row per loan-month.
The Phase 1 contract validates the 108-field public sample layout and the
110-field official R-importer extension documented in ADR-004.

Fannie Mae does not publish checksums with these files. After download, record
local SHA-256 values in PROGRESS.md before Phase 3 golden-record work begins.
On Windows PowerShell:

```powershell
Get-FileHash data\raw\2005Q1.csv -Algorithm SHA256
```
