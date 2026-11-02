# Wind Day-Ahead Portal

Web app for a GB energy utility's day-ahead desk. It answers two questions using Elexon national wind data only:

1. **What is the latest wind forecast available when I must place tomorrow's bid?**
2. **How accurate has that forecast been, in numbers I can build into my decision?**

**Live app:** `<paste Vercel / Heroku URL here>`  ·  **Video:** `<paste unlisted YouTube URL here>`

> **AI disclosure:** this project was designed and written with the assistance of an AI tool (Claude, Anthropic). Domain assumptions, design and code were reviewed and are explained in the video and in `docs/DESIGN.md`.

## What it does

| Tab | Purpose |
|---|---|
| **Day-ahead view** | Pick a decision day in Jan 2026. Shows the wind forecast for tomorrow *as it stood at the auction gate*, a P10–P90 range from past errors, peak/trough, a "risk buffer" (energy to cover if wind lands at P10), the revision vs. the forecast 24 h earlier, optional hindsight overlay of the actual, CSV export. |
| **Forecast accuracy** | MAE, RMSE, bias, wMAPE, P90/P95 absolute error; error by day, by hour of day, by forecast lead time, and the error distribution. |
| **Method & caveats** | Definitions, assumptions and limitations, shown in-product. |

### Key modelling decisions (read these)
- **Decision-time forecast:** for each half-hour of delivery day *D+1*, the latest WINDFOR forecast with `publishTime <= gate` on day *D*. Later forecasts are ignored (no look-ahead). Default gate **09:00 UK** — an *assumption*, editable in the UI; confirm your auction's real cut-off.
- **"Decisions made in January 2026"** = decision days 1–31 Jan, so delivery days are 2 Jan – 1 Feb.
- **Error = actual − forecast.** Positive = more wind than forecast; negative = wind shortfall (the costly case for a buyer).
- **Uncertainty range** uses empirical P10/P90 of past signed errors, computed **walk-forward** (only days whose actuals were known at decision time; first days of the month fall back to in-sample and are flagged).
- wMAPE is used instead of MAPE because wind can be near zero.

## Repository layout

```
backend/
  app/config.py      settings (gate time, data source, paths) - all env-overridable
  app/elexon.py      Elexon Insights client (FUELHH actuals, WINDFOR forecasts), chunked + retried
  app/store.py       in-memory dataset; loads snapshot file, else live fetch
  app/analysis.py    PURE functions: decision-time forecast, metrics, horizon analysis, bands
  app/main.py        FastAPI routes (/api/meta, /api/decision, /api/accuracy) + serves React bundle
  tests/             pytest unit tests (no-look-ahead, sign convention, bands, buckets)
  data/              snapshot_jan2026.json (real data, committed) 
frontend/            React + Vite + Recharts (src/components: DecisionView, AccuracyView, Method)
scripts/
  fetch_snapshot.py  download real Jan-2026 data from Elexon into backend/data/
  make_synthetic.py  SYNTHETIC data generator for offline dev/tests (UI shows a red banner)
api/index.py         Vercel serverless entrypoint
Dockerfile, docker-compose.yml, heroku.yml, vercel.json
docs/DESIGN.md       architecture & design rationale     docs/VIDEO_SCRIPT.md  video storyboard
```

## Run it

**One-time: freeze the real data** (needs internet; commit the resulting file):
```bash
pip install -r backend/requirements.txt
python scripts/fetch_snapshot.py        # writes backend/data/snapshot_jan2026.json
```

**Docker (single container: API + built UI)**
```bash
docker compose up --build               # http://localhost:8000
```

**Local dev (hot reload)**
```bash
cd backend && pip install -r requirements-dev.txt && uvicorn app.main:app --reload   # :8000
cd frontend && npm install && npm run dev                                          # :5173, proxies /api
cd backend && pytest                                                               # tests
```
No internet / no snapshot yet? `python scripts/make_synthetic.py && DATA_SOURCE=synthetic uvicorn app.main:app` — clearly labelled synthetic.

**Config (env):** `DATA_SOURCE=auto|snapshot|live|synthetic`, `DEFAULT_GATE=09:00`, `ELEXON_BASE`, `DATA_DIR`.

## Deploy
- **Heroku (uses the Docker image):** `heroku create && heroku stack:set container && git push heroku main`
- **Vercel (no Docker; uses `vercel.json` + `api/index.py`):** import the repo, framework "Other". The committed snapshot is read at runtime, so the function never calls Elexon.

## API
`GET /api/meta` · `GET /api/decision?decision_date=2026-01-15&gate=09:00` · `GET /api/accuracy?from=2026-01-01&to=2026-01-31&gate=09:00` · `GET /api/health`
