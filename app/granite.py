"""IBM Granite layer. Granite does two language jobs; it never produces a number the app relies on.

1. parse_posting(): messy job-posting text -> structured shift JSON (address, start/end, days).
2. write_memo():    computed facts -> a 3-sentence memo for the employer. Every number in the memo
                    is checked against the facts; if Granite invents one, we fall back to a template.

Providers (env LBO_LLM_PROVIDER):
  watsonx - IBM watsonx.ai chat API (hackathon account, Dallas region)
  ollama  - Granite open weights running locally (backup if cloud access is slow)
  mock    - regex fallback for offline demos; clearly labeled as NOT Granite in the UI
"""
import json
import re
import time

import httpx
from pydantic import BaseModel, Field, ValidationError

from . import config

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Shift(BaseModel):
    label: str = "Shift"
    start: str = Field(..., description="24h HH:MM")
    end: str = Field(..., description="24h HH:MM")
    days: list[str] = Field(default_factory=list)


class Posting(BaseModel):
    employer: str | None = None
    job_title: str | None = None
    address: str | None = None
    shifts: list[Shift] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


PARSE_SYSTEM = (
    "You extract structured data from job postings. Reply with ONLY a JSON object, no prose. "
    "Schema: {\"employer\": string|null, \"job_title\": string|null, \"address\": string|null, "
    "\"shifts\": [{\"label\": string, \"start\": \"HH:MM\" (24-hour), \"end\": \"HH:MM\" (24-hour), "
    "\"days\": [\"Mon\"|\"Tue\"|\"Wed\"|\"Thu\"|\"Fri\"|\"Sat\"|\"Sun\"]}], \"notes\": [string]}. "
    "address must be the street address or intersection where the work happens, including city. "
    "Convert times like 3pm or 11:30 PM to 24-hour HH:MM. If days are not stated, use Mon-Fri. "
    "Put scheduling details that do not fit (rotating shifts, mandatory overtime, weekends) in notes. "
    "Never invent an address or time that is not in the text; use null or omit the shift."
)

MEMO_SYSTEM = (
    "You write a short, plain-language memo to an employer about whether workers without a car can "
    "get to and from a shift by bus. Write at most 3 sentences. Use ONLY the numbers that appear in the "
    "FACTS JSON, copied exactly as written there. Do not compute new numbers, percentages or times. "
    "Do not promise anything about bus reliability. End with one concrete suggestion if FACTS has one."
)


# ----------------------------------------------------------------------------- providers
class LLMError(RuntimeError):
    pass


_token_cache = {"token": None, "exp": 0.0}


def _watsonx_token() -> str:
    if _token_cache["token"] and time.time() < _token_cache["exp"] - 60:
        return _token_cache["token"]
    if not config.WATSONX_API_KEY:
        raise LLMError("WATSONX_API_KEY not set")
    r = httpx.post("https://iam.cloud.ibm.com/identity/token",
                   data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": config.WATSONX_API_KEY},
                   headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=config.LLM_TIMEOUT_S)
    r.raise_for_status()
    j = r.json()
    _token_cache.update(token=j["access_token"], exp=time.time() + int(j.get("expires_in", 3600)))
    return _token_cache["token"]


