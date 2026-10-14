# Silver Forecast Platform

Complete end-to-end silver forecasting product in one repository: market history, causal feature engineering, persisted models, forecast API, forecast-history persistence, verified backtesting, historical reports, and professional frontend.

## What runs

`Browser → Prediction Portal → FastAPI → Forecasting → Feature Engineering → Model Registry → Persisted Model → Forecast History`

## Forecast horizons

1D · 2D · 3D · 7D · 14D · 30D (trading sessions).

## Architecture

The repository follows Screaming Architecture. There are no top-level `components`, `assets`, `services`, `utils`, or `helpers` buckets. See `ARCHITECTURE.md`.

## Local run

```bash
pip install -r requirements.txt
uvicorn silver_forecast.http_api.application:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000`.

## Main API

- `GET /health`
- `GET /api/forecast/dashboard?mode=challenger`
- `GET /api/forecast/latest`
- `GET /api/forecast/{1D|2D|3D|7D|14D|30D}`
- `GET /api/market/latest`
- `GET /api/market/history`
- `POST /api/market/observations`
- `GET /api/models`
- `GET /api/backtesting`
- `GET /api/forecast-history`
- `GET /api/reports`
- `GET /api/data-quality`

## Automated daily data pipeline

`.github/workflows/daily-market-data.yml` runs after each trading session (23:30 UTC, Tuesday–Saturday):

1. Restores the verified runtime bundle (models + packaged market history).
2. Fetches daily silver OHLCV from keyless sources (Yahoo Finance `SI=F`, Stooq `xagusd` fallback) and converts USD/troy-oz → USD/kg with the single explicit factor `1000 / 31.1034768`.
3. Merges the rows into `historical_market_data/silver_ohlcv_usd_per_kg.csv` text-based, preserving untouched rows byte-for-byte.
4. Runs the **data quality gate**: parseable and strictly ascending unique dates, valid OHLC rows, non-negative volume, ≤5 missing business days in the trailing 30 calendar days, staleness ≤5 days, and a ±25% close-to-close jump guard limited to newly fetched rows. On failure nothing is committed and a `data-quality-alert` issue is opened.
5. Rebuilds the checksum-verified runtime bundle (tar+xz+base64 parts + manifest) and commits the update.
6. Optionally POSTs the new observations to `PRODUCTION_API_URL/api/market/observations` (set the repository secrets `PRODUCTION_API_URL` and optionally `MARKET_OBSERVATIONS_TOKEN` — see `DEPLOYMENT.md`).

`.github/workflows/branch-cleanup.yml` deletes the retired runtime-repair branches daily (02:00 UTC).

## Persistence

SQLite is the zero-configuration local default. Set `DATABASE_URL` to PostgreSQL in production (Railway or Coolify — see `DEPLOYMENT.md`).

## Models

Runtime includes the six active CatBoost challenger artifacts. The 54-candidate Stage-9 research archive is intentionally excluded from the deployable Git tree because it is not loaded at runtime; `forecast_model_archive/README.md` documents that boundary.

## Scientific integrity

The UI never presents `100 - MAPE` as classification accuracy. Stage-10 evidence keeps Last Close as the primary price benchmark; ML remains a challenger until it proves superior on future evidence.
