from __future__ import annotations

import pandas as pd


def annual_market_report(market_history) -> list[dict]:
    frame = market_history.all_as_frame()
    frame['Date'] = pd.to_datetime(frame['Date'])
    frame['Year'] = frame['Date'].dt.year
    rows = []
    for year, group in frame.groupby('Year'):
        first = float(group.iloc[0]['Close'])
        last = float(group.iloc[-1]['Close'])
        rows.append({
            'year': int(year),
            'start_price': first,
            'end_price': last,
            'change_pct': (last / first - 1) * 100,
            'high': float(group['High'].max()),
            'low': float(group['Low'].min()),
            'observations': int(len(group)),
        })
    return rows
