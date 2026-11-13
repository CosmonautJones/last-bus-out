"""Central settings. Everything secret comes from environment variables (see .env.example)."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text().strip()

RAW_DIR = Path(os.getenv("LBO_RAW_DIR", ROOT / "data" / "raw"))
BUILD_DIR = Path(os.getenv("LBO_BUILD_DIR", ROOT / "data" / "build"))
WEB_DIR = ROOT / "web"
SAMPLES_DIR = ROOT / "samples"

# --- Reachability rules (deterministic, shown in the UI so judges can see them) ---
MAX_WALK_M = int(os.getenv("LBO_MAX_WALK_M", "800"))          # ~0.5 mile to/from a stop
WALK_SPEED_MPS = 1.34                                          # ~3 mph
WALK_DETOUR = 1.3                                              # straight line -> street distance
ARRIVE_BUFFER_MIN = int(os.getenv("LBO_ARRIVE_BUFFER_MIN", "5"))   # must arrive >= 5 min before shift start
MAX_EARLY_MIN = int(os.getenv("LBO_MAX_EARLY_MIN", "60"))          # ...but not more than 60 min early
MAX_WAIT_HOME_MIN = int(os.getenv("LBO_MAX_WAIT_HOME_MIN", "45"))  # a bus home must leave within 45 min of shift end
MAX_RIDE_MIN = int(os.getenv("LBO_MAX_RIDE_MIN", "90"))            # ignore one-seat rides longer than 90 min

# Counties covered: Wayne (163), Oakland (125), Macomb (099) in Michigan (26)
STATE_FIPS = "26"
COUNTY_FIPS = ["163", "125", "099"]

# --- Granite provider ---
# LBO_LLM_PROVIDER: "watsonx" (IBM watsonx.ai, Dallas), "ollama" (Granite open weights locally), or "mock"
LLM_PROVIDER = os.getenv("LBO_LLM_PROVIDER", "watsonx")
WATSONX_URL = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_API_KEY = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
# Check Prompt Lab for the exact Granite model IDs available in the hackathon account.
GRANITE_MODEL_ID = os.getenv("GRANITE_MODEL_ID", "ibm/granite-4-h-small")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite3.3:8b")
LLM_TIMEOUT_S = float(os.getenv("LBO_LLM_TIMEOUT_S", "30"))
