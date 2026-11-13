"""List available models in the watsonx.ai account."""
import json
import sys
import time
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import httpx
import os

api_key = os.getenv("WATSONX_API_KEY", "")
project_id = os.getenv("WATSONX_PROJECT_ID", "")
url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

if not api_key:
    print("WATSONX_API_KEY not set"); sys.exit(1)

# Get IAM token
r = httpx.post("https://iam.cloud.ibm.com/identity/token",
               data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
               headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
r.raise_for_status()
token = r.json()["access_token"]
print("IAM token obtained.")

# List chat-capable models
r = httpx.get(f"{url}/ml/v1/foundation_model_specs?version=2024-10-08&limit=200",
              headers={"Authorization": f"Bearer {token}"}, timeout=30)
r.raise_for_status()
models = r.json().get("resources", [])
granite_chat = [m for m in models if "granite" in m.get("model_id","").lower()
                and "chat" in str(m.get("functions", []))]
print(f"\nGranite chat-capable models ({len(granite_chat)}):")
for m in granite_chat:
    print(f"  {m['model_id']}")
print(f"\nAll granite models ({sum(1 for m in models if 'granite' in m.get('model_id','').lower())}):")
for m in models:
    mid = m.get("model_id","")
    if "granite" in mid.lower():
        funcs = [f.get("id","") for f in m.get("functions",[])]
        print(f"  {mid}  functions={funcs}")
