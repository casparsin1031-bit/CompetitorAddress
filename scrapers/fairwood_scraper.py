"""Fairwood scraper for official Hong Kong Next.js store locator."""

from __future__ import annotations

from typing import List

import requests

from .base_scraper import BaseScraper, RawStore
from .source_parsers import parse_fairwood_hk_nextjs


class FairwoodScraper(BaseScraper):
    """Deterministic scraper for Fairwood's official HK store locator."""

    def scrape(self) -> List[RawStore]:
        if self.market_code.upper() != "HK":
            return []

        response = requests.get(
            self.url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,zh-HK;q=0.8",
            },
            timeout=40,
        )
        response.raise_for_status()
        return parse_fairwood_hk_nextjs(response.text)
