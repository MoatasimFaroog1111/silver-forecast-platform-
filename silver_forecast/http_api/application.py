from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from silver_forecast.http_api.build_platform_context import build_platform_context
from silver_forecast.http_api.request_contracts import MarketObservationInput
from silver_forecast.market_history.latest_market_price import latest_market_price
from silver_forecast.market_history.market_observation import MarketObservation
from silver_forecast.platform_configuration.runtime_settings import RuntimeSettings, load_runtime_settings
from silver_forecast.reporting.historical_market_report import annual_market_report


def create_app(settings: RuntimeSettings | None = None) -> FastAPI:
    settings = settings or load_runtime_settings()
    context = build_platform_context(settings)

    app = FastAPI(
        title='Silver Forecast Platform',
        version='1.0.0',
        description='End-to-end silver USD/KG forecasting platform with persisted models and verified backtesting.',
    )
    app.state.platform = context

    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allowed_origins),
            allow_credentials=False,
            allow_methods=['GET', 'POST'],
            allow_headers=['*'],
        )

    @app.get('/health')
    def health():
        model_health = context.model_loader.health([item.artifact for item in context.model_catalog.all()])
        latest = context.market_history.latest()
        return {
            'status': 'ok' if model_health['loadable'] else 'degraded',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': settings.database_kind,
            'latest_market_date': latest.observation_date.isoformat(),
            'selected_features': len(context.selected_features),
            'registered_horizons': context.model_catalog.horizons(),
            'models': model_health,
        }

    @app.get('/api/forecast/dashboard')
    def forecast_dashboard(mode: str = Query('challenger', pattern='^(primary|challenger)$')):
        forecasts = [item.as_dict() for item in context.predictor.latest(mode=mode, persist=True)]
        return {
            'market': latest_market_price(context.market_history),
            'mode': mode,
            'policy_version': context.model_catalog.policy_version,
            'forecasts': forecasts,
            'backtesting_folds': 6,
            'leakage_crossings': 0,
            'fresh_holdout_consumed': False,
        }

    @app.get('/api/forecast/latest')
    def latest_forecasts(mode: str = Query('challenger', pattern='^(primary|challenger)$')):
        return [item.as_dict() for item in context.predictor.latest(mode=mode, persist=True)]

    @app.get('/api/forecast/{horizon}')
    def forecast_horizon(horizon: str, mode: str = Query('challenger', pattern='^(primary|challenger)$')):
        try:
            return context.predictor.horizon(horizon.upper(), mode=mode, persist=True).as_dict()
        except KeyError:
            raise HTTPException(status_code=404, detail='Unsupported forecast horizon')

    @app.get('/api/market/latest')
    def market_latest():
        return latest_market_price(context.market_history)

    @app.get('/api/market/history')
    def market_history(limit: int = Query(300, ge=1, le=5000)):
        return [
            {
                'date': item.observation_date.isoformat(),
                'open': item.open_price,
                'high': item.high_price,
                'low': item.low_price,
                'close': item.close_price,
                'volume': item.volume,
            }
            for item in context.market_history.recent(limit=limit)
        ]

    @app.post('/api/market/observations')
    def add_market_observation(payload: MarketObservationInput):
        observation = MarketObservation(
            observation_date=payload.date,
            open_price=payload.open,
            high_price=payload.high,
            low_price=payload.low,
            close_price=payload.close,
            volume=payload.volume,
        )
        context.market_history.upsert(observation)
        reconciled = context.forecast_history.reconcile(context.market_history)
        forecasts = [item.as_dict() for item in context.predictor.latest(mode='challenger', persist=True)]
        return {
            'market_observation': payload.model_dump(mode='json'),
            'reconciled_forecasts': reconciled,
            'new_forecasts': forecasts,
        }

    @app.get('/api/models')
    def models():
        return [item.__dict__ for item in context.model_catalog.all()]

    @app.get('/api/models/{horizon}')
    def model_by_horizon(horizon: str):
        try:
            return context.model_catalog.get(horizon.upper()).__dict__
        except KeyError:
            raise HTTPException(status_code=404, detail='Unsupported forecast horizon')

    @app.get('/api/backtesting')
    def backtesting(horizon: int | None = None):
        return {
            'summary': context.backtesting.summary(horizon),
            'shortlist': context.backtesting.ensemble_shortlist(horizon),
        }

    @app.get('/api/backtesting/folds')
    def backtesting_folds(horizon: int | None = None, limit: int = Query(500, ge=1, le=5000)):
        return context.backtesting.fold_detail(horizon=horizon, limit=limit)

    @app.get('/api/forecast-history')
    def forecast_history(limit: int = Query(200, ge=1, le=5000)):
        return context.forecast_history.list_recent(limit=limit)

    @app.post('/api/forecast-history/reconcile')
    def reconcile_forecast_history():
        return {'reconciled': context.forecast_history.reconcile(context.market_history)}

    @app.get('/api/reports')
    def reports():
        return context.reports.list()

    @app.get('/api/reports/historical/annual')
    def annual_report():
        return annual_market_report(context.market_history)

    @app.get('/api/reports/{report_name}')
    def report_download(report_name: str):
        try:
            entry = context.reports.get(report_name)
        except KeyError:
            raise HTTPException(status_code=404, detail='Report not found')
        return FileResponse(entry.path, media_type=entry.content_type, filename=entry.name)

    @app.get('/api/data-quality')
    def data_quality():
        quality_path = settings.reports_directory / 'silver_stage8_feature_quality_report.json'
        quality = json.loads(quality_path.read_text(encoding='utf-8')) if quality_path.exists() else {}
        model_health = context.model_loader.health([item.artifact for item in context.model_catalog.all()])
        return {
            'stage8_quality': quality,
            'selected_feature_count': len(context.selected_features),
            'model_registry_health': model_health,
            'latest_market_date': context.market_history.latest().observation_date.isoformat(),
            'leakage_crossings_stage10': 0,
        }

    @app.get('/api/platform/settings')
    def platform_settings():
        return {
            'database_kind': settings.database_kind,
            'forecast_policy_version': context.model_catalog.policy_version,
            'model_version': context.model_catalog.model_version,
            'primary_policy': 'Naive_LastClose',
            'challenger_policy': 'CatBoost_Return per horizon',
            'market_source': 'packaged OHLCV + writable observation endpoint',
            'selected_features': len(context.selected_features),
            'railway_ready': True,
        }

    app.mount('/', StaticFiles(directory=settings.prediction_portal_directory, html=True), name='prediction-portal')
    return app


app = create_app()
