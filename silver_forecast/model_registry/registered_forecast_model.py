from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegisteredForecastModel:
    horizon: str
    horizon_sessions: int
    primary_model: str
    challenger_model: str
    artifact: str
    model_version: str
    training_date_end: str
    selected_feature_count: int
    mae_usd_per_kg: float
    mape_pct: float
    price_accuracy_pct: float
    directional_accuracy_pct: float
    folds_beating_naive_mae: int
    mean_mae_improvement_vs_naive_pct: float
    production_eligible: bool
