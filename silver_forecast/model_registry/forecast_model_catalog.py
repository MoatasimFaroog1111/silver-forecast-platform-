from __future__ import annotations

import json
from pathlib import Path

from silver_forecast.model_registry.registered_forecast_model import RegisteredForecastModel


class ForecastModelCatalog:
    def __init__(self, manifest_path: Path):
        self._manifest_path = manifest_path
        self._payload = json.loads(manifest_path.read_text(encoding='utf-8'))

    @property
    def policy_version(self) -> str:
        return self._payload['policy_version']

    @property
    def model_version(self) -> str:
        return self._payload['model_version']

    def horizons(self) -> list[str]:
        return list(self._payload['horizons'].keys())

    def get(self, horizon: str) -> RegisteredForecastModel:
        if horizon not in self._payload['horizons']:
            raise KeyError(f'Unsupported horizon: {horizon}')
        item = self._payload['horizons'][horizon]
        return RegisteredForecastModel(
            horizon=horizon,
            horizon_sessions=int(item['horizon_sessions']),
            primary_model=item['primary_model'],
            challenger_model=item['challenger_model'],
            artifact=item['artifact'],
            model_version=self.model_version,
            training_date_end=item['training_date_end'],
            selected_feature_count=int(item['selected_feature_count']),
            mae_usd_per_kg=float(item['mae_usd_per_kg']),
            mape_pct=float(item['mape_pct']),
            price_accuracy_pct=float(item['price_accuracy_pct']),
            directional_accuracy_pct=float(item['directional_accuracy_pct']),
            folds_beating_naive_mae=int(item['folds_beating_naive_mae']),
            mean_mae_improvement_vs_naive_pct=float(item['mean_mae_improvement_vs_naive_pct']),
            production_eligible=bool(item['production_eligible']),
        )

    def all(self) -> list[RegisteredForecastModel]:
        return [self.get(horizon) for horizon in self.horizons()]
