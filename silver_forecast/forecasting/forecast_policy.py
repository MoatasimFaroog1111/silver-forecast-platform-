from __future__ import annotations

from enum import Enum


class ForecastMode(str, Enum):
    PRIMARY = 'primary'
    CHALLENGER = 'challenger'


def normalize_forecast_mode(value: str | ForecastMode) -> ForecastMode:
    if isinstance(value, ForecastMode):
        return value
    try:
        return ForecastMode(value.lower())
    except ValueError as exc:
        raise ValueError("forecast mode must be 'primary' or 'challenger'") from exc