def _chat_watsonx(system: str, user: str, max_tokens: int) -> str:
    if not config.WATSONX_PROJECT_ID:
        raise LLMError("WATSONX_PROJECT_ID not set")
    r = httpx.post(
        f"{config.WATSONX_URL}/ml/v1/text/chat?version=2024-10-08",
        headers={"Authorization": f"Bearer {_watsonx_token()}", "Content-Type": "application/json"},
        json={"model_id": config.GRANITE_MODEL_ID, "project_id": config.WATSONX_PROJECT_ID,
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
              "max_tokens": max_tokens, "temperature": 0},
        timeout=config.LLM_TIMEOUT_S)
    if r.status_code >= 400:
        raise LLMError(f"watsonx {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _chat_ollama(system: str, user: str, max_tokens: int, json_mode: bool) -> str:
    body = {"model": config.OLLAMA_MODEL, "stream": False, "options": {"temperature": 0, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["format"] = "json"
    r = httpx.post(f"{config.OLLAMA_URL}/api/chat", json=body, timeout=config.LLM_TIMEOUT_S * 2)
    if r.status_code >= 400:
        raise LLMError(f"ollama {r.status_code}: {r.text[:300]}")
    return r.json()["message"]["content"]


def chat(system: str, user: str, max_tokens: int = 600, json_mode: bool = False) -> tuple[str, str]:
    """Returns (text, provider_label)."""
    p = config.LLM_PROVIDER
    if p == "watsonx":
        return _chat_watsonx(system, user, max_tokens), f"IBM watsonx.ai · {config.GRANITE_MODEL_ID}"
    if p == "ollama":
        return _chat_ollama(system, user, max_tokens, json_mode), f"Granite (local) · {config.OLLAMA_MODEL}"
    raise LLMError("mock provider selected")


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


# ----------------------------------------------------------------------------- 1. parse posting
def parse_posting(text: str) -> dict:
    """Returns {"posting": Posting dict, "provider": str, "raw": str, "fallback": bool, "error": str|None}."""
    error = None
    if config.LLM_PROVIDER != "mock":
        for attempt in range(2):
            try:
                raw, provider = chat(PARSE_SYSTEM, f"JOB POSTING:\n{text}", max_tokens=500, json_mode=True)
                posting = Posting.model_validate(_extract_json(raw))
                posting.shifts = [s for s in posting.shifts if _valid_hhmm(s.start) and _valid_hhmm(s.end)]
                return {"posting": posting.model_dump(), "provider": provider, "raw": raw,
                        "fallback": False, "error": None}
            except (LLMError, httpx.HTTPError, ValidationError, json.JSONDecodeError, KeyError) as e:
                error = f"{type(e).__name__}: {e}"
    posting = mock_parse(text)
    return {"posting": posting.model_dump(), "provider": "Fallback regex parser (not Granite)",
            "raw": json.dumps(posting.model_dump(), indent=2), "fallback": True, "error": error}


def _valid_hhmm(s: str) -> bool:
    return bool(re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", s or ""))


_TIME = r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m?\.?"


def _to24(h: str, m: str | None, ap: str) -> str:
    h, m = int(h), int(m or 0)
    if ap.lower() == "p" and h != 12:
        h += 12
    if ap.lower() == "a" and h == 12:
        h = 0
    return f"{h:02d}:{m:02d}"


def mock_parse(text: str) -> Posting:
    """Deterministic fallback so the demo never dies. Labeled as not-Granite in the UI."""
    shifts = []
    for i, m in enumerate(re.finditer(_TIME + r"\s*(?:-|–|—|to)\s*" + _TIME, text, flags=re.I)):
        shifts.append(Shift(label=f"Shift {i + 1}", start=_to24(*m.groups()[:3]), end=_to24(*m.groups()[3:]),
                            days=DAYS[:5]))
    addr = None
    m = re.search(r"(?:location|address|where)\s*:\s*(.+)", text, flags=re.I)
    if m:
        addr = m.group(1).strip()
    else:
        m = re.search(r"\d{2,6}\s+[A-Z][\w .]+(?:Rd|Road|Ave|Avenue|St|Street|Blvd|Dr|Drive|Hwy|Pkwy)\b[^\n]*", text)
        addr = m.group(0).strip() if m else None
    notes = [w for w in ["rotating", "overtime", "weekend", "overnight"] if w in text.lower()]
    return Posting(address=addr, shifts=shifts, notes=[f"mentions {n}" for n in notes])


# ----------------------------------------------------------------------------- 2. memo + number check
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?(?::\d{2})?")


def _numbers(s: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUM.findall(s)}


def verify_numbers(memo: str, facts: dict) -> tuple[bool, list[str]]:
    allowed = _numbers(json.dumps(facts))
    found = _numbers(memo)
    bad = sorted(n for n in found if n not in allowed)
    return (not bad), bad


def template_memo(f: dict) -> str:
    s = (f"For the {f['shift']} shift at {f['site']}, {f['zero_car_hh_round_trip']} car-free households "
         f"({f['pct_round_trip']}) can make the full round trip by bus with no transfers.")
    if f.get("stranded_hh"):
        s += f" Another {f['stranded_hh']} car-free households can get there by bus but have no bus home within the wait window."
    if f.get("suggestion"):
        s += f" {f['suggestion']}"
    return s


def write_memo(facts: dict) -> dict:
    error = None
    if config.LLM_PROVIDER != "mock":
        try:
            memo, provider = chat(MEMO_SYSTEM, "FACTS:\n" + json.dumps(facts, indent=2), max_tokens=220)
            memo = memo.strip()
            ok, bad = verify_numbers(memo, facts)
            if ok:
                return {"memo": memo, "provider": provider, "verified": True, "rejected_numbers": [], "fallback": False}
            error = f"Granite used numbers not in the facts: {bad}"
            return {"memo": template_memo(facts), "provider": provider + " (rejected → template)",
                    "verified": True, "rejected_numbers": bad, "fallback": True, "error": error}
        except (LLMError, httpx.HTTPError, KeyError) as e:
            error = f"{type(e).__name__}: {e}"
    return {"memo": template_memo(facts), "provider": "Template (not Granite)", "verified": True,
            "rejected_numbers": [], "fallback": True, "error": error}
