from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_div(numerator, denominator):
    if isinstance(denominator, pd.Series):
        denominator = denominator.replace(0, np.nan)
    return numerator / denominator


def calculate_forecast_features(market_history: pd.DataFrame) -> pd.DataFrame:
    """Calculate the Stage-8 causal feature set from OHLCV only.

    Every transformation uses the current row and/or trailing observations. No target column,
    future shift, centered window, backfill, or future interpolation is used.
    """
    x = market_history.copy()
    x['Date'] = pd.to_datetime(x['Date'])
    x = x.sort_values('Date').reset_index(drop=True)

    close = x['Close'].astype(float)
    open_ = x['Open'].astype(float)
    high = x['High'].astype(float)
    low = x['Low'].astype(float)
    volume = x['Volume'].astype(float)

    daily_return = (close / close.shift(1) - 1) * 100
    x['Daily_Return'] = daily_return
    x['Volatility'] = daily_return.rolling(30, min_periods=30).std(ddof=1)

    for window in (7, 14, 30, 200):
        x[f'SMA_{window}'] = close.rolling(window, min_periods=window).mean()

    x['EMA_12'] = close.ewm(span=12, adjust=False).mean()
    x['EMA_26'] = close.ewm(span=26, adjust=False).mean()
    x['MACD'] = x['EMA_12'] - x['EMA_26']
    x['Signal_Line'] = x['MACD'].ewm(span=9, adjust=False).mean()
    x['MACD_Histogram'] = x['MACD'] - x['Signal_Line']

    x['BB_Middle'] = close.rolling(20, min_periods=20).mean()
    bb_std = close.rolling(20, min_periods=20).std(ddof=1)
    x['BB_Upper'] = x['BB_Middle'] + 2 * bb_std
    x['BB_Lower'] = x['BB_Middle'] - 2 * bb_std

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ], axis=1,
    ).max(axis=1)
    x['ATR'] = true_range.rolling(14, min_periods=14).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = gain.rolling(14, min_periods=14).mean()
    average_loss = loss.rolling(14, min_periods=14).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = pd.Series(np.where((average_loss == 0) & (average_gain > 0), 100, rsi), index=x.index)
    rsi = pd.Series(np.where((average_gain == 0) & (average_loss > 0), 0, rsi), index=x.index)
    x['RSI'] = rsi

    volume_ma = volume.rolling(14, min_periods=14).mean()
    x['Volume_Ratio'] = _safe_div(volume, volume_ma)

    for window in (3, 5, 10, 20, 60):
        x[f'Return_{window}D_Pct'] = (close / close.shift(window) - 1) * 100

    for window in (5, 10, 20, 60):
        x[f'Return_Std_{window}D_Pct'] = daily_return.rolling(window, min_periods=window).std(ddof=1)
        x[f'Positive_Return_Ratio_{window}D'] = (
            (daily_return > 0).astype(float).rolling(window, min_periods=window).mean()
        )

    x['Momentum_Acceleration_5_20'] = x['Return_5D_Pct'] - x['Return_20D_Pct']
    x['Momentum_Acceleration_10_60'] = x['Return_10D_Pct'] - x['Return_60D_Pct']

    x['ATR_Pct'] = _safe_div(x['ATR'], close) * 100
    x['MACD_Pct'] = _safe_div(x['MACD'], close) * 100
    x['MACD_Histogram_Pct'] = _safe_div(x['MACD_Histogram'], close) * 100
    x['SMA_7_30_Spread_Pct'] = _safe_div(x['SMA_7'] - x['SMA_30'], close) * 100
    x['SMA_30_200_Spread_Pct'] = _safe_div(x['SMA_30'] - x['SMA_200'], close) * 100

    for window in (7, 14, 30, 200):
        x[f'Price_vs_SMA_{window}_Pct'] = (close / x[f'SMA_{window}'] - 1) * 100

    bollinger_width = x['BB_Upper'] - x['BB_Lower']
    x['BB_Width_Pct'] = _safe_div(bollinger_width, x['BB_Middle']) * 100
    x['BB_Position'] = _safe_div(close - x['BB_Lower'], bollinger_width)
    x['Daily_Range_Pct'] = _safe_div(high - low, close) * 100
    x['Candle_Body_Pct'] = _safe_div(close - open_, open_) * 100
    x['Gap_From_Prev_Close_Pct'] = _safe_div(open_ - close.shift(1), close.shift(1)) * 100
    day_range = high - low
    x['Close_Location_In_Daily_Range'] = np.where(day_range > 0, (close - low) / day_range, 0.5)

    for window in (20, 60):
        rolling_high = high.rolling(window, min_periods=window).max()
        rolling_low = low.rolling(window, min_periods=window).min()
        x[f'Price_Position_{window}D'] = _safe_div(close - rolling_low, rolling_high - rolling_low)
        x[f'Drawdown_From_{window}D_High_Pct'] = (close / rolling_high - 1) * 100
        x[f'Distance_From_{window}D_Low_Pct'] = (close / rolling_low - 1) * 100

    def normalized_slope(values):
        values = np.asarray(values, dtype=float)
        time = np.arange(len(values), dtype=float)
        centered = time - time.mean()
        denominator = np.dot(centered, centered)
        slope = np.dot(centered, values - values.mean()) / denominator if denominator else 0.0
        return slope / values[-1] * 100 if values[-1] != 0 else np.nan

    for window in (10, 20, 60):
        x[f'Trend_Slope_{window}D_PctPerDay'] = close.rolling(
            window, min_periods=window
        ).apply(normalized_slope, raw=True)

    x['Volatility_Relative_60D'] = _safe_div(
        x['Volatility'], x['Volatility'].rolling(60, min_periods=60).median()
    )
    x['ATR_Pct_Relative_60D'] = _safe_div(
        x['ATR_Pct'], x['ATR_Pct'].rolling(60, min_periods=60).median()
    )

    x['RSI_Overbought_Flag'] = (x['RSI'] > 70).astype(int)
    x['RSI_Oversold_Flag'] = (x['RSI'] < 30).astype(int)
    x['Trend_Up_Flag'] = ((close > x['SMA_30']) & (x['SMA_30'] > x['SMA_200'])).astype(int)
    x['Trend_Down_Flag'] = ((close < x['SMA_30']) & (x['SMA_30'] < x['SMA_200'])).astype(int)
    x['High_Volatility_Flag'] = (x['Volatility_Relative_60D'] > 1.25).astype(int)
    x['High_ATR_Flag'] = (x['ATR_Pct_Relative_60D'] > 1.25).astype(int)
    x['Strong_Positive_Momentum_Flag'] = (x['Return_20D_Pct'] > 5).astype(int)
    x['Strong_Negative_Momentum_Flag'] = (x['Return_20D_Pct'] < -5).astype(int)

    x['Zero_Volume_Flag'] = (volume <= 0).astype(int)
    x['Log1p_Volume'] = np.log1p(volume.clip(lower=0))
    x['Log1p_Volume_Change_1D'] = x['Log1p_Volume'] - x['Log1p_Volume'].shift(1)
    x['Volume_vs_Median20'] = _safe_div(volume, volume.rolling(20, min_periods=20).median())
    x['Nonzero_Volume_Ratio_20D'] = (
        (volume > 0).astype(float).rolling(20, min_periods=20).mean()
    )

    day_of_week = x['Date'].dt.dayofweek
    month = x['Date'].dt.month
    x['DayOfWeek_Sin'] = np.sin(2 * np.pi * day_of_week / 5)
    x['DayOfWeek_Cos'] = np.cos(2 * np.pi * day_of_week / 5)
    x['Month_Sin'] = np.sin(2 * np.pi * (month - 1) / 12)
    x['Month_Cos'] = np.cos(2 * np.pi * (month - 1) / 12)

    return x.replace([np.inf, -np.inf], np.nan)
