"""Central configuration. Everything tunable is an env var with a sane default."""
import os
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data"))
SNAPSHOT_PATH = DATA_DIR / "snapshot_jan2026.json"
SYNTHETIC_PATH = DATA_DIR / "synthetic_jan2026.json"
STATIC_DIR = Path(os.getenv("STATIC_DIR", BACKEND_DIR.parent / "frontend" / "dist"))

# auto: snapshot file if present, else live Elexon fetch | snapshot | live | synthetic
DATA_SOURCE = os.getenv("DATA_SOURCE", "auto")

# Decisions made in January 2026 (each one is for delivery on the following day).
DECISION_START = date(2026, 1, 1)
DECISION_END = date(2026, 1, 31)

# ASSUMPTION: local (UK) wall-clock time on day D-1 after which new forecasts can no
# longer inform the day-ahead bid. GB day-ahead auctions close in the morning
# (~09:20-09:50 UK); we default to 09:00 to stay on the safe side. Configurable in UI.
DEFAULT_GATE = time.fromisoformat(os.getenv("DEFAULT_GATE", "09:00"))

ELEXON_BASE = os.getenv("ELEXON_BASE", "https://data.elexon.co.uk/bmrs/api/v1")
