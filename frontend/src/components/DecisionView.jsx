import { useEffect, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { gwh, hhmm, longDate, mw, signed } from "../format";
import Kpi from "./Kpi";

function toCsv(view) {
  const head = "time_local,forecast_mw,p10_mw,p90_mw,previous_day_forecast_mw,forecast_published_local,actual_mw_hindsight";
  const rows = view.series.map((s) => [s.t, s.forecast, s.lo?.toFixed(0), s.hi?.toFixed(0), s.prev_forecast, s.published, s.actual].map((x) => x ?? "").join(","));
  return [head, ...rows].join("\n");
}

export default function DecisionView({ meta, gate }) {
  const [day, setDay] = useState("2026-01-15");
  const [view, setView] = useState(null);
  const [err, setErr] = useState(null);
  const [showActual, setShowActual] = useState(false);
  const [showPrev, setShowPrev] = useState(false);

  useEffect(() => {
    setView(null); setErr(null);
    api.decision(day, gate).then(setView).catch((e) => setErr(e.message));
  }, [day, gate]);

  const shift = (n) => {
    const d = new Date(day + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n);
    const s = d.toISOString().slice(0, 10);
    if (s >= meta.decision_start && s <= meta.decision_end) setDay(s);
  };
  const download = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([toCsv(view)], { type: "text/csv" }));
    a.download = `wind_forecast_for_${view.delivery_date}.csv`; a.click();
  };

  const s = view?.summary;
  const data = view?.series.map((x) => ({ ...x, label: hhmm(x.t), band: x.lo != null ? [x.lo, x.hi] : null }));
  const b = view?.bands;

  return (
    <section>
      <div className="toolbar">
        <button onClick={() => shift(-1)} aria-label="Previous day">←</button>
        <label>Decision day (bid placed)
          <input type="date" value={day} min={meta.decision_start} max={meta.decision_end} onChange={(e) => e.target.value && setDay(e.target.value)} />
        </label>
        <button onClick={() => shift(1)} aria-label="Next day">→</button>
        {view && <span className="pill">Buying for <b>{longDate(view.delivery_date)}</b></span>}
        <span className="spacer" />
        {view && <button className="ghost" onClick={download}>Download CSV</button>}
      </div>

      {err && <div className="error">{err}</div>}
      {!view && !err && <div className="loading">Loading…</div>}

      {view && s.slots_with_forecast === 0 && <div className="error">No forecast was published before the gate for this delivery day.</div>}

      {view && s.slots_with_forecast > 0 && (
        <>
          <p className="lede">
            Latest forecast available at <b>{gate} UK time on {longDate(view.decision_date)}</b>
            {" "}(published {s.published_first.slice(11, 16)}{s.published_first !== s.published_last ? `–${s.published_last.slice(11, 16)}` : ""}).
            Wind is expected to average <b>{mw(s.forecast_avg_mw)}</b>, peaking at {mw(s.peak_mw)} around {hhmm(s.peak_time)}.
          </p>
          <div className="kpis">
            <Kpi label="Expected wind energy" value={gwh(s.forecast_mwh)} hint={`avg ${mw(s.forecast_avg_mw)}`} />
            <Kpi label="Peak / trough" value={`${mw(s.peak_mw)} / ${mw(s.min_mw)}`} hint={`${hhmm(s.peak_time)} / ${hhmm(s.min_time)}`} />
            <Kpi label="Risk buffer (P10 case)" value={s.buffer_mwh != null ? gwh(s.buffer_mwh) : "–"} tone="warn"
              hint="extra energy to cover if wind lands at the low end of its error range" />
            <Kpi label="Change vs. yesterday's view"
              value={s.revision_slots === s.slots ? signed(s.revision_mwh / 1000, "GWh") : "n/a"}
              hint={s.revision_slots === s.slots ? "same delivery day, forecast as of 24h earlier" : "prior-day forecast not available for all slots"} />
          </div>

          <div className="card">
            <div className="chart-head">
              <h3>Wind forecast for delivery day</h3>
              <label className="chk"><input type="checkbox" checked={showPrev} onChange={(e) => setShowPrev(e.target.checked)} /> Yesterday's forecast</label>
              <label className="chk"><input type="checkbox" checked={showActual} onChange={(e) => setShowActual(e.target.checked)} /> Reveal actual (hindsight)</label>
            </div>
            <ResponsiveContainer width="100%" height={380}>
              <ComposedChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis dataKey="label" interval={5} stroke="var(--muted)" />
                <YAxis stroke="var(--muted)" tickFormatter={(v) => `${v / 1000}`} label={{ value: "GW", angle: -90, position: "insideLeft", fill: "var(--muted)" }} />
                <Tooltip formatter={(v, n) => (Array.isArray(v) ? `${Math.round(v[0])} – ${Math.round(v[1])} MW` : `${Math.round(v)} MW`)} contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
                <Legend />
                <Area dataKey="band" name="P10–P90 range" stroke="none" fill="var(--accent)" fillOpacity={0.18} isAnimationActive={false} />
                <Line dataKey="forecast" name="Forecast at gate" stroke="var(--accent)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
                {showPrev && <Line dataKey="prev_forecast" name="Yesterday's forecast" stroke="var(--muted)" strokeDasharray="5 4" dot={false} isAnimationActive={false} />}
                {showActual && <Line dataKey="actual" name="Actual" stroke="var(--good)" strokeWidth={2} dot={false} isAnimationActive={false} />}
              </ComposedChart>
            </ResponsiveContainer>
            {b && (
              <p className="note">
                Range = forecast {signed(b.q10)} to {signed(b.q90)} (empirical P10/P90 of past error).{" "}
                {b.basis === "walk_forward"
                  ? `Estimated only from ${b.days} earlier decision days — no hindsight.`
                  : "⚠ Too little history before this date, so the range uses the full month (in-sample)."}
              </p>
            )}
          </div>

          {showActual && s.day_accuracy?.n > 0 && (
            <p className="note">Outcome: this day's MAE was <b>{mw(s.day_accuracy.mae)}</b>, bias <b>{signed(s.day_accuracy.bias)}</b> (positive = more wind than forecast).</p>
          )}
        </>
      )}
    </section>
  );
}
