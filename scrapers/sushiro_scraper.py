"""
Sushiro scraper — Playwright-based.

Sushiro (スシロー) is a Japanese conveyor-belt sushi chain with branches
in HK, TH, SG, and expanding markets.

Implementation strategy:
- Navigate to the store-locator page.
- Intercept JSON API responses for store data.
- Fall back to DOM parsing of store-card elements.

Sushiro's websites commonly follow a pattern where stores are loaded
as JSON from an endpoint like /api/stores or /wp-json/... (WordPress REST).
"""

from __future__ import annotations

import json
import re
from typing import List

import requests
from playwright.sync_api import sync_playwright, Page, Response

from .base_scraper import BaseScraper, RawStore
from .source_parsers import parse_sushiro_hk, parse_sushiro_sg, parse_sushiro_th


class SushiroScraper(BaseScraper):
    """Playwright scraper for Sushiro store locators."""

    _API_PATTERN = re.compile(
        r"(store|shop|location|branch|restaurant|outlet|wp-json)",
        re.IGNORECASE,
    )

    _OFFICIAL_HTML_PARSERS = {
        "HK": parse_sushiro_hk,
        "TH": parse_sushiro_th,
        "SG": parse_sushiro_sg,
    }

    def scrape(self) -> List[RawStore]:
        official = self._scrape_official_html()
        if official:
            return official

        captured: list[dict] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            def handle_response(response: Response) -> None:
                try:
                    if response.status != 200:
                        return
                    if "json" not in response.headers.get("content-type", ""):
                        return
                    if not self._API_PATTERN.search(response.url):
                        return
                    data = json.loads(response.text())
                    captured.append(data)
                except Exception:
                    pass

            page.on("response", handle_response)
            page.goto(self.url, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(4_000)

            # Scroll to trigger any lazy-load
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2_000)

            stores: List[RawStore] = []
            for payload in captured:
                stores.extend(self._parse_api(payload))

            if not stores:
                stores = self._parse_dom(page)

            browser.close()

        return stores

    def _scrape_official_html(self) -> List[RawStore]:
        """Use deterministic official HTML parsers for markets with stable markup."""
        parser = self._OFFICIAL_HTML_PARSERS.get(self.market_code.upper())
        if parser is None:
            return []
        try:
            response = requests.get(
                self.url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=30,
            )
            response.raise_for_status()
            return parser(response.text)
        except Exception:
            return []

    def _parse_api(self, data) -> List[RawStore]:
        stores: List[RawStore] = []
        if isinstance(data, dict):
            for key in ("data", "stores", "locations", "restaurants", "results", "items"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            return stores
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("title") or item.get("storeName") or ""
            address = item.get("address") or item.get("fullAddress") or item.get("location") or ""
            if isinstance(address, dict):
                address = ", ".join(str(v) for v in address.values() if v)
            phone = str(item.get("phone") or item.get("telephone") or "")
            hours = str(item.get("hours") or item.get("openingHours") or item.get("businessHours") or "")
            if name or address:
                stores.append(RawStore(
                    shop_name=str(name).strip(),
                    address=str(address).strip(),
                    phone=phone.strip(),
                    operating_hours=hours.strip(),
                ))
        return stores

    def _parse_dom(self, page: Page) -> List[RawStore]:
        """Fallback DOM parser for Sushiro store-card pages."""
        stores: List[RawStore] = []
        card_selectors = [
            "[class*='store-card']",
            "[class*='shop-card']",
            "[class*='location-item']",
            "[class*='store-item']",
            "li[class*='store']",
            "li[class*='shop']",
            ".store",
        ]
        cards = []
        for sel in card_selectors:
            try:
                els = page.query_selector_all(sel)
                if len(els) > 1:
                    cards = els
                    break
            except Exception:
                pass

        for card in cards:
            try:
                lines = [ln.strip() for ln in card.inner_text().split("\n") if ln.strip()]
                if not lines:
                    continue
                name = lines[0]
                address = lines[1] if len(lines) > 1 else ""
                stores.append(RawStore(shop_name=name, address=address))
            except Exception:
                pass

        return stores
