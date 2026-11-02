export default function Method({ meta }) {
  return (
    <section className="prose">
      <h3>How "the forecast at decision time" is defined</h3>
      <p>
        Day-ahead bids for delivery day <i>D+1</i> are placed on day <i>D</i> before the auction gate (default <b>{meta.default_gate} UK</b>, adjustable above).
        For every half-hour of <i>D+1</i> we take the <b>most recent WINDFOR forecast published at or before the gate</b>. Anything published later is ignored, so no result in this portal uses information the trader could not have had.
      </p>
      <h3>Scope</h3>
      <p>Decisions made 1–31 January 2026 (delivery 2 Jan – 1 Feb). Actuals: Elexon FUELHH, fuel type WIND. Forecasts: Elexon WINDFOR. National level, 30-minute resolution, no other data.</p>
      <h3>Metrics</h3>
      <ul>
        <li><b>Error</b> = actual − forecast. Positive: more wind than forecast (buyer over-bought). Negative: wind fell short, the costly direction for a buyer.</li>
        <li><b>MAE / RMSE / bias</b> in MW; <b>wMAPE</b> = Σ|error| ÷ Σ actual (robust when wind is near zero, unlike plain MAPE).</li>
        <li><b>P10–P90 range</b> = forecast + empirical 10th/90th percentile of past signed errors. Computed walk-forward (only days whose actuals were known at decision time).</li>
        <li><b>Risk buffer</b> = energy between the forecast and the P10 line: what to cover if wind lands at the low end.</li>
      </ul>
      <h3>Limitations (be aware)</h3>
      <ul>
        <li>One month of data: percentiles in the tails are noisy; do not over-read a single day.</li>
        <li>The error band has the same width at every wind level, though errors are usually larger when it is windy. A level-dependent band is the first planned upgrade.</li>
        <li>Wind only. The "how much to buy" figure also needs demand and other supply, which are outside this pilot.</li>
        <li>Gate time is an assumption; confirm your auction's actual cut-off.</li>
      </ul>
      <p className="note">Data source: <b>{meta.data_source}</b> · loaded {meta.fetched_at} · {meta.forecast_rows.toLocaleString("en-GB")} forecast rows, {meta.actual_rows.toLocaleString("en-GB")} actual rows · slot coverage {meta.coverage.with_both}/{meta.coverage.slots}.</p>
    </section>
  );
}
