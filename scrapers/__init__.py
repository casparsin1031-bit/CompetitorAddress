from .mcdonalds_scraper import McDonaldsScraper
from .changee_scraper import ChangeeScraper
from .sushiro_scraper import SushiroScraper
from .luckin_scraper import LuckinScraper
from .google_maps_scraper import GoogleMapsScraper

REGISTRY: dict = {
    "McDonaldsScraper": McDonaldsScraper,
    "ChangeeScraper": ChangeeScraper,
    "SushiroScraper": SushiroScraper,
    "LuckinScraper": LuckinScraper,
    "GoogleMapsScraper": GoogleMapsScraper,
}
