from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SilverForecastSchema(DeclarativeBase):
    pass


class MarketObservationRow(SilverForecastSchema):
    __tablename__ = 'market_observations'

    observation_date: Mapped[object] = mapped_column(Date, primary_key=True)
    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    high_price: Mapped[float] = mapped_column(Float, nullable=False)
    low_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)


class ForecastRunRow(SilverForecastSchema):
    __tablename__ = 'forecast_runs'
    __table_args__ = (
        UniqueConstraint(
            'observation_date', 'horizon_sessions', 'forecast_mode', 'model_name', 'model_version',
            name='uq_forecast_run_identity',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_date: Mapped[object] = mapped_column(Date, nullable=False, index=True)
    horizon_sessions: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_price: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    price_accuracy_pct: Mapped[float] = mapped_column(Float, nullable=False)
    directional_accuracy_pct: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    actual_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    absolute_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    absolute_percentage_error_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_accuracy_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


def create_database_schema(engine) -> None:
    SilverForecastSchema.metadata.create_all(engine)
