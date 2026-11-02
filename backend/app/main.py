"""FastAPI app: JSON API under /api, plus the built React bundle at / (single-container deploy)."""
from __future__ import annotations

from datetime import date, time, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import analysis, config
from .store import get_dataset

app = FastAPI(title="Wind Day-Ahead Forecast Portal", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def _dataset():
    try:
        return get_dataset()
    except Exception as e:  # surfaced to UI as a readable error
        raise HTTPException(503, f"Data unavailable: {e}")


def _gate(gate: str | None) -> time:
    if not gate:
        return config.DEFAULT_GATE
    try:
        return time.fromisoformat(gate)
    except ValueError:
        raise HTTPException(400, "gate must be HH:MM (UK local time)")


def _day(s: str, name: str) -> date:
    try:
        d = date.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, f"{name} must be YYYY-MM-DD")
    if not (config.DECISION_START <= d <= config.DECISION_END):
        raise HTTPException(400, f"{name} must be within {config.DECISION_START} .. {config.DECISION_END}")
    return d


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    ds = _dataset()
    g = config.DEFAULT_GATE
    d0, d1 = config.DECISION_START, config.DECISION_END
    total = with_f = with_a = both = 0
    d = d0
    while d <= d1:
        for r in analysis.decision_rows(ds, d, g):
            total += 1
            with_f += r["forecast"] is not None
            with_a += r["actual"] is not None
            both += r["forecast"] is not None and r["actual"] is not None
        d += timedelta(days=1)
    return {
        "data_source": ds.source,
        "fetched_at": ds.fetched_at,
        "decision_start": d0.isoformat(),
        "decision_end": d1.isoformat(),
        "default_gate": g.strftime("%H:%M"),
        "forecast_rows": ds.n_forecast_rows,
        "actual_rows": len(ds.actuals),
        "coverage": {"slots": total, "with_forecast": with_f, "with_actual": with_a, "with_both": both},
    }


@app.get("/api/decision")
def decision(decision_date: str, gate: str | None = None):
    return analysis.decision_view(_dataset(), _day(decision_date, "decision_date"), _gate(gate))


@app.get("/api/accuracy")
def accuracy(
    date_from: str = Query(default=config.DECISION_START.isoformat(), alias="from"),
    date_to: str = Query(default=config.DECISION_END.isoformat(), alias="to"),
    gate: str | None = None,
):
    d_from, d_to = _day(date_from, "from"), _day(date_to, "to")
    if d_from > d_to:
        raise HTTPException(400, "from must be <= to")
    return analysis.accuracy(_dataset(), d_from, d_to, _gate(gate))


if config.STATIC_DIR.exists():  # must be mounted last so /api/* wins
    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
