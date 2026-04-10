from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class RawStore:
    """Minimal store record as scraped from the competitor website."""
    shop_name: str
    address: str
    phone: str = ""
    operating_hours: str = ""


class BaseScraper(ABC):
    """
    Abstract base for all competitor scrapers.

    Each concrete subclass handles one competitor (possibly multiple markets
    via config). The single required method is `scrape()`, which returns a
    list of RawStore objects for the configured competitor-market entry.

    Subclasses that use Playwright must implement `_scrape_async()` and can
    call `self.run_async()` to execute it from the synchronous `scrape()`.
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.market_code: str = config["market_code"]
        self.competitor_name: str = config["competitor_name"]
        self.competitor_initial: str = config["competitor_initial"]
        self.url: str = config["url"]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    def scrape(self) -> List[RawStore]:
        """Return all stores for this competitor-market entry."""
        ...

    # ------------------------------------------------------------------
    # Helpers available to subclasses
    # ------------------------------------------------------------------

    def run_async(self, coro) -> List[RawStore]:
        """Run an async coroutine synchronously (used by Playwright scrapers)."""
        return asyncio.run(coro)

    @property
    def label(self) -> str:
        return f"{self.competitor_name} {self.market_code}"
