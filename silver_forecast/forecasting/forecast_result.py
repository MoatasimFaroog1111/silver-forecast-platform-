from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ForecastResult:
    observation_date: str
    horizon: str
    horizon_sessions: int
    forecast_mode: str
    current_price: float
    predicted_price: float
    predicted_change_usd_per_kg: float
    predicted_change_pct: float
    price_accuracy_pct: float
    mape_pct: float
    mae_usd_per_kg: float
    directional_accuracy_pct: float
    model_name: str
    model_version: str
    primary_model: str
    challenger_model: str
    production_eligible: bool
    unit: str = 'USD/KG'

    def as_dict(self) -> dict:
        return asdict(self)
