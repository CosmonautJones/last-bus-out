# Last Bus Out — Hackathon Submission

**Michigan DevFest + AI Hackathon · Detroit · November 13, 2026 · Team: Trav**

---

## One-line pitch

> *Can workers without a car get to this shift, and home again?*

---

## Demo video

**<https://youtu.be/d1puFY888es>**

---

## Problem statement

HR and operations leads at Southeast Michigan warehouses, hospitals and auto suppliers set shift
times without knowing whether workers who don't own a car can get to the shift and back home by
bus. That gap shrinks their hiring pool and strands late-shift workers — with no tool today that
answers the employer's side of the transit question.

---

## Solution statement

Last Bus Out turns a pasted job posting into a map of which neighborhoods can make the round trip
by DDOT or SMART bus for that exact shift. IBM Granite on watsonx.ai reads the posting and writes
a short memo for the employer; every number comes from deterministic analysis of public bus
schedules and Census car-ownership data, and the memo is rejected and replaced if Granite invents
a number.

---

## Technology statement

| Layer | Technology |
|---|---|
| **Core build tool** | **IBM Bob IDE** — ran and fixed the DDOT/SMART GTFS + Census ACS pipeline, wired and verified Granite on watsonx.ai, made Windows encoding and basemap fixes, wrote and ran the test suite, managed commits (see `BOB_PLAYBOOK.md` and `bob_usage/`) |
| **AI — extraction & memo** | **IBM watsonx.ai + IBM Granite** (`ibm/granite-4-h-small`) — extracts employer, address, shift times and days from raw job postings; writes the employer summary memo from computed facts, with every number verified |
| **Reachability engine** | Pure Python + pandas over the public GTFS feeds and Census ACS table B25044; no AI in the decision path |
| **Front end** | FastAPI + Leaflet (one-page web app) |
| **IBM Orchestrate** | Not used |

**IBM Bob is the central build tool for this project.** Every meaningful code change, pipeline
fix and integration test was driven through Bob. See `BOB_PLAYBOOK.md` for the session-by-session
log and `bob_usage/` for the Bob Budget screenshot.

---

## Bob usage evidence

Screenshots are in [`bob_usage/`](bob_usage/) — specifically
`bob_usage/Trav_MichiganDevFest2026_IBM_Bob_usage.png`.

A full session-by-session log of what Bob built, fixed and verified is in
[`BOB_PLAYBOOK.md`](BOB_PLAYBOOK.md).
