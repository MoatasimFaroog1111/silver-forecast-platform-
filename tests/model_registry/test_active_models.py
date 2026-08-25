from pathlib import Path
import numpy as np
import pandas as pd

from silver_forecast.feature_engineering.calculate_forecast_features import calculate_forecast_features
from silver_forecast.feature_engineering.selected_forecast_features import load_selected_forecast_features
from silver_forecast.feature_engineering.validate_feature_vector import validate_latest_feature_vector
from silver_forecast.model_registry.forecast_model_catalog import ForecastModelCatalog
from silver_forecast.model_registry.load_registered_model import RegisteredModelLoader

ROOT = Path(__file__).resolve().parents[2]


def test_all_active_models_load_and_predict_finite_values():
    selected = load_selected_forecast_features(ROOT / 'silver_forecast' / 'feature_engineering' / 'selected_forecast_features.json')
    raw = pd.read_csv(ROOT / 'historical_market_data' / 'silver_ohlcv_usd_per_kg.csv')
    latest = validate_latest_feature_vector(calculate_forecast_features(raw), selected)
    catalog = ForecastModelCatalog(ROOT / 'persisted_forecast_models' / 'model_manifest.json')
    loader = RegisteredModelLoader(ROOT / 'persisted_forecast_models')
    assert len(catalog.all()) == 6
    for registered in catalog.all():
        payload = loader.load(registered.artifact)
        assert payload['selected_features'] == selected
        prediction = payload['model'].predict(latest)
        assert np.isfinite(np.asarray(prediction, dtype=float)).all()
