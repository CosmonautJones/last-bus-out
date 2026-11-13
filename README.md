# Last Bus Out · v0.1.5

**Can workers without a car get to this shift, and home again?**

**[▶ Demo video (1 min)](https://youtu.be/d1puFY888es)**

Last Bus Out is a small web app for the person who sets shift times at a Southeast Michigan
warehouse, hospital or auto supplier. Paste a job posting and it shows, on a map, which
neighborhoods can reach that shift by bus and still catch a bus home afterwards.

Built for the Michigan DevFest + AI Hackathon (Detroit, November 13, 2026). Team: **Trav**.
Focus area: Next-Gen Mobility.

## Why it exists

About one in three Detroit residents don't own a car. Transit apps (Google Maps, Transit,
DDOT Bus Tracker) answer a rider's question about one trip. None of them answer the
employer's question: **if my shift ends at 11:30 PM, who can still get home?**

Employers who don't know the answer shrink their own hiring pool and strand late-shift workers.

## What you see in the demo

One of the sample postings is a fictional warehouse in Romulus with a 3:00 PM to 11:30 PM shift
and the line "Reliable transportation required." For that shift the app shows:

- **1,867 car-free households** live where a bus gets them to the shift on time.
- **None of them** have a bus home: the last SMART 280 leaves at 11:23 PM, seven minutes
  before the shift ends.
- Move the shift end to 11:00 PM and **1,699 of those households** can make the round trip.

## How to use it

1. **Paste a job posting** (or click one of the three samples) and press **Check this shift**.
2. **IBM Granite reads the posting** and pulls out the employer, address, shift times and days.
   You can see exactly what it read, and the raw JSON.
3. **The map colors every census tract** in Wayne, Oakland and Macomb counties:

   | Color | Meaning |
   |---|---|
   | Green | A bus gets you there before the shift **and** a bus gets you home after it |
   | Amber | You can get there, but there is **no bus home** within 45 minutes of the shift ending |
   | Grey | No one-seat bus ride to this site |

4. **Read the result**: the share and number of car-free households that can make the round
   trip, and a **"Last bus home"** line showing the last scheduled bus and how many minutes
   before or after the shift it leaves.
5. **Drag the shift sliders** and the map recolors instantly. If the posting lists two shifts,
   buttons let you switch between them and a line compares their coverage.
6. **Granite writes a short memo for the employer.** Every number in the memo is checked against
   the computed facts. If Granite invents a number, the memo is thrown away and replaced with a
   plain template.

## How it works

The AI reads and writes text. It never decides who can get to work; the bus schedules do.

| Step | What does it | AI? |
|---|---|---|
| Read the posting (address, shift start and end, days, notes) | **IBM Granite** on **watsonx.ai** | Yes |
| Turn the address into coordinates | U.S. Census Geocoder | No |
| Find bus stops within a half-mile walk of the site and every scheduled trip through them | Python (pandas) over the DDOT and SMART schedules | No |
| For each census tract: is there a bus before the shift, and a bus home after? | Fixed rules, listed below | No |
| Weight each tract by its car-free households | Census ACS table B25044 | No |
| Write the employer memo from the computed facts | **IBM Granite**, then a number checker | Yes, checked |

**The rules** (set in `app/config.py`):

- Walk at most 800 m (about half a mile) at each end, at roughly 3 mph with a 1.3 street-detour factor.
- Arrive between 5 and 60 minutes before the shift starts.
- A bus home must leave within 45 minutes of the shift ending.
- One-seat rides only, 90 minutes at most. **Transfers are not modeled yet**, so results are conservative.

**Size of the real data build:** 10,541 bus stops, 82 routes, 1,218 census tracts (739 with a stop
in walking distance) and about 130,800 car-free households.

## Run it yourself

Requires Python 3.10 or newer, an IBM watsonx.ai API key and project ID, and a free Census API key.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then add your watsonx.ai key, project ID and Census key
.venv\Scripts\python scripts\fetch_data.py
.venv\Scripts\python scripts\build_index.py
.venv\Scripts\uvicorn app.main:app --port 8000      # open http://localhost:8000
.venv\Scripts\python -m pytest -q tests
```

macOS / Linux:

```bash
make setup && cp .env.example .env    # add your keys to .env (never commit it)
make data                             # downloads the public data and builds data/build/
make run                              # http://localhost:8000
make test
```

The city's DDOT download blocks scripts. To use the newest DDOT schedule, download
`ddot_gtfs.zip` from the City of Detroit in a browser, save it as `data/raw/ddot_gtfs.zip`,
and run `build_index.py` again. `fetch_data.py` never overwrites a file that is already there.

No watsonx.ai access? Set `LBO_LLM_PROVIDER=ollama` to run Granite's open weights locally, or
`mock` for a regex fallback that the UI clearly labels as "not Granite".

## Project layout

| Path | What it is |
|---|---|
| `app/main.py` | FastAPI server and JSON API |
| `app/engine.py` | The deterministic reachability engine |
| `app/granite.py` | Granite calls: posting extraction, memo, number checker |
| `app/geocode.py` | U.S. Census Geocoder client |
| `scripts/fetch_data.py`, `scripts/build_index.py` | Download the public data and build the index |
| `scripts/record_demo.py` | Optional: records the captioned demo video with Playwright |
| `web/` | The one-page interface (Leaflet map) |
| `samples/postings.json` | Three fictional job postings |
| `tests/` | Tests on a small synthetic bus network (no internet needed) |
| `data/SOURCES.md` | Every data source and its terms |
| `HACKATHON.md`, `BOB_PLAYBOOK.md`, `bob_usage/` | Submission kit and IBM Bob usage evidence |

## Data sources

All public; details and links are in `data/SOURCES.md`.

- DDOT bus schedule (GTFS), City of Detroit
- SMART bus schedule (GTFS), Suburban Mobility Authority for Regional Transportation
- U.S. Census Bureau ACS 5-year table B25044 (vehicles available by household), tracts in Wayne, Oakland and Macomb
- U.S. Census Bureau tract boundaries and Geocoder

The sample job postings are **fictional**. No personal information is collected or stored.

## Tools used (required disclosure)

- **IBM Bob IDE**: core build tool. Bob ran and fixed the real-data pipeline, wired and verified
  Granite on watsonx.ai, and made the Windows and basemap fixes (see `BOB_PLAYBOOK.md` and `bob_usage/`).
- **IBM watsonx.ai + IBM Granite** (`ibm/granite-4-h-small`): posting extraction and the employer memo.
- **Claude (Anthropic)**: research, the initial scaffold, the front-end polish in v0.1.2 and later
  (shift switch, last-bus line, styling), this README and the demo recording script.
- **IBM Code Engine**: optional deployment target (`Dockerfile`); not deployed for the demo.
- Leaflet with the Esri World Light Gray basemap.
- No Google tools were used.

## Limitations

- **Scheduled times, not live arrivals.** DDOT's weekday afternoon on-time rate was about two-thirds
  in 2025, so treat tight margins as risky.
- **The DDOT schedule in the demo is from July 2026**, the newest copy that could be downloaded
  automatically. The SMART schedule is current (November 2026). The page footer shows both dates.
- **One-seat rides only.** A tract shown as grey may still be reachable with a transfer.
- **The memo's numbers are checked exactly; its wording only partly.** Two known misleading phrasings
  are caught and replaced with the template, but the map and the counts beside it are the source of truth.
- Tract centers approximate where people live, and Census estimates have margins of error.
- Weekend results use one representative Saturday and Sunday from each feed.
