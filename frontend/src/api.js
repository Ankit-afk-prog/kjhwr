async function get(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ""));
  const res = await fetch(`/api/${path}${qs.size ? `?${qs}` : ""}`);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch { /* non-JSON error */ }
    throw new Error(msg);
  }
  return res.json();
}
export const api = {
  meta: () => get("meta"),
  decision: (decision_date, gate) => get("decision", { decision_date, gate }),
  accuracy: (from, to, gate) => get("accuracy", { from, to, gate }),
};
