from datetime import date

from silver_forecast.market_history.update_market_history import (
    build_pending_observations,
    detect_price_precision,
    detect_volume_is_integer,
    merge_observations_text,
    read_last_observation_date,
)

CSV_SAMPLE = (
    "Date,Open,High,Low,Close,Volume\n"
    "2026-01-22,1900.55,1910.25,1895.10,1905.40,150\n"
    "2026-01-23,1919.10,1925.00,1912.75,1920.85,180\n"
)


def row(day, close=1950.0, volume=0):
    return {
        "date": date.fromisoformat(day),
        "open": close,
        "high": close + 10.0,
        "low": close - 10.0,
        "close": close,
        "volume": volume,
    }


def test_read_last_observation_date():
    assert read_last_observation_date(CSV_SAMPLE) == date(2026, 1, 23)


def test_merge_appends_new_rows_sorted():
    merged_text, applied = merge_observations_text(CSV_SAMPLE, [row("2026-01-26")])
    lines = merged_text.strip().splitlines()
    assert lines[-1].startswith("2026-01-26,")
    assert len(applied) == 1


def test_merge_replaces_existing_date():
    merged_text, applied = merge_observations_text(CSV_SAMPLE, [row("2026-01-23", close=9999.0)])
    lines = merged_text.strip().splitlines()
    assert len(lines) == 3
    assert "9999.00" in lines[-1]
    assert len(applied) == 1


def test_untouched_rows_are_preserved_verbatim():
    merged_text, _ = merge_observations_text(CSV_SAMPLE, [row("2026-01-26")])
    assert "2026-01-22,1900.55,1910.25,1895.10,1905.40,150" in merged_text.splitlines()


def test_detect_price_precision():
    assert detect_price_precision("2026-01-23,1919.10,1925.00,1912.75,1920.85,180") == 2
    assert detect_price_precision("2026-01-23,1919.1000,1925.00,1912.75,1920.85,180") == 4
    assert detect_price_precision("2026-01-23,1919,1925,1912,1920,180") == 2


def test_detect_volume_is_integer():
    assert detect_volume_is_integer(CSV_SAMPLE) is True
    decimal_volume = CSV_SAMPLE.replace(",150\n", ",150.5\n")
    assert detect_volume_is_integer(decimal_volume) is False


def test_merge_formats_new_rows_with_detected_precision():
    merged_text, _ = merge_observations_text(
        CSV_SAMPLE.replace("1919.10,", "1919.1000,"), [row("2026-01-26")]
    )
    new_line = merged_text.strip().splitlines()[-1]
    assert new_line.startswith("2026-01-26,1950.0000,")
    assert new_line.endswith(",0")


def test_build_pending_observations():
    applied = [row("2026-01-22"), row("2026-01-23"), row("2026-01-26")]
    pending = build_pending_observations(applied, date(2026, 1, 23))
    assert [entry["date"] for entry in pending] == ["2026-01-23", "2026-01-26"]
    assert pending[0]["close"] == 1950.0
