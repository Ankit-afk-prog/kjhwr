"""Pure analysis functions (no I/O, no FastAPI) so they are trivially unit-testable.

Vocabulary
  decision day D   : the day the trader buys in the day-ahead auction
  delivery day D+1 : the day the power is for
  gate             : UK wall-clock time on D after which new forecasts cannot inform the bid
  decision forecast: for each half-hour of D+1, the latest WINDFOR forecast with publishTime <= gate
  error            : actual - forecast  (positive => wind UNDER-forecast => the buyer is short)
"""
from __future__ import annotations

import bisect
import math
from datetime import date, datetime, time, timedelta
from functools import lru_cache

from .config import DECISION_END, DECISION_START, LONDON
from .store import Dataset

SLOT_S = 1800
HORIZON_EDGES_H = [0, 6, 12, 18, 24, 30, 36, 42, 48, 72, 168]


# ---------- small helpers -------------------------------------------------------------
def quantile(sorted_vals: list[float], q: float) -> float | None:
    """Linear-interpolated quantile of an already-sorted list."""
    if not sorted_vals:
        return None
    pos = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def local_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, LONDON).isoformat(timespec="minutes")


def delivery_slots(day: date) -> list[int]:
    """Epoch starts of every half-hour of a UK local day (handles 46/50-slot DST days)."""
    start = int(datetime.combine(day, time(0), tzinfo=LONDON).timestamp())
    end = int(datetime.combine(day + timedelta(days=1), time(0), tzinfo=LONDON).timestamp())
    return list(range(start, end, SLOT_S))


def gate_ts(decision_day: date, gate: time) -> int:
    return int(datetime.combine(decision_day, gate, tzinfo=LONDON).timestamp())


def pick_forecast(ds: Dataset, start: int, gate: int) -> tuple[int, float] | None:
    """Latest forecast for `start` published at or before `gate` (no look-ahead)."""
    lst = ds.forecasts.get(start)
    if not lst:
        return None
    i = bisect.bisect_right(lst, (gate, math.inf)) - 1
    return lst[i] if i >= 0 else None


# ---------- decision-time forecast ----------------------------------------------------
@lru_cache(maxsize=256)
def decision_rows(ds: Dataset, decision_day: date, gate: time) -> tuple[dict, ...]:
    return rows_at(ds, decision_day + timedelta(days=1), gate_ts(decision_day, gate))


def rows_at(ds: Dataset, delivery_day: date, g: int) -> tuple[dict, ...]:
    out = []
    for ts in delivery_slots(delivery_day):
        pick = pick_forecast(ds, ts, g)
        out.append(
            {
                "ts": ts,
                "forecast": pick[1] if pick else None,
                "published": pick[0] if pick else None,
                "actual": ds.actuals.get(ts),
            }
        )
    return tuple(out)


