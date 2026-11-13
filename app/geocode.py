"""Address -> lat/lon using the free U.S. Census Geocoder (no key, no personal data)."""
import re

import httpx

URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def geocode(address: str) -> dict | None:
    # Allow "42.33,-83.05" so the demo can skip geocoding entirely
    m = re.fullmatch(r"\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*", address or "")
    if m:
        return {"lat": float(m.group(1)), "lon": float(m.group(2)), "matched": "coordinates", "source": "input"}
    if not address:
        return None
    q = address if re.search(r"\bMI\b|Michigan", address, re.I) else f"{address}, MI"
    try:
        r = httpx.get(URL, params={"address": q, "benchmark": "Public_AR_Current", "format": "json"}, timeout=15)
        r.raise_for_status()
        matches = r.json().get("result", {}).get("addressMatches", [])
    except (httpx.HTTPError, ValueError):
        return None
    if not matches:
        return None
    c = matches[0]["coordinates"]
    return {"lat": float(c["y"]), "lon": float(c["x"]), "matched": matches[0].get("matchedAddress"),
            "source": "U.S. Census Geocoder"}
