"""Deterministic reachability engine: one-seat bus rides between a job site and every census tract.

For a job site we find every scheduled bus trip that stops within walking distance of it, then:
  inbound  = rides that board near a tract and get off near the site   (getting TO the shift)
  outbound = rides that board near the site and get off near a tract   (getting HOME after the shift)

Transfers are not modeled yet (v0.1), so results are conservative: a tract marked "no bus"
may still be reachable with a transfer. The UI says so.
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (ARRIVE_BUFFER_MIN, BUILD_DIR, MAX_EARLY_MIN, MAX_RIDE_MIN,
                     MAX_WAIT_HOME_MIN, MAX_WALK_M, WALK_DETOUR, WALK_SPEED_MPS)
from .geo import haversine_m, walk_seconds

DAY_TYPES = ("weekday", "saturday", "sunday")


@dataclass
class Rules:
    arrive_buffer_min: int = ARRIVE_BUFFER_MIN
    max_early_min: int = MAX_EARLY_MIN
    max_wait_home_min: int = MAX_WAIT_HOME_MIN
    max_ride_min: int = MAX_RIDE_MIN
    max_walk_m: int = MAX_WALK_M

    def as_dict(self):
        return dict(self.__dict__)


class Network:
    def __init__(self, build_dir: Path = BUILD_DIR):
        self.build_dir = Path(build_dir)
        self.meta = json.loads((self.build_dir / "meta.json").read_text(encoding="utf-8"))
        self.stops = pd.read_pickle(self.build_dir / "stops.pkl")
        self.routes = pd.read_pickle(self.build_dir / "routes.pkl")
        self.tracts = pd.read_pickle(self.build_dir / "tracts.pkl")
        self.stop_tract = pd.read_pickle(self.build_dir / "stop_tract.pkl")
        self.stop_times = {d: pd.read_pickle(self.build_dir / f"stop_times_{d}.pkl") for d in DAY_TYPES
                           if (self.build_dir / f"stop_times_{d}.pkl").exists()}
        self.route_labels = dict(zip(self.routes["route_idx"].astype(int), self.routes["label"].astype(str)))
        self.stop_names = dict(zip(self.stops["stop_idx"].astype(int), self.stops["name"].astype(str)))
        self.zero_car_total = int(self.tracts["zero_car_hh"].sum())

    # ------------------------------------------------------------------ core query
    def site_stops(self, lat: float, lon: float, max_walk_m: int = MAX_WALK_M) -> pd.DataFrame:
        d = haversine_m(lat, lon, self.stops["lat"].to_numpy(), self.stops["lon"].to_numpy())
        near = d <= max_walk_m
        out = self.stops.loc[near, ["stop_idx", "name", "lat", "lon", "agency"]].copy()
        out["dist_m"] = d[near]
        out["walk_s"] = walk_seconds(out["dist_m"], WALK_SPEED_MPS, WALK_DETOUR)
        return out.sort_values("dist_m")

    def reach(self, lat: float, lon: float, day_type: str = "weekday", rules: Rules | None = None) -> dict:
        """Return, for each tract, the one-seat ride options to and from the site.

        Times are minutes after midnight of the service day (can exceed 1440 for after-midnight trips).
        in:  [arrive_at_site_min, route_idx, door_to_door_min]
        out: [leave_site_min,     route_idx, door_to_door_min]
        """
        rules = rules or Rules()
        st = self.stop_times.get(day_type)
        if st is None:
            raise ValueError(f"No schedule built for day type '{day_type}'")
        site = self.site_stops(lat, lon, rules.max_walk_m)
        result = {"day_type": day_type, "rules": rules.as_dict(), "site_stops": [], "tracts": {}}
        result["site_stops"] = [
            {"name": r.name, "agency": r.agency, "dist_m": round(float(r.dist_m)), "lat": r.lat, "lon": r.lon}
            for r in site.head(8).itertuples()]
        if site.empty:
            return result

        at_site = st[st["stop_idx"].isin(site["stop_idx"])].merge(
            site[["stop_idx", "walk_s"]], on="stop_idx")
        at_site = at_site.rename(columns={"stop_idx": "site_stop", "seq": "seq_s", "arr": "arr_s",
                                          "dep": "dep_s", "walk_s": "walk_site"})
        same_trip = st[st["trip_idx"].isin(at_site["trip_idx"].unique())]
        m = same_trip.merge(at_site[["trip_idx", "seq_s", "arr_s", "dep_s", "walk_site"]], on="trip_idx")
        m = m.merge(self.stop_tract, on="stop_idx")  # adds tract_idx, walk_s (tract <-> stop)

        # Inbound: board near tract (earlier in trip), alight near site
        inb = m[m["seq"] < m["seq_s"]]
        inb = pd.DataFrame({
            "tract_idx": inb["tract_idx"],
            "route_idx": inb["route_idx"],
            "t_min": np.floor((inb["arr_s"] + inb["walk_site"]) / 60).astype(int),           # arrive at site
            "trip_min": np.ceil(((inb["arr_s"] + inb["walk_site"]) - (inb["dep"] - inb["walk_s"])) / 60).astype(int),
        })
        # Outbound: board near site, alight near tract (later in trip)
        outb = m[m["seq"] > m["seq_s"]]
        outb = pd.DataFrame({
            "tract_idx": outb["tract_idx"],
            "route_idx": outb["route_idx"],
            "t_min": np.floor((outb["dep_s"] - outb["walk_site"]) / 60).astype(int),         # leave site
            "trip_min": np.ceil(((outb["arr"] + outb["walk_s"]) - (outb["dep_s"] - outb["walk_site"])) / 60).astype(int),
        })

        def compact(df):
            df = df[df["trip_min"] <= rules.max_ride_min]
            # keep the fastest option per (tract, minute)
            df = df.sort_values("trip_min").drop_duplicates(["tract_idx", "t_min"])
            return {int(k): g.sort_values("t_min")[["t_min", "route_idx", "trip_min"]].to_numpy().tolist()
                    for k, g in df.groupby("tract_idx")}

        ins, outs = compact(inb), compact(outb)
        for t in set(ins) | set(outs):
            result["tracts"][t] = {"in": ins.get(t, []), "out": outs.get(t, [])}
        result["routes"] = {int(r): self.route_labels.get(int(r), str(r))
                            for t in result["tracts"].values() for lst in (t["in"], t["out"]) for _, r, _ in lst}
        return result

    # ------------------------------------------------------------------ evaluation (mirrors web/app.js)
    @staticmethod
    def tract_status(opts: dict, start_min: int, end_min: int, rules: Rules) -> tuple:
        lo, hi = start_min - rules.max_early_min, start_min - rules.arrive_buffer_min
        can_in = next((o for o in opts.get("in", []) if lo <= o[0] <= hi), None)
        homes = [o for o in opts.get("out", []) if end_min <= o[0] <= end_min + rules.max_wait_home_min]
        can_out = homes[0] if homes else None
        return can_in, can_out

    def evaluate(self, reach: dict, start_min: int, end_min: int, rules: Rules | None = None) -> dict:
        rules = rules or Rules()
        if end_min <= start_min:
            end_min += 1440  # overnight shift
        zc = dict(zip(self.tracts["tract_idx"].astype(int), self.tracts["zero_car_hh"].astype(int)))
        both = to_only = 0
        hh_both = hh_to_only = 0
        first_home = []
        for t, opts in reach["tracts"].items():
            a, b = self.tract_status(opts, start_min, end_min, rules)
            if a and b:
                both += 1
                hh_both += zc.get(int(t), 0)
                first_home.append(b[0])
            elif a:
                to_only += 1
                hh_to_only += zc.get(int(t), 0)
        total = self.zero_car_total or 1
        # latest bus leaving the site within the wait window, across all tracts (for the "last bus" line)
        window = [o for opts in reach["tracts"].values() for o in opts.get("out", [])
                  if end_min <= o[0] <= end_min + rules.max_wait_home_min]
        last_bus = max(window, key=lambda o: o[0]) if window else None
        return {
            "start_min": start_min, "end_min": end_min,
            "tracts_round_trip": both, "tracts_to_only": to_only,
            "zero_car_hh_round_trip": hh_both, "zero_car_hh_to_only": hh_to_only,
            "zero_car_hh_total": self.zero_car_total,
            "pct_round_trip": round(100 * hh_both / total, 1),
            "stranded_hh": hh_to_only,
            "last_bus_home": ({"leave_min": int(last_bus[0]), "route": self.route_labels.get(int(last_bus[1]), "")}
                              if last_bus else None),
        }

    def best_end_time(self, reach: dict, start_min: int, end_min: int, rules: Rules | None = None,
                      window_min: int = 120, step: int = 15) -> dict | None:
        """Search nearby shift-end times (same shift length shift is not assumed) for better round-trip coverage."""
        base = self.evaluate(reach, start_min, end_min, rules)
        best = None
        for delta in range(-window_min, window_min + 1, step):
            if delta == 0:
                continue
            e = self.evaluate(reach, start_min, end_min + delta, rules)
            if e["zero_car_hh_round_trip"] > base["zero_car_hh_round_trip"]:
                if best is None or e["zero_car_hh_round_trip"] > best["zero_car_hh_round_trip"] or (
                        e["zero_car_hh_round_trip"] == best["zero_car_hh_round_trip"] and abs(delta) < abs(best["delta"])):
                    best = {**e, "delta": delta}
        return best


@lru_cache(maxsize=1)
def get_network() -> Network:
    return Network()


def fmt_time(minutes: int) -> str:
    """Minutes after midnight -> '11:42 PM' (wraps after-midnight times)."""
    m = int(minutes) % 1440
    h, mm = divmod(m, 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{mm:02d} {suffix}"


def parse_hhmm(s: str) -> int:
    h, m = s.strip().split(":")[:2]
    return int(h) * 60 + int(m)
