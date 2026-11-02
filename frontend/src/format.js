export const mw = (v) => (v == null ? "–" : `${Math.round(v).toLocaleString("en-GB")} MW`);
export const gwh = (v) => (v == null ? "–" : `${(v / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 })} GWh`);
export const signed = (v, unit = "MW") =>
  v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(Math.round(v)).toLocaleString("en-GB")} ${unit}`;
export const pct = (v) => (v == null ? "–" : `${(v * 100).toFixed(1)}%`);
export const hhmm = (iso) => iso.slice(11, 16);
export const longDate = (iso) =>
  new Date(iso + "T12:00:00Z").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
