# CompetitorAddress

Monthly competitor store-address pipeline for building a Power BI-ready competitor store dimension table.

This repo scrapes configured competitor store locators, caches monthly raw results, optionally enriches each store with latitude/longitude and GADM-style admin fields via `maplatlong`, then exports:

- `output/dim_competitor_stores.parquet`
- `output/dim_competitor_stores.csv`

## If you reopen this repo and feel lost

Start here:

```bash
cd /root/work/CompetitorAddress
git status --short --branch
.venv/bin/python -m pytest
```

Then check these 5 files, in this order:

1. `README.md` — this guide.
2. `config/competitors.yaml` — what competitor/market pairs the pipeline runs.
3. `registry/source_registry.yaml` — source trust, expected store counts, and monthly sanity rules.
4. `pipeline.py` — main scrape/enrich/export pipeline.
5. `scripts/monthly_agent_maintain.py` — monthly automation entrypoint used by GitHub Actions.

Useful quick commands:

```bash
# Fast test: parser + sanity unit tests only
.venv/bin/python -m pytest

# Run one source without geocoding; good for debugging scraper output
.venv/bin/python pipeline.py --filter HKF --no-enrich --force

# Run monthly maintenance for one source without geocoding
.venv/bin/python scripts/monthly_agent_maintain.py --filter HKF --no-enrich --force

# Run source discovery/validation report for known candidate sources
.venv/bin/python scripts/validate_sources.py
```

## What this project does

The core business object is a monthly competitor store dimension table.

Each output row represents one competitor store in one month with fields such as:

- `shop_id` — stable ID in format `{market_code}{competitor_initial}{seq:05d}`; e.g. `HKM00001`, `HKF00151`.
- `market_code` — `HK`, `TH`, `VN`, `SG`, etc.
- `competitor_name` — McDonald's, Sushiro, Fairwood, etc.
- `shop_name`, `address`, `phone`, `operating_hours`.
- `lat`, `lon`, `province`, `city`, `district`.
- `data_month`, `scraped_at`, `source_url`.

The intended consumer is Power BI / analytics work, not a public web app.

## Current tracked competitors

Enabled entries are controlled by `config/competitors.yaml`; monthly guardrails are controlled by `registry/source_registry.yaml`.

Currently active/high-priority sources include:

| Key | Competitor / market | Primary source style |
|---|---|---|
| `HKM` | McDonald's Hong Kong | Official WordPress AJAX endpoint |
| `THM` | McDonald's Thailand | Official HTML parser |
| `VNM` | McDonald's Vietnam | Official HTML parser |
| `SGM` | McDonald's Singapore | Official support article / parser fallback |
| `HKS` | Sushiro Hong Kong | Official HTML parser |
| `THS` | Sushiro Thailand | Official HTML parser |
| `SGS` | Sushiro Singapore | Official HTML parser |
| `HKL` | Luckin Coffee Hong Kong | Google Maps / candidate source |
| `HKF` | Fairwood Hong Kong | Official Next.js `__NEXT_DATA__` parser |

Some competitors/markets are intentionally disabled in `config/competitors.yaml` because the source is absent, unconfirmed, or not yet safe for monthly automation.

## Repository map

```text
.
├── pipeline.py                         # Main scrape -> enrich -> export pipeline
├── requirements.txt                    # Python dependencies
├── config/
│   └── competitors.yaml                # Runtime competitor/market config
├── registry/
│   ├── source_registry.yaml            # Source confidence + sanity guardrails
│   └── evidence/                       # Evidence notes for source decisions
├── scrapers/
│   ├── base_scraper.py                 # RawStore + BaseScraper contract
│   ├── source_parsers.py               # Deterministic parsers for official sources
│   ├── mcdonalds_scraper.py
│   ├── sushiro_scraper.py
│   ├── fairwood_scraper.py
│   ├── google_maps_scraper.py
│   ├── luckin_scraper.py
│   └── changee_scraper.py
├── enrichment/
│   └── maplatlong_client.py            # Wrapper around private maplatlong geocoder repo
├── scripts/
│   ├── monthly_agent_maintain.py       # Pipeline + sanity gate entrypoint
│   ├── sanity_check.py                 # Fails bad monthly results before publish
│   └── validate_sources.py             # Candidate source validation report
├── tests/
│   ├── test_source_parsers.py
│   └── test_sanity_check.py
├── output/                             # Generated CSV/Parquet; gitignored locally
├── cache/                              # Monthly raw scraped JSON; gitignored locally
├── reports/                            # Generated validation/sanity reports
├── new_brand_request_form.html         # Local form to generate a Hermes onboarding prompt
└── new_brand_onboarding_tickets.md     # Workflow/tickets for adding a new competitor
```

## Setup

Use the existing venv when present:

```bash
cd /root/work/CompetitorAddress
.venv/bin/python -m pytest
```

If rebuilding from scratch:

```bash
cd /root/work/CompetitorAddress
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

For full enrichment, the private `maplatlong` repo must also be available. By default the wrapper expects `../maplatlong`; override with:

```bash
export MAPLATLONG_DIR=/path/to/maplatlong
```

If `maplatlong` is missing, the pipeline continues but enrichment fields may be blank. For scraper debugging, use `--no-enrich`.

## Running the pipeline

Main usage:

```bash
# Full enabled monthly run; uses current UTC month and cache when available
.venv/bin/python pipeline.py

