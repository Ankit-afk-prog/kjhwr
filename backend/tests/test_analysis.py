from datetime import date, datetime, time, timezone

import pytest

from app import analysis
from app.store import build_dataset

UTC = timezone.utc
def ep(y, m, d, hh=0, mm=0):
    return int(datetime(y, m, d, hh, mm, tzinfo=UTC).timestamp())  # Jan: London == UTC


GATE = time(9, 0)
SLOT = ep(2026, 1, 11, 12)  # delivery slot, decision day = 10 Jan


def make(forecasts, actuals):
    return build_dataset("test", "now", actuals, forecasts)


def test_quantile_interpolates():
    assert analysis.quantile([1, 2, 3, 4], 0.5) == 2.5
    assert analysis.quantile([], 0.5) is None
    assert analysis.quantile([7], 0.9) == 7


def test_picks_latest_forecast_not_after_gate_no_lookahead():
    ds = make(
        [(ep(2026, 1, 9, 6), SLOT, 100), (ep(2026, 1, 10, 8, 59), SLOT, 200),
         (ep(2026, 1, 10, 9, 0), SLOT, 300), (ep(2026, 1, 10, 9, 1), SLOT, 999)],
        [(SLOT, 250)],
    )
    # publishTime == gate is allowed; 09:01 is a leak and must be ignored
    assert analysis.pick_forecast(ds, SLOT, analysis.gate_ts(date(2026, 1, 10), GATE)) == (ep(2026, 1, 10, 9), 300)
    assert analysis.pick_forecast(ds, SLOT, ep(2026, 1, 9, 5)) is None


def test_sign_convention_and_metrics():
    # forecast 100 vs actual 130 -> error +30 (under-forecast); 200 vs 180 -> -20
    s = analysis.summarize([(100, 130), (200, 180)])
    assert s["bias"] == pytest.approx(5)
    assert s["mae"] == pytest.approx(25)
    assert s["rmse"] == pytest.approx(((900 + 400) / 2) ** 0.5)
    assert s["wmape"] == pytest.approx(50 / 310)


def test_delivery_day_has_48_slots_in_january():
    assert len(analysis.delivery_slots(date(2026, 1, 11))) == 48


def test_decision_view_missing_data_does_not_crash():
    ds = make([], [])
    v = analysis.decision_view(ds, date(2026, 1, 10), GATE)
    assert v["summary"]["slots_with_forecast"] == 0 and len(v["series"]) == 48


def test_bands_use_only_history_up_to_d_minus_2():
    fc, ac = [], []
    for day in range(1, 31):  # decision days 1..30, delivery day = day+1
        slot = ep(2026, 1, day + 1, 12)
        fc.append((ep(2026, 1, day, 8), slot, 1000))
        ac.append((slot, 1000 + (50 if day <= 8 else 900)))  # errors jump after day 8
    ds = make(fc, ac)
    b = analysis.error_bands(ds, date(2026, 1, 10), GATE)  # may only see days 1..8
    assert b["basis"] == "walk_forward" and b["days"] == 8
    assert b["q10"] == pytest.approx(50) and b["q90"] == pytest.approx(50)
    early = analysis.error_bands(ds, date(2026, 1, 2), GATE)
    assert early["basis"] == "in_sample"


def test_horizon_buckets():
    ds = make([(SLOT - 3 * 3600, SLOT, 100), (SLOT - 26 * 3600, SLOT, 150)], [(SLOT, 120)])
    out = analysis.horizon_accuracy(ds, date(2026, 1, 11), date(2026, 1, 11))
    by = {(r["lo"], r["hi"]): r for r in out}
    assert by[(0, 6)]["mae"] == 20 and by[(24, 30)]["mae"] == 30
