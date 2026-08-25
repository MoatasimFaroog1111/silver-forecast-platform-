from datetime import date, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

from silver_forecast.http_api.application import create_app
from silver_forecast.platform_configuration.runtime_settings import load_runtime_settings, RuntimeSettings

ROOT = Path(__file__).resolve().parents[2]


def test_market_observation_to_forecast_to_history(tmp_path):
    base = load_runtime_settings(ROOT)
    settings = RuntimeSettings(**{**base.__dict__, 'database_url': f"sqlite:///{(tmp_path / 'journey.db').as_posix()}"})
    client = TestClient(create_app(settings))

    initial = client.get('/api/market/latest').json()
    first_forecasts = client.get('/api/forecast/latest?mode=challenger').json()
    assert len(first_forecasts) == 6

    last_date = date.fromisoformat(initial['date'])
    next_date = last_date + timedelta(days=3)
    close = float(initial['close']) * 1.003
    observation = {
        'date': next_date.isoformat(),
        'open': float(initial['close']),
        'high': close * 1.004,
        'low': float(initial['close']) * 0.996,
        'close': close,
        'volume': max(float(initial['volume']), 1.0),
    }
    response = client.post('/api/market/observations', json=observation)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload['new_forecasts']) == 6
    assert all(item['observation_date'] == next_date.isoformat() for item in payload['new_forecasts'])
    assert all(item['predicted_price'] > 0 for item in payload['new_forecasts'])

    latest = client.get('/api/market/latest').json()
    assert latest['date'] == next_date.isoformat()
    history = client.get('/api/forecast-history?limit=50').json()
    assert len(history) >= 12
    assert {row['forecast_mode'] for row in history}.issuperset({'challenger'})