# Force re-scrape even when cache exists
.venv/bin/python pipeline.py --force

# Run only one key/brand/market
.venv/bin/python pipeline.py --filter HKF
.venv/bin/python pipeline.py --filter Fairwood
.venv/bin/python pipeline.py --filter SG

# Skip maplatlong enrichment for faster scraper validation
.venv/bin/python pipeline.py --filter HKF --no-enrich --force
```

Pipeline stages:

1. Load enabled entries from `config/competitors.yaml`.
2. For each entry, load `cache/{KEY}_{YYYYMM}.json` unless `--force` is used.
3. Scrape source using the configured scraper class.
4. Build dimension rows and optionally enrich with `maplatlong`.
5. Export `output/dim_competitor_stores.parquet` and `.csv`.

## Monthly maintenance and sanity gates

Monthly automation should use:

```bash
.venv/bin/python scripts/monthly_agent_maintain.py --force
```

This runs:

1. `pipeline.py`
2. `scripts/sanity_check.py --write-report`

The sanity gate blocks automatic publish/commit when any enabled registry entry has issues such as:

- zero stores returned;
- count below configured minimum;
- count above configured maximum, usually warning;
- significant drop versus previous month;
- too many missing addresses;
- too many missing coordinates, unless `--skip-geo-check` / `--no-enrich` is used.

Reports are written to:

- `reports/{YYYYMM}_sanity_report.md`
- `reports/{YYYYMM}_sanity_report.json`

## GitHub Actions

Workflow: `.github/workflows/monthly_scrape.yml`

Schedule:

- Runs at `02:00 UTC` on the 1st of every month.
- Can also be run manually from GitHub Actions.

Manual inputs:

- `force` — re-scrape and ignore existing cache.
- `filter` — run only a key/brand/market; e.g. `HKF`, `McDonald's`, `SG`.
- `no_enrich` — skip `maplatlong` geocoding for scrape-only validation.

Secrets / permissions:

- `MAPLATLONG_TOKEN` is required when enrichment is enabled because the workflow checks out the private `casparsin1031-bit/maplatlong` repo.
- Workflow has `contents: write` so it can commit refreshed `output/`, `cache/`, and `reports/` back after sanity checks pass.

## Adding or changing a competitor

Default safe flow: assess first, then change files only after evidence is strong.

1. Use `new_brand_request_form.html` to create a structured Hermes prompt.
2. Run or update `scripts/validate_sources.py` to test candidate official/fallback pages.
3. Record evidence and guardrails in `registry/source_registry.yaml`.
4. Add runtime entry to `config/competitors.yaml`.
5. Add or update a scraper/parser in `scrapers/`.
6. Add parser/sanity tests in `tests/`.
7. Run scrape-only validation:

   ```bash
   .venv/bin/python pipeline.py --filter <KEY> --no-enrich --force
   .venv/bin/python scripts/sanity_check.py --month <YYYYMM> --filter <KEY> --skip-geo-check --write-report
   .venv/bin/python -m pytest
   ```

8. Enable monthly automation only when the source and sanity report are strong enough.

Important rule: fallback-only sources such as Google Maps/OpenRice should not silently become fully automated monthly sources unless Caspar explicitly approves that risk.

## Testing

```bash
# All tests
.venv/bin/python -m pytest

# Parser tests only
.venv/bin/python -m pytest tests/test_source_parsers.py

# Sanity gate tests only
.venv/bin/python -m pytest tests/test_sanity_check.py
```

Current tests focus on:

- deterministic parsers for official source pages/API payloads;
- sanity-check behavior for zero counts, plausible counts, and significant drops.

## Data and git hygiene

- `cache/` and `output/` are gitignored locally because they are generated.
- GitHub Actions force-adds `output/`, `cache/`, and `reports/` during monthly maintenance to preserve snapshots after a passing sanity gate.
- Do not treat a zero-row scrape as valid data.
- Do not loosen expected ranges just to pass automation; update ranges only with evidence.
- Prefer deterministic `requests` + parser logic before Playwright/browser scraping.

## Common recovery checklist

When something breaks:

1. Check current branch and local changes:

   ```bash
   git status --short --branch
   ```

2. Run tests:

   ```bash
   .venv/bin/python -m pytest
   ```

3. Reproduce with one filtered source and no enrichment:

   ```bash
   .venv/bin/python pipeline.py --filter <KEY> --no-enrich --force
   ```

4. Inspect raw cache:

   ```bash
   # Example
   .venv/bin/python -m json.tool cache/HKF_202607.json | less
   ```

5. Run sanity report for that key/month:

   ```bash
   .venv/bin/python scripts/sanity_check.py --month <YYYYMM> --filter <KEY> --skip-geo-check --write-report
   ```

6. If source markup/API changed, update the narrow parser in `scrapers/source_parsers.py` and add a fixture-style unit test.

## Current branch note

At the time this README was created, active work was on branch:

```text
claude/competitor-store-dimension-NrT2h
```

This branch includes Fairwood HK source validation/onboarding work and monthly-maintenance improvements.
