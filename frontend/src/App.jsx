import { useEffect, useState } from "react";
import { api } from "./api";
import AccuracyView from "./components/AccuracyView";
import DecisionView from "./components/DecisionView";
import Method from "./components/Method";

const TABS = [["decision", "Day-ahead view"], ["accuracy", "Forecast accuracy"], ["method", "Method & caveats"]];

export default function App() {
  const [meta, setMeta] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useState("decision");
  const [gate, setGate] = useState("09:00");

  useEffect(() => {
    api.meta().then((m) => { setMeta(m); setGate(m.default_gate); }).catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="app">
      <header>
        <div>
          <h1>Wind Day-Ahead Portal</h1>
          <div className="sub">GB national wind · Elexon FUELHH &amp; WINDFOR · January 2026 decisions</div>
        </div>
        <label className="gate">Auction gate (UK time)
          <input type="time" value={gate} onChange={(e) => e.target.value && setGate(e.target.value)} />
        </label>
      </header>

      {meta?.data_source === "synthetic" && (
        <div className="banner">SYNTHETIC DEMO DATA — not Elexon data. Numbers are illustrative only.</div>
      )}
      {err && <div className="error">Could not reach the API: {err}</div>}
      {!meta && !err && <div className="loading">Loading…</div>}

      {meta && (
        <>
          <nav>{TABS.map(([k, label]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>)}</nav>
          <main>
            {tab === "decision" && <DecisionView meta={meta} gate={gate} />}
            {tab === "accuracy" && <AccuracyView gate={gate} />}
            {tab === "method" && <Method meta={meta} />}
          </main>
        </>
      )}
    </div>
  );
}
