"""Download January-2026 WIND actuals (FUELHH) and forecasts (WINDFOR) from Elexon and
freeze them into backend/data/snapshot_jan2026.json.

Run once, commit the file: the app then starts instantly and never depends on Elexon at
request time (January 2026 is history, so the data does not change).

    python scripts/fetch_snapshot.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import config, store  # noqa: E402

actuals, forecasts = store.fetch_live()
print(f"actuals: {len(actuals)} rows | forecasts: {len(forecasts)} rows")
if not actuals or not forecasts:
    sys.exit("Empty result - check the Elexon endpoint/params before committing a snapshot.")
store.save_snapshot(config.SNAPSHOT_PATH, "elexon-live", [list(a) for a in actuals], [list(f) for f in forecasts])
print("written", config.SNAPSHOT_PATH)
