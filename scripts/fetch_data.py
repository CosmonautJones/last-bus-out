"""Download the public datasets into data/raw/. Run once on a machine with internet:

    python scripts/fetch_data.py

Sources (all public; see data/SOURCES.md):
  - DDOT GTFS schedule (City of Detroit)
  - SMART GTFS schedule (Suburban Mobility Authority for Regional Transportation)
  - Census ACS 5-year table B25044 (tenure by vehicles available), tracts in Wayne/Oakland/Macomb
  - Census cartographic boundary file for Michigan census tracts
"""
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import COUNTY_FIPS, RAW_DIR, STATE_FIPS  # noqa: E402

ACS_YEAR = os.getenv("LBO_ACS_YEAR", "2023")
TIGER_YEAR = os.getenv("LBO_TIGER_YEAR", "2023")

DOWNLOADS = {
    "ddot_gtfs.zip": "https://www.detroitmi.gov/Portals/0/docs/deptoftransportation/pdfs/ddot_gtfs.zip",
    "smart_gtfs.zip": "https://apps1.smartbus.org/gtfs/smart_gtfs.zip",
    "mi_tracts.zip": f"https://www2.census.gov/geo/tiger/GENZ{TIGER_YEAR}/shp/cb_{TIGER_YEAR}_{STATE_FIPS}_tract_500k.zip",
}


def download(name: str, url: str) -> None:
    out = RAW_DIR / name
    if out.exists() and out.stat().st_size > 0:
        print(f"  skip {name} (already downloaded)")
        return
    print(f"  get  {name} <- {url}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120,
                      headers={"User-Agent": "last-bus-out-hackathon/0.1"}) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    print(f"       {out.stat().st_size/1e6:.1f} MB")


def fetch_acs() -> None:
    out = RAW_DIR / "acs_b25044.json"
    if out.exists():
        print("  skip acs_b25044.json (already downloaded)")
        return
    rows = []
    key = os.getenv("CENSUS_API_KEY", "")  # optional; small queries work without one
    for county in COUNTY_FIPS:
        url = (f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
               f"?get=NAME,B25044_001E,B25044_003E,B25044_010E"
               f"&for=tract:*&in=state:{STATE_FIPS}%20county:{county}")
        if key:
            url += f"&key={key}"
        print(f"  get  ACS {ACS_YEAR} B25044 county {county}")
        r = httpx.get(url, timeout=60)
        r.raise_for_status()
        data = r.json()
        header, body = data[0], data[1:]
        rows.extend(dict(zip(header, row)) for row in body)
    out.write_text(json.dumps({"year": ACS_YEAR, "table": "B25044", "rows": rows}))
    print(f"       {len(rows)} tracts")


if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading into {RAW_DIR}")
    for name, url in DOWNLOADS.items():
        try:
            download(name, url)
        except Exception as e:  # keep going so one failure doesn't block the rest
            print(f"  FAILED {name}: {e}")
    try:
        fetch_acs()
    except Exception as e:
        print(f"  FAILED ACS: {e}")
    print("Done. Next: python scripts/build_index.py")
