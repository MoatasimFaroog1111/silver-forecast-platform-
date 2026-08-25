# Screaming Architecture

This repository is organized by **what the product does**, not by framework categories.

## Product capabilities

- `forecasting/` — creates silver price forecasts and applies primary/challenger policy.
- `market_history/` — owns OHLCV observations and market-history access.
- `feature_engineering/` — reproduces the verified 63-feature causal contract.
- `model_registry/` — registers, loads, versions, and audits persisted forecast models.
- `prediction_accuracy/` — owns accuracy semantics.
- `backtesting/` — exposes verified purged walk-forward evidence.
- `forecast_history/` — stores forecasts and reconciles them against later market observations.
- `reporting/` — publishes verified reports and historical market summaries.
- `http_api/` — outer delivery adapter only. FastAPI does not own business rules.
- `prediction_portal/` — product-facing web experience grouped by business screens.

## Dependency rule

`forecasting` does not import FastAPI, SQLAlchemy, joblib, or CatBoost. Framework and storage details remain outside the forecast decision logic.

## Train once, persist, load, predict

Production requests never train a model. Stage-9 artifacts are loaded through the model registry and reused.

## Prediction policy

Stage 10 did not prove ML price-MAE superiority over Last Close. Therefore:

- `primary` = `Naive_LastClose`
- `challenger` = verified CatBoost artifact per horizon

The UI shows both honestly.
