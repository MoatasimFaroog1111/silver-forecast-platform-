from __future__ import annotations

from datetime import date
from pathlib import Path
import pandas as pd
from sqlalchemy import select

from silver_forecast.market_history.market_observation import MarketObservation
from silver_forecast.persistent_state.database_schema import MarketObservationRow


class SqlMarketHistory:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def seed_from_csv_if_empty(self, csv_path: Path) -> int:
        with self._session_factory() as session:
            has_any = session.execute(select(MarketObservationRow.observation_date).limit(1)).first()
            if has_any:
                return 0
        frame = pd.read_csv(csv_path)
        observations = [
            MarketObservation(
                observation_date=pd.Timestamp(row.Date).date(),
                open_price=float(row.Open), high_price=float(row.High), low_price=float(row.Low),
                close_price=float(row.Close), volume=float(row.Volume),
            )
            for row in frame.itertuples(index=False)
        ]
        with self._session_factory() as session:
            session.add_all([
                MarketObservationRow(
                    observation_date=o.observation_date,
                    open_price=o.open_price, high_price=o.high_price, low_price=o.low_price,
                    close_price=o.close_price, volume=o.volume,
                ) for o in observations
            ])
            session.commit()
        return len(observations)

    def upsert(self, observation: MarketObservation) -> MarketObservation:
        observation.validate()
        with self._session_factory() as session:
            row = session.get(MarketObservationRow, observation.observation_date)
            if row is None:
                row = MarketObservationRow(observation_date=observation.observation_date)
                session.add(row)
            row.open_price = observation.open_price
            row.high_price = observation.high_price
            row.low_price = observation.low_price
            row.close_price = observation.close_price
            row.volume = observation.volume
            session.commit()
        return observation

    def latest(self) -> MarketObservation:
        with self._session_factory() as session:
            row = session.execute(
                select(MarketObservationRow).order_by(MarketObservationRow.observation_date.desc()).limit(1)
            ).scalar_one()
            return self._to_domain(row)

    def all_as_frame(self) -> pd.DataFrame:
        with self._session_factory() as session:
            rows = session.execute(
                select(MarketObservationRow).order_by(MarketObservationRow.observation_date.asc())
            ).scalars().all()
        return pd.DataFrame([
            {
                'Date': row.observation_date.isoformat(),
                'Open': row.open_price,
                'High': row.high_price,
                'Low': row.low_price,
                'Close': row.close_price,
                'Volume': row.volume,
            }
            for row in rows
        ])

    def recent(self, limit: int = 200) -> list[MarketObservation]:
        with self._session_factory() as session:
            rows = session.execute(
                select(MarketObservationRow)
                .order_by(MarketObservationRow.observation_date.desc())
                .limit(limit)
            ).scalars().all()
        return [self._to_domain(row) for row in reversed(rows)]

    @staticmethod
    def _to_domain(row: MarketObservationRow) -> MarketObservation:
        return MarketObservation(
            observation_date=row.observation_date,
            open_price=row.open_price,
            high_price=row.high_price,
            low_price=row.low_price,
            close_price=row.close_price,
            volume=row.volume,
        )
