from __future__ import annotations

"""Quality gate applied to the merged silver OHLCV history before any write.

The gate protects the packaged CSV from bad upstream data: broken date
sequences, invalid OHLC rows, negative volume, silently missing sessions,
stale feeds, and unit or tick errors that show up as absurd close-to-close
jumps. The jump guard can be limited to newly fetched rows
(``jump_check_from``) so genuine historical spikes never fail the gate.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd

from silver_forecast.market_history.market_observation import MarketObservation

MAX_MISSING_BUSINESS_DAYS_IN_TRAILING_30 = 5
MAX_STALENESS_CALENDAR_DAYS = 5
MAX_ABSOLUTE_DAILY_CLOSE_CHANGE = 0.25
TRAILING_WINDOW_CALENDAR_DAYS = 30


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class DataQualityReport:
    checks: tuple[QualityCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> tuple[QualityCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)

    def summary(self) -> str:
        lines = [
            f"{'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}"
            for check in self.checks
        ]
        lines.append("Data quality gate " + ("PASSED" if self.passed else "FAILED"))
        return "\n".join(lines)


def _parse_dates(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["Date"], errors="coerce")


def _check_dates_parseable(dates: pd.Series) -> QualityCheck:
    unparseable = int(dates.isna().sum())
    return QualityCheck(
        "dates_parseable",
        unparseable == 0,
        f"{unparseable} unparseable date(s)",
    )


def _check_dates_sorted_unique(dates: pd.Series) -> QualityCheck:
    known = dates.dropna()
    ascending = bool(known.is_monotonic_increasing)
    duplicates = int(known.duplicated().sum())
    passed = ascending and duplicates == 0
    return QualityCheck(
        "dates_sorted_unique",
        passed,
        f"{len(known)} rows, ascending={ascending}, duplicates={duplicates}",
    )


def _observation(row: Any) -> MarketObservation:
    return MarketObservation(
        observation_date=pd.Timestamp(row["Date"]).date(),
        open_price=float(row["Open"]),
        high_price=float(row["High"]),
        low_price=float(row["Low"]),
        close_price=float(row["Close"]),
        volume=float(row["Volume"]),
    )


def _check_ohlc_valid(frame: pd.DataFrame) -> QualityCheck:
    invalid: list[str] = []
    for _, row in frame.iterrows():
        try:
            _observation(row).validate()
        except (TypeError, ValueError) as exc:
            invalid.append(f"{row['Date']}: {exc}")
            if len(invalid) >= 5:
                break
    return QualityCheck(
        "ohlc_valid",
        not invalid,
        "; ".join(invalid) if invalid else f"{len(frame)} row(s) satisfy the OHLC domain rules",
    )


def _check_volume_non_negative(frame: pd.DataFrame) -> QualityCheck:
    volumes = pd.to_numeric(frame["Volume"], errors="coerce")
    negative = int((volumes < 0).sum())
    missing = int(volumes.isna().sum())
    return QualityCheck(
        "volume_non_negative",
        negative == 0 and missing == 0,
        f"negative={negative}, missing={missing} (zero volume is allowed)",
    )


def _check_recent_sessions(dates: pd.Series, as_of: date) -> QualityCheck:
    observed = set(dates.dropna().dt.date)
    window = pd.bdate_range(as_of - timedelta(days=TRAILING_WINDOW_CALENDAR_DAYS - 1), as_of)
    missing = sorted(session.date() for session in window if session.date() not in observed)
    passed = len(missing) <= MAX_MISSING_BUSINESS_DAYS_IN_TRAILING_30
    detail = (
        f"{len(missing)} business day(s) missing in trailing {TRAILING_WINDOW_CALENDAR_DAYS} "
        f"calendar days (limit {MAX_MISSING_BUSINESS_DAYS_IN_TRAILING_30})"
    )
    if missing:
        detail += f": {', '.join(day.isoformat() for day in missing[:5])}"
    return QualityCheck("recent_sessions_present", passed, detail)


def _check_freshness(dates: pd.Series, as_of: date) -> QualityCheck:
    known = dates.dropna()
    last = known.max().date() if not known.empty else None
    stale_days = (as_of - last).days if last is not None else None
    passed = last is not None and stale_days <= MAX_STALENESS_CALENDAR_DAYS
    detail = (
        f"last observation {last}, {stale_days} calendar day(s) behind {as_of} "
        f"(limit {MAX_STALENESS_CALENDAR_DAYS})"
    )
    return QualityCheck("freshness", passed, detail)


def _check_close_jump_guard(
    frame: pd.DataFrame,
    dates: pd.Series,
    jump_check_from: date | None,
    max_daily_close_change: float,
) -> QualityCheck:
    closes = pd.to_numeric(frame["Close"], errors="coerce")
    if jump_check_from is not None:
        guard = dates > pd.Timestamp(jump_check_from)
    else:
        guard = pd.Series(True, index=frame.index)

    violations: list[str] = []
    previous: float | None = None
    for position, (row_date, close) in enumerate(zip(dates, closes)):
        if pd.isna(row_date) or pd.isna(close):
            previous = None
            continue
        if position > 0 and previous is not None and bool(guard.iloc[position]):
            change = abs(float(close) / previous - 1.0)
            if change > max_daily_close_change:
                violations.append(f"{row_date.date()}: {change:.1%} close-to-close")
                if len(violations) >= 5:
                    break
        previous = float(close)

    window_description = (
        f"rows after {jump_check_from}" if jump_check_from is not None else "all rows"
    )
    return QualityCheck(
        "close_jump_guard",
        not violations,
        "; ".join(violations) if violations
        else f"no close-to-close move beyond {max_daily_close_change:.0%} in {window_description}",
    )


def evaluate_data_quality(
    frame: pd.DataFrame,
    as_of: date,
    jump_check_from: date | None = None,
    max_daily_close_change: float = MAX_ABSOLUTE_DAILY_CLOSE_CHANGE,
) -> DataQualityReport:
    """Evaluate the merged history and return a full quality report."""
    dates = _parse_dates(frame)
    checks = (
        _check_dates_parseable(dates),
        _check_dates_sorted_unique(dates),
        _check_ohlc_valid(frame),
        _check_volume_non_negative(frame),
        _check_recent_sessions(dates, as_of),
        _check_freshness(dates, as_of),
        _check_close_jump_guard(frame, dates, jump_check_from, max_daily_close_change),
    )
    return DataQualityReport(checks=checks)
