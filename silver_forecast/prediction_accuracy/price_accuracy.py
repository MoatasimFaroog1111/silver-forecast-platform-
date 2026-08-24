from __future__ import annotations


def price_accuracy_from_mape(mape_pct: float) -> float:
    return max(0.0, min(100.0, 100.0 - float(mape_pct)))
