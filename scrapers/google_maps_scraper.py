"""
Google Maps scraper — Playwright-based.

For competitors that have no official store-locator website, this scraper
searches Google Maps and visits each place detail page to extract the address.

self.url should be a Google Maps search URL, e.g.:
  https://www.google.com/maps/search/Luckin+Coffee+Hong+Kong/?hl=en

The hl=en parameter forces English results, which gives clean English
addresses for non-English-speaking markets like HK.
"""

from __future__ import annotations

from typing import List

from playwright.sync_api import sync_playwright

from .base_scraper import BaseScraper, RawStore


class GoogleMapsScraper(BaseScraper):
    """Playwright scraper that uses Google Maps search to find stores."""

    def scrape(self) -> List[RawStore]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            page = context.new_page()
            page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)

            # Dismiss consent / cookie dialog if present
            for label in ("Accept all", "Agree", "I agree"):
                try:
                    page.get_by_role("button", name=label).click(timeout=3_000)
                    page.wait_for_timeout(1_000)
                    break
                except Exception:
                    pass

            # Wait for results feed
            try:
                page.wait_for_selector("div[role='feed']", timeout=30_000)
            except Exception:
                browser.close()
                return []

            # Scroll the feed to load all results (Google Maps lazy-loads)
            feed = page.locator("div[role='feed']")
            for _ in range(20):
                prev = page.locator("div[role='feed'] a[href*='/maps/place/']").count()
                feed.evaluate("el => el.scrollTop = el.scrollHeight")
                page.wait_for_timeout(2_000)
                cur = page.locator("div[role='feed'] a[href*='/maps/place/']").count()
                if cur == prev:
                    break

            # Collect unique place-detail URLs from the feed
            hrefs = list(dict.fromkeys(
                a.get_attribute("href")
                for a in page.locator("div[role='feed'] a[href*='/maps/place/']").all()
                if a.get_attribute("href")
            ))

            stores: List[RawStore] = []
            for href in hrefs:
                try:
                    page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(2_000)

                    name = page.locator("h1").first.inner_text().strip()

                    # Address row — data-item-id="address" has been stable in Maps
                    addr_btn = page.locator("[data-item-id='address']")
                    address = (
                        addr_btn.locator("div").first.inner_text().strip()
                        if addr_btn.count() else ""
                    )

                    # Phone row
                    phone_btn = page.locator("[data-item-id^='phone:tel']")
                    phone = (
                        phone_btn.locator("div").first.inner_text().strip()
                        if phone_btn.count() else ""
                    )

                    if name or address:
                        stores.append(RawStore(
                            shop_name=name,
                            address=address,
                            phone=phone,
                        ))
                except Exception:
                    pass

            browser.close()
        return stores
