c
#!/usr/bin/env bash
# =============================================================================
# Phase 1 — data pipeline & cleanup push script
# Repo: https://github.com/MoatasimFaroog1111/silver-forecast-platform-
#
# Usage:
#   git clone https://github.com/MoatasimFaroog1111/silver-forecast-platform-.git
#   cd silver-forecast-platform-
#   bash phase1-push.sh
#
# Codespaces alternative (no Git install, no PAT needed — auth is automatic):
#   GitHub → repository → green "Code" button → Codespaces tab → "+ Create codespace on main"
#   In the codespace terminal: create phase1-push.sh with this script's content, then:
#   bash phase1-push.sh
#
# Creates 11 files (or overwrites 3 existing ones), commits and pushes to main.
# git push uses your existing Git credentials (HTTPS PAT or SSH).
# In a codespace, credentials are preconfigured — do NOT paste any token.
# =============================================================================
set -euo pipefail

if [ ! -d silver_forecast ] || [ ! -f pyproject.toml ]; then
  echo "ERROR: run this from the repository root (the clone of silver-forecast-platform-)." >&2
  exit 1
fi

git switch main
git pull --ff-only origin main

# Markdown files below use %%%FENCE%%% as a placeholder for triple backticks.
FENCE="$(printf '%s%s%s' '`' '`' '`')"
restore_fence() { sed -i "s/%%%FENCE%%%/${FENCE}/g" "$1"; }


echo "Writing .github/workflows/daily-market-data.yml"
mkdir -p '.github/workflows'
cat > '.github/workflows/daily-market-data.yml' <<'SILVER_EOF'
name: Daily Market Data

on:
  schedule:
    # 23:30 UTC, Tuesday-Saturday: captures the Monday-Friday sessions.
    - cron: "30 23 * * 2-6"
  workflow_dispatch:

permissions:
  contents: write
  issues: write

concurrency:
  group: daily-market-data
  cancel-in-progress: false

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install 'yfinance>=0.2,<2'

      - name: Materialize exact runtime repair parts
        run: python -m silver_forecast.platform_configuration.materialize_runtime_parts

      - name: Restore exact runtime artifacts
        run: python -m silver_forecast.platform_configuration.restore_runtime_artifacts

      - name: Fetch and merge daily silver prices (USD/kg)
        run: >
          python -m silver_forecast.market_history.update_market_history
          --csv historical_market_data/silver_ohlcv_usd_per_kg.csv
          --pending runtime_state/pending_observations.json

      - name: Rebuild runtime payload bundle
        run: python -m silver_forecast.platform_configuration.rebuild_runtime_payload

      - name: Verify rebuilt bundle
        run: python -m silver_forecast.platform_configuration.restore_runtime_artifacts

      - name: Commit and push updated history
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add historical_market_data/silver_ohlcv_usd_per_kg.csv \
                  runtime_artifacts \
                  runtime_state/pending_observations.json
          if git diff --staged --quiet; then
            echo "No market data changes to commit."
          else
            git commit -m "data: daily silver OHLCV update (USD/kg) [skip ci]"
            git push
          fi

      - name: Push observations to production API
        env:
          HAS_API_URL: ${{ secrets.PRODUCTION_API_URL != '' }}
          PRODUCTION_API_URL: ${{ secrets.PRODUCTION_API_URL }}
          MARKET_OBSERVATIONS_TOKEN: ${{ secrets.MARKET_OBSERVATIONS_TOKEN }}
        if: env.HAS_API_URL == 'true'
        run: |
          count=$(jq '.observations | length' runtime_state/pending_observations.json)
          echo "Pushing $count observation(s) to the production API..."
          jq -c '.observations[]' runtime_state/pending_observations.json | while read -r payload; do
            args=(-X POST "${PRODUCTION_API_URL%/}/api/market/observations"
              -H 'Content-Type: application/json' --fail --silent --show-error)
            if [ -n "$MARKET_OBSERVATIONS_TOKEN" ]; then
              args+=(-H "Authorization: Bearer $MARKET_OBSERVATIONS_TOKEN")
            fi
            curl "${args[@]}" -d "$payload"
          done

  alert:
    needs: update
    if: ${{ failure() }}
    runs-on: ubuntu-latest
    permissions:
      issues: write
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - name: Open data quality alert issue
        run: |
          repo="${{ github.repository }}"
          run_url="${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          body="The daily silver market data pipeline failed. Either the fetch or the data quality gate did not pass, so the packaged CSV was **not** modified.

          Inspect the run: ${run_url}

          _After fixing the cause, close this issue; a new alert will be opened if the next run fails again._"
          existing=$(gh api "repos/${repo}/issues?state=open&labels=data-quality-alert" --jq '.[0].number // empty')
          if [ -n "$existing" ]; then
            echo "Commenting on existing alert issue #${existing}"
            gh api "repos/${repo}/issues/${existing}/comments" -f body="$body"
          else
            gh api "repos/${repo}/issues" \
              -f title="Data quality alert: daily market data pipeline failed" \
              -f body="$body" \
              -F 'labels[]=data-quality-alert'
          fi
