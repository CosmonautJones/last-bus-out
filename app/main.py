"""FastAPI app: serves the one-page UI and a small JSON API.

Run:  uvicorn app.main:app --reload --port 8000
"""
import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, granite
from .engine import DAY_TYPES, Rules, fmt_time, get_network, parse_hhmm
from .geocode import geocode

app = FastAPI(title="Last Bus Out", version=config.VERSION)


class TextIn(BaseModel):
    text: str


class AddressIn(BaseModel):
    address: str


class SiteIn(BaseModel):
    lat: float
    lon: float
    day_type: str = "weekday"


class MemoIn(SiteIn):
    start: str  # "HH:MM"
    end: str
    site_label: str = "this location"
    employer: str | None = None


def network():
    try:
        return get_network()
    except FileNotFoundError:
        raise HTTPException(503, "Data not built yet. Run: python scripts/fetch_data.py && python scripts/build_index.py")


@lru_cache(maxsize=64)
def _reach_cached(lat: float, lon: float, day_type: str) -> dict:
    return network().reach(lat, lon, day_type)


def reach_for(lat, lon, day_type):
    if day_type not in DAY_TYPES:
        raise HTTPException(400, f"day_type must be one of {DAY_TYPES}")
    return _reach_cached(round(lat, 4), round(lon, 4), day_type)


@app.get("/api/health")
def health():
    info = {"version": config.VERSION, "llm_provider": config.LLM_PROVIDER, "granite_model":
            config.GRANITE_MODEL_ID if config.LLM_PROVIDER == "watsonx" else config.OLLAMA_MODEL}
    try:
        n = get_network()
        info.update(data_loaded=True, meta=n.meta)
    except FileNotFoundError:
        info.update(data_loaded=False)
    return info


@app.get("/api/tracts")
def tracts():
    p = config.BUILD_DIR / "tracts.geojson"
    if not p.exists():
        raise HTTPException(503, "Data not built yet")
    return FileResponse(p, media_type="application/geo+json")


@app.get("/api/samples")
def samples():
    p = config.SAMPLES_DIR / "postings.json"
    return json.loads(p.read_text()) if p.exists() else []


@app.post("/api/parse")
def parse(body: TextIn):
    if len(body.text) > 8000:
        raise HTTPException(413, "Posting too long")
    return granite.parse_posting(body.text)


@app.post("/api/geocode")
def do_geocode(body: AddressIn):
    g = geocode(body.address)
    if not g:
        raise HTTPException(404, "Could not find that address. Click the map to place the job site instead.")
    return g


@app.post("/api/reach")
def reach(body: SiteIn):
    r = reach_for(body.lat, body.lon, body.day_type)
    n = network()
    return JSONResponse({**r, "zero_car_hh_total": n.zero_car_total, "service_dates": {
        a: v.get(body.day_type, {}).get("date") for a, v in n.meta.get("feeds", {}).items()}})


@app.post("/api/memo")
def memo(body: MemoIn):
    n = network()
    r = reach_for(body.lat, body.lon, body.day_type)
    rules = Rules()
    start, end = parse_hhmm(body.start), parse_hhmm(body.end)
    ev = n.evaluate(r, start, end, rules)
    best = n.best_end_time(r, start, end, rules)
    facts = {
        "employer": body.employer or "the employer",
        "site": body.site_label,
        "shift": f"{fmt_time(start)} to {fmt_time(ev['end_min'])} ({body.day_type})",
        "zero_car_hh_round_trip": f"{ev['zero_car_hh_round_trip']:,}",
        "pct_round_trip": f"{ev['pct_round_trip']}%",
        "zero_car_hh_region": f"{ev['zero_car_hh_total']:,}",
        "stranded_hh": f"{ev['stranded_hh']:,}" if ev["stranded_hh"] else None,
        "last_bus_home": (f"{ev['last_bus_home']['route']} leaving {fmt_time(ev['last_bus_home']['leave_min'])}"
                          if ev["last_bus_home"] else "no bus leaves within the wait window"),
        "suggestion": (f"Ending the shift at {fmt_time(best['end_min'])} would let "
                       f"{best['zero_car_hh_round_trip']:,} car-free households make the round trip."
                       if best else None),
    }
    out = granite.write_memo(facts)
    return {"facts": facts, "evaluation": ev, "best_alternative": best, **out}


# ---- static UI (must be last so /api routes win)
app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")
