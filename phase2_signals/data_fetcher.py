"""
phase2_signals/data_fetcher.py
================================
Phase 2 — Script 01: Data Fetcher
India Sector Rotation Strategy

Fetches daily OHLCV data for all 49 indices in the universe using NSEPython.
Outputs clean, validated Parquet + CSV files to data/ directory.

Features:
  - Fetches all 47 rotation indices + 2 reference indices
  - Configurable lookback (default: 520 trading days ≈ 2 years for signals
    + buffer; set FULL_HISTORY=True for max history ≈ 2005 onwards)
  - Handles NSE rate-limiting with exponential backoff
  - Data quality checks: gaps, outliers, stale data
  - Incremental refresh: only fetches missing dates on subsequent runs
  - Saves per-index CSV + combined Parquet master file

Usage:
  python phase2_signals/data_fetcher.py                 # Default: 520 days
  python phase2_signals/data_fetcher.py --full          # Full history
  python phase2_signals/data_fetcher.py --index "NIFTY BANK"  # Single index
  python phase2_signals/data_fetcher.py --refresh       # Force re-fetch all

Author: India Sector Rotation Strategy
Last updated: February 2026
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
from tqdm import tqdm

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.index_universe import ALL_SYMBOLS, ROTATION_SYMBOLS, REFERENCE_SYMBOLS

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"data_fetcher_{datetime.now():%Y%m%d}.log"),
    ],
)
logger = logging.getLogger(__name__)

# ── Data directory ────────────────────────────────────────────────────────────
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
INDEX_DATA_DIR = DATA_DIR / "indices"
INDEX_DATA_DIR.mkdir(exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_LOOKBACK_DAYS = 520          # ~2 years trading days (252 × 2 + 16 buffer)
FULL_HISTORY_START   = "01-01-2005"  # NSEPython date format: DD-MM-YYYY
NSE_RATE_LIMIT_SLEEP = 1.5           # seconds between API calls (be polite)
MAX_RETRIES          = 3             # retries per failed fetch
BACKOFF_BASE         = 2             # exponential backoff multiplier

# Outlier thresholds
MAX_DAILY_RETURN = 0.30              # flag if daily return > 30%
MIN_DAILY_RETURN = -0.30             # flag if daily return < -30%
MAX_ZERO_VOLUME_STREAK = 5           # flag if volume = 0 for > 5 consecutive days


# ══════════════════════════════════════════════════════════════════════════════
# NSEPython wrapper
# ══════════════════════════════════════════════════════════════════════════════

def _import_nsepython():
    """Import NSEPython with a helpful error message if not installed."""
    try:
        import nsepython  # noqa: F401
        from nsepython import index_history
        return index_history
    except ImportError:
        logger.error(
            "NSEPython not found. Install with: pip install nsepython\n"
            "If you are in a restricted environment, see README for alternatives."
        )
        raise


def fetch_index_ohlcv(
    index_name: str,
    start_date: str,
    end_date: str,
    retries: int = MAX_RETRIES,
) -> pd.DataFrame | None:
    """
    Fetch OHLCV data for a single NSE index via NSEPython.

    Parameters
    ----------
    index_name : str
        NSE index name exactly as in config/index_universe.py
        e.g. "NIFTY BANK", "NIFTY IT"
    start_date : str
        Format: "DD-MM-YYYY"
    end_date : str
        Format: "DD-MM-YYYY"
    retries : int
        Number of retry attempts on failure

    Returns
    -------
    pd.DataFrame with columns [Date, Open, High, Low, Close, Volume]
    or None if all retries exhausted.
    """
    index_history = _import_nsepython()

    for attempt in range(1, retries + 1):
        try:
            logger.debug(f"Fetching {index_name} | {start_date} → {end_date} (attempt {attempt})")
            raw = index_history(index_name, start_date, end_date)

            if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
                logger.warning(f"Empty response for {index_name} on attempt {attempt}")
                if attempt < retries:
                    time.sleep(NSE_RATE_LIMIT_SLEEP * attempt)
                    continue
                return None

            df = _normalise_ohlcv(raw, index_name)
            return df

        except Exception as e:
            logger.warning(f"Error fetching {index_name} (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                sleep_time = NSE_RATE_LIMIT_SLEEP * (BACKOFF_BASE ** attempt)
                logger.info(f"Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"Failed to fetch {index_name} after {retries} attempts.")
                return None

    return None


def _normalise_ohlcv(raw: pd.DataFrame, index_name: str) -> pd.DataFrame:
    """
    Standardise NSEPython output into a clean OHLCV DataFrame.

    NSEPython column names vary slightly across versions; this function
    handles the known variants and produces a consistent schema.
    """
    df = raw.copy()

    # ── Column name normalisation ─────────────────────────────────────────────
    col_map = {}
    for col in df.columns:
        col_lower = col.strip().lower().replace(" ", "_")
        if col_lower in ("index_date", "date", "HistoricalDate".lower()):
            col_map[col] = "Date"
        elif col_lower in ("open", "open_index_value"):
            col_map[col] = "Open"
        elif col_lower in ("high", "high_index_value"):
            col_map[col] = "High"
        elif col_lower in ("low", "low_index_value"):
            col_map[col] = "Low"
        elif col_lower in ("closing_index_value", "close", "closing"):
            col_map[col] = "Close"
        elif col_lower in ("volume", "turnover_(rs._cr.)", "turnover_rs_cr"):
            col_map[col] = "Volume"
        elif col_lower in ("pe_ratio", "pb_ratio", "div_yield"):
            # Keep fundamental columns if present — useful for Block 4
            col_map[col] = col_lower.upper()

    df.rename(columns=col_map, inplace=True)

    # Ensure required columns exist
    required = ["Date", "Open", "High", "Low", "Close"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in NSEPython output for {index_name}. "
                             f"Available: {list(df.columns)}")

    # Add Volume column with NaN if not available (some indices don't report volume)
    if "Volume" not in df.columns:
        df["Volume"] = np.nan

    # ── Type conversion ───────────────────────────────────────────────────────
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── Sort and deduplicate ──────────────────────────────────────────────────
    df.sort_values("Date", inplace=True)
    df.drop_duplicates(subset="Date", keep="last", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ── Add index identifier column ───────────────────────────────────────────
    df.insert(0, "Index", index_name)

    # ── Select final columns ──────────────────────────────────────────────────
    keep_cols = ["Index", "Date", "Open", "High", "Low", "Close", "Volume"]
    # Preserve fundamental columns if present
    extra_cols = [c for c in df.columns if c in ("PE_RATIO", "PB_RATIO", "DIV_YIELD")]
    df = df[keep_cols + extra_cols]

    return df


# ══════════════════════════════════════════════════════════════════════════════
# Data Quality Checks
# ══════════════════════════════════════════════════════════════════════════════

def run_quality_checks(df: pd.DataFrame, index_name: str) -> dict:
    """
    Run data quality checks on a fetched OHLCV DataFrame.

    Returns a dict with check results and a boolean 'passed' flag.
    Warnings are logged; only critical failures set passed=False.
    """
    issues = []
    warnings = []

    if df is None or df.empty:
        return {"passed": False, "issues": ["Empty DataFrame"], "warnings": []}

    close = df["Close"].dropna()

    # 1. Minimum row count
    if len(df) < 20:
        issues.append(f"Only {len(df)} rows — too few for signal computation (min 20)")

    # 2. Missing Close values
    missing_close = df["Close"].isna().sum()
    if missing_close > 0:
        pct = missing_close / len(df) * 100
        if pct > 10:
            issues.append(f"{missing_close} missing Close values ({pct:.1f}%) — exceeds 10% threshold")
        else:
            warnings.append(f"{missing_close} missing Close values ({pct:.1f}%) — will forward-fill")

    # 3. Extreme daily returns (potential data errors)
    if len(close) > 1:
        daily_returns = close.pct_change().dropna()
        outliers = daily_returns[(daily_returns > MAX_DAILY_RETURN) | (daily_returns < MIN_DAILY_RETURN)]
        if not outliers.empty:
            warnings.append(
                f"{len(outliers)} extreme daily return(s) detected (|return| > 30%): "
                f"{outliers.index.tolist()[:5]}"
            )

    # 4. Zero volume streak
    if "Volume" in df.columns and df["Volume"].notna().any():
        volume = df["Volume"].fillna(0)
        zero_streak = _max_consecutive_zeros(volume)
        if zero_streak > MAX_ZERO_VOLUME_STREAK:
            warnings.append(f"Volume = 0 for {zero_streak} consecutive days — possible data gap")

    # 5. High < Low check
    invalid_hl = df[df["High"] < df["Low"]]
    if not invalid_hl.empty:
        issues.append(f"{len(invalid_hl)} rows where High < Low — data corruption")

    # 6. Stale data (last date more than 5 trading days ago)
    if not df.empty:
        last_date = df["Date"].max()
        days_since = (datetime.now() - last_date).days
        if days_since > 7:
            warnings.append(f"Last data point is {days_since} days ago ({last_date.date()}) — may be stale")

    passed = len(issues) == 0
    for w in warnings:
        logger.warning(f"  ⚠  {index_name}: {w}")
    for i in issues:
        logger.error(f"  ✗  {index_name}: {i}")
    if passed and not warnings:
        logger.debug(f"  ✓  {index_name}: All quality checks passed")

    return {"passed": passed, "issues": issues, "warnings": warnings}


def _max_consecutive_zeros(series: pd.Series) -> int:
    """Return the maximum consecutive run of zeros in a Series."""
    max_streak = streak = 0
    for val in series:
        if val == 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


# ══════════════════════════════════════════════════════════════════════════════
# Incremental refresh logic
# ══════════════════════════════════════════════════════════════════════════════

def get_existing_data(index_name: str) -> pd.DataFrame | None:
    """Load existing CSV for an index if it exists."""
    safe_name = index_name.replace(" ", "_").replace("&", "AND").replace("/", "_")
    csv_path = INDEX_DATA_DIR / f"{safe_name}.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path, parse_dates=["Date"])
            return df
        except Exception as e:
            logger.warning(f"Could not read existing data for {index_name}: {e}")
    return None


def get_incremental_start_date(existing_df: pd.DataFrame | None) -> str:
    """
    If existing data is present, return the day after the last available date.
    Otherwise return the default lookback start date.
    """
    if existing_df is not None and not existing_df.empty:
        last_date = existing_df["Date"].max()
        next_date = last_date + timedelta(days=1)
        return next_date.strftime("%d-%m-%Y")
    return None


def merge_with_existing(new_df: pd.DataFrame, existing_df: pd.DataFrame | None) -> pd.DataFrame:
    """Merge newly fetched data with existing data, deduplicating on Date."""
    if existing_df is None or existing_df.empty:
        return new_df
    combined = pd.concat([existing_df, new_df], ignore_index=True)
    combined["Date"] = pd.to_datetime(combined["Date"])
    combined.sort_values("Date", inplace=True)
    combined.drop_duplicates(subset="Date", keep="last", inplace=True)
    combined.reset_index(drop=True, inplace=True)
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# Save functions
# ══════════════════════════════════════════════════════════════════════════════

def save_index_csv(df: pd.DataFrame, index_name: str) -> Path:
    """Save per-index CSV to data/indices/."""
    safe_name = index_name.replace(" ", "_").replace("&", "AND").replace("/", "_")
    csv_path = INDEX_DATA_DIR / f"{safe_name}.csv"
    df.to_csv(csv_path, index=False)
    logger.debug(f"Saved: {csv_path}")
    return csv_path


def save_master_parquet(all_dfs: dict[str, pd.DataFrame]) -> Path:
    """
    Combine all index DataFrames into a single master Parquet file.
    Long format: Index | Date | Open | High | Low | Close | Volume
    """
    if not all_dfs:
        logger.warning("No data to save to master Parquet.")
        return None

    master_df = pd.concat(all_dfs.values(), ignore_index=True)
    master_df["Date"] = pd.to_datetime(master_df["Date"])
    master_df.sort_values(["Index", "Date"], inplace=True)
    master_df.reset_index(drop=True, inplace=True)

    parquet_path = DATA_DIR / "master_ohlcv.parquet"
    master_df.to_parquet(parquet_path, index=False, engine="pyarrow")
    logger.info(f"Master Parquet saved: {parquet_path} ({len(master_df):,} rows, {master_df['Index'].nunique()} indices)")
    return parquet_path


def save_master_csv(all_dfs: dict[str, pd.DataFrame]) -> Path:
    """Save combined master CSV (fallback if Parquet unavailable)."""
    if not all_dfs:
        return None
    master_df = pd.concat(all_dfs.values(), ignore_index=True)
    master_df["Date"] = pd.to_datetime(master_df["Date"])
    master_df.sort_values(["Index", "Date"], inplace=True)
    master_df.reset_index(drop=True, inplace=True)

    csv_path = DATA_DIR / "master_ohlcv.csv"
    master_df.to_csv(csv_path, index=False)
    logger.info(f"Master CSV saved: {csv_path} ({len(master_df):,} rows)")
    return csv_path


# ══════════════════════════════════════════════════════════════════════════════
# Main fetch orchestrator
# ══════════════════════════════════════════════════════════════════════════════

def compute_date_range(full_history: bool, lookback_days: int) -> tuple[str, str]:
    """Compute start and end date strings in DD-MM-YYYY format."""
    end_dt = datetime.now()
    if full_history:
        start_str = FULL_HISTORY_START
    else:
        start_dt = end_dt - timedelta(days=lookback_days * 1.5)  # 1.5× buffer for weekends/holidays
        start_str = start_dt.strftime("%d-%m-%Y")
    end_str = end_dt.strftime("%d-%m-%Y")
    return start_str, end_str


def fetch_all(
    symbols: list[str],
    start_date: str,
    end_date: str,
    incremental: bool = True,
    force_refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for all symbols in the list.

    Parameters
    ----------
    symbols      : list of index name strings
    start_date   : default start date (DD-MM-YYYY)
    end_date     : end date (DD-MM-YYYY)
    incremental  : if True, only fetch missing dates
    force_refresh: if True, re-fetch all data from scratch

    Returns
    -------
    Dict mapping index_name → clean OHLCV DataFrame
    """
    results = {}
    failed = []
    skipped = []

    logger.info(f"Starting fetch for {len(symbols)} indices")
    logger.info(f"Date range: {start_date} → {end_date}")
    logger.info(f"Mode: {'FULL REFRESH' if force_refresh else 'INCREMENTAL' if incremental else 'STANDARD'}")

    for symbol in tqdm(symbols, desc="Fetching indices", unit="index"):
        time.sleep(NSE_RATE_LIMIT_SLEEP)  # Rate limit: polite to NSE

        # Load existing data
        existing_df = None if force_refresh else get_existing_data(symbol)

        # Determine fetch start date
        if incremental and existing_df is not None and not force_refresh:
            fetch_start = get_incremental_start_date(existing_df)
            if fetch_start is None:
                logger.info(f"  ↷ {symbol}: Up to date — skipping")
                results[symbol] = existing_df
                skipped.append(symbol)
                continue

            # Check if incremental start is after today
            fetch_start_dt = datetime.strptime(fetch_start, "%d-%m-%Y")
            end_dt = datetime.strptime(end_date, "%d-%m-%Y")
            if fetch_start_dt > end_dt:
                logger.info(f"  ↷ {symbol}: Already current (last: {fetch_start}) — skipping")
                results[symbol] = existing_df
                skipped.append(symbol)
                continue

            logger.info(f"  ↻ {symbol}: Incremental fetch from {fetch_start}")
            effective_start = fetch_start
        else:
            effective_start = start_date

        # Fetch from NSE
        df = fetch_index_ohlcv(symbol, effective_start, end_date)

        if df is None:
            logger.error(f"  ✗ {symbol}: Fetch failed — skipped")
            failed.append(symbol)
            # Keep existing data if available
            if existing_df is not None:
                results[symbol] = existing_df
            continue

        # Merge with existing
        if incremental and existing_df is not None and not force_refresh:
            df = merge_with_existing(df, existing_df)

        # Quality checks
        qc = run_quality_checks(df, symbol)
        if not qc["passed"]:
            logger.error(f"  ✗ {symbol}: Failed quality checks — {qc['issues']}")
            failed.append(symbol)
            # Still save what we have (degraded data is better than none)

        # Forward-fill missing Close values (minor gaps only)
        df["Close"] = df["Close"].ffill()
        df["Open"]  = df["Open"].ffill()
        df["High"]  = df["High"].ffill()
        df["Low"]   = df["Low"].ffill()

        # Save per-index CSV
        save_index_csv(df, symbol)
        results[symbol] = df

        rows = len(df)
        date_range = f"{df['Date'].min().date()} → {df['Date'].max().date()}"
        logger.info(f"  ✓ {symbol}: {rows:,} rows | {date_range}")

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("─" * 60)
    logger.info(f"Fetch complete:")
    logger.info(f"  ✓ Successful : {len(results) - len(failed)} indices")
    logger.info(f"  ↷ Skipped    : {len(skipped)} indices (already current)")
    logger.info(f"  ✗ Failed     : {len(failed)} indices")
    if failed:
        logger.warning(f"  Failed indices: {failed}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Diagnostic helpers
# ══════════════════════════════════════════════════════════════════════════════

def print_fetch_summary(all_dfs: dict[str, pd.DataFrame]) -> None:
    """Print a formatted summary table of all fetched indices."""
    if not all_dfs:
        print("No data fetched.")
        return

    print("\n" + "═" * 75)
    print(f"{'INDEX':<45} {'ROWS':>7} {'FROM':>12} {'TO':>12}")
    print("─" * 75)

    total_rows = 0
    for index_name, df in sorted(all_dfs.items()):
        rows = len(df)
        total_rows += rows
        if not df.empty and "Date" in df.columns:
            date_from = df["Date"].min().strftime("%d-%m-%Y")
            date_to   = df["Date"].max().strftime("%d-%m-%Y")
        else:
            date_from = date_to = "N/A"
        print(f"{index_name:<45} {rows:>7,} {date_from:>12} {date_to:>12}")

    print("─" * 75)
    print(f"{'TOTAL':>45} {total_rows:>7,}")
    print("═" * 75 + "\n")


def load_master_parquet() -> pd.DataFrame:
    """Load the master OHLCV Parquet file."""
    parquet_path = DATA_DIR / "master_ohlcv.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Master Parquet not found at {parquet_path}. "
            "Run data_fetcher.py first."
        )
    df = pd.read_parquet(parquet_path)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def get_close_prices_wide(min_date: str = None) -> pd.DataFrame:
    """
    Return a wide-format DataFrame of Close prices.
    Columns = index names, Rows = dates.
    Convenient for signal computation scripts.

    Parameters
    ----------
    min_date : str, optional
        Filter to dates >= min_date (format: YYYY-MM-DD)
    """
    master = load_master_parquet()
    wide = master.pivot_table(index="Date", columns="Index", values="Close")
    wide.sort_index(inplace=True)
    if min_date:
        wide = wide[wide.index >= pd.Timestamp(min_date)]
    return wide


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="India Sector Rotation — Data Fetcher (Phase 2, Script 01)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data_fetcher.py                        # Default 520-day fetch, incremental
  python data_fetcher.py --full                 # Full history from Jan 2005
  python data_fetcher.py --refresh              # Force re-fetch all data
  python data_fetcher.py --index "NIFTY BANK"   # Single index
  python data_fetcher.py --rotation-only        # Skip thematic indices
        """,
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=f"Fetch full history from {FULL_HISTORY_START} (slow — ~5-10 min)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-fetch all data (ignore existing files)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"Lookback in trading days (default: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument(
        "--index",
        type=str,
        default=None,
        help='Fetch a single index only (e.g. "NIFTY BANK")',
    )
    parser.add_argument(
        "--rotation-only",
        action="store_true",
        help="Fetch only rotation indices (skip reference indices)",
    )
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="Skip saving master Parquet (save CSV only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be fetched without making API calls",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info("═" * 60)
    logger.info("India Sector Rotation — Data Fetcher v1.0")
    logger.info(f"Run time: {datetime.now():%Y-%m-%d %H:%M:%S IST}")
    logger.info("═" * 60)

    # Determine symbol list
    if args.index:
        symbols = [args.index]
        logger.info(f"Single-index mode: {args.index}")
    elif args.rotation_only:
        symbols = ROTATION_SYMBOLS
        logger.info(f"Rotation-only mode: {len(symbols)} indices")
    else:
        symbols = ALL_SYMBOLS
        logger.info(f"Full universe mode: {len(symbols)} indices")

    # Compute date range
    start_date, end_date = compute_date_range(args.full, args.lookback)

    if args.dry_run:
        logger.info("[DRY RUN] Would fetch the following:")
        for s in symbols:
            existing = get_existing_data(s)
            status = f"EXISTS ({len(existing)} rows)" if existing is not None else "NEW"
            print(f"  {s:<50} {status}")
        logger.info(f"Date range: {start_date} → {end_date}")
        return

    # Run fetch
    all_dfs = fetch_all(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        incremental=not args.refresh,
        force_refresh=args.refresh,
    )

    # Print summary
    print_fetch_summary(all_dfs)

    # Save master files
    if all_dfs:
        if not args.no_parquet:
            try:
                save_master_parquet(all_dfs)
            except ImportError:
                logger.warning("pyarrow not installed — falling back to CSV master")
                save_master_csv(all_dfs)
        else:
            save_master_csv(all_dfs)

    logger.info("Data fetch complete. Ready for signal computation.")
    logger.info("Next: python phase2_signals/momentum_score.py")


if __name__ == "__main__":
    main()
