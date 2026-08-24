from __future__ import annotations


def latest_market_price(market_history) -> dict:
    observation = market_history.latest()
    return {
        'date': observation.observation_date.isoformat(),
        'open': observation.open_price,
        'high': observation.high_price,
        'low': observation.low_price,
        'close': observation.close_price,
        'volume': observation.volume,
        'unit': 'USD/KG',
    }
