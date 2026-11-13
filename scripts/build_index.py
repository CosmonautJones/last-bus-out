"""Turn the raw public data into small, fast lookup tables in data/build/.

    python scripts/build_index.py

Everything here is deterministic. No AI is involved in any number the app shows.
"""
import datetime as dt
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# Load .env if present so the script works without manually exporting vars
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import (BUILD_DIR, COUNTY_FIPS, MAX_WALK_M, RAW_DIR,  # noqa: E402
                        STATE_FIPS, WALK_DETOUR, WALK_SPEED_MPS)
from app.geo import haversine_m, walk_seconds  # noqa: E402

FEEDS = [("DDOT", "ddot_gtfs.zip"), ("SMART", "smart_gtfs.zip")]
DAY_TYPES = {"weekday": 2, "saturday": 5, "sunday": 6}  # Python weekday(): Mon=0 ... Wed=2


# ----------------------------------------------------------------------------- GTFS
def read_gtfs(path: Path) -> dict:
    """Read a GTFS feed from a .zip or a directory into DataFrames (all columns as str)."""
    tables = {}
    wanted = ["stops", "routes", "trips", "stop_times", "calendar", "calendar_dates", "agency"]
    if path.is_dir():
        for t in wanted:
            f = path / f"{t}.txt"
            if f.exists():
                tables[t] = pd.read_csv(f, dtype=str, keep_default_na=False)
    else:
        with zipfile.ZipFile(path) as z:
            names = {Path(n).name: n for n in z.namelist()}
            for t in wanted:
                n = names.get(f"{t}.txt")
                if n:
                    with z.open(n) as fh:
                        tables[t] = pd.read_csv(fh, dtype=str, keep_default_na=False)
    for t in ["stops", "routes", "trips", "stop_times"]:
        if t not in tables:
            raise ValueError(f"{path}: missing {t}.txt")
    return tables


def to_seconds(s: pd.Series) -> pd.Series:
    """'25:10:00' -> 90600. Blank -> NaN. GTFS allows hours >= 24 for after-midnight trips."""
    s = s.str.strip()
    parts = s.str.split(":", expand=True)
    out = pd.Series(np.nan, index=s.index)
    ok = s != ""
    if ok.any():
        h = pd.to_numeric(parts.loc[ok, 0], errors="coerce")
        m = pd.to_numeric(parts.loc[ok, 1], errors="coerce")
        sec = pd.to_numeric(parts.loc[ok, 2], errors="coerce") if parts.shape[1] > 2 else 0
        out.loc[ok] = h * 3600 + m * 60 + sec
    return out


def active_services(feed: dict, date: dt.date) -> set:
    ymd = date.strftime("%Y%m%d")
    dow = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][date.weekday()]
    active = set()
    cal = feed.get("calendar")
    if cal is not None and len(cal):
        m = (cal["start_date"] <= ymd) & (cal["end_date"] >= ymd) & (cal[dow] == "1")
        active |= set(cal.loc[m, "service_id"])
    cd = feed.get("calendar_dates")
    if cd is not None and len(cd):
        day = cd[cd["date"] == ymd]
        active |= set(day.loc[day["exception_type"] == "1", "service_id"])
        active -= set(day.loc[day["exception_type"] == "2", "service_id"])
    return active


def pick_service_date(feed: dict, weekday: int, label: str, agency: str) -> tuple:
    """Pick a real date with this weekday that the feed actually covers.

    Prefers the next matching date from today; falls back to scanning backwards
    (expired feed) so the build never silently produces an empty network.
    Override with env LBO_SERVICE_DATE (YYYY-MM-DD) to force a specific date for all feeds.
    """
    override = os.getenv("LBO_SERVICE_DATE")
    if override:
        d = dt.date.fromisoformat(override)
        return d, active_services(feed, d)
    today = dt.date.today()
    for step in list(range(0, 120)) + [-x for x in range(1, 400)]:
        d = today + dt.timedelta(days=step)
        if d.weekday() != weekday:
            continue
        svc = active_services(feed, d)
        if svc:
            if step < 0:
                print(f"  WARNING {agency} {label}: feed has no service after today; using past date {d}")
            return d, svc
    print(f"  WARNING {agency} {label}: no active service found at all")
    return None, set()