SILVER_EOF

echo "Writing .github/workflows/branch-cleanup.yml"
mkdir -p '.github/workflows'
cat > '.github/workflows/branch-cleanup.yml' <<'SILVER_EOF'
name: Branch Cleanup

on:
  schedule:
    - cron: "0 2 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  delete-stale-runtime-repair-branches:
    runs-on: ubuntu-latest
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - name: Delete retired runtime-repair branches
        run: |
          set -euo pipefail
          branches=(
            fix/railway-exact-runtime-restore
            fix/railway-runtime-recovery
            fix/runtime-part031-exact
            materialize-v8
            runtime-payload-staging
          )
          for branch in "${branches[@]}"; do
            ref=$(printf 'heads/%s' "$branch" | jq -Rr @uri)
            if gh api "repos/${{ github.repository }}/git/refs/$ref" >/dev/null 2>&1; then
              gh api --method DELETE "repos/${{ github.repository }}/git/refs/$ref"
              echo "Deleted $branch"
            else
              echo "Branch $branch not found (already deleted)"
            fi
          done
SILVER_EOF

echo "Writing silver_forecast/market_history/silver_price_sources.py"
mkdir -p 'silver_forecast/market_history'
cat > 'silver_forecast/market_history/silver_price_sources.py' <<'SILVER_EOF'
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
SILVER_EOF

echo "Writing silver_forecast/market_history/data_quality_gate.py"
mkdir -p 'silver_forecast/market_history'
cat > 'silver_forecast/market_history/data_quality_gate.py' <<'SILVER_EOF'
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
SILVER_EOF

echo "Writing silver_forecast/market_history/update_market_history.py"
mkdir -p 'silver_forecast/market_history'
cat > 'silver_forecast/market_history/update_market_history.py' <<'SILVER_EOF'
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
    body = [incoming.get(day, existing[day]) for day in merged_dates]
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
SILVER_EOF

echo "Writing silver_forecast/platform_configuration/rebuild_runtime_payload.py"
mkdir -p 'silver_forecast/platform_configuration'
cat > 'silver_forecast/platform_configuration/rebuild_runtime_payload.py' <<'SILVER_EOF'
from __future__ import annotations

"""Rebuild the base64-part runtime bundle after runtime artifacts change.

The runtime bundle (models + packaged history + verified reports) is stored
as tar+xz+base64 parts with a strict SHA256 manifest (see
``restore_runtime_artifacts.py``). After the daily market data update changes
a target file, the parts and manifest must be rebuilt so the chain stays
verifiable.

The historical ``runtime_part_repairs.json`` fragment mechanism is retired at
the same time: stale fragments would otherwise be re-merged over the rebuilt
``runtime_v2.part031.b64`` on the next fresh checkout. The repairs document is
replaced with a no-op repair anchored to a stable sentinel file, and every
leftover fragment (and obsolete v1 payload part) is deleted.
"""

import base64
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import tarfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = ROOT / "runtime_artifacts"
MANIFEST_PATH = BUNDLE_DIR / "runtime_payload_manifest.json"
REPAIRS_PATH = BUNDLE_DIR / "runtime_part_repairs.json"
SUPPORTED_FORMAT = "tar+xz+base64-parts-v2"
LEGACY_PART_PREFIX = "forecast_runtime_payload.part"
REPAIRS_FORMAT = "runtime-part-repair-v1"

