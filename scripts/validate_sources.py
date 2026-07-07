#!/usr/bin/env python3
"""Validate candidate official/fallback source pages for competitor stores.

This is a lightweight discovery aid: it fetches known candidate pages and checks
whether a deterministic parser can extract plausible store records. It does not
replace the monthly pipeline; use its output to decide which scraper fixes to
implement next.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
}


@dataclass
class SourceResult:
    key: str
    competitor: str
    market: str
    source_type: str
    url: str
    status_code: int | None
    extracted_count: int
    confidence: str
    notes: str
    samples: list[dict]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch(url: str) -> tuple[int, str]:
    r = requests.get(url, headers=HEADERS, timeout=30)
    return r.status_code, r.text


def fetch_mcd_hk() -> tuple[int, list[dict]]:
    """Fetch McDonald's HK official WordPress AJAX store list."""
    r = requests.post(
        "https://mcdonalds.com.hk/wp-admin/admin-ajax.php",
        params={"action": "get_restaurants"},
        data={"type": "init"},
        headers={
            **HEADERS,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://mcdonalds.com.hk",
            "Referer": "https://mcdonalds.com.hk/en/find-a-restaurant/",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )
    data = r.json() if r.status_code == 200 else {}
    restaurants = data.get("restaurants", []) if isinstance(data, dict) else []
    stores: list[dict] = []
    if isinstance(restaurants, list):
        for item in restaurants:
            if not isinstance(item, dict):
                continue
            stores.append({
                "shop_name": clean(str(item.get("title") or "")),
                "address": clean(str(item.get("address") or "")),
                "phone": clean(str(item.get("telephone") or "")),
                "lat": item.get("lat"),
                "lon": item.get("lng"),
                "source_url": "https://mcdonalds.com.hk/wp-admin/admin-ajax.php?action=get_restaurants",
            })
    return r.status_code, stores


def parse_mcd_th(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    stores = []
    for card in soup.select(".store-container"):
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if not lines:
            continue
        stores.append({
            "shop_name": lines[0],
            "address": lines[1] if len(lines) > 1 else "",
            "lat": card.get("data-lat"),
            "lon": card.get("data-lng"),
            "source_url": card.get("href"),
        })
    return stores


def parse_mcd_vn(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    stores = []
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
        maps = card.find("a", href=re.compile("google.com/maps"))
        coords = re.search(r"place/(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)", maps.get("href", "") if maps else "")
        stores.append({
            "shop_name": name,
            "address": address,
            "phone": phone,
            "operating_hours": hours,
            "lat": coords.group(1) if coords else None,
            "lon": coords.group(2) if coords else None,
            "source_url": maps.get("href") if maps else None,
        })
    return stores


def parse_sushiro_hk(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    stores = []
    for card in soup.select(".store-list-box-wrapper"):
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if len(lines) < 2:
            continue
        phone = next((re.sub(r"^TEL\s*:?\s*", "", x, flags=re.I) for x in lines if x.upper().startswith("TEL")), "")
        stores.append({"shop_name": lines[0], "address": lines[1], "phone": phone})
    return stores


def parse_sushiro_th(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    stores = []
    for card in soup.select(".box-branch--detail"):
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if not lines:
            continue
        if lines[0] == "เส้นทาง":
            lines = lines[1:]
        name = lines[0] if lines else ""
        maps = card.find("a", href=True)
        stores.append({
            "shop_name": name,
            "address": lines[1] if len(lines) > 1 else "",
            "operating_hours": lines[2] if len(lines) > 2 else "",
            "phone": lines[3] if len(lines) > 3 else "",
            "source_url": maps.get("href") if maps else None,
        })
    return stores


def parse_sushiro_sg(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    stores = []
    seen = set()
    for link in soup.find_all("a", href=re.compile(r"maps\.app\.goo\.gl")):
        card = link.find_parent("div", class_=lambda c: c and "e-child" in c)
        if not card:
            continue
        lines = [clean(x) for x in card.get_text("\n", strip=True).split("\n") if clean(x)]
        if not lines or not lines[0].lower().startswith("sushiro"):
            continue
        name = lines[0]
        if name in seen:
            continue
        seen.add(name)
        # Address is usually lines between name and Operating Hours.
        try:
            end = lines.index("Operating Hours:")
        except ValueError:
            end = min(len(lines), 4)
        address = ", ".join(lines[1:end])
        hours = lines[end + 1] if end + 1 < len(lines) else ""
        stores.append({
            "shop_name": name,
            "address": address,
            "operating_hours": hours,
            "source_url": link.get("href"),
        })
    return stores


def validate() -> list[SourceResult]:
    specs: list[tuple[str, str, str, str, str, Callable[[str], list[dict]], tuple[int, int], str]] = [
        ("THM", "McDonald's", "TH", "official", "https://www.mcdonalds.co.th/storeLocations", parse_mcd_th, (50, 400), "official HTML contains .store-container cards with lat/lon"),
        ("VNM", "McDonald's", "VN", "official", "https://mcdonalds.vn/restaurants.html", parse_mcd_vn, (10, 80), "official HTML contains store cards and Google Maps coordinates"),
        ("HKS", "Sushiro", "HK", "official", "https://sushirohk.com.hk/tc/shop.php?wid=3&cid=1", parse_sushiro_hk, (15, 80), "official HTML contains .store-list-box-wrapper cards"),
        ("THS", "Sushiro", "TH", "official", "https://sushiro.co.th/branch/", parse_sushiro_th, (5, 80), "official HTML contains .box-branch--detail cards"),
        ("SGS", "Sushiro", "SG", "official", "https://www.sushiro.com.sg/contact-location/", parse_sushiro_sg, (5, 80), "official Elementor page contains one card per store with maps links"),
    ]
    results: list[SourceResult] = []

    try:
        code, rows = fetch_mcd_hk()
        expected = (150, 350)
        plausible = expected[0] <= len(rows) <= expected[1]
        complete_addr = sum(1 for r in rows if r.get("address"))
        complete_coords = sum(1 for r in rows if r.get("lat") not in (None, "") and r.get("lon") not in (None, ""))
        confidence = "high" if code == 200 and plausible and complete_addr == len(rows) else "medium" if rows else "low"
        notes = (
            "official WordPress AJAX endpoint returns restaurants; "
            f"expected {expected[0]}-{expected[1]}; addresses {complete_addr}/{len(rows)}; "
            f"coordinates {complete_coords}/{len(rows)}"
        )
        results.append(SourceResult(
            "HKM",
            "McDonald's",
            "HK",
            "official_ajax",
            "https://mcdonalds.com.hk/en/find-a-restaurant/",
            code,
            len(rows),
            confidence,
            notes,
            rows[:3],
        ))
    except Exception as exc:
        results.append(SourceResult(
            "HKM",
            "McDonald's",
            "HK",
            "official_ajax",
            "https://mcdonalds.com.hk/en/find-a-restaurant/",
            None,
            0,
            "low",
            f"validation failed: {exc}",
            [],
        ))

    for key, comp, market, source_type, url, parser, expected, note in specs:
        try:
            code, html = fetch(url)
            rows = parser(html)
            plausible = expected[0] <= len(rows) <= expected[1]
            complete_addr = sum(1 for r in rows if r.get("address"))
            confidence = "high" if code == 200 and plausible and complete_addr == len(rows) else "medium" if rows else "low"
            notes = f"{note}; expected {expected[0]}-{expected[1]}; addresses {complete_addr}/{len(rows)}"
            results.append(SourceResult(key, comp, market, source_type, url, code, len(rows), confidence, notes, rows[:3]))
        except Exception as exc:
            results.append(SourceResult(key, comp, market, source_type, url, None, 0, "low", f"validation failed: {exc}", []))
    return results


def render_markdown(results: list[SourceResult]) -> str:
    lines = [
        "# Source validation — CompetitorAddress",
        "",
        "Validated official/fallback sources for entries that failed the current Playwright scraper.",
        "",
        "| Key | Source | Count | Confidence | Notes |",
        "|---|---|---:|---|---|",
    ]
    for r in sorted(results, key=lambda x: x.key):
        lines.append(f"| `{r.key}` | {r.source_type}: {r.url} | {r.extracted_count} | {r.confidence} | {r.notes} |")
    lines.append("\n## Samples\n")
    for r in sorted(results, key=lambda x: x.key):
        lines.append(f"### {r.key} — {r.competitor} {r.market}\n")
        if not r.samples:
            lines.append("No deterministic official sample extracted.\n")
            continue
        lines.append("```json")
        lines.append(json.dumps(r.samples, ensure_ascii=False, indent=2))
        lines.append("```\n")
    return "\n".join(lines)


def main() -> int:
    results = validate()
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "source_validation_20260705.json").write_text(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_markdown(results)
    (REPORTS / "source_validation_20260705.md").write_text(md, encoding="utf-8")
    print(md)
    return 0 if all(r.confidence in {"high", "medium"} for r in results if r.key != "HKM") else 1


if __name__ == "__main__":
    raise SystemExit(main())
