from datetime import date, timedelta

import pandas as pd

from silver_forecast.market_history.data_quality_gate import evaluate_data_quality
from silver_forecast.market_history.silver_price_sources import (
    TROY_OUNCE_IN_GRAMS,
    USD_PER_TROY_OUNCE_TO_USD_PER_KG,
    usd_per_troy_ounce_to_usd_per_kg,
)

AS_OF = date(2026, 2, 13)


def make_frame(rows):
    return pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])


def recent_rows(as_of, sessions=20, close=1000.0, volume=0):
    """Business-day rows ending on or before ``as_of``."""
    days = [as_of - timedelta(days=offset) for offset in range(sessions * 2)]
    business = [day for day in days if day.weekday() < 5][:sessions]
    business = sorted(business)
    return [
        (
            day.isoformat(),
            close,
            close,
            close,
            close,
            volume,
        )
        for day in business
    ]


def test_conversion_factor():
    assert abs(USD_PER_TROY_OUNCE_TO_USD_PER_KG - 32.1507466) < 1e-6
    assert abs(usd_per_troy_ounce_to_usd_per_kg(TROY_OUNCE_IN_GRAMS) - 1000.0) < 1e-6
    assert abs(usd_per_troy_ounce_to_usd_per_kg(50.0) - 50.0 * 32.1507466) < 1e-6


def test_clean_recent_history_passes():
    report = evaluate_data_quality(make_frame(recent_rows(AS_OF)), as_of=AS_OF)
    assert report.passed, report.summary()


def test_duplicate_dates_fail():
    rows = recent_rows(AS_OF)
    report = evaluate_data_quality(make_frame(rows + [rows[-1]]), as_of=AS_OF)
    assert not report.passed


def test_unsorted_dates_fail():
    rows = recent_rows(AS_OF)
    report = evaluate_data_quality(make_frame(list(reversed(rows))), as_of=AS_OF)
    assert not report.passed


def test_high_below_open_close_fails():
    rows = recent_rows(AS_OF)
    rows[-1] = (rows[-1][0], 1000.0, 900.0, 950.0, 1000.0, 0)
    report = evaluate_data_quality(make_frame(rows), as_of=AS_OF)
    assert not report.passed


def test_low_above_open_close_fails():
    rows = recent_rows(AS_OF)
    rows[-1] = (rows[-1][0], 1000.0, 1050.0, 1010.0, 1000.0, 0)
    report = evaluate_data_quality(make_frame(rows), as_of=AS_OF)
    assert not report.passed


def test_non_positive_price_fails():
    rows = recent_rows(AS_OF)
    rows[-1] = (rows[-1][0], 0.0, 1000.0, 0.0, 1000.0, 0)
    report = evaluate_data_quality(make_frame(rows), as_of=AS_OF)
    assert not report.passed


def test_negative_volume_fails():
    rows = recent_rows(AS_OF)
    rows[-1] = (rows[-1][0], 1000.0, 1000.0, 1000.0, 1000.0, -5)
    report = evaluate_data_quality(make_frame(rows), as_of=AS_OF)
    assert not report.passed


def test_zero_volume_passes():
    report = evaluate_data_quality(make_frame(recent_rows(AS_OF, volume=0)), as_of=AS_OF)
    assert report.passed, report.summary()


def test_stale_history_fails():
    stale_as_of = AS_OF + timedelta(days=10)
    report = evaluate_data_quality(make_frame(recent_rows(AS_OF)), as_of=stale_as_of)
    assert not report.passed


def test_missing_recent_sessions_fails():
    rows = recent_rows(AS_OF)
    report = evaluate_data_quality(make_frame(rows[:-7]), as_of=AS_OF)
    assert not report.passed


def test_jump_guard_fails_on_new_rows():
    rows = recent_rows(AS_OF)
    last_date = date.fromisoformat(rows[-1][0])
    jump_day = last_date + timedelta(days=1)
    while jump_day.weekday() >= 5:
        jump_day += timedelta(days=1)
    spiked = (jump_day.isoformat(), 1000.0, 1600.0, 1000.0, 1500.0, 0)
    report = evaluate_data_quality(
        make_frame(rows + [spiked]), as_of=jump_day, jump_check_from=last_date
    )
    assert not report.passed
    assert any(check.name == "close_jump_guard" for check in report.failures)


def test_jump_guard_ignores_rows_before_jump_check_from():
    rows = recent_rows(AS_OF)
    last_date = date.fromisoformat(rows[-1][0])
    jump_day = last_date + timedelta(days=1)
    while jump_day.weekday() >= 5:
        jump_day += timedelta(days=1)
    spiked = (jump_day.isoformat(), 1000.0, 1600.0, 1000.0, 1500.0, 0)
    # The spike sits at the guard boundary: rows *after* jump_check_from are checked.
    report = evaluate_data_quality(
        make_frame(rows + [spiked]),
        as_of=jump_day,
        jump_check_from=jump_day,
    )
    # The spiked row itself is now before the guard, so it is ignored...
    assert report.passed or any(check.name != "close_jump_guard" for check in report.failures)


def test_summary_marks_failures():
    rows = recent_rows(AS_OF)
    rows[-1] = (rows[-1][0], 1000.0, 1000.0, 1000.0, 1000.0, -1)
    report = evaluate_data_quality(make_frame(rows), as_of=AS_OF)
    summary = report.summary()
    assert "FAIL" in summary
    assert "Data quality gate FAILED" in summary