SENTINEL_NAME = "runtime_repairs_complete.json"
SENTINEL_TEXT = (
    '{"status": "complete", "note": "All runtime part repairs are finished; '
    'rebuild_runtime_payload.py now maintains the bundle."}\n'
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    temp = path.with_name(f".{path.name}.rebuild-{os.getpid()}.tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("format") != SUPPORTED_FORMAT:
        raise RuntimeError(f"Unsupported runtime artifact format: {manifest.get('format')!r}")
    if int(manifest["part_size"]) <= 0:
        raise RuntimeError("Runtime artifact part_size must be positive")
    targets = list(manifest["targets"])
    if not targets:
        raise RuntimeError("Runtime artifact manifest has no targets")
    return manifest


def _pack_targets(targets: list[str]) -> tuple[bytes, dict[str, dict[str, Any]]]:
    """Pack target files into a deterministic TAR and compute integrity."""
    buffer = io.BytesIO()
    integrity: dict[str, dict[str, Any]] = {}
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for relative in sorted(targets):
            source = ROOT / relative
            data = source.read_bytes()
            integrity[relative] = {"size": len(data), "sha256": _sha256(data)}
            info = tarfile.TarInfo(relative)
            info.size = len(data)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue(), integrity


def _retire_repairs_document() -> None:
    """Replace the fragment-repair document with a stable no-op repair."""
    sentinel = BUNDLE_DIR / SENTINEL_NAME
    _atomic_write_bytes(sentinel, SENTINEL_TEXT.encode("utf-8"))
    document = {
        "format": REPAIRS_FORMAT,
        "repairs": [
            {
                "output": SENTINEL_NAME,
                "size": len(SENTINEL_TEXT.encode("utf-8")),
                "sha256": _sha256(SENTINEL_TEXT.encode("utf-8")),
                "fragments": [],
            }
        ],
    }
    _atomic_write_bytes(
        REPAIRS_PATH,
        (json.dumps(document, indent=2) + "\n").encode("utf-8"),
    )


def rebuild_runtime_payload() -> None:
    manifest = _load_manifest()
    part_prefix = str(manifest["part_prefix"])
    part_size = int(manifest["part_size"])
    targets = list(manifest["targets"])

    raw_tar, integrity = _pack_targets(targets)
    archive_xz = lzma.compress(raw_tar)
    encoded = base64.b64encode(archive_xz)

    part_count = (len(encoded) + part_size - 1) // part_size
    parts = [encoded[index * part_size:(index + 1) * part_size] for index in range(part_count)]

    for pattern in (f"{part_prefix}*.b64", f"{LEGACY_PART_PREFIX}*.b64"):
        for path in BUNDLE_DIR.glob(pattern):
            path.unlink()
    for index, part in enumerate(parts):
        (BUNDLE_DIR / f"{part_prefix}{index:03d}.b64").write_bytes(part)

    manifest["part_count"] = len(parts)
    manifest["last_part_size"] = len(parts[-1])
    manifest["encoded_size"] = len(encoded)
    manifest["archive_size"] = len(archive_xz)
    manifest["archive_sha256"] = _sha256(archive_xz)
    manifest["decoded_tar_sha256"] = _sha256(raw_tar)
    manifest["target_integrity"] = integrity
    _atomic_write_bytes(MANIFEST_PATH, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))

    _retire_repairs_document()

    print(
        f"Rebuilt runtime bundle: {len(parts)} part(s), archive {len(archive_xz)} bytes "
        f"(sha256 {manifest['archive_sha256'][:12]}...)"
    )


if __name__ == "__main__":
    rebuild_runtime_payload()
SILVER_EOF

echo "Writing tests/market_history/test_data_quality_gate.py"
mkdir -p 'tests/market_history'
cat > 'tests/market_history/test_data_quality_gate.py' <<'SILVER_EOF'
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
SILVER_EOF

echo "Writing tests/market_history/test_update_market_history.py"
mkdir -p 'tests/market_history'
cat > 'tests/market_history/test_update_market_history.py' <<'SILVER_EOF'
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
SILVER_EOF

echo "Writing docker-compose.coolify.yml"
mkdir -p '.'
cat > 'docker-compose.coolify.yml' <<'SILVER_EOF'
# =============================================================================
#  Coolify variant of the stack.
#
#  Coolify runs its own reverse proxy (Traefik) on host ports 80/443, so this
#  file exposes NO host ports. Coolify's proxy routes the configured domain to
#  `app:8000` (configure the domain in Coolify's UI / docker_compose_domains).
#
#  The app serves both the FastAPI (port 8000: /health, /api/*, /docs) and the
#  static prediction portal (mounted at `/`).
#
#  REQUIRED before first start: POSTGRES_PASSWORD (generate one with
#  `openssl rand -base64 24`). There is intentionally no default password.
# =============================================================================

name: silver-forecast

services:
  app:
    build: .
    restart: unless-stopped
    environment:
      PORT: "8000"
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/silver}
      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS:-}
    depends_on:
      postgres:
        condition: service_healthy
    networks: [app]

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set (generate with: openssl rand -base64 24)}
      POSTGRES_DB: ${POSTGRES_DB:-silver}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-silver}"]
      interval: 5s
      timeout: 5s
      retries: 12
    networks: [app]

