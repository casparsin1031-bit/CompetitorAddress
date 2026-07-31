from __future__ import annotations

import html
import json
import re
from typing import Any

from bs4 import BeautifulSoup

from .base_scraper import RawStore


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _coords_from_maps_url(url: str) -> tuple[float | None, float | None]:
    """Extract decimal lat/lon from common Google Maps URL forms."""
    patterns = [
        r"place/(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        r"[?&]q=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        r"@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


def parse_mcd_hk_api(data: dict[str, Any]) -> list[RawStore]:
    """Parse McDonald's Hong Kong official admin-ajax restaurant payload."""
    restaurants = data.get("restaurants", [])
    if not isinstance(restaurants, list):
        return []

    stores: list[RawStore] = []
    for item in restaurants:
        if not isinstance(item, dict):
            continue
        name = clean(str(item.get("title") or item.get("name") or ""))
        address = clean(str(item.get("address") or ""))
        if not name and not address:
            continue
        lat = item.get("lat")
        lon = item.get("lng") or item.get("lon")
        stores.append(RawStore(
            shop_name=name,
            address=address,
            phone=clean(str(item.get("telephone") or "")),
            lat=float(lat) if lat not in (None, "") else None,
            lon=float(lon) if lon not in (None, "") else None,
        ))
    return stores


def parse_mcd_th(html: str) -> list[RawStore]:
    """Parse McDonald's Thailand official `.store-container` cards."""
    soup = BeautifulSoup(html, "html.parser")
    stores: list[RawStore] = []
    for card in soup.select(".store-container"):
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if not lines:
            continue
        lat = card.get("data-lat")
        lon = card.get("data-lng")
        stores.append(RawStore(
            shop_name=lines[0],
            address=lines[1] if len(lines) > 1 else "",
            lat=float(lat) if lat else None,
            lon=float(lon) if lon else None,
        ))
    return stores


def parse_mcd_vn(html: str) -> list[RawStore]:
    """Parse McDonald's Vietnam official `.tbox-address-store` cards."""
    soup = BeautifulSoup(html, "html.parser")
    stores: list[RawStore] = []
    for card in soup.select(".tbox-address-store"):
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if not lines:
            continue
        name = lines[0]
        address = ""
        hours = ""
        phone = ""
        for i, line in enumerate(lines):
            low = line.lower().rstrip(":")
            if low == "address" and i + 1 < len(lines):
                address = lines[i + 1]
            elif low == "opening time" and i + 1 < len(lines):
                hours = lines[i + 1]
            elif low == "hotline" and i + 1 < len(lines):
                phone = lines[i + 1]
        maps = card.find("a", href=re.compile(r"google\.(?:com|com\.vn)/maps|maps\.google"))
        lat, lon = _coords_from_maps_url(maps.get("href", "") if maps else "")
        stores.append(RawStore(
            shop_name=name,
            address=address,
            phone=phone,
            operating_hours=hours,
            lat=lat,
            lon=lon,
        ))
    return stores


def parse_sushiro_hk(html: str) -> list[RawStore]:
    """Parse Sushiro Hong Kong official `.store-list-box-wrapper` cards."""
    soup = BeautifulSoup(html, "html.parser")
    stores: list[RawStore] = []
    for card in soup.select(".store-list-box-wrapper"):
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if len(lines) < 2:
            continue
        phone = next((re.sub(r"^TEL\s*:?\s*", "", x, flags=re.I) for x in lines if x.upper().startswith("TEL")), "")
        stores.append(RawStore(shop_name=lines[0], address=lines[1], phone=phone))
    return stores


def parse_sushiro_th(html: str) -> list[RawStore]:
    """Parse Sushiro Thailand official `.box-branch--detail` cards."""
    soup = BeautifulSoup(html, "html.parser")
    stores: list[RawStore] = []
    for card in soup.select(".box-branch--detail"):
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if not lines:
            continue
        if lines[0] == "เส้นทาง":
            lines = lines[1:]
        if not lines:
            continue
        stores.append(RawStore(
            shop_name=lines[0],
            address=lines[1] if len(lines) > 1 else "",
            operating_hours=lines[2] if len(lines) > 2 else "",
            phone=lines[3] if len(lines) > 3 else "",
        ))
    return stores


def parse_sushiro_sg(html: str) -> list[RawStore]:
    """Parse Sushiro Singapore official Elementor cards with maps links."""
    soup = BeautifulSoup(html, "html.parser")
    stores: list[RawStore] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=re.compile(r"maps\.app\.goo\.gl|google\.(?:com|com\.sg)/maps|maps\.google")):
        card = link.find_parent("div", class_=lambda c: c and "e-child" in c)
        if not card:
            card = link.find_parent("div", class_=lambda c: c and "elementor" in c)
        if not card:
            continue
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if not lines or not lines[0].lower().startswith("sushiro"):
            continue
        name = lines[0]
        if name in seen:
            continue
        seen.add(name)
        try:
            end = lines.index("Operating Hours:")
        except ValueError:
            end = min(len(lines), 4)
        address = ", ".join(lines[1:end])
        hours = lines[end + 1] if end + 1 < len(lines) else ""
        lat, lon = _coords_from_maps_url(link.get("href", ""))
        stores.append(RawStore(shop_name=name, address=address, operating_hours=hours, lat=lat, lon=lon))
    return stores


def parse_fairwood_hk_nextjs(page_html: str) -> list[RawStore]:
    """Parse Fairwood Hong Kong official Next.js ``__NEXT_DATA__`` store list."""
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        page_html,
        re.S,
    )
    if not match:
        return []

    try:
        data = json.loads(html.unescape(match.group(1)))
        stores_data = data["props"]["pageProps"]["data"]["stores"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return []

    if not isinstance(stores_data, list):
        return []

    stores: list[RawStore] = []
    for item in stores_data:
        if not isinstance(item, dict):
            continue
        name = clean(str(item.get("name") or ""))
        address = clean(str(item.get("address") or ""))
        if not name and not address:
            continue
        lat = item.get("latitude")
        lon = item.get("longitude")
        stores.append(RawStore(
            shop_name=name,
            address=address,
            phone=clean(str(item.get("phoneNumber") or "")),
            lat=float(lat) if lat not in (None, "") else None,
            lon=float(lon) if lon not in (None, "") else None,
        ))
    return stores


def to_plain_dict(store: RawStore) -> dict[str, Any]:
    row: dict[str, Any] = {
        "shop_name": store.shop_name,
        "address": store.address,
        "phone": store.phone,
        "operating_hours": store.operating_hours,
    }
    if store.lat is not None:
        row["lat"] = store.lat
    if store.lon is not None:
        row["lon"] = store.lon
    return row
