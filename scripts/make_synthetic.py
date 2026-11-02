"""Generate a SYNTHETIC wind dataset with the same shape as the real snapshot.

Used for offline development and automated tests only. The API labels it
data_source="synthetic" and the UI shows a red banner - never present it as real data.
Forecast errors are AR(1) paths whose size grows with lead time, plus a small over-forecast bias.
"""
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backend" / "data" / "synthetic_jan2026.json"
rng = random.Random(42)
UTC = timezone.utc
t0 = datetime(2026, 1, 1, tzinfo=UTC)
t_end = datetime(2026, 2, 2, 0, 0, tzinfo=UTC)

# "true" wind: slow weather regimes + diurnal wiggle + AR noise
n_slots = int((t_end - t0).total_seconds() // 1800)
truth, ar = {}, 0.0
for i in range(n_slots):
    ts = int((t0 + timedelta(minutes=30 * i)).timestamp())
    ar = 0.98 * ar + rng.gauss(0, 0.12)
    regime = math.sin(i / 48 / 2.3) + 0.6 * math.sin(i / 48 / 0.9 + 1.0)
    v = 8000 + 4300 * regime + 900 * ar + 300 * math.sin(2 * math.pi * i / 48)
    truth[ts] = max(150.0, min(14800.0, v))

actuals = [[ts, round(v)] for ts, v in truth.items()]

forecasts = []
for k in range(31 * 24):  # hourly publications through January
    pub = t0 + timedelta(hours=k)
    e = 0.0
    for step in range(96):  # 48h ahead, half-hourly
        start = pub + timedelta(minutes=30 * step) + timedelta(minutes=30)
        ts = int(start.timestamp())
        if ts not in truth:
            continue
        h = (step + 1) * 0.5
        e = 0.97 * e + rng.gauss(0, 25 + 5 * h)
        forecasts.append([int(pub.timestamp()), ts, round(max(0.0, truth[ts] - e - 120))])

OUT.write_text(json.dumps({"source": "synthetic", "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                           "actuals": actuals, "forecasts": forecasts}, separators=(",", ":")))
print(f"wrote {OUT} ({len(actuals)} actuals, {len(forecasts)} forecasts)")
