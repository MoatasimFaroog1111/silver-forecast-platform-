# Model Card

## Purpose
Predict silver price in **USD/KG** for 1, 2, 3, 7, 14, and 30 trading-session horizons.

## Runtime challengers
Six Stage-9 persisted `CatBoost_Return` models, one per horizon.

## Feature contract
63 selected causal features. No `Target_*` field and no future shift participates in inference.

## Validation
Stage 10 used six expanding walk-forward folds with a 30-session purge and no shuffle. Total fold/model evaluations: 360. Leakage crossings: 0.

## Accuracy semantics
`Price Accuracy = 100 - MAPE` is a display metric, not classification accuracy. MAE, MAPE, and directional accuracy are always retained.

## Production gate
ML challengers are **not** promoted to primary price forecast because they did not beat Last Close on mean MAE across Stage 10.
