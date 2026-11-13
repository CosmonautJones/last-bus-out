# Submission kit (Michigan DevFest + AI Hackathon, Nov 13 2026)

Deadline: **6:00 PM hard close** · target submit 5:45 PM · feature freeze 5:00 PM · video by 5:30 PM.

## Rules checklist (from the IBM Hackathon Guide and keynote)
- [x] **IBM Bob IDE used as a core component** (required for judging eligibility) → `BOB_PLAYBOOK.md`
- [x] **`bob_usage/` folder with each participant's Bob Budget screenshot (PNG)**
- [x] Public GitHub repo, **no API keys** (history scanned at v0.1.3) (leaked IBM keys get the cloud account suspended)
- [x] Only public data, no personal info; every source listed → `data/SOURCES.md`
- [x] Not using out-of-scope watsonx.ai models: llama-3-405b-instruct, mistral-medium-2505, mistral-small-3-1-24b-instruct-2503
- [x] AI tools disclosed (Bob, watsonx.ai/Granite, Claude) → README
- [ ] One-minute demo video uploaded; URL in submission
- [ ] Team lead submits before 6:00 PM
- [ ] Export anything from IBM Cloud / Bob you want to keep (accounts close after the event)

## Problem statement
HR and operations leads at Southeast Michigan warehouses, hospitals and auto suppliers set shift
times without knowing whether workers who don't own a car can get to the shift and back home by bus,
which shrinks their hiring pool and strands late-shift workers.

## Solution statement
Last Bus Out turns a pasted job posting into a map of which neighborhoods can make the round trip by
DDOT or SMART bus for that exact shift. IBM Granite on watsonx.ai reads the posting and writes a short
memo for the employer; every number comes from deterministic analysis of public bus schedules and
Census car-ownership data, and the memo is rejected if Granite invents a number.

## How we used IBM (and Google) tools
| Tool | What it does in our app |
|---|---|
| IBM Bob IDE | Core build tool: ran and fixed the real-data pipeline (DDOT/SMART GTFS, Census ACS), wired and verified Granite on watsonx.ai, Windows encoding and basemap fixes, tests, commits |
| IBM watsonx.ai + IBM Granite (`ibm/granite-4-h-small`) | Extracts address/shift times/days from messy postings; writes the employer memo from computed facts, with every number verified |
| Google tools | Not used |
| Claude (Anthropic) | Research, initial scaffold, v0.1.2 front-end polish (disclosed in README) |

## One-minute video script
| Time | Beat | Say / show |
|---|---|---|
| 0:00 | User | "This is for the person who sets shift times at a Michigan warehouse." |
| 0:10 | Problem | "A third of Detroiters don't own a car. Nobody tells employers whether there's a bus home at 11:30 PM." |
| 0:20 | Click 1 | Click the Romulus sample → "Check this shift". Granite pulls out the address and 3 PM–11:30 PM shift. |
| 0:30 | Click 2 | Map is all amber: 1,867 car-free households can ride in, zero can ride home. "The last bus leaves at 11:23, seven minutes before the shift ends." |
| 0:40 | Click 3 | Drag the shift end to 11:00 PM; the map turns green (1,699 households); Granite's memo updates with a verified suggestion. |
| 0:50 | Impact | "Employers widen their hiring pool, workers don't get stranded. Granite reads; the schedules decide." |

## Three-minute pitch: what's next (one more week)
Transfers between routes, live DDOT reliability per route, a workforce-board view that ranks job
postings by transit access, and SMS output for job seekers.