# ----------------------------------------------------------------------------- tracts + ACS
def read_tracts(raw_dir: Path) -> pd.DataFrame:
    """Return GEOID, name, county, centroid lat/lon and a simplified GeoJSON geometry."""
    from shapely.geometry import mapping, shape

    gj = raw_dir / "tracts.geojson"  # optional pre-converted file (used by tests)
    feats = []
    if gj.exists():
        for f in json.loads(gj.read_text(encoding="utf-8"))["features"]:
            feats.append((f["properties"], shape(f["geometry"])))
    else:
        import shapefile  # pyshp
        z = raw_dir / "mi_tracts.zip"
        if not z.exists():
            raise FileNotFoundError("data/raw/mi_tracts.zip missing; run scripts/fetch_data.py")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            zipfile.ZipFile(z).extractall(td)
            shp = next(Path(td).glob("*.shp"))
            r = shapefile.Reader(str(shp))
            fields = [f[0] for f in r.fields[1:]]
            for sr in r.iterShapeRecords():
                props = dict(zip(fields, sr.record))
                feats.append((props, shape(sr.shape.__geo_interface__)))
            r.close()  # release file handles before temp dir cleanup (needed on Windows)
    rows = []
    for props, geom in feats:
        if str(props.get("STATEFP", STATE_FIPS)) != STATE_FIPS or str(props.get("COUNTYFP")) not in COUNTY_FIPS:
            continue
        c = geom.representative_point()  # always inside the polygon
        simple = geom.simplify(0.0004, preserve_topology=True)
        rows.append({
            "geoid": str(props["GEOID"]),
            "name": str(props.get("NAMELSAD") or props.get("NAME") or props["GEOID"]),
            "county": str(props["COUNTYFP"]),
            "lat": c.y, "lon": c.x,
            "geometry": mapping(simple),
        })
    return pd.DataFrame(rows)


def read_acs(raw_dir: Path) -> pd.DataFrame:
    data = json.loads((raw_dir / "acs_b25044.json").read_text(encoding="utf-8"))
    df = pd.DataFrame(data["rows"])
    df["geoid"] = df["state"] + df["county"] + df["tract"]
    for c in ["B25044_001E", "B25044_003E", "B25044_010E"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).clip(lower=0)  # Census uses negatives for N/A
    df["total_hh"] = df["B25044_001E"].astype(int)
    df["zero_car_hh"] = (df["B25044_003E"] + df["B25044_010E"]).astype(int)
    return df[["geoid", "total_hh", "zero_car_hh"]], data.get("year")


