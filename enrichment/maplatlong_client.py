"""
Google Maps Geocoding client for the CompetitorAddress pipeline.

Replaces the original subprocess-based maplatlong client with a
self-contained implementation that calls the Google Maps Geocoding REST API
directly, with address cleaning, multi-variant fallback queries, CSV result
caching, and rate limiting.

Configuration
-------------
Create a .env file at the project root (see .env.example):

    GOOGLE_API_KEY=AIzaSy...your_real_key...

The .env file is gitignored — never commit the real key.

Cache
-----
Results are cached at cache/geocode_cache.csv keyed by query string.
The cache persists across pipeline runs. Delete it to force re-geocoding.
Missed queries (ZERO_RESULTS) are also cached so they are never retried.

Rate limiting
-------------
RATE_LIMIT_SECONDS = 0.05  (20 req/s, well within Google's default quota of
                             50 req/s for the Geocoding API)

Public interface (unchanged from the original client)
------------------------------------------------------
    from enrichment.maplatlong_client import lookup, GeoResult
    result: GeoResult = lookup(shop_name, address)
    # result = {lat, lon, province, city, district}
"""

from __future__ import annotations

import csv
import logging
import os
import re
import time
from pathlib import Path
from typing import TypedDict

import requests
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file: enrichment/ → project root)
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
RATE_LIMIT_SECONDS = 0.05
CACHE_PATH = _PROJECT_ROOT / "cache" / "geocode_cache.csv"

# ── GeoResult type (same shape as original maplatlong_client) ─────────────────

class GeoResult(TypedDict):
    lat: float | None
    lon: float | None
    province: str | None
    city: str | None
    district: str | None


_EMPTY: GeoResult = {
    "lat": None,
    "lon": None,
    "province": None,
    "city": None,
    "district": None,
}

# ── Cache helpers ─────────────────────────────────────────────────────────────

_CACHE_FIELDS = ["query", "lat", "lon", "province", "city", "district"]


