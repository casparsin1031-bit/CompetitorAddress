"""
Luckin Coffee scraper — Playwright-based.

Luckin Coffee (瑞幸咖啡) primarily operates in China but has international
locations in Singapore and Malaysia.

Implementation strategy:
- Navigate to the store-locator page.
- Intercept JSON API responses (Luckin's app/web API commonly returns
  store lists as JSON).
- Fall back to DOM parsing if no API is intercepted.

Note: Luckin may use app-deep-link redirects on mobile URLs; we use a
desktop user-agent to avoid this.
"""

from __future__ import annotations

import json
import re
from typing import List

from playwright.sync_api import sync_playwright, Page, Response

from .base_scraper import BaseScraper, RawStore


class LuckinScraper(BaseScraper):
    """Playwright scraper for Luckin Coffee store locators."""

    _API_PATTERN = re.compile(
        r"(store|shop|location|branch|outlet|cafe|coffee)",
        re.IGNORECASE,
    )

    def scrape(self) -> List[RawStore]:
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

            stores: List[RawStore] = []
            for payload in captured:
                stores.extend(self._parse_api(payload))

            if not stores:
                stores = self._parse_dom(page)

            browser.close()

        return stores

    def _parse_api(self, data) -> List[RawStore]:
        stores: List[RawStore] = []
        if isinstance(data, dict):
            # Luckin API commonly nests under "data" or "result"
            for key in ("data", "result", "stores", "shopList", "storeList", "list", "results"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            return stores
        for item in data:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("shopName") or item.get("storeName") or
                item.get("name") or item.get("title") or ""
            )
            address = (
                item.get("address") or item.get("shopAddress") or
                item.get("storeAddress") or item.get("fullAddress") or ""
            )
            if isinstance(address, dict):
                address = ", ".join(str(v) for v in address.values() if v)
            phone = str(item.get("phone") or item.get("tel") or item.get("mobile") or "")
            hours = str(item.get("hours") or item.get("openHours") or item.get("businessHour") or "")
            if name or address:
                stores.append(RawStore(
                    shop_name=str(name).strip(),
                    address=str(address).strip(),
                    phone=phone.strip(),
                    operating_hours=hours.strip(),
                ))
        return stores

    def _parse_dom(self, page: Page) -> List[RawStore]:
        """Fallback DOM parser for Luckin store pages."""
        stores: List[RawStore] = []
        card_selectors = [
            "[class*='store-card']",
            "[class*='shop-card']",
            "[class*='cafe-card']",
            "[class*='store-item']",
            "[class*='location-item']",
            "li[class*='store']",
            "li[class*='shop']",
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
