"""
Competitor Store Dimension Pipeline
=====================================
Scrapes competitor restaurant/store locations, enriches with lat/long and
GADM level-2 geographic attributes, and exports a dimension table as
Parquet + CSV.

Usage
-----
  python pipeline.py                         # full run (skip cached months)
  python pipeline.py --force                 # re-scrape even if cache exists
  python pipeline.py --filter HKM            # run only entries whose prefix matches
  python pipeline.py --filter McDonald's     # match by competitor name
  python pipeline.py --no-enrich             # skip maplatlong lookup (faster test)

Output
------
  cache/{prefix}_{YYYYMM}.json              raw scraped stores (per entry per month)
  output/dim_competitor_stores.parquet      full dimension table
  output/dim_competitor_stores.csv          same, CSV format

Shop ID format: {market_code}{competitor_initial}{seq:05d}
  e.g.  HKM00001  = McDonald's HK, store #1
        SGS00003  = Sushiro Singapore, store #3
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from enrichment.maplatlong_client import lookup as geo_lookup
from scrapers import REGISTRY

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config" / "competitors.yaml"
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"

CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("pipeline")

# ─────────────────────────────────────────────────────────────────────────────
# Config loading
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> List[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw.get("competitors", [])


# ─────────────────────────────────────────────────────────────────────────────
# Cache helpers
# ─────────────────────────────────────────────────────────────────────────────

def cache_path(entry: dict, month: str) -> Path:
    """Return path to cache file for a competitor-market entry + month (YYYYMM)."""
    prefix = f"{entry['market_code']}{entry['competitor_initial']}"
    return CACHE_DIR / f"{prefix}_{month}.json"


def load_cache(path: Path) -> list | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(path: Path, stores: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Scraping
# ─────────────────────────────────────────────────────────────────────────────

def scrape_entry(entry: dict) -> list[dict]:
    """
    Instantiate the correct scraper and run it.
    Returns a list of plain dicts (serialisable for cache).
    """
    cls_name = entry["scraper_class"]
    cls = REGISTRY.get(cls_name)
    if cls is None:
        raise ValueError(f"Unknown scraper class: {cls_name}")

    scraper = cls(entry)
    log.info("  Scraping %s %s via %s …", entry["competitor_name"], entry["market_code"], cls_name)
    raw_stores = scraper.scrape()

    return [
        {
            "shop_name": s.shop_name,
            "address": s.address,
            "phone": s.phone,
            "operating_hours": s.operating_hours,
        }
        for s in raw_stores
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Building the dimension rows
# ─────────────────────────────────────────────────────────────────────────────

def build_dim_rows(
    entry: dict,
    raw_stores: list[dict],
    month: str,
    scraped_at: str,
    enrich: bool,
) -> list[dict]:
    """
    Convert raw stores → dimension table rows, assigning shop IDs and
    optionally enriching with lat/long + GADM data via maplatlong.
    """
    rows = []
    market_code = entry["market_code"]
    comp_initial = entry["competitor_initial"]
    prefix = f"{market_code}{comp_initial}"

    for seq, store in enumerate(raw_stores, start=1):
        shop_id = f"{prefix}{seq:05d}"

        geo = {"lat": None, "lon": None, "province": None, "city": None, "district": None}
        if enrich:
            try:
                geo = geo_lookup(store["shop_name"], store["address"])
            except Exception as exc:
                log.warning("    geo_lookup failed for %s: %s", shop_id, exc)

        rows.append({
            "shop_id": shop_id,
            "market_code": market_code,
            "competitor_initial": comp_initial,
            "shop_seq": f"{seq:05d}",
            "competitor_name": entry["competitor_name"],
            "market": market_code,
            "shop_name": store["shop_name"],
            "address": store["address"],
            "phone": store.get("phone", ""),
            "operating_hours": store.get("operating_hours", ""),
            "lat": geo["lat"],
            "lon": geo["lon"],
            "province": geo["province"],
            "city": geo["city"],
            "district": geo["district"],
            "data_month": month[:4] + "-" + month[4:],   # "YYYYMM" → "YYYY-MM"
            "scraped_at": scraped_at,
            "source_url": entry["url"],
        })

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

_PARQUET_SCHEMA = pa.schema([
    pa.field("shop_id",            pa.string()),
    pa.field("market_code",        pa.string()),
    pa.field("competitor_initial", pa.string()),
    pa.field("shop_seq",           pa.string()),
    pa.field("competitor_name",    pa.string()),
    pa.field("market",             pa.string()),
    pa.field("shop_name",          pa.string()),
    pa.field("address",            pa.string()),
    pa.field("phone",              pa.string()),
    pa.field("operating_hours",    pa.string()),
    pa.field("lat",                pa.float64()),
    pa.field("lon",                pa.float64()),
    pa.field("province",           pa.string()),
    pa.field("city",               pa.string()),
    pa.field("district",           pa.string()),
    pa.field("data_month",         pa.string()),
    pa.field("scraped_at",         pa.string()),
    pa.field("source_url",         pa.string()),
])


def export(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)

    # Ensure consistent column order / types
    for col in ["lat", "lon"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in _PARQUET_SCHEMA.names:
        if col not in df.columns:
            df[col] = None

    parquet_path = OUTPUT_DIR / "dim_competitor_stores.parquet"
    csv_path = OUTPUT_DIR / "dim_competitor_stores.csv"

    table = pa.Table.from_pandas(df[_PARQUET_SCHEMA.names], schema=_PARQUET_SCHEMA, preserve_index=False)
    pq.write_table(table, parquet_path, compression="snappy")
    df[_PARQUET_SCHEMA.names].to_csv(csv_path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel compat

    log.info("Exported %d rows → %s + %s", len(df), parquet_path, csv_path)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Competitor Store Dimension Pipeline")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-scrape even if a cache file for the current month already exists.",
    )
    parser.add_argument(
        "--filter", metavar="TERM", default="",
        help=(
            "Only run entries whose market_code+competitor_initial prefix "
            "or competitor_name contains TERM (case-insensitive)."
        ),
    )
    parser.add_argument(
        "--no-enrich", action="store_true",
        help="Skip maplatlong lat/long + GADM enrichment (useful for quick scrape tests).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    month = datetime.now(timezone.utc).strftime("%Y%m")
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    enrich = not args.no_enrich
    filter_term = args.filter.lower()

    entries = load_config()
    enabled = [e for e in entries if e.get("enabled", False)]

    if filter_term:
        enabled = [
            e for e in enabled
            if filter_term in (e["market_code"] + e["competitor_initial"]).lower()
            or filter_term in e["competitor_name"].lower()
            or filter_term in e["market_code"].lower()
        ]

    log.info("Pipeline start — month=%s  entries=%d  enrich=%s  force=%s",
             month, len(enabled), enrich, args.force)

    all_rows: list[dict] = []
    stats: list[dict] = []

    for entry in enabled:
        label = f"{entry['competitor_name']} {entry['market_code']}"
        c_path = cache_path(entry, month)

        # ── Step 1: scrape (or load from cache) ──────────────────────────
        raw: list[dict] | None = None
        if not args.force:
            raw = load_cache(c_path)
            if raw is not None:
                log.info("[CACHE HIT] %s — %d stores from %s", label, len(raw), c_path.name)

        if raw is None:
            try:
                raw = scrape_entry(entry)
                save_cache(c_path, raw)
                log.info("  Scraped %d stores for %s", len(raw), label)
            except Exception as exc:
                log.error("  SCRAPE FAILED for %s: %s", label, exc)
                stats.append({"entry": label, "scraped": 0, "enriched": 0, "failed_enrich": 0, "error": str(exc)})
                continue

        # ── Step 2: enrich + build dim rows ──────────────────────────────
        log.info("  Enriching %d stores for %s …", len(raw), label)
        rows = build_dim_rows(entry, raw, month, scraped_at, enrich)

        enriched = sum(1 for r in rows if r["lat"] is not None)
        failed_enrich = len(rows) - enriched
        if enrich:
            log.info("  Enriched %d/%d stores for %s", enriched, len(rows), label)

        all_rows.extend(rows)
        stats.append({
            "entry": label,
            "scraped": len(raw),
            "enriched": enriched,
            "failed_enrich": failed_enrich,
            "error": "",
        })

    # ── Step 3: export ────────────────────────────────────────────────────
    if all_rows:
        export(all_rows)
    else:
        log.warning("No rows to export — nothing written.")

    # ── Step 4: summary ───────────────────────────────────────────────────
    log.info("\n%s", "─" * 70)
    log.info("%-35s %8s %8s %12s %s", "Entry", "Scraped", "Enriched", "Geo Failed", "Error")
    log.info("─" * 70)
    total_scraped = total_enriched = 0
    for s in stats:
        log.info("%-35s %8d %8d %12d %s",
                 s["entry"], s["scraped"], s["enriched"], s["failed_enrich"], s["error"])
        total_scraped += s["scraped"]
        total_enriched += s["enriched"]
    log.info("─" * 70)
    log.info("TOTAL: %d stores scraped, %d enriched with geo data", total_scraped, total_enriched)


if __name__ == "__main__":
    main()
