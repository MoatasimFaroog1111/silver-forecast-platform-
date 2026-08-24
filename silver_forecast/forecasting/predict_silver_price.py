from __future__ import annotations

import numpy as np

from silver_forecast.feature_engineering.calculate_forecast_features import calculate_forecast_features
from silver_forecast.feature_engineering.validate_feature_vector import validate_latest_feature_vector
from silver_forecast.forecasting.forecast_policy import ForecastMode, normalize_forecast_mode
from silver_forecast.forecasting.forecast_result import ForecastResult


class PredictSilverPrice:
    def __init__(
        self,
        market_history,
        selected_features: list[str],
        model_catalog,
        model_loader,
        forecast_history,
    ):
        self._market_history = market_history
        self._selected_features = selected_features
        self._model_catalog = model_catalog
        self._model_loader = model_loader
        self._forecast_history = forecast_history

    def latest(self, mode: str | ForecastMode = ForecastMode.CHALLENGER, persist: bool = True) -> list[ForecastResult]:
        normalized = normalize_forecast_mode(mode)
        raw_history = self._market_history.all_as_frame()
        feature_history = calculate_forecast_features(raw_history)
        latest_features = validate_latest_feature_vector(feature_history, self._selected_features)
        observation_date = str(feature_history.iloc[-1]['Date'].date())
        current_price = float(feature_history.iloc[-1]['Close'])
        results = [
            self._predict_horizon(
                registered=self._model_catalog.get(horizon),
                normalized_mode=normalized,
                observation_date=observation_date,
                current_price=current_price,
                latest_features=latest_features,
            )
            for horizon in self._model_catalog.horizons()
        ]
        if persist:
            self._forecast_history.save_many(results)
        return results

    def horizon(self, horizon: str, mode: str | ForecastMode = ForecastMode.CHALLENGER, persist: bool = True) -> ForecastResult:
        normalized = normalize_forecast_mode(mode)
        raw_history = self._market_history.all_as_frame()
        feature_history = calculate_forecast_features(raw_history)
        latest_features = validate_latest_feature_vector(feature_history, self._selected_features)
        result = self._predict_horizon(
            registered=self._model_catalog.get(horizon.upper()),
            normalized_mode=normalized,
            observation_date=str(feature_history.iloc[-1]['Date'].date()),
            current_price=float(feature_history.iloc[-1]['Close']),
            latest_features=latest_features,
        )
        if persist:
            self._forecast_history.save_many([result])
        return result

    def _predict_horizon(self, registered, normalized_mode, observation_date, current_price, latest_features):
        if normalized_mode is ForecastMode.PRIMARY:
            predicted_price = current_price
            model_name = registered.primary_model
        else:
            payload = self._model_loader.load(registered.artifact)
            artifact_features = list(payload.get('selected_features', self._selected_features))
            if artifact_features != self._selected_features:
                raise ValueError(f'Feature contract mismatch for {registered.artifact}')
            raw_prediction = float(payload['model'].predict(latest_features)[0])
            if payload['prediction_mode'] == 'return':
                predicted_price = current_price * (1 + raw_prediction / 100.0)
            elif payload['prediction_mode'] == 'direct':
                predicted_price = raw_prediction
            else:
                raise ValueError(f"Unknown prediction mode: {payload['prediction_mode']}")
            model_name = registered.challenger_model
        if not np.isfinite(predicted_price) or predicted_price <= 0:
            raise ValueError(f'Invalid predicted price for {registered.horizon}: {predicted_price}')
        change = predicted_price - current_price
        change_pct = change / current_price * 100
        return ForecastResult(
            observation_date=observation_date,
            horizon=registered.horizon,
            horizon_sessions=registered.horizon_sessions,
            forecast_mode=normalized_mode.value,
            current_price=current_price,
            predicted_price=float(predicted_price),
            predicted_change_usd_per_kg=float(change),
            predicted_change_pct=float(change_pct),
            price_accuracy_pct=registered.price_accuracy_pct,
            mape_pct=registered.mape_pct,
            mae_usd_per_kg=registered.mae_usd_per_kg,
            directional_accuracy_pct=registered.directional_accuracy_pct,
            model_name=model_name,
            model_version=registered.model_version,
            primary_model=registered.primary_model,
            challenger_model=registered.challenger_model,
            production_eligible=registered.production_eligible,
        )
