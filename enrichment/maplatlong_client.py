"""
maplatlong client — subprocess wrapper for the casparsin1031-bit/maplatlong repo.

The maplatlong script takes a shop name and address string and returns
lat/long + GADM level-2 geographic attributes (province, city, district).

Expected call interface (assumed from repo description):
    python geocode.py --name "<shop_name>" --address "<address>"

Expected stdout (JSON):
    {
        "lat": 22.2988,
        "lon": 114.1722,
        "province": "Hong Kong",
        "city": "Wan Chai",
        "district": "Wan Chai"
    }

Configure the path to the cloned maplatlong repo via the MAPLATLONG_DIR
environment variable (default: ../maplatlong relative to this project).

If the lookup fails (non-zero exit, timeout, malformed JSON), all geo
fields are returned as None so the pipeline can continue without crashing.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import TypedDict


MAPLATLONG_DIR = os.environ.get("MAPLATLONG_DIR", "../maplatlong")
LOOKUP_TIMEOUT = int(os.environ.get("MAPLATLONG_TIMEOUT", "30"))  # seconds


class GeoResult(TypedDict):
    lat: float | None
    lon: float | None
    province: str | None
    city: str | None
    district: str | None


_EMPTY: GeoResult = {
    "lat": None,
    "lon": None,
    "province": None,
    "city": None,
    "district": None,
}


def lookup(shop_name: str, address: str) -> GeoResult:
    """
    Call the maplatlong geocode script and return geographic attributes.

    Parameters
    ----------
    shop_name : str
        The name of the store (passed to maplatlong for context).
    address : str
        Full address string for geocoding.

    Returns
    -------
    GeoResult
        Dict with lat, lon, province, city, district.
        All values are None on failure.
    """
    if not address.strip() and not shop_name.strip():
        return dict(_EMPTY)

    script = os.path.join(MAPLATLONG_DIR, "geocode.py")
    if not os.path.isfile(script):
        # maplatlong not cloned — return empty rather than crashing the pipeline
        return dict(_EMPTY)

    try:
        result = subprocess.run(
            ["python", script, "--name", shop_name, "--address", address],
            capture_output=True,
            text=True,
            timeout=LOOKUP_TIMEOUT,
            cwd=MAPLATLONG_DIR,
        )
    except subprocess.TimeoutExpired:
        return dict(_EMPTY)
    except Exception:
        return dict(_EMPTY)

    if result.returncode != 0:
        return dict(_EMPTY)

    try:
        data: dict = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return dict(_EMPTY)

    return GeoResult(
        lat=_to_float(data.get("lat")),
        lon=_to_float(data.get("lon") or data.get("lng") or data.get("longitude")),
        province=_to_str(data.get("province") or data.get("state")),
        city=_to_str(data.get("city") or data.get("municipality")),
        district=_to_str(data.get("district") or data.get("subdistrict")),
    )


def _to_float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_str(value) -> str | None:
    return str(value).strip() if value is not None else None
