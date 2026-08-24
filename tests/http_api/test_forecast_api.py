from pathlib import Path
from fastapi.testclient import TestClient

from silver_forecast.http_api.application import create_app
from silver_forecast.platform_configuration.runtime_settings import load_runtime_settings, RuntimeSettings

ROOT = Path(__file__).resolve().parents[2]


def settings_for(tmp_path):
    base = load_runtime_settings(ROOT)
    return RuntimeSettings(**{**base.__dict__, 'database_url': f"sqlite:///{(tmp_path / 'api.db').as_posix()}"})


def test_health_forecast_models_and_reports(tmp_path):
    client = TestClient(create_app(settings_for(tmp_path)))
    health = client.get('/health')
    assert health.status_code == 200
    assert health.json()['status'] == 'ok'
    assert health.json()['selected_features'] == 63

    dashboard = client.get('/api/forecast/dashboard?mode=challenger')
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert len(payload['forecasts']) == 6
    assert payload['market']['unit'] == 'USD/KG'
    assert all(item['predicted_price'] > 0 for item in payload['forecasts'])

    primary = client.get('/api/forecast/latest?mode=primary').json()
    assert all(abs(item['predicted_price'] - item['current_price']) < 1e-9 for item in primary)

    assert len(client.get('/api/models').json()) == 6
    assert client.get('/api/backtesting').status_code == 200
    assert len(client.get('/api/reports').json()) >= 10
    assert client.get('/api/data-quality').json()['leakage_crossings_stage10'] == 0
    assert client.get('/').status_code == 200
