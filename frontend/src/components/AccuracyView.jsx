import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { mw, pct, signed } from "../format";
import Kpi from "./Kpi";

const axis = { stroke: "var(--muted)" };
const tip = { contentStyle: { background: "var(--card)", border: "1px solid var(--border)" } };

function Card({ title, sub, children }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {sub && <p className="note top">{sub}</p>}
      {children}
    </div>
  );
}

export default function AccuracyView({ gate }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setD(null); setErr(null);
    api.accuracy(undefined, undefined, gate).then(setD).catch((e) => setErr(e.message));
  }, [gate]);

  if (err) return <div className="error">{err}</div>;
  if (!d) return <div className="loading">Loading…</div>;
  const o = d.overall;
  if (!o.n) return <div className="error">No overlapping forecast and actual data.</div>;

  const hours = d.by_hour.map((h) => ({ ...h, label: String(h.hour).padStart(2, "0") }));
  const hor = d.by_horizon.map((h) => ({ ...h, label: `${h.lo}–${h.hi}h`, inDecision: d.decision_horizon_h && h.hi > d.decision_horizon_h[0] && h.lo < d.decision_horizon_h[1] }));
  const days = d.by_day.map((x) => ({ ...x, label: x.delivery_date.slice(8) }));
  const hist = d.histogram.map((x) => ({ ...x, label: `${x.lo}` }));
  const worst = [...d.by_day].sort((a, b) => b.mae - a.mae)[0];
  const worstHour = [...d.by_hour].sort((a, b) => b.mae - a.mae)[0];
  const dir = o.bias > 0 ? "under-forecast" : "over-forecast";

  return (
    <section>
      <p className="lede">
        Across <b>{o.n.toLocaleString("en-GB")}</b> half-hours of January decisions (forecast as it stood at {gate}), the typical miss is <b>{mw(o.mae)}</b> ({pct(o.wmape)} of generation).
        On average wind was <b>{dir}</b> by {mw(Math.abs(o.bias))}; 1 period in 10 missed by more than <b>{mw(o.p90_abs)}</b>.
      </p>
      <div className="kpis">
        <Kpi label="MAE" value={mw(o.mae)} hint="mean absolute error" />
        <Kpi label="RMSE" value={mw(o.rmse)} hint="penalises large misses" />
        <Kpi label="Bias" value={signed(o.bias)} hint="actual − forecast; + means wind beat forecast" />
        <Kpi label="wMAPE" value={pct(o.wmape)} hint="Σ|error| ÷ Σ actual" />
        <Kpi label="P90 |error|" value={mw(o.p90_abs)} hint={`P95: ${mw(o.p95_abs)}`} tone="warn" />
        <Kpi label="Error range (P5–P95)" value={`${signed(o.err_p05)} … ${signed(o.err_p95)}`} hint="signed, actual − forecast" />
      </div>

      <div className="grid2">
        <Card title="Daily error" sub={`Worst day: delivery ${worst.delivery_date} (MAE ${mw(worst.mae)}).`}>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={days}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="label" {...axis} /><YAxis {...axis} />
              <Tooltip {...tip} formatter={(v) => `${Math.round(v)} MW`} labelFormatter={(l) => `Delivery day ${l} Jan/Feb`} />
              <Legend /><ReferenceLine y={0} stroke="var(--muted)" />
              <Bar dataKey="mae" name="MAE (MW)" fill="var(--accent)" isAnimationActive={false} />
              <Line dataKey="bias" name="Bias (MW)" stroke="var(--warn)" dot={false} strokeWidth={2} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Error by hour of delivery day" sub={`Hardest hour: ${worstHour.label ?? String(worstHour.hour).padStart(2, "0")}:00 (MAE ${mw(worstHour.mae)}).`}>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={hours}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="label" {...axis} /><YAxis {...axis} />
              <Tooltip {...tip} formatter={(v) => `${Math.round(v)} MW`} labelFormatter={(l) => `${l}:00`} />
              <Legend /><ReferenceLine y={0} stroke="var(--muted)" />
              <Bar dataKey="mae" name="MAE (MW)" fill="var(--accent)" isAnimationActive={false} />
              <Line dataKey="bias" name="Bias (MW)" stroke="var(--warn)" dot={false} strokeWidth={2} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Error vs. forecast lead time" sub="All forecast vintages. Highlighted bars are the lead times a day-ahead decision actually uses.">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={hor}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="label" {...axis} /><YAxis {...axis} />
              <Tooltip {...tip} formatter={(v) => `${Math.round(v)} MW`} />
              <Bar dataKey="mae" name="MAE (MW)" isAnimationActive={false}>
                {hor.map((h, i) => <Cell key={i} fill={h.inDecision ? "var(--accent)" : "var(--muted)"} fillOpacity={h.inDecision ? 1 : 0.45} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Error distribution" sub="actual − forecast, 500 MW buckets (left = over-forecast, right = under-forecast).">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={hist}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="label" {...axis} interval={1} /><YAxis {...axis} />
              <Tooltip {...tip} formatter={(v) => `${v} half-hours`} labelFormatter={(l) => `from ${l} MW`} />
              <ReferenceLine x="0" stroke="var(--muted)" />
              <Bar dataKey="count" name="Half-hours" fill="var(--accent)" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </section>
  );
}
