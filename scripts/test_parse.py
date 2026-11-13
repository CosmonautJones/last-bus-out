"""POST each sample posting to /api/parse and print the result."""
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
samples = json.loads((ROOT / "samples" / "postings.json").read_text())

for s in samples:
    print(f"\n--- {s['id']}: {s['title']} ---")
    try:
        r = httpx.post("http://localhost:8000/api/parse",
                       json={"text": s["text"]},
                       timeout=60)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        print(f"  REQUEST FAILED: {e}")
        sys.exit(1)

    provider = d.get("provider", "")
    print(f"  provider : {provider}")
    print(f"  fallback : {d.get('fallback')}")
    if d.get("error"):
        print(f"  error    : {d['error']}")
    p = d.get("posting", {})
    print(f"  address  : {p.get('address')}")
    for sh in p.get("shifts", []):
        print(f"  shift    : {sh['label']}  {sh['start']}-{sh['end']}  days={sh['days']}")
    if "watsonx" not in provider.lower():
        print("  *** WARNING: provider is NOT IBM watsonx.ai ***")
    time.sleep(1)

print("\nDone.")
