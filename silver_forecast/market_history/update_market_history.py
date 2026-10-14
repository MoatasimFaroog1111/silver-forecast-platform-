from __future__ import annotations

"""Daily update of the packaged silver OHLCV history (USD/KG).

The CSV is rewritten text-based: untouched rows keep their original bytes,
new or revised rows are formatted with the decimal precision detected in the
file. The merged result must pass the data quality gate before anything is
written, so a failing run never corrupts the packaged history.
"""

import argparse
import io
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from silver_forecast.market_history.data_quality_gate import evaluate_data_quality
from silver_forecast.market_history.silver_price_sources import fetch_daily_ohlcv_usd_per_kg

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV_PATH = ROOT / "historical_market_data" / "silver_ohlcv_usd_per_kg.csv"
FETCH_OVERLAP_DAYS = 7
FALLBACK_PRICE_DECIMALS = 2


def _parse_row_date(line: str) -> date:
    token = line.split(",")[0].strip()
    return pd.Timestamp(token).date()


def read_last_observation_date(csv_text: str) -> date:
    lines = [line for line in csv_text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("market history CSV must contain a header and at least one row")
    return _parse_row_date(lines[-1])


def detect_price_precision(sample_line: str) -> int:
    """Detect price decimals from a CSV row (its Open token)."""
    fields = sample_line.split(",")
    token = fields[1].strip() if len(fields) > 1 else ""
    if "." in token:
        return len(token.split(".", 1)[1])
    return FALLBACK_PRICE_DECIMALS


def detect_volume_is_integer(csv_text: str) -> bool:
    """True when every volume token in the CSV body is integer-formatted."""
    for line in csv_text.splitlines()[1:]:
        fields = line.split(",")
        if len(fields) < 6:
            continue
        if "." in fields[5]:
            return False
    return True


def _format_row(row: dict[str, Any], price_decimals: int, volume_is_integer: bool) -> str:
    volume = float(row["volume"])
    volume_text = str(int(round(volume))) if volume_is_integer else f"{volume:g}"
    return ",".join(
        [
            row["date"].isoformat(),
            f"{float(row['open']):.{price_decimals}f}",
            f"{float(row['high']):.{price_decimals}f}",
            f"{float(row['low']):.{price_decimals}f}",
            f"{float(row['close']):.{price_decimals}f}",
            volume_text,
        ]
    )


def merge_observations_text(csv_text: str, new_rows: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Merge observation dicts into the CSV text.

    Existing rows are preserved byte-for-byte unless their date appears in
    ``new_rows``. Returns ``(merged_text, applied_rows)`` where ``applied_rows``
    lists the appended or revised rows in date order.
    """
    lines = [line for line in csv_text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("market history CSV must contain a header and at least one row")
    header, data_lines = lines[0], lines[1:]
    price_decimals = detect_price_precision(data_lines[-1])
    volume_is_integer = detect_volume_is_integer(csv_text)

    existing: dict[date, str] = {}
    for line in data_lines:
        existing[_parse_row_date(line)] = line

    incoming: dict[date, str] = {}
    applied: dict[date, dict[str, Any]] = {}
    for row in new_rows:
        row_date = row["date"]
        incoming[row_date] = _format_row(row, price_decimals, volume_is_integer)
        applied[row_date] = row

    merged_dates = sorted(existing.keys() | incoming.keys())
    body = [incoming[day] if day in incoming else existing[day] for day in merged_dates]
    return header + "\n" + "\n".join(body) + "\n", [applied[day] for day in sorted(applied.keys())]


def build_pending_observations(
    applied_rows: list[dict[str, Any]],
    last_known_date: date,
) -> list[dict[str, Any]]:
    """Rows to push to the production API: revised last row plus new dates."""
    pending: list[dict[str, Any]] = []
    for row in applied_rows:
        if row["date"] >= last_known_date:
            pending.append(
                {
                    "date": row["date"].isoformat(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )
    return pending


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.update-{os.getpid()}.tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and merge daily silver prices (USD/KG) behind a data quality gate."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="packaged history CSV")
    parser.add_argument("--pending", type=Path, default=None, help="write pending observations JSON here")
    parser.add_argument("--start", default=None, help="ISO date; default: last CSV date minus 7 days")
    parser.add_argument("--end", default=None, help="ISO date; default: today")
    parser.add_argument(
        "--max-daily-close-change",
        type=float,
        default=0.25,
        help="close-to-close jump guard threshold (default 0.25)",
    )
    args = parser.parse_args(argv)

    csv_text = args.csv.read_text(encoding="utf-8")
    last_known = read_last_observation_date(csv_text)
    start = pd.Timestamp(args.start).date() if args.start else last_known - timedelta(days=FETCH_OVERLAP_DAYS)
    end = pd.Timestamp(args.end).date() if args.end else date.today()

    frame = fetch_daily_ohlcv_usd_per_kg(start, end)
    new_rows = [
        {
            "date": pd.Timestamp(row["Date"]).date(),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]),
        }
        for _, row in frame.iterrows()
    ]

    merged_text, applied_rows = merge_observations_text(csv_text, new_rows)
    merged_frame = pd.read_csv(io.StringIO(merged_text))
    report = evaluate_data_quality(
        merged_frame,
        as_of=end,
        jump_check_from=last_known,
        max_daily_close_change=args.max_daily_close_change,
    )
    print(report.summary())
    if not report.passed:
        print("Quality gate failed; the CSV was not modified.", file=sys.stderr)
        return 1

    _atomic_write_text(args.csv, merged_text)
    last_row_date = pd.Timestamp(merged_frame["Date"].iloc[-1]).date()
    print(
        f"Updated {args.csv}: {len(applied_rows)} new/revised row(s), "
        f"{len(merged_frame)} total, last date {last_row_date}"
    )

    if args.pending is not None:
        pending = build_pending_observations(applied_rows, last_known)
        payload = {"as_of": end.isoformat(), "observations": pending}
        _atomic_write_text(args.pending, json.dumps(payload, indent=2) + "\n")
        print(f"Wrote {len(pending)} pending observation(s) to {args.pending}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
