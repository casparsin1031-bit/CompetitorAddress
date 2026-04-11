"""
McDonald's scraper — Playwright-based, handles all market variants.

Strategy:
  1. Open the restaurant-finder page in headless Chromium.
  2. Intercept XHR/fetch responses that look like store JSON arrays.
  3. If interception yields data → parse directly from JSON.
  4. Otherwise fall back to DOM parsing (click "View All" / scroll / paginate).

Each McDonald's market site has a slightly different HTML/API structure;
market-specific tweaks are handled via `_get_market_strategy()`.
"""

from __future__ import annotations

import json
import re
from typing import List

from playwright.sync_api import sync_playwright, Page, Response

from .base_scraper import BaseScraper, RawStore


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _looks_like_store_json(body: str) -> bool:
    """Heuristic: does the response body contain store-like fields?"""
    return any(kw in body for kw in (
        '"address"', '"restaurant"', '"store"', '"branch"', '"outlet"',
        '"latitude"', '"lat"', '"lng"', '"longitude"',
    ))


def _extract_stores_from_json(data) -> List[RawStore]:
    """
    Walk common JSON shapes used by McDonald's APIs across markets.
    Returns a list of RawStore; empty list if shape is unrecognised.
    """
    stores: List[RawStore] = []

    # Unwrap envelope shapes: {"data": [...]} / {"restaurants": [...]} / [...]
    if isinstance(data, dict):
        for key in ("data", "restaurants", "stores", "branches", "outlets", "results", "items"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break

    if not isinstance(data, list):
        return stores

    for item in data:
        if not isinstance(item, dict):
            continue

        name = (
            item.get("name") or item.get("restaurantName") or
            item.get("title") or item.get("storeName") or ""
        )
        address = (
            item.get("address") or item.get("fullAddress") or
            item.get("addressLine1") or item.get("location") or ""
        )
        # address may be a nested object
        if isinstance(address, dict):
            address = ", ".join(
                str(v) for v in address.values() if v
            )

        phone = str(item.get("phone") or item.get("telephone") or item.get("tel") or "")
        hours = str(item.get("hours") or item.get("openingHours") or item.get("businessHours") or "")

        if name or address:
            stores.append(RawStore(
                shop_name=str(name).strip(),
                address=str(address).strip(),
                phone=phone.strip(),
                operating_hours=hours.strip(),
            ))

    return stores


# ─────────────────────────────────────────────────────────────────────────────
# Scraper
# ─────────────────────────────────────────────────────────────────────────────

class McDonaldsScraper(BaseScraper):
    """Playwright scraper for McDonald's restaurant finders across markets."""

    # Patterns that, when found in a response URL, are likely store-data APIs
    _API_URL_PATTERNS = re.compile(
        r"(restaurant|store|branch|outlet|location|locator|finder|map)",
        re.IGNORECASE,
    )

    def scrape(self) -> List[RawStore]:
        captured: list[dict] = []
        self._sg_article_stores: List[RawStore] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = context.new_page()

            # ── Intercept responses ───────────────────────────────────────
            def handle_response(response: Response) -> None:
                try:
                    if response.status != 200:
                        return
                    ct = response.headers.get("content-type", "")
                    if "json" not in ct:
                        return
                    if not self._API_URL_PATTERNS.search(response.url):
                        return
                    body = response.text()
                    if not _looks_like_store_json(body):
                        return
                    data = json.loads(body)
                    captured.append(data)
                except Exception:
                    pass

            page.on("response", handle_response)

            # ── Navigate ──────────────────────────────────────────────────
            page.goto(self.url, wait_until="networkidle", timeout=60_000)
            self._apply_market_interactions(page)

            browser.close()

        # ── SG Zendesk article: DOM parse results take priority ───────────
        if self.market_code.upper() == "SG" and self._sg_article_stores:
            return self._sg_article_stores

        # ── Parse captured API payloads ───────────────────────────────────
        stores: List[RawStore] = []
        for payload in captured:
            stores.extend(_extract_stores_from_json(payload))

        # ── Deduplicate by (name, address) ────────────────────────────────
        seen: set[tuple] = set()
        unique: List[RawStore] = []
        for s in stores:
            key = (s.shop_name.lower(), s.address.lower())
            if key not in seen:
                seen.add(key)
                unique.append(s)

        return unique

    # ------------------------------------------------------------------
    # Market-specific page interactions
    # ------------------------------------------------------------------

    def _apply_market_interactions(self, page: Page) -> None:
        """
        Each market's site may need different interactions to reveal all stores
        (e.g. clicking "View All", dismissing cookie banners, scrolling).
        Dispatches based on market_code.
        """
        market = self.market_code.upper()
        if market == "HK":
            self._interact_hk(page)
        elif market == "TH":
            self._interact_th(page)
        elif market == "SG":
            self._interact_sg(page)
        elif market == "MY":
            self._interact_my(page)
        else:
            # Generic: wait for network to settle after load
            page.wait_for_timeout(5_000)

    def _interact_hk(self, page: Page) -> None:
        """McDonald's HK store finder interactions."""
        page.wait_for_timeout(4_000)
        # Dismiss cookie banner if present
        for selector in ("button[id*='cookie']", "button[class*='cookie']", "#onetrust-accept-btn-handler"):
            try:
                page.click(selector, timeout=2_000)
            except Exception:
                pass
        # Try clicking "View All" / "List View" / "All Restaurants"
        for text in ("View All", "All Restaurants", "List View", "全部"):
            try:
                page.get_by_text(text, exact=False).first.click(timeout=2_000)
                page.wait_for_timeout(3_000)
                break
            except Exception:
                pass
        page.wait_for_timeout(3_000)

    def _interact_th(self, page: Page) -> None:
        """McDonald's Thailand store finder interactions."""
        page.wait_for_timeout(5_000)
        # Scroll down to trigger lazy-load
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3_000)

    def _interact_sg(self, page: Page) -> None:
        """
        McDonald's SG URL is a static Zendesk Help Centre article listing all
        stores.  No API call is made — parse the article DOM directly.
        """
        page.wait_for_timeout(3_000)
        self._sg_article_stores = self._scrape_sg_article(page)

    def _scrape_sg_article(self, page: Page) -> List[RawStore]:
        """
        Parse the McDonald's SG Zendesk article for store name, address,
        phone and operating hours.

        The article body is in `.article-body` (Zendesk standard selector).
        Two layouts are handled:
          A) HTML table  → each <tr> is one store (header row skipped)
          B) Plain text  → blank-line-separated blocks; first non-blank line
                           is the store name, subsequent labelled lines give
                           address / tel / hours
        """
        stores: List[RawStore] = []

        # ── Locate article body ───────────────────────────────────────────
        body_el = None
        for sel in (".article-body", ".article-content", "article", "[class*='article-body']"):
            try:
                el = page.query_selector(sel)
                if el:
                    body_el = el
                    break
            except Exception:
                pass

        if body_el is None:
            return stores

        # ── Strategy A: table ─────────────────────────────────────────────
        try:
            rows = body_el.query_selector_all("tr")
            if len(rows) > 1:
                header = [td.inner_text().strip().lower() for td in rows[0].query_selector_all("th, td")]
                # Map common column header names → indices
                col = {
                    "name":    next((i for i, h in enumerate(header) if "name" in h or "outlet" in h or "store" in h), 0),
                    "address": next((i for i, h in enumerate(header) if "address" in h or "location" in h), 1),
                    "phone":   next((i for i, h in enumerate(header) if "tel" in h or "phone" in h or "contact" in h), -1),
                    "hours":   next((i for i, h in enumerate(header) if "hour" in h or "operating" in h), -1),
                }
                for row in rows[1:]:
                    cells = [td.inner_text().strip() for td in row.query_selector_all("td")]
                    if not cells:
                        continue
                    def _cell(idx: int) -> str:
                        return cells[idx] if 0 <= idx < len(cells) else ""
                    name = _cell(col["name"])
                    address = _cell(col["address"])
                    if name or address:
                        stores.append(RawStore(
                            shop_name=name,
                            address=address,
                            phone=_cell(col["phone"]),
                            operating_hours=_cell(col["hours"]),
                        ))
                if stores:
                    return stores
        except Exception:
            pass

        # ── Strategy B: plain text blocks ────────────────────────────────
        try:
            raw_text = body_el.inner_text()
            # Split into blocks separated by one or more blank lines
            blocks = re.split(r"\n\s*\n", raw_text.strip())
            for block in blocks:
                lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
                if not lines:
                    continue
                name = lines[0]
                address = phone = hours = ""
                for line in lines[1:]:
                    ll = line.lower()
                    if ll.startswith("address"):
                        address = re.sub(r"^address\s*[:\-]\s*", "", line, flags=re.IGNORECASE)
                    elif ll.startswith("tel") or ll.startswith("phone"):
                        phone = re.sub(r"^(tel|phone)\s*[:\-]\s*", "", line, flags=re.IGNORECASE)
                    elif ll.startswith("operating") or ll.startswith("hour") or ll.startswith("open"):
                        hours = re.sub(r"^(operating hours?|hours?|opening hours?)\s*[:\-]\s*", "", line, flags=re.IGNORECASE)
                    elif not address:
                        # If no labelled address yet, treat second line as address
                        address = line
                # Skip blocks that look like headings/footers (no address at all)
                if name and (address or phone):
                    stores.append(RawStore(
                        shop_name=name,
                        address=address,
                        phone=phone,
                        operating_hours=hours,
                    ))
        except Exception:
            pass

        return stores

    def _interact_my(self, page: Page) -> None:
        """McDonald's Malaysia store finder interactions."""
        page.wait_for_timeout(5_000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3_000)
