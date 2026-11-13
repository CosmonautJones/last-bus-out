# Last Bus Out · v0.1.0

**Can workers without a car get to this shift, and home again?**

Paste a job posting. IBM Granite reads the address and shift times out of the messy text. Then a
deterministic engine checks every scheduled DDOT and SMART bus and colors the Detroit-area map:

- 🟢 **green**: a bus gets you there before the shift **and** a bus gets you home after it
- 🟠 **amber**: you can get there, but **no bus home** within 45 minutes of the shift ending
- ⚪ **grey**: no one-seat bus ride

Drag the shift-end slider and watch the map change. Granite then writes a three-sentence memo
for the employer. Every number in that memo is checked against the schedule data, and if Granite
invents one, the memo is rejected and replaced with a template.

Michigan DevFest + AI Hackathon, Nov 13 2026 · Focus area: **Next-Gen Mobility**
(transportation and logistics for Michigan) · overlaps Modernizing Michigan Manufacturing (shift work).

## The user and the problem

**User:** the HR or operations lead at a Southeast Michigan warehouse, hospital or auto supplier
who sets shift times. Second user: workforce boards that place job seekers.

**Problem:** employers set shift times without knowing whether car-free workers can get home.
About a third of Detroit residents don't own a car, DDOT's weekday afternoon on-time rate was
about two-thirds in 2025, and riders report evening service gaps. Existing tools (Transit app,
Google Maps, DDOT Bus Tracker) answer a rider's question about one trip. None answer the
employer's question: *if my shift ends at 11:30 PM, who can still get home?*

## How it works

| Step | What does it | AI? |
|---|---|---|
| Read the posting (address, shift start/end, days, notes like "rotating Saturdays") | **IBM Granite** on **watsonx.ai** | ✅ |
| Address → coordinates | U.S. Census Geocoder | no |
| Find bus stops ≤ 0.5 mi of the site; every scheduled trip through them | Python (pandas) over DDOT + SMART GTFS | no |
| For each census tract: a bus there before the shift? a bus home after? | Deterministic rules (shown in UI) | no |
| Weight by car-free households (ACS table B25044) | Python | no |
| Write the employer memo from computed facts; reject invented numbers | **IBM Granite** + number verifier | ✅ (checked) |

Rules (in `app/config.py`): walk ≤ 800 m each end at ~3 mph with a 1.3 street-detour factor;
arrive 5–60 min before shift start; a bus home must leave within 45 min of shift end; one-seat
rides ≤ 90 min. **Transfers are not modeled in v0.1**, so results are conservative.

## Run it

```bash
make setup                 # or: python -m venv .venv && pip install -r requirements.txt
cp .env.example .env       # add watsonx.ai API key + project ID (never commit .env)
make data                  # downloads public data, builds data/build/ (~1-3 min)
make run                   # http://localhost:8000
make test                  # synthetic-network tests, no internet needed
```

No watsonx access yet? Set `LBO_LLM_PROVIDER=ollama` (Granite open weights via `ollama pull granite3.3:8b`)
or `mock` (regex fallback, clearly labeled "not Granite" in the UI).

## Data sources (all public; details in `data/SOURCES.md`)

- DDOT GTFS schedule, City of Detroit
- SMART GTFS schedule, Suburban Mobility Authority for Regional Transportation
- U.S. Census Bureau ACS 5-year, table B25044 (tenure by vehicles available), tracts in Wayne, Oakland, Macomb
- U.S. Census Bureau cartographic boundary file, Michigan census tracts
- U.S. Census Geocoder

Sample job postings in `samples/` are **fictional**. No personal information is collected or stored.

## Tools used (required disclosure)

- **IBM Bob IDE**: core build tool (see `BOB_PLAYBOOK.md` and `bob_usage/`)
- **IBM watsonx.ai + IBM Granite**: posting extraction and employer memo
- **IBM Code Engine**: deployment target (`Dockerfile`)
- Claude (Anthropic) was used for research and the initial scaffold
- Leaflet + CARTO/OpenStreetMap basemap

## Limitations (we say these out loud)

- Scheduled times, not live arrivals. DDOT reliability means tight margins are risky.
- One-seat rides only; tract centroids approximate where people live; ACS estimates have margins of error.
- Weekend modeling uses one representative Saturday and Sunday from each feed.
