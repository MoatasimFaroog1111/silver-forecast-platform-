from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlatformContext:
    settings: object
    engine: object
    session_factory: object
    market_history: object
    selected_features: list[str]
    model_catalog: object
    model_loader: object
    forecast_history: object
    predictor: object
    backtesting: object
    reports: object
