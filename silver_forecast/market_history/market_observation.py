from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MarketObservation:
    observation_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float

    def validate(self) -> None:
        if min(self.open_price, self.high_price, self.low_price, self.close_price) <= 0:
            raise ValueError('OHLC prices must be positive.')
        if self.volume < 0:
            raise ValueError('Volume cannot be negative.')
        if self.high_price < max(self.open_price, self.close_price, self.low_price):
            raise ValueError('High must be greater than or equal to Open, Close, and Low.')
        if self.low_price > min(self.open_price, self.close_price, self.high_price):
            raise ValueError('Low must be less than or equal to Open, Close, and High.')