# ---------- metrics -------------------------------------------------------------------
def summarize(pairs: list[tuple[float, float]]) -> dict:
    """pairs = [(forecast, actual)]. All errors are actual - forecast, in MW."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    errs = [a - f for f, a in pairs]
    abs_errs = sorted(abs(e) for e in errs)
    s_errs = sorted(errs)
    total_actual = sum(a for _, a in pairs)
    return {
        "n": n,
        "mae": sum(abs_errs) / n,
        "rmse": math.sqrt(sum(e * e for e in errs) / n),
        "bias": sum(errs) / n,
        "wmape": (sum(abs_errs) / total_actual) if total_actual > 0 else None,
        "mean_actual": total_actual / n,
        "p50_abs": quantile(abs_errs, 0.50),
        "p90_abs": quantile(abs_errs, 0.90),
        "p95_abs": quantile(abs_errs, 0.95),
        "err_p05": quantile(s_errs, 0.05),
        "err_p10": quantile(s_errs, 0.10),
        "err_p90": quantile(s_errs, 0.90),
        "err_p95": quantile(s_errs, 0.95),
    }


def _pairs(rows) -> list[tuple[float, float]]:
    return [(r["forecast"], r["actual"]) for r in rows if r["forecast"] is not None and r["actual"] is not None]


def _decision_days(d_from: date, d_to: date):
    d = d_from
    while d <= d_to:
        yield d
        d += timedelta(days=1)


def accuracy(ds: Dataset, d_from: date, d_to: date, gate: time) -> dict:
    """Accuracy of the *decision-time* forecast over decision days d_from..d_to."""
    all_pairs, by_hour, by_day, hist_errs = [], {}, [], []
    for d in _decision_days(d_from, d_to):
        rows = decision_rows(ds, d, gate)
        pairs = _pairs(rows)
        if pairs:
            s = summarize(pairs)
            by_day.append({"delivery_date": (d + timedelta(days=1)).isoformat(), "decision_date": d.isoformat(),
                           **{k: s[k] for k in ("n", "mae", "rmse", "bias", "mean_actual")}})
        for r in rows:
            if r["forecast"] is None or r["actual"] is None:
                continue
            all_pairs.append((r["forecast"], r["actual"]))
            by_hour.setdefault(datetime.fromtimestamp(r["ts"], LONDON).hour, []).append((r["forecast"], r["actual"]))
            hist_errs.append(r["actual"] - r["forecast"])

    overall = summarize(all_pairs)
    hours = []
    for h in sorted(by_hour):
        s = summarize(by_hour[h])
        hours.append({"hour": h, **{k: s[k] for k in ("n", "mae", "rmse", "bias", "mean_actual")}})

    histogram = []
    if hist_errs:
        width = 500
        bound = math.ceil(max(abs(e) for e in hist_errs) / width) * width or width
        edges = list(range(-bound, bound + width, width))
        counts = [0] * (len(edges) - 1)
        for e in hist_errs:
            counts[min(int((e + bound) // width), len(counts) - 1)] += 1
        histogram = [{"lo": edges[i], "hi": edges[i + 1], "count": c} for i, c in enumerate(counts)]

    return {
        "overall": overall,
        "by_hour": hours,
        "by_day": by_day,
        "histogram": histogram,
        "by_horizon": horizon_accuracy(ds, d_from + timedelta(days=1), d_to + timedelta(days=1)),
        "decision_horizon_h": decision_horizon_range(ds, d_from, d_to, gate),
    }


def horizon_accuracy(ds: Dataset, deliv_from: date, deliv_to: date) -> list[dict]:
    """Error vs forecast lead time, using EVERY forecast vintage for the delivery window
    (not only the decision-time one) - shows how quickly accuracy improves as gate nears."""
    lo_ts = delivery_slots(deliv_from)[0]
    hi_ts = delivery_slots(deliv_to)[-1]
    acc = [[0, 0.0, 0.0, 0.0] for _ in range(len(HORIZON_EDGES_H) - 1)]  # n, sum_abs, sum_sq, sum_err
    for start, lst in ds.forecasts.items():
        if not (lo_ts <= start <= hi_ts) or start not in ds.actuals:
            continue
        actual = ds.actuals[start]
        for pub, mw in lst:
            h = (start - pub) / 3600
            if h < 0 or h >= HORIZON_EDGES_H[-1]:
                continue
            b = bisect.bisect_right(HORIZON_EDGES_H, h) - 1
            e = actual - mw
            a = acc[b]
            a[0] += 1; a[1] += abs(e); a[2] += e * e; a[3] += e
    out = []
    for i, (n, sa, sq, se) in enumerate(acc):
        if n:
            out.append({"lo": HORIZON_EDGES_H[i], "hi": HORIZON_EDGES_H[i + 1], "n": n,
                        "mae": sa / n, "rmse": math.sqrt(sq / n), "bias": se / n})
    return out


def decision_horizon_range(ds: Dataset, d_from: date, d_to: date, gate: time) -> list[float] | None:
    """Min/max lead time (hours) of the forecasts actually used for decisions."""
    hs = []
    for d in _decision_days(d_from, d_to):
        for r in decision_rows(ds, d, gate):
            if r["published"] is not None:
                hs.append((r["ts"] - r["published"]) / 3600)
    return [min(hs), max(hs)] if hs else None


# ---------- uncertainty bands ---------------------------------------------------------
def error_bands(ds: Dataset, decision_day: date, gate: time, min_days: int = 3) -> dict | None:
    """Empirical P10/P90 of signed error, estimated WITHOUT look-ahead where possible.

    Walk-forward: only decision days <= D-2 are used, because the delivery day of D-1 is
    still in progress at the gate on D, so its actuals are not yet known to the trader.
    For the first days of the month (not enough history) we fall back to the full-month
    sample and flag it as in-sample.
    """
    hist_end = decision_day - timedelta(days=2)
    n_hist = (hist_end - DECISION_START).days + 1
    if n_hist >= min_days:
        basis, last = "walk_forward", hist_end
    else:
        basis, last = "in_sample", DECISION_END
    errs = sorted(a - f for f, a in (p for d in _decision_days(DECISION_START, last)
                                     for p in _pairs(decision_rows(ds, d, gate))))
    if not errs:
        return None
    return {"basis": basis, "days": (last - DECISION_START).days + 1, "n": len(errs),
            "q10": quantile(errs, 0.10), "q90": quantile(errs, 0.90)}


def decision_view(ds: Dataset, decision_day: date, gate: time) -> dict:
    deliv = decision_day + timedelta(days=1)
    g = gate_ts(decision_day, gate)
    rows = decision_rows(ds, decision_day, gate)
    prev = rows_at(ds, deliv, g - 86400)  # same delivery day, forecast as of one day earlier
    bands = error_bands(ds, decision_day, gate)

    series, mw_to_mwh = [], 0.5
    for r, p in zip(rows, prev):
        f = r["forecast"]
        lo = hi = None
        if f is not None and bands:
            lo = max(0.0, f + bands["q10"])  # wind unlikely to be below this (90% conf.)
            hi = max(0.0, f + bands["q90"])
        series.append({"t": local_iso(r["ts"]), "ts": r["ts"], "forecast": f, "lo": lo, "hi": hi,
                       "prev_forecast": p["forecast"], "actual": r["actual"],
                       "published": local_iso(r["published"]) if r["published"] else None})

    have = [s for s in series if s["forecast"] is not None]
    summary: dict = {"slots": len(series), "slots_with_forecast": len(have)}
    if have:
        peak = max(have, key=lambda s: s["forecast"])
        trough = min(have, key=lambda s: s["forecast"])
        fc_mwh = sum(s["forecast"] for s in have) * mw_to_mwh
        prev_have = [s for s in have if s["prev_forecast"] is not None]
        summary.update(
            forecast_mwh=fc_mwh,
            forecast_avg_mw=fc_mwh / (len(have) * mw_to_mwh),
            peak_mw=peak["forecast"], peak_time=peak["t"],
            min_mw=trough["forecast"], min_time=trough["t"],
            buffer_mwh=(sum(max(0.0, s["forecast"] - s["lo"]) for s in have if s["lo"] is not None) * mw_to_mwh
                        if bands else None),
            revision_mwh=(sum(s["forecast"] - s["prev_forecast"] for s in prev_have) * mw_to_mwh
                          if prev_have else None),
            revision_slots=len(prev_have),  # revision is only comparable if == slots
            published_first=min(s["published"] for s in have),
            published_last=max(s["published"] for s in have),
        )
    pairs = _pairs(rows)
    summary["day_accuracy"] = summarize(pairs) if pairs else None
    return {
        "decision_date": decision_day.isoformat(),
        "delivery_date": deliv.isoformat(),
        "gate_local": f"{decision_day.isoformat()}T{gate.strftime('%H:%M')}",
        "bands": bands,
        "summary": summary,
        "series": series,
    }
