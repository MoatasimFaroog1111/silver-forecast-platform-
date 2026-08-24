from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSettings:
    repository_root: Path
    database_url: str
    market_history_csv: Path
    selected_features_json: Path
    model_manifest_json: Path
    persisted_models_directory: Path
    backtesting_directory: Path
    reports_directory: Path
    prediction_portal_directory: Path
    cors_allowed_origins: tuple[str, ...]

    @property
    def database_kind(self) -> str:
        value = self.database_url.lower()
        if value.startswith('postgres'):
            return 'postgresql'
        if value.startswith('sqlite'):
            return 'sqlite'
        return 'other'


def load_runtime_settings(repository_root: Path | None = None) -> RuntimeSettings:
    root = repository_root or Path(__file__).resolve().parents[2]
    default_db = f"sqlite:///{(root / 'runtime_state' / 'silver_forecast.db').as_posix()}"
    origins = tuple(
        origin.strip()
        for origin in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
        if origin.strip()
    )
    return RuntimeSettings(
        repository_root=root,
        database_url=os.getenv('DATABASE_URL', default_db),
        market_history_csv=root / 'historical_market_data' / 'silver_ohlcv_usd_per_kg.csv',
        selected_features_json=root / 'silver_forecast' / 'feature_engineering' / 'selected_forecast_features.json',
        model_manifest_json=root / 'persisted_forecast_models' / 'model_manifest.json',
        persisted_models_directory=root / 'persisted_forecast_models',
        backtesting_directory=root / 'verified_backtesting',
        reports_directory=root / 'verified_reports',
        prediction_portal_directory=root / 'prediction_portal',
        cors_allowed_origins=origins,
    )
