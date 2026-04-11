# CompetitorAddress — Project Guide for Claude

## What this project does
Scrapes competitor restaurant/store locations across Asian markets, enriches them
with lat/lon + GADM geographic attributes, and exports a store dimension table as
**Parquet**, **CSV**, and **GeoJSON**.

## Quick-start commands

```bash
# UAT — scrape McDonald's HK only, skip geo enrichment (fast, ~35 s)
py pipeline.py --filter HKM --no-enrich --force

# Full run — all enabled competitors
py pipeline.py

# Re-scrape (ignore month cache)
py pipeline.py --force

# Filter by competitor or market
py pipeline.py --filter "McDonald's"
py pipeline.py --filter HK
```

## Project layout

```
CompetitorAddress/
├── pipeline.py              # Main entry point — scrape → enrich → export
├── requirements.txt
├── config/
│   └── competitors.yaml     # Registry of all competitor-market entries
├── scrapers/
│   ├── __init__.py          # REGISTRY dict mapping class names → classes
│   ├── base_scraper.py      # BaseScraper ABC + RawStore dataclass
│   ├── mcdonalds_scraper.py # Playwright-based; intercepts XHR + WordPress AJAX
│   ├── changee_scraper.py
│   ├── sushiro_scraper.py
│   └── luckin_scraper.py
├── enrichment/
│   └── maplatlong_client.py # Subprocess wrapper for casparsin1031-bit/maplatlong
├── cache/                   # Auto-created; raw JSON per competitor-market per month
└── output/                  # Auto-created; final exports
    ├── dim_competitor_stores.parquet
    ├── dim_competitor_stores.csv
    └── dim_competitor_stores.geojson
```

## Output schema (dim_competitor_stores)

| Column              | Type    | Notes                                    |
|---------------------|---------|------------------------------------------|
| shop_id             | string  | e.g. HKM00001 = McDonald's HK store #1  |
| market_code         | string  | HK / TH / VN / SG / MY / MC / KH / LA  |
| competitor_initial  | string  | M / C / S / L                           |
| shop_seq            | string  | Zero-padded 5-digit sequence             |
| competitor_name     | string  |                                          |
| market              | string  | Same as market_code                      |
| shop_name           | string  |                                          |
| address             | string  |                                          |
| phone               | string  |                                          |
| operating_hours     | string  |                                          |
| lat                 | float64 | From source API or maplatlong fallback   |
| lon                 | float64 | From source API or maplatlong fallback   |
| province            | string  | From maplatlong (GADM level-1)           |
| city                | string  | From maplatlong (GADM level-2)           |
| district            | string  | From maplatlong (GADM level-3)           |
| data_month          | string  | YYYY-MM                                  |
| scraped_at          | string  | ISO 8601 UTC                             |
| source_url          | string  |                                          |

## GeoJSON output
- RFC 7946 FeatureCollection
- Each store = Feature with `Point` geometry `[lon, lat]`
- All dimension columns exposed as `properties`
- Stores without coordinates get `"geometry": null`

## Scraper notes

### McDonald's HK
- URL: `https://mcdonalds.com.hk/en/find-a-restaurant/`
- Data comes from WordPress AJAX: `admin-ajax.php?action=get_restaurants`
- Content-Type is `text/html` (not JSON) — handled by `_looks_like_store_json_url()`
- API already includes `lat`/`lng` per store → no maplatlong needed for coordinates

### Adding a new scraper
1. Create `scrapers/mynewbrand_scraper.py` extending `BaseScraper`
2. Register it in `scrapers/__init__.py` REGISTRY
3. Add entries to `config/competitors.yaml` with `enabled: true`

## Geo enrichment (maplatlong)
- Requires the `casparsin1031-bit/maplatlong` repo cloned alongside this project
- Set `MAPLATLONG_DIR` env var to point to it (default: `../maplatlong`)
- Enrichment is skipped gracefully when the repo is absent (all geo fields → null)
- Scrapers that already return lat/lon from the source API skip maplatlong automatically

## Known TODO
- `CHANGEE` HK scraper: URL placeholder in config, scraper not yet implemented
- Sushiro VN / MC / KH / LA — presence not confirmed
- Luckin Coffee — no URLs confirmed for any market yet
- `operating_hours` is empty for McDonald's HK (not exposed by the API)
- Add `--markets` flag to filter by market code without needing the competitor prefix
