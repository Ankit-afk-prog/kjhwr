# Design notes (for the technical review)

## Shape of the system
Browser (React) → `/api/*` (FastAPI) → `analysis.py` (pure functions) → `store.Dataset` (in memory) ← snapshot JSON (frozen from Elexon).
One container serves both the API and the built React bundle, so there is no CORS or second deployable in production.

## Why a frozen snapshot
Jan-2026 data is history and will not change. Reading a committed file gives instant cold starts (important on serverless), no runtime dependency on Elexon availability/rate limits, and fully reproducible numbers in a demo. `fetch_snapshot.py` is the single, auditable ingestion path; `store.get_dataset` falls back to live fetch if the file is absent.

## Data model
- `actuals: {startTime -> MW}` (FUELHH, fuelType WIND; newest publishTime wins on duplicates)
- `forecasts: {startTime -> [(publishTime, MW)] sorted}` (WINDFOR). Sorted lists make "latest forecast ≤ gate" a `bisect`, O(log n), and the look-ahead rule is one line (`pick_forecast`).
- Timestamps are epoch seconds internally; London local time is used only for gates, day boundaries and display (`zoneinfo`, DST-safe even though January has none).

## Analysis choices
| Choice | Why |
|---|---|
| Decision-time forecast, not "latest ever" | Evaluating a forecast the trader could not have seen would flatter accuracy. |
| Signed error actual − forecast | Direction matters: shortfall costs more than surplus. |
| wMAPE over MAPE | Wind approaches 0 → MAPE explodes. |
| Walk-forward P10/P90 (history ≤ D-2) | Delivery day D-1 is still running at the gate on D. Avoids optimistic bands. |
| Horizon chart uses all vintages | Shows value of waiting for later forecasts (the trade-off vs. gate time). |
| Pure-Python stats, no pandas/numpy | ~1.5k decision rows, ~70k vintage rows: fast enough; keeps the serverless bundle small. |

## Testing
`backend/tests` pin the behaviours that would silently corrupt results: no look-ahead at the gate boundary (09:00 allowed, 09:01 not), sign convention, wMAPE, walk-forward window, horizon bucketing, empty-data safety.

## Known limitations / next steps
1. Band width is constant in MW; errors are heteroscedastic → condition quantiles on forecast level / lead time.
2. One month of data → noisy tails; extend history for production.
3. Gate time is assumed; make it per-auction (EPEX/N2EX) and per-day.
4. Wind only; add demand & other supply to turn the buffer into a true "volume to buy".
5. The Elexon client was written from the documented Insights API shape; verify param names against the live API on first run (`fetch_snapshot.py` aborts on empty results).