volumes:
  pgdata:

networks:
  app:
    driver: bridge
SILVER_EOF

echo "Writing DEPLOYMENT.md"
cat > 'DEPLOYMENT.md' <<'SILVER_EOF'
# Deployment

## Local

%%%FENCE%%%bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn silver_forecast.http_api.application:app --reload --port 8000
%%%FENCE%%%

Open `http://127.0.0.1:8000`. API docs: `/docs`.

## Railway

1. Push this repository to GitHub.
2. Create a Railway project from the GitHub repository.
3. Add Railway PostgreSQL for durable forecast history.
4. Railway exposes `DATABASE_URL`; no code change is required.
5. Deploy. Railway builds the root `Dockerfile` and checks `/health`.

If PostgreSQL is not attached, the application still runs with SQLite, but Railway filesystem persistence should not be treated as durable production storage.

## Coolify

Deploy the stack from `docker-compose.coolify.yml`.

### 1. Create the resource

1. In Coolify: **New Resource → Docker Compose** and paste `docker-compose.coolify.yml` (or point it at this repository).
2. Do **not** start it yet — set the required environment first.

### 2. Environment

| Variable | Required | Default | Notes |
|---|---|---|---|
| `POSTGRES_PASSWORD` | **Yes** | — | `openssl rand -base64 24`. There is no default on purpose. |
| `DATABASE_URL` | No | `postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/silver` | Override only if you use an external database. |
| `POSTGRES_USER` | No | `postgres` | |
| `POSTGRES_DB` | No | `silver` | |
| `CORS_ALLOWED_ORIGINS` | Recommended | — | Comma-separated origins of your portal domain. |

Set `POSTGRES_PASSWORD` in Coolify's environment editor **before the first start** and keep it stable: it is stored inside the `pgdata` volume, so changing it later requires a manual `ALTER USER` inside the container or a volume reset.

### 3. Domain and HTTPS

