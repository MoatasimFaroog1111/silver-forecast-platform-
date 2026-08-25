from __future__ import annotations

from datetime import date
from sqlalchemy import select

from silver_forecast.persistent_state.database_schema import ForecastRunRow


class SqlForecastHistory:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def save_many(self, results) -> int:
        inserted = 0
        with self._session_factory() as session:
            for result in results:
                observation_date = date.fromisoformat(result.observation_date)
                existing = session.execute(
                    select(ForecastRunRow).where(
                        ForecastRunRow.observation_date == observation_date,
                        ForecastRunRow.horizon_sessions == result.horizon_sessions,
                        ForecastRunRow.forecast_mode == result.forecast_mode,
                        ForecastRunRow.model_name == result.model_name,
                        ForecastRunRow.model_version == result.model_version,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    continue
                session.add(ForecastRunRow(
                    observation_date=observation_date,
                    horizon_sessions=result.horizon_sessions,
                    current_price=result.current_price,
                    predicted_price=result.predicted_price,
                    predicted_change_pct=result.predicted_change_pct,
                    price_accuracy_pct=result.price_accuracy_pct,
                    directional_accuracy_pct=result.directional_accuracy_pct,
                    forecast_mode=result.forecast_mode,
                    model_name=result.model_name,
                    model_version=result.model_version,
                ))
                inserted += 1
            session.commit()
        return inserted

    def list_recent(self, limit: int = 200) -> list[dict]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ForecastRunRow).order_by(ForecastRunRow.id.desc()).limit(limit)
            ).scalars().all()
        return [self._serialize(row) for row in rows]

    def unreconciled(self) -> list[ForecastRunRow]:
        with self._session_factory() as session:
            return list(session.execute(
                select(ForecastRunRow).where(ForecastRunRow.actual_price.is_(None))
            ).scalars().all())

    def reconcile(self, market_history) -> int:
        observations = market_history.recent(limit=100000)
        index_by_date = {item.observation_date: idx for idx, item in enumerate(observations)}
        reconciled = 0
        with self._session_factory() as session:
            rows = session.execute(
                select(ForecastRunRow).where(ForecastRunRow.actual_price.is_(None))
            ).scalars().all()
            for row in rows:
                start_index = index_by_date.get(row.observation_date)
                if start_index is None:
                    continue
                target_index = start_index + row.horizon_sessions
                if target_index >= len(observations):
                    continue
                actual = float(observations[target_index].close_price)
                absolute_error = abs(actual - row.predicted_price)
                ape = absolute_error / actual * 100 if actual else None
                row.actual_price = actual
                row.absolute_error = absolute_error
                row.absolute_percentage_error_pct = ape
                row.realized_accuracy_pct = None if ape is None else max(0.0, min(100.0, 100.0 - ape))
                reconciled += 1
            session.commit()
        return reconciled

    @staticmethod
    def _serialize(row: ForecastRunRow) -> dict:
        return {
            'id': row.id,
            'observation_date': row.observation_date.isoformat(),
            'horizon_sessions': row.horizon_sessions,
            'current_price': row.current_price,
            'predicted_price': row.predicted_price,
            'predicted_change_pct': row.predicted_change_pct,
            'price_accuracy_pct': row.price_accuracy_pct,
            'directional_accuracy_pct': row.directional_accuracy_pct,
            'forecast_mode': row.forecast_mode,
            'model_name': row.model_name,
            'model_version': row.model_version,
            'actual_price': row.actual_price,
            'absolute_error': row.absolute_error,
            'absolute_percentage_error_pct': row.absolute_percentage_error_pct,
            'realized_accuracy_pct': row.realized_accuracy_pct,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
