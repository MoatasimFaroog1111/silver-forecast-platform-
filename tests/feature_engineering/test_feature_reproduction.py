import json
from pathlib import Path
import numpy as np
import pandas as pd

from silver_forecast.feature_engineering.calculate_forecast_features import calculate_forecast_features
from silver_forecast.feature_engineering.selected_forecast_features import load_selected_forecast_features
from silver_forecast.feature_engineering.validate_feature_vector import validate_latest_feature_vector

ROOT = Path(__file__).resolve().parents[2]


def test_latest_selected_features_reproduce_stage8_reference():
    raw = pd.read_csv(ROOT / 'historical_market_data' / 'silver_ohlcv_usd_per_kg.csv')
    selected = load_selected_forecast_features(ROOT / 'silver_forecast' / 'feature_engineering' / 'selected_forecast_features.json')
    reference = json.loads((ROOT / 'verified_reports' / 'feature_reference_latest.json').read_text(encoding='utf-8'))
    features = calculate_forecast_features(raw)
    latest = validate_latest_feature_vector(features, selected).iloc[0]
    assert str(features.iloc[-1]['Date'].date()) == reference['date']
    for name in selected:
        assert np.isclose(float(latest[name]), float(reference['features'][name]), atol=1e-6, rtol=1e-8), name
