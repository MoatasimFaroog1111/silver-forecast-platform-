from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field, model_validator


class MarketObservationInput(BaseModel):
    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode='after')
    def validate_ohlc(self):
        if self.high < max(self.open, self.close, self.low):
            raise ValueError('high must be >= open, close, and low')
        if self.low > min(self.open, self.close, self.high):
            raise ValueError('low must be <= open, close, and high')
        return self
