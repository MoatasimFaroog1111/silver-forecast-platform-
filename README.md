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

## Persistence

SQLite is the zero-configuration local default. Set `DATABASE_URL` to Railway PostgreSQL in production.

## Models

Runtime includes the six active CatBoost challenger artifacts. The 54-candidate Stage-9 research archive is intentionally excluded from the deployable Git tree because it is not loaded at runtime; `forecast_model_archive/README.md` documents that boundary.

## Scientific integrity

The UI never presents `100 - MAPE` as classification accuracy. Stage-10 evidence keeps Last Close as the primary price benchmark; ML remains a challenger until it proves superior on future evidence.
