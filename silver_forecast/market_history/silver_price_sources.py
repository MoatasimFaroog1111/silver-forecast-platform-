from __future__ import annotations

"""Keyless silver price sources normalized to USD/KG.

The packaged market history stores prices in USD per kilogram while public
sources quote USD per troy ounce. Every row fetched here is converted with a
single explicit factor so the pipeline never mixes units.
"""

import io
import urllib.request
from datetime import date, timedelta
from typing import Callable

import pandas as pd

TROY_OUNCE_IN_GRAMS = 31.1034768
USD_PER_TROY_OUNCE_TO_USD_PER_KG = 1000.0 / TROY_OUNCE_IN_GRAMS

YAHOO_SYMBOL = "SI=F"
STOOQ_SYMBOL = "xagusd"
STOOQ_DAILY_URL = "https://stooq.com/q/d/l/?s={symbol}&d1={start}&d2={end}&i=d"
STOOQ_TIMEOUT_SECONDS = 30
USER_AGENT = "Mozilla/5.0 (compatible; silver-forecast-platform/1.0)"

PRICE_COLUMNS = ("Open", "High", "Low", "Close")
REQUIRED_COLUMNS = ("Date", *PRICE_COLUMNS, "Volume")


class SilverPriceFetchError(RuntimeError):
    """Raised when no silver price source returns usable rows."""


def usd_per_troy_ounce_to_usd_per_kg(price: float) -> float:
    return float(price) * USD_PER_TROY_OUNCE_TO_USD_PER_KG


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(REQUIRED_COLUMNS))


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert USD/troy-oz OHLCV rows to the packaged USD/KG schema."""
    if frame is None or frame.empty:
        return _empty_frame()
    normalized = frame.copy()
    if isinstance(normalized.columns, pd.MultiIndex):
        normalized.columns = normalized.columns.get_level_values(0)
    if "Date" not in normalized.columns:
        normalized = normalized.reset_index()
    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise SilverPriceFetchError(f"price source is missing columns: {missing}")
    normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce")
    for column in PRICE_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce") * USD_PER_TROY_OUNCE_TO_USD_PER_KG
    normalized["Volume"] = pd.to_numeric(normalized["Volume"], errors="coerce").fillna(0.0)
    normalized = normalized.dropna(subset=["Date", *PRICE_COLUMNS])
    normalized = normalized.sort_values("Date").reset_index(drop=True)
    return normalized[list(REQUIRED_COLUMNS)]


def fetch_from_yahoo(start: date, end: date) -> pd.DataFrame:
    """Daily silver futures OHLCV from Yahoo Finance (keyless, USD/troy-oz)."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise SilverPriceFetchError("yfinance is not installed") from exc

    frame = yf.download(
        YAHOO_SYMBOL,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        progress=False,
        auto_adjust=False,
    )
    return _normalize(frame)


def fetch_from_stooq(start: date, end: date) -> pd.DataFrame:
    """Daily silver spot OHLCV from Stooq (keyless CSV, USD/troy-oz)."""
    url = STOOQ_DAILY_URL.format(
        symbol=STOOQ_SYMBOL,
        start=start.strftime("%Y%m%d"),
        end=end.strftime("%Y%m%d"),
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=STOOQ_TIMEOUT_SECONDS) as response:
        text = response.read().decode("utf-8", errors="replace")
    if not text.strip() or text.strip().startswith("No data"):
        return _empty_frame()
    return _normalize(pd.read_csv(io.StringIO(text)))


def fetch_daily_ohlcv_usd_per_kg(start: date, end: date) -> pd.DataFrame:
    """Fetch daily silver OHLCV rows in USD/KG, trying sources in order."""
    fetchers: list[tuple[str, Callable[[date, date], pd.DataFrame]]] = [
        ("yahoo", fetch_from_yahoo),
        ("stooq", fetch_from_stooq),
    ]
    problems: list[str] = []
    for name, fetcher in fetchers:
        try:
            frame = fetcher(start, end)
        except Exception as exc:  # noqa: BLE001 - report and fall through
            problems.append(f"{name}: {exc}")
            continue
        if frame.empty:
            problems.append(f"{name}: no rows between {start} and {end}")
            continue
        observed = frame["Date"].dt.date
        frame = frame[(observed >= start) & (observed <= end)]
        if frame.empty:
            problems.append(f"{name}: no rows between {start} and {end}")
            continue
        return frame.reset_index(drop=True)
    raise SilverPriceFetchError("; ".join(problems) or "no silver price source available")


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    today = date.today()
    print(fetch_daily_ohlcv_usd_per_kg(today - timedelta(days=14), today).tail())
