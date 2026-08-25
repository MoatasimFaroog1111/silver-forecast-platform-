# Local Verification

Date: 2026-08-23

## Automated tests

- `pytest`: **6 passed / 0 failed**
- Python compile check: **PASS**
- JavaScript syntax check (`node --check`): **PASS for every portal module**
- Screaming Architecture forbidden buckets (`components`, `assets`, `services`, `utils`, `helpers`): **0 found**
- Secret-pattern scan: **no matching API keys or private-key blocks found**

## Feature contract

- Selected features: **63**
- Recomputed from packaged OHLCV only: **PASS**
- Latest reference comparison against Stage 8: **63/63 within tolerance**
- Target fields in inference feature contract: **0**

## Model registry

- Runtime persisted models: **6** (`CatBoost_Return`, one per horizon)
- Full Stage-9 research archive retained: **54 models**
- Runtime artifacts loadable: **6/6**
- Finite sample predictions: **6/6**

## Real HTTP run

Uvicorn was started locally and the following returned HTTP 200:

- `/health`
- `/api/forecast/dashboard?mode=challenger`
- `/api/forecast/latest?mode=primary`
- `/api/models`
- `/api/backtesting`
- `/api/reports`
- `/api/data-quality`
- `/api/platform/settings`
- `/`
- `/silver_forecast_portal.js`
- `/docs`

## Full HTTP journey

A new OHLCV observation dated **2026-01-26** was POSTed to a temporary SQLite database. The running application:

1. stored the market observation,
2. recalculated the causal feature history,
3. produced **6 fresh model forecasts**,
4. saved the forecast records,
5. returned the new date from `/api/market/latest`, and
6. returned the persisted forecasts from `/api/forecast-history`.

Result: **PASS**.

## Docker note

The repository contains a production Dockerfile and Railway configuration. The current execution environment does not provide a Docker CLI, so an image build could not be executed here. The same application entrypoint used by the Docker CMD was executed directly through Uvicorn and passed the HTTP verification above.