def _load_cache() -> dict[str, GeoResult]:
    """Load geocode_cache.csv into a dict keyed by query string."""
    cache: dict[str, GeoResult] = {}
    if not CACHE_PATH.exists():
        return cache
    try:
        with open(CACHE_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = row.get("query", "").strip()
                if not key:
                    continue
                cache[key] = GeoResult(
                    lat=_to_float(row.get("lat")),
                    lon=_to_float(row.get("lon")),
                    province=_to_str(row.get("province")),
                    city=_to_str(row.get("city")),
                    district=_to_str(row.get("district")),
                )
    except Exception as exc:
        log.warning("geocode cache load failed: %s", exc)
    return cache


def _save_cache(cache: dict[str, GeoResult]) -> None:
    """Persist the entire cache dict back to geocode_cache.csv."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(CACHE_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CACHE_FIELDS)
            writer.writeheader()
            for query, geo in cache.items():
                writer.writerow({
                    "query": query,
                    "lat": geo["lat"] if geo["lat"] is not None else "",
                    "lon": geo["lon"] if geo["lon"] is not None else "",
                    "province": geo["province"] or "",
                    "city": geo["city"] or "",
                    "district": geo["district"] or "",
                })
    except Exception as exc:
        log.warning("geocode cache save failed: %s", exc)


# Module-level cache singleton — loaded once at import time
_cache: dict[str, GeoResult] = _load_cache()

# ── Address and name cleaning ─────────────────────────────────────────────────

# Matches unit/floor/room prefixes at the start of an address
_UNIT_PREFIX_RE = re.compile(
    r"^(Unit|Flat|Shop|Room|Rm|Floor|F|G\/F|UG|LG|B\d*|L\d+)[,\s/\-]+",
    re.IGNORECASE,
)
# Chinese characters optionally followed by common shop/floor suffixes
_CHINESE_NOISE_RE = re.compile(r"[\u4e00-\u9fff]+[號号樓楼層层鋪铺]?\s*", re.UNICODE)
# Hash-style unit numbers: #01-02, #B2-05
_HASH_UNIT_RE = re.compile(r"#[\w/\-]+\s*")
# Multiple spaces/commas
_MULTI_SPACE_RE = re.compile(r"\s{2,}")
_LEADING_COMMA_RE = re.compile(r"^[,\s]+|[,\s]+$")

# Contract-date metadata appended to store names, e.g. "(C : OCT-2008)"
_CONTRACT_DATE_RE = re.compile(r"\s*\(C\s*:.*?\)", re.IGNORECASE)
_BARE_DATE_RE = re.compile(r"\s*\([A-Z]{3}-\d{4}\)")


def clean_address(raw: str) -> str:
    """
    Strip unit/floor prefixes, Chinese shop notation, and hash unit numbers;
    normalise spacing and trailing commas.
    """
    if not raw:
        return ""
    s = str(raw).strip()
    s = _UNIT_PREFIX_RE.sub("", s)
    s = _HASH_UNIT_RE.sub("", s)
    s = _CHINESE_NOISE_RE.sub(" ", s)
    s = _MULTI_SPACE_RE.sub(" ", s)
    s = _LEADING_COMMA_RE.sub("", s)
    return s.strip()


def clean_store_name(raw: str) -> str:
    """Strip contract-date metadata appended to store names."""
    if not raw or str(raw).strip() in ("", "nan"):
        return ""
    s = _CONTRACT_DATE_RE.sub("", str(raw).strip())
    s = _BARE_DATE_RE.sub("", s)
    return s.strip()


# ── Query variant builder ─────────────────────────────────────────────────────

def build_query_variants(shop_name: str, address: str, country: str = "") -> list[str]:
    """
    Build an ordered list of geocoding query strings, from most specific to least.

    Parameters
    ----------
    shop_name : str   Raw store/outlet name.
    address   : str   Raw address string.
    country   : str   Optional country hint (e.g. "Hong Kong", "Thailand").

    Returns
    -------
    list[str]  Up to 6 deduplicated query strings; first successful match wins.
    """
    name = clean_store_name(shop_name)
    addr = clean_address(address)
    sfx = f", {country}" if country else ""

    candidates: list[str] = []

    def _add(q: str) -> None:
        q = q.strip().strip(",").strip()
        if q and q not in candidates:
            candidates.append(q)

    # 1. Most specific: name + full address
    if name and addr:
        _add(f"{name}, {addr}")

    # 2. Full address only
    if addr:
        _add(addr)

    # 3. Name + full address + country
    if name and addr and country:
        _add(f"{name}, {addr}{sfx}")

    # 4. Address + country
    if addr and country:
        _add(f"{addr}{sfx}")

    # 5. Name + country (neighbourhood / POI level)
    if name and country:
        _add(f"{name}{sfx}")

    # 6. Name only (last resort — broadest match)
    if name:
        _add(name)

    return candidates


# ── Google Geocoding API ──────────────────────────────────────────────────────

def _google_geocode(query: str) -> tuple[list[dict] | None, str | None]:
    """
    Call Google Maps Geocoding API for a single query string.

    Returns the full `results` list from the API response so the caller can
    extract both coordinates and address_components in one call.

    Returns
    -------
    (results_list, None)        on success (results_list is the API "results" array)
    (None, error_message_str)   on failure
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return None, "GOOGLE_API_KEY not set"

    try:
        resp = requests.get(
            GOOGLE_GEOCODE_URL,
            params={"address": query, "key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return None, str(exc)

    if "error_message" in data:
        return None, f"API error: {data['error_message']}"

    status = data.get("status")
    if status == "ZERO_RESULTS":
        return None, None  # no result, not an error

    if status != "OK":
        return None, f"API status: {status}"

    results: list[dict] = data.get("results", [])
    if not results:
        return None, "Empty results list"

    return results, None


# ── address_components parser ─────────────────────────────────────────────────

def _parse_address_components(
    results: list[dict],
) -> tuple[str | None, str | None, str | None]:
    """
    Extract (province, city, district) from Google API address_components.

    Mapping
    -------
    province  ← administrative_area_level_1
    city      ← locality  OR  administrative_area_level_2
    district  ← sublocality_level_1  OR  sublocality
    """
    if not results:
        return None, None, None

    components: list[dict] = results[0].get("address_components", [])
    province = city = district = None

    for comp in components:
        types: list[str] = comp.get("types", [])
        name: str | None = comp.get("long_name", "").strip() or None

        if "administrative_area_level_1" in types:
            province = name
        elif "locality" in types and city is None:
            city = name
        elif "administrative_area_level_2" in types and city is None:
            city = name
        elif "sublocality_level_1" in types:
            district = name
        elif "sublocality" in types and district is None:
            district = name

    return province, city, district


# ── Public interface ──────────────────────────────────────────────────────────

def lookup(shop_name: str, address: str) -> GeoResult:
    """
    Geocode a store by name and address; return geographic attributes.

    Tries multiple query variants (most-specific first). Caches every result
    (including misses) to cache/geocode_cache.csv. Rate-limits API calls to
    respect Google's quota.

    Parameters
    ----------
    shop_name : str   Store/outlet name (used to enrich query variants).
    address   : str   Full address string for geocoding.

    Returns
    -------
    GeoResult
        Dict with lat, lon, province, city, district.
        All values are None when geocoding fails or the API key is absent.
    """
    if not shop_name.strip() and not address.strip():
        return dict(_EMPTY)

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        log.warning("GOOGLE_API_KEY not set — geo enrichment skipped. "
                    "Copy .env.example to .env and add your key.")
        return dict(_EMPTY)

    variants = build_query_variants(shop_name, address)
    if not variants:
        return dict(_EMPTY)

    for query in variants:
        cached = _cache.get(query)

        # Cache hit with valid coordinates → return immediately
        if cached is not None and cached["lat"] is not None:
            return dict(cached)

        # Cache hit but known miss → skip to next variant without an API call
        if cached is not None and cached["lat"] is None:
            continue

        # Cache miss → live API call (rate-limited)
        time.sleep(RATE_LIMIT_SECONDS)

        results, err = _google_geocode(query)

        if results is None:
            log.debug("geocode miss for %r: %s", query[:80], err)
            _cache[query] = dict(_EMPTY)
            _save_cache(_cache)
            continue

        # Success — extract coordinates and address attributes
        loc = results[0]["geometry"]["location"]
        province, city, district = _parse_address_components(results)

        geo: GeoResult = {
            "lat": loc["lat"],
            "lon": loc["lng"],
            "province": province,
            "city": city,
            "district": district,
        }
        _cache[query] = geo
        _save_cache(_cache)
        return geo

    return dict(_EMPTY)


# ── Type coercion helpers ─────────────────────────────────────────────────────

def _to_float(value) -> float | None:
    try:
        v = str(value).strip()
        return float(v) if v else None
    except (TypeError, ValueError):
        return None


def _to_str(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None
