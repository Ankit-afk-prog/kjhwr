"""Thin client for the Elexon Insights (BMRS) stream endpoints.

Only two datasets are used:
  FUELHH  - half-hourly outturn by fuel type  (we keep fuelType == WIND)  -> actuals
  WINDFOR - wind generation forecast, one row per (publishTime, startTime) -> forecasts
Stream endpoints return a plain JSON array; we also tolerate {"data": [...]}.
"""
from __future__ import annotations

import time as _time
from datetime import date, datetime, timedelta, timezone

import httpx

from .config import ELEXON_BASE


def parse_ts(s: str) -> int:
    """ISO-8601 (with Z or offset) -> epoch seconds (UTC)."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _get_json(client: httpx.Client, path: str, params: dict, retries: int = 4):
    for attempt in range(retries):
        try:
            r = client.get(f"{ELEXON_BASE}{path}", params=params, timeout=60)
            r.raise_for_status()
            body = r.json()
            return body["data"] if isinstance(body, dict) and "data" in body else body
        except (httpx.HTTPError, ValueError):
            if attempt == retries - 1:
                raise
            _time.sleep(2**attempt)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_actuals(client: httpx.Client, d_from: date, d_to: date) -> list[tuple[int, float]]:
    """Actual national wind generation (MW) per half hour, by settlement date window."""
    rows = _get_json(
        client,
        "/datasets/FUELHH/stream",
        {
            "settlementDateFrom": d_from.isoformat(),
            "settlementDateTo": d_to.isoformat(),
            "fuelType": "WIND",
        },
    )
    latest: dict[int, tuple[int, float]] = {}  # startTime -> (publishTime, MW); keep newest
    for r in rows:
        if r.get("fuelType") != "WIND" or r.get("generation") is None:
            continue
        start, pub = parse_ts(r["startTime"]), parse_ts(r.get("publishTime", r["startTime"]))
        if start not in latest or pub >= latest[start][0]:
            latest[start] = (pub, float(r["generation"]))
    return sorted((s, mw) for s, (_, mw) in latest.items())


def fetch_forecasts(
    client: httpx.Client, pub_from: datetime, pub_to: datetime, chunk_hours: int = 48
) -> list[tuple[int, int, float]]:
    """All WINDFOR rows published in [pub_from, pub_to): (publishTime, startTime, MW)."""
    out: dict[tuple[int, int], float] = {}
    cur = pub_from
    while cur < pub_to:
        nxt = min(cur + timedelta(hours=chunk_hours), pub_to)
        rows = _get_json(
            client,
            "/datasets/WINDFOR/stream",
            {"publishDateTimeFrom": _iso(cur), "publishDateTimeTo": _iso(nxt)},
        )
        for r in rows:
            if r.get("generation") is None:
                continue
            out[(parse_ts(r["publishTime"]), parse_ts(r["startTime"]))] = float(r["generation"])
        cur = nxt
    return sorted((p, s, mw) for (p, s), mw in out.items())
