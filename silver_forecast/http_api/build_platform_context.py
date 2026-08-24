from __future__ import annotations

from silver_forecast.backtesting.walk_forward_result_catalog import WalkForwardResultCatalog
from silver_forecast.feature_engineering.selected_forecast_features import load_selected_forecast_features
from silver_forecast.forecast_history.sql_forecast_history import SqlForecastHistory
from silver_forecast.forecasting.predict_silver_price import PredictSilverPrice
from silver_forecast.http_api.platform_context import PlatformContext
from silver_forecast.market_history.sql_market_history import SqlMarketHistory
from silver_forecast.model_registry.forecast_model_catalog import ForecastModelCatalog
from silver_forecast.model_registry.load_registered_model import RegisteredModelLoader
from silver_forecast.persistent_state.database_connection import build_database_engine, build_session_factory
from silver_forecast.persistent_state.database_schema import create_database_schema
from silver_forecast.reporting.report_catalog import ReportCatalog


def build_platform_context(settings) -> PlatformContext:
    engine = build_database_engine(settings.database_url)
    create_database_schema(engine)
    session_factory = build_session_factory(engine)
    market_history = SqlMarketHistory(session_factory)
    market_history.seed_from_csv_if_empty(settings.market_history_csv)
    selected_features = load_selected_forecast_features(settings.selected_features_json)
    model_catalog = ForecastModelCatalog(settings.model_manifest_json)
    model_loader = RegisteredModelLoader(settings.persisted_models_directory)
    forecast_history = SqlForecastHistory(session_factory)
    predictor = PredictSilverPrice(
        market_history=market_history,
        selected_features=selected_features,
        model_catalog=model_catalog,
        model_loader=model_loader,
        forecast_history=forecast_history,
    )
    backtesting = WalkForwardResultCatalog(settings.backtesting_directory)
    reports = ReportCatalog(settings.reports_directory, settings.backtesting_directory)
    return PlatformContext(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        market_history=market_history,
        selected_features=selected_features,
        model_catalog=model_catalog,
        model_loader=model_loader,
        forecast_history=forecast_history,
        predictor=predictor,
        backtesting=backtesting,
        reports=reports,
    )
