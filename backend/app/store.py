"""In-memory dataset + loading strategy (snapshot file -> live Elexon fetch)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import httpx

from . import config, elexon


@dataclass(eq=False)  # eq=False -> hashable by identity, so it can be an lru_cache key
class Dataset:
    source: str
    fetched_at: str
    actuals: dict[int, float]                      # startTime(epoch s) -> MW
    forecasts: dict[int, list[tuple[int, float]]]  # startTime -> [(publishTime, MW)] sorted by publish
    n_forecast_rows: int = 0
    notes: list[str] = field(default_factory=list)


def build_dataset(source: str, fetched_at: str, actuals, forecasts) -> Dataset:
    fc: dict[int, list[tuple[int, float]]] = {}
    for pub, start, mw in forecasts:
        fc.setdefault(start, []).append((pub, mw))
    for lst in fc.values():
        lst.sort()
    return Dataset(
        source=source,
        fetched_at=fetched_at,
        actuals={s: mw for s, mw in actuals},
        forecasts=fc,
        n_forecast_rows=len(forecasts),
    )


def _from_file(path) -> Dataset:
    raw = json.loads(path.read_text())
    return build_dataset(raw["source"], raw["fetched_at"], raw["actuals"], raw["forecasts"])


def save_snapshot(path, source, actuals, forecasts) -> None:
    payload = {
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actuals": actuals,        # [[startEpoch, MW], ...]
        "forecasts": forecasts,    # [[publishEpoch, startEpoch, MW], ...]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")))


def fetch_live():
    """Everything needed for January-2026 decisions: forecasts published in January,
    actuals for delivery days 2 Jan - 1 Feb (decision day + 1)."""
    d0, d1 = config.DECISION_START, config.DECISION_END
    with httpx.Client(headers={"Accept": "application/json"}) as client:
        actuals = elexon.fetch_actuals(client, d0, d1 + timedelta(days=2))
        forecasts = elexon.fetch_forecasts(
            client,
            datetime(d0.year, d0.month, d0.day, tzinfo=timezone.utc),
            datetime(d1.year, d1.month, d1.day, tzinfo=timezone.utc) + timedelta(days=1),
        )
    return actuals, forecasts


@lru_cache(maxsize=1)
def get_dataset() -> Dataset:
    mode = config.DATA_SOURCE
    if mode == "synthetic":
        return _from_file(config.SYNTHETIC_PATH)
    if mode in ("auto", "snapshot") and config.SNAPSHOT_PATH.exists():
        return _from_file(config.SNAPSHOT_PATH)
    if mode == "snapshot":
        raise RuntimeError(f"Snapshot not found at {config.SNAPSHOT_PATH}; run scripts/fetch_snapshot.py")
    actuals, forecasts = fetch_live()
    try:  # best effort cache (read-only filesystems e.g. serverless are fine)
        save_snapshot(config.SNAPSHOT_PATH, "elexon-live", [list(a) for a in actuals], [list(f) for f in forecasts])
    except OSError:
        pass
    return build_dataset("elexon-live", datetime.now(timezone.utc).isoformat(timespec="seconds"), actuals, forecasts)