# ----------------------------------------------------------------------------- build
def build(raw_dir: Path = RAW_DIR, build_dir: Path = BUILD_DIR, feeds=FEEDS) -> dict:
    build_dir.mkdir(parents=True, exist_ok=True)
    meta = {"built_at": dt.datetime.now().isoformat(timespec="seconds"), "feeds": {}, "rules": {
        "max_walk_m": MAX_WALK_M, "walk_speed_mps": WALK_SPEED_MPS, "walk_detour": WALK_DETOUR}}

    all_stops, all_routes, st_by_day = [], [], {d: [] for d in DAY_TYPES}
    trip_offset = 0
    for agency, fname in feeds:
        p = raw_dir / fname
        if not p.exists():
            print(f"  skip {agency}: {p} not found")
            continue
        print(f"  reading {agency}")
        g = read_gtfs(p)
        stops = g["stops"].copy()
        if "location_type" in stops:
            stops = stops[stops["location_type"].isin(["", "0"])]
        stops = pd.DataFrame({
            "stop_id": agency + ":" + stops["stop_id"],
            "name": stops.get("stop_name", ""),
            "lat": pd.to_numeric(stops["stop_lat"]), "lon": pd.to_numeric(stops["stop_lon"]),
            "agency": agency,
        })
        all_stops.append(stops)
        r = g["routes"]
        routes = pd.DataFrame({
            "route_key": agency + ":" + r["route_id"], "agency": agency,
            "short": r.get("route_short_name", ""), "long": r.get("route_long_name", ""),
        })
        all_routes.append(routes)

        trips = g["trips"][["trip_id", "route_id", "service_id"]].copy()
        trips["trip_key"] = agency + ":" + trips["trip_id"]
        trips["route_key"] = agency + ":" + trips["route_id"]
        stt = g["stop_times"][["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"]].copy()
        stt["arr"] = to_seconds(stt["arrival_time"])
        stt["dep"] = to_seconds(stt["departure_time"])
        stt["arr"] = stt["arr"].fillna(stt["dep"])
        stt["dep"] = stt["dep"].fillna(stt["arr"])
        stt["seq"] = pd.to_numeric(stt["stop_sequence"])
        stt = stt.sort_values(["trip_id", "seq"])
        # interpolate blank (non-timepoint) times within each trip
        if stt["arr"].isna().any():
            stt["arr"] = stt.groupby("trip_id")["arr"].transform(lambda s: s.interpolate(limit_area="inside"))
            stt["dep"] = stt["dep"].fillna(stt["arr"])
        stt = stt.dropna(subset=["arr", "dep"])
        stt["stop_id"] = agency + ":" + stt["stop_id"]
        stt["trip_key"] = agency + ":" + stt["trip_id"]

        meta["feeds"][agency] = {}
        for label, wd in DAY_TYPES.items():
            date, svc = pick_service_date(g, wd, label, agency)
            act = trips[trips["service_id"].isin(svc)]
            day = stt[stt["trip_key"].isin(act["trip_key"])].merge(act[["trip_key", "route_key"]], on="trip_key")
            st_by_day[label].append(day[["trip_key", "route_key", "stop_id", "seq", "arr", "dep"]])
            meta["feeds"][agency][label] = {"date": date.isoformat() if date else None,
                                            "trips": int(act.shape[0]), "stop_times": int(day.shape[0])}
            print(f"    {label:8s} {date}  trips={act.shape[0]}  stop_times={day.shape[0]}")
        cal = g.get("calendar")
        if cal is not None and len(cal):
            meta["feeds"][agency]["calendar_range"] = [cal["start_date"].min(), cal["end_date"].max()]

    if not all_stops:
        raise SystemExit("No GTFS feeds found in data/raw. Run scripts/fetch_data.py first.")

    stops = pd.concat(all_stops, ignore_index=True).drop_duplicates("stop_id").reset_index(drop=True)
    stops["stop_idx"] = stops.index.astype("int32")
    routes = pd.concat(all_routes, ignore_index=True).drop_duplicates("route_key").reset_index(drop=True)
    routes["route_idx"] = routes.index.astype("int32")
    routes["label"] = np.where(routes["short"].astype(str).str.len() > 0,
                               routes["agency"] + " " + routes["short"].astype(str), routes["agency"] + " " + routes["long"].astype(str))
    stop_ix = dict(zip(stops["stop_id"], stops["stop_idx"]))
    route_ix = dict(zip(routes["route_key"], routes["route_idx"]))

    for label, parts in st_by_day.items():
        day = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
            columns=["trip_key", "route_key", "stop_id", "seq", "arr", "dep"])
        trip_codes, _ = pd.factorize(day["trip_key"])
        out = pd.DataFrame({
            "trip_idx": trip_codes.astype("int32"),
            "route_idx": day["route_key"].map(route_ix).astype("int32"),
            "stop_idx": day["stop_id"].map(stop_ix),
            "seq": day["seq"].astype("int32"),
            "arr": day["arr"].astype("int32"),
            "dep": day["dep"].astype("int32"),
        }).dropna()
        out["stop_idx"] = out["stop_idx"].astype("int32")
        out.sort_values(["trip_idx", "seq"]).reset_index(drop=True).to_pickle(build_dir / f"stop_times_{label}.pkl")

    stops.to_pickle(build_dir / "stops.pkl")
    routes.to_pickle(build_dir / "routes.pkl")

    # tracts + zero-car households
    print("  reading tracts + ACS")
    tracts = read_tracts(raw_dir)
    acs, acs_year = read_acs(raw_dir)
    tracts = tracts.merge(acs, on="geoid", how="left").fillna({"total_hh": 0, "zero_car_hh": 0})
    tracts = tracts.sort_values("geoid").reset_index(drop=True)
    tracts["tract_idx"] = tracts.index.astype("int32")
    meta["acs_year"] = acs_year
    meta["tracts"] = int(len(tracts))
    meta["zero_car_hh_total"] = int(tracts["zero_car_hh"].sum())

    # stop <-> tract walk links (from tract representative point, <= MAX_WALK_M)
    links = []
    s_lat, s_lon = stops["lat"].to_numpy(), stops["lon"].to_numpy()
    for t in tracts.itertuples():
        d = haversine_m(t.lat, t.lon, s_lat, s_lon)
        near = np.nonzero(d <= MAX_WALK_M)[0]
        for i in near:
            links.append((int(i), int(t.tract_idx), float(walk_seconds(d[i], WALK_SPEED_MPS, WALK_DETOUR))))
    stop_tract = pd.DataFrame(links, columns=["stop_idx", "tract_idx", "walk_s"])
    stop_tract = stop_tract.astype({"stop_idx": "int32", "tract_idx": "int32", "walk_s": "float32"})
    stop_tract.to_pickle(build_dir / "stop_tract.pkl")
    meta["tracts_with_stop"] = int(stop_tract["tract_idx"].nunique())

    tracts.drop(columns=["geometry"]).to_pickle(build_dir / "tracts.pkl")
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": row.geometry,
         "properties": {"i": int(row.tract_idx), "geoid": row.geoid, "name": row.name,
                        "zc": int(row.zero_car_hh), "hh": int(row.total_hh)}}
        for row in tracts.itertuples()]}
    (build_dir / "tracts.geojson").write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    (build_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  stops={len(stops)} routes={len(routes)} tracts={len(tracts)} "
          f"tracts_with_stop={meta['tracts_with_stop']} zero_car_hh={meta['zero_car_hh_total']}")
    return meta


if __name__ == "__main__":
    build()
    print(f"Done. Build written to {BUILD_DIR}")
