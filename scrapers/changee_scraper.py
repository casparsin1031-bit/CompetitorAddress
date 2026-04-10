"""
CHANGEE scraper — Playwright-based.

CHANGEE is a Hong Kong-origin coffee brand. Each enabled market entry
should have its `url` pointing to the store-locator page.

Implementation notes:
- Most lifestyle brand store-locator pages render store cards via JS.
- We first try to intercept JSON API responses; if none are found we
  fall back to parsing the rendered DOM for store-card elements.
- Update `_DOM_SELECTORS` if the website structure changes.
"""

from __future__ import annotations

import json
import re
from typing import List

from playwright.sync_api import sync_playwright, Page, Response

from .base_scraper import BaseScraper, RawStore


_DOM_SELECTORS = {
    # (name_selector, address_selector, phone_selector, hours_selector)
    # These are educated guesses; update after inspecting the live site.
    "default": (
        "[class*='store-name'], [class*='shop-name'], [class*='location-name'], h3, h4",
        "[class*='store-address'], [class*='shop-address'], [class*='address'], p",
        "[class*='phone'], [class*='tel']",
        "[class*='hours'], [class*='opening']",
    ),
}


def _parse_dom(page: Page) -> List[RawStore]:
    """
    Generic DOM parser: finds store-card containers and extracts text.
    Selector strategy: look for repeated card-like elements.
    """
    stores: List[RawStore] = []

    # Try common card container patterns
    card_selectors = [
        "[class*='store-card']",
        "[class*='shop-card']",
        "[class*='location-card']",
        "[class*='store-item']",
        "[class*='branch-item']",
        "li[class*='store']",
        "li[class*='shop']",
        "li[class*='location']",
        ".store",
        ".shop",
        ".branch",
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
            name = card.inner_text().split("\n")[0].strip()
            # Try to extract address as second line
            lines = [ln.strip() for ln in card.inner_text().split("\n") if ln.strip()]
            address = lines[1] if len(lines) > 1 else ""
            if name:
                stores.append(RawStore(shop_name=name, address=address))
        except Exception:
            pass

    return stores


class ChangeeScraper(BaseScraper):
    """Playwright scraper for CHANGEE coffee stores."""

    _API_PATTERN = re.compile(r"(store|shop|location|branch|outlet)", re.IGNORECASE)

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

            # If no API data captured, fall back to DOM
            stores: List[RawStore] = []
            for payload in captured:
                stores.extend(self._parse_api(payload))

            if not stores:
                stores = _parse_dom(page)

            browser.close()

        return stores

    def _parse_api(self, data) -> List[RawStore]:
        stores: List[RawStore] = []
        if isinstance(data, dict):
            for key in ("data", "stores", "shops", "locations", "branches", "results"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            return stores
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("storeName") or item.get("title") or ""
            address = item.get("address") or item.get("fullAddress") or ""
            if isinstance(address, dict):
                address = ", ".join(str(v) for v in address.values() if v)
            phone = str(item.get("phone") or item.get("tel") or "")
            hours = str(item.get("hours") or item.get("openingHours") or "")
            if name or address:
                stores.append(RawStore(
                    shop_name=str(name).strip(),
                    address=str(address).strip(),
                    phone=phone.strip(),
                    operating_hours=hours.strip(),
                ))
        return stores
