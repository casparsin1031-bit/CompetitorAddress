from .mcdonalds_scraper import McDonaldsScraper
from .changee_scraper import ChangeeScraper
from .sushiro_scraper import SushiroScraper
from .luckin_scraper import LuckinScraper

REGISTRY: dict = {
    "McDonaldsScraper": McDonaldsScraper,
    "ChangeeScraper": ChangeeScraper,
    "SushiroScraper": SushiroScraper,
    "LuckinScraper": LuckinScraper,
}