1. Open the **app** service → **Domains** and add your domain (the stack exposes no host ports; Coolify's Traefik proxy routes the domain to `app:8000`).
2. Issue a **Let's Encrypt** certificate and enable **Force HTTPS**.
3. Verify `https://<your-domain>/health` returns `{"status": "ok"}`.

The `postgres` service must stay unreachable from the internet: do not attach a domain to it.

### 4. First boot

On first boot the app seeds the PostgreSQL market history from the packaged CSV (restored from the verified runtime bundle) and is immediately usable. `DATABASE_URL` is provided by the compose default; nothing else is required.

### 5. Receiving the daily data push

The `Daily Market Data` GitHub Action can POST each day's new observations to the live API (`POST /api/market/observations`, idempotent upsert). Add these repository secrets (**Settings → Secrets and variables → Actions**) once Coolify is live:

| Secret | Required | Notes |
|---|---|---|
| `PRODUCTION_API_URL` | No | e.g. `https://silver.example.com`. Empty = skip the push step. |
| `MARKET_OBSERVATIONS_TOKEN` | No | Optional bearer token if you front the endpoint with auth. |

### 6. Backups

The `pgdata` volume is the only durable state. Schedule a PostgreSQL backup from the host (Phase 2 adds an automated daily dump):

%%%FENCE%%%bash
docker exec <postgres-container> pg_dump -U postgres silver | gzip > silver-$(date +%F).sql.gz
%%%FENCE%%%
SILVER_EOF
restore_fence 'DEPLOYMENT.md'

echo "Writing README.md"
cat > 'README.md' <<'SILVER_EOF'
# Silver Forecast Platform

Complete end-to-end silver forecasting product in one repository: market history, causal feature engineering, persisted models, forecast API, forecast-history persistence, verified backtesting, historical reports, and professional frontend.

## What runs

`Browser → Prediction Portal → FastAPI → Forecasting → Feature Engineering → Model Registry → Persisted Model → Forecast History`

## Forecast horizons

1D · 2D · 3D · 7D · 14D · 30D (trading sessions).

## Architecture

The repository follows Screaming Architecture. There are no top-level `components`, `assets`, `services`, `utils`, or `helpers` buckets. See `ARCHITECTURE.md`.

## Local run

%%%FENCE%%%bash
pip install -r requirements.txt
uvicorn silver_forecast.http_api.application:app --host 0.0.0.0 --port 8000
%%%FENCE%%%

Then open `http://localhost:8000`.

## Main API

- `GET /health`
- `GET /api/forecast/dashboard?mode=challenger`
- `GET /api/forecast/latest`
- `GET /api/forecast/{1D|2D|3D|7D|14D|30D}`
- `GET /api/market/latest`
- `GET /api/market/history`
- `POST /api/market/observations`
- `GET /api/models`
- `GET /api/backtesting`
- `GET /api/forecast-history`
- `GET /api/reports`
- `GET /api/data-quality`

## Automated daily data pipeline

`.github/workflows/daily-market-data.yml` runs after each trading session (23:30 UTC, Tuesday–Saturday):

1. Restores the verified runtime bundle (models + packaged market history).
2. Fetches daily silver OHLCV from keyless sources (Yahoo Finance `SI=F`, Stooq `xagusd` fallback) and converts USD/troy-oz → USD/kg with the single explicit factor `1000 / 31.1034768`.
3. Merges the rows into `historical_market_data/silver_ohlcv_usd_per_kg.csv` text-based, preserving untouched rows byte-for-byte.
4. Runs the **data quality gate**: parseable and strictly ascending unique dates, valid OHLC rows, non-negative volume, ≤5 missing business days in the trailing 30 calendar days, staleness ≤5 days, and a ±25% close-to-close jump guard limited to newly fetched rows. On failure nothing is committed and a `data-quality-alert` issue is opened.
5. Rebuilds the checksum-verified runtime bundle (tar+xz+base64 parts + manifest) and commits the update.
6. Optionally POSTs the new observations to `PRODUCTION_API_URL/api/market/observations` (set the repository secrets `PRODUCTION_API_URL` and optionally `MARKET_OBSERVATIONS_TOKEN` — see `DEPLOYMENT.md`).

`.github/workflows/branch-cleanup.yml` deletes the retired runtime-repair branches daily (02:00 UTC).

## Persistence

SQLite is the zero-configuration local default. Set `DATABASE_URL` to PostgreSQL in production (Railway or Coolify — see `DEPLOYMENT.md`).

## Models

Runtime includes the six active CatBoost challenger artifacts. The 54-candidate Stage-9 research archive is intentionally excluded from the deployable Git tree because it is not loaded at runtime; `forecast_model_archive/README.md` documents that boundary.

## Scientific integrity

The UI never presents `100 - MAPE` as classification accuracy. Stage-10 evidence keeps Last Close as the primary price benchmark; ML remains a challenger until it proves superior on future evidence.
SILVER_EOF
restore_fence 'README.md'

echo "Committing and pushing..."
git add .github/workflows/daily-market-data.yml \
        .github/workflows/branch-cleanup.yml \
        silver_forecast/market_history/silver_price_sources.py \
        silver_forecast/market_history/data_quality_gate.py \
        silver_forecast/market_history/update_market_history.py \
        silver_forecast/platform_configuration/rebuild_runtime_payload.py \
        tests/market_history/test_data_quality_gate.py \
        tests/market_history/test_update_market_history.py \
        docker-compose.coolify.yml \
        DEPLOYMENT.md \
        README.md
git commit -m "feat: Phase 1 — daily market data pipeline, quality gate, branch cleanup, Coolify hardening

- daily-market-data.yml: fetch Yahoo SI=F / Stooq xagusd, convert USD/ozt to USD/kg,
  merge into packaged CSV (byte-preserving), run data quality gate, rebuild the
  runtime payload bundle, commit, optionally POST observations to the production API
- data_quality_gate.py: date sequence, OHLC, volume, missing sessions, staleness,
  close-jump guard (limited to newly fetched rows); failure opens a data-quality-alert issue
- update_market_history.py: text-based merge with precision detection; CSV is written
  only after the gate passes
- rebuild_runtime_payload.py: rebuilds tar+xz+base64 parts + manifest, retires the
  runtime_part_repairs.json fragment mechanism
- branch-cleanup.yml: deletes the 5 retired runtime-repair branches daily
- docker-compose.coolify.yml: POSTGRES_PASSWORD is now required (no default password)
- DEPLOYMENT.md: full Coolify guide (env, domain + Let's Encrypt HTTPS, backups)
- README.md: documents the automated daily data pipeline"
git push origin main

echo ""
echo "Done. Next steps:"
echo "  1. Watch the Quality Gate workflow on GitHub Actions (it runs the new tests)."
echo "  2. Trigger 'Daily Market Data' manually once, or wait for 23:30 UTC (Tue-Sat)."
echo "  3. Trigger 'Branch Cleanup' manually once, or wait for 02:00 UTC."
echo "  4. Follow DEPLOYMENT.md for the Coolify domain + HTTPS + secrets."
