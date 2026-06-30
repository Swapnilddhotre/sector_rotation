"""
india-sector-rotation | Phase 2 | Script 01
============================================
data_fetcher.py

PURPOSE
-------
Fetches, validates, caches, and exports historical OHLCV price data for the
full 49-index universe (47 rotation + 2 reference) from NSE via nsepython.
Also fetches P/E, P/B, and Dividend Yield for the Valuation Score (Block 4).

OUTPUTS  (all written to  data/raw/)
--------------------------------------
prices_daily.parquet      — Daily OHLCV, multi-index columns: (date, index_name)
prices_daily.csv          — Same, human-readable CSV copy
pe_pb_div_monthly.parquet — Monthly P/E, P/B, Div Yield per index
pe_pb_div_monthly.csv     — Same, CSV copy
fetch_log.json            — Audit log: success / failed / skipped per index

USAGE
------
  python data_fetcher.py                              # full fetch, default start date
  python data_fetcher.py --start 2015-01-01           # custom start date
  python data_fetcher.py --end 2024-12-31             # custom end date
  python data_fetcher.py --refresh                    # force re-fetch even if cached
  python data_fetcher.py --indices "NIFTY BANK,NIFTY IT"  # fetch a subset only
  python data_fetcher.py --no-fundamentals            # skip P/E/P/B/DY fetch

DEPENDENCIES
------------
  pip install nsepython pandas pyarrow tqdm colorama
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# ── Optional coloured console output ──────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    GREEN  = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED    = Fore.RED
    CYAN   = Fore.CYAN
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = YELLOW = RED = CYAN = RESET = ""

# ── NSEPython ─────────────────────────────────────────────────────────────────
try:
    from nsepython import index_history, index_pe_pb_div
except ImportError:
    print(f"{RED}ERROR: nsepython not found.  Run:  pip install nsepython{RESET}")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_START_DATE  = "01-01-2005"   # NSEPython uses DD-MM-YYYY format
OUTPUT_DIR          = Path("data/raw")
LOG_DIR             = Path("logs")
RETRY_ATTEMPTS      = 3
RETRY_DELAY_SECONDS = 5              # wait between retries
RATE_LIMIT_SECONDS  = 1.5            # wait between successive NSE calls


# ═══════════════════════════════════════════════════════════════════════════════
#  INDEX UNIVERSE  (47 rotation + 2 reference = 49 total)
# ═══════════════════════════════════════════════════════════════════════════════

# Reference indices — used as benchmark in momentum calculations
REFERENCE_INDICES = [
    "NIFTY 50",
    "NIFTY 500",
]

# --- 14 Core Sectoral Indices -------------------------------------------------
CORE_SECTORAL = [
    "NIFTY BANK",
    "NIFTY AUTO",
    "NIFTY IT",
    "NIFTY FMCG",
    "NIFTY PHARMA",
    "NIFTY METAL",
    "NIFTY REALTY",
    "NIFTY ENERGY",
    "NIFTY INFRA",
    "NIFTY MEDIA",
    "NIFTY FINANCIAL SERVICES",
    "NIFTY CONSUMER DURABLES",
    "NIFTY HEALTHCARE INDEX",
    "NIFTY OIL AND GAS",
]

# --- 8 Sectoral Variants ------------------------------------------------------
SECTORAL_VARIANTS = [
    "NIFTY PSU BANK",
    "NIFTY PRIVATE BANK",
    "NIFTY MIDSMALL FINANCIAL SERVICES",
    "NIFTY TOTAL MARKET",
    "NIFTY LARGE MIDCAP 250",
    "NIFTY MIDCAP 150",
    "NIFTY SMALLCAP 250",
    "NIFTY MICROCAP 250",
]

# --- 25 Thematic Indices ------------------------------------------------------
THEMATIC = [
    "NIFTY INDIA DEFENCE",
    "NIFTY INDIA DIGITAL",
    "NIFTY INDIA MANUFACTURING",
    "NIFTY INDIA CONSUMPTION",
    "NIFTY COMMODITIES",
    "NIFTY CPSE",
    "NIFTY PSE",
    "NIFTY MNC",
    "NIFTY SERV SECTOR",
    "NIFTY TRANSPORT & LOGISTICS",
    "NIFTY MOBILITY",
    "NIFTY TATA GROUP",
    "NIFTY100 QUALITY 30",
    "NIFTY ALPHA 50",
    "NIFTY200 ALPHA 30",
    "NIFTY500 MULTICAP INDIA LEADING",
    "NIFTY INDIA CORPORATE GROUP INDEX",
    "NIFTY CAPITAL MARKETS",
    "NIFTY HOUSING",
    "NIFTY NEW INDIA MANUFACTURING",
    "NIFTY RURAL INDEX",
    "NIFTY INDIA TOURISM",
    "NIFTY TECH INDEX",
    "NIFTY ENVIRONMENT",
    "NIFTY100 ESG SECTOR LEADERS",
]

# Full rotation universe
ROTATION_INDICES = CORE_SECTORAL + SECTORAL_VARIANTS + THEMATIC

# All 49 indices
ALL_INDICES = REFERENCE_INDICES + ROTATION_INDICES

# Indices for which P/E, P/B, Div Yield are tracked
# (NSE only publishes fundamentals for major indices; others will be skipped gracefully)
FUNDAMENTALS_INDICES = REFERENCE_INDICES + CORE_SECTORAL

# Categorisation map for logging / reporting
CATEGORY_MAP = {}
for idx in REFERENCE_INDICES:   CATEGORY_MAP[idx] = "Reference"
for idx in CORE_SECTORAL:        CATEGORY_MAP[idx] = "Core Sectoral"
for idx in SECTORAL_VARIANTS:    CATEGORY_MAP[idx] = "Sectoral Variant"
for idx in THEMATIC:             CATEGORY_MAP[idx] = "Thematic"


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"fetch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger("data_fetcher")
    logger.info(f"Log file: {log_file}")
    return logger


# ═══════════════════════════════════════════════════════════════════════════════
#  DATE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def to_nse_date(dt: datetime) -> str:
    """Convert datetime to NSEPython DD-MM-YYYY string."""
    return dt.strftime("%d-%m-%Y")


def from_nse_date(s: str) -> datetime:
    """Parse NSEPython DD-MM-YYYY string to datetime."""
    return datetime.strptime(s, "%d-%m-%Y")


def parse_input_date(s: str) -> datetime:
    """Accept YYYY-MM-DD or DD-MM-YYYY from the user CLI."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: '{s}'. Use YYYY-MM-DD or DD-MM-YYYY.")


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _cache_path(output_dir: Path, index_name: str, data_type: str) -> Path:
    safe_name = index_name.replace(" ", "_").replace("&", "AND")
    return output_dir / "cache" / data_type / f"{safe_name}.parquet"


def _load_cached(path: Path) -> pd.DataFrame | None:
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            return None
    return None


def _save_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  FETCH: PRICE HISTORY (OHLCV)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_price_response(raw_df: pd.DataFrame, index_name: str) -> pd.DataFrame:
    """
    NSEPython returns columns: HistoricalDate, OPEN, HIGH, LOW, CLOSE, SharesTraded, Turnover.
    Standardise to: date, open, high, low, close, volume, turnover, index_name.
    """
    df = raw_df.copy()

    # Normalise column names
    df.columns = [c.strip().upper() for c in df.columns]

    rename_map = {
        "HISTORICALDATE": "date",
        "OPEN":           "open",
        "HIGH":           "high",
        "LOW":            "low",
        "CLOSE":          "close",
        "SHARESTRADED":   "volume",
        "TURNOVER":       "turnover",
    }
    df.rename(columns=rename_map, inplace=True)

    # Keep only expected columns (ignore extras)
    keep = [c for c in ["date", "open", "high", "low", "close", "volume", "turnover"]
            if c in df.columns]
    df = df[keep]

    # Parse date
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df.dropna(subset=["date"], inplace=True)

    # Parse numerics (NSE sometimes returns strings with commas)
    for col in ["open", "high", "low", "close", "volume", "turnover"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                       .str.replace(",", "", regex=False)
                       .pipe(pd.to_numeric, errors="coerce")
            )

    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["index_name"] = index_name
    return df


def fetch_price_history(
    index_name: str,
    start_date: str,
    end_date: str,
    output_dir: Path,
    refresh: bool,
    logger: logging.Logger,
) -> pd.DataFrame | None:
    """
    Fetch OHLCV history for one index.
    Uses cache unless --refresh is set.
    Implements retry logic with exponential back-off.
    Returns a clean DataFrame or None on failure.
    """
    cache_path = _cache_path(output_dir, index_name, "prices")

    # --- Cache hit ---
    if not refresh:
        cached = _load_cached(cache_path)
        if cached is not None:
            logger.info(f"  [CACHE HIT]  {index_name}")
            return cached

    # --- Fetch from NSE ---
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            raw = index_history(index_name, start_date, end_date)

            if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
                logger.warning(f"  [EMPTY]      {index_name} — no data returned")
                return None

            if isinstance(raw, dict):
                # nsepython sometimes returns dict with 'data' key
                if "data" in raw:
                    raw = pd.DataFrame(raw["data"])
                else:
                    logger.warning(f"  [BAD RESP]   {index_name} — unexpected dict structure")
                    return None

            df = _parse_price_response(raw, index_name)

            if df.empty:
                logger.warning(f"  [EMPTY]      {index_name} — parsed DataFrame is empty")
                return None

            _save_cache(df, cache_path)
            logger.info(
                f"  [OK]         {index_name} — "
                f"{len(df):,} rows  "
                f"({df['date'].min().date()} → {df['date'].max().date()})"
            )
            return df

        except Exception as exc:
            wait = RETRY_DELAY_SECONDS * attempt
            logger.warning(
                f"  [RETRY {attempt}/{RETRY_ATTEMPTS}]  {index_name} — {exc}  "
                f"(waiting {wait}s)"
            )
            time.sleep(wait)

    logger.error(f"  [FAILED]     {index_name} — all {RETRY_ATTEMPTS} attempts exhausted")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  FETCH: P/E, P/B, DIVIDEND YIELD (FUNDAMENTALS)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_fundamental_response(raw_df: pd.DataFrame, index_name: str) -> pd.DataFrame:
    """
    NSEPython index_pe_pb_div returns columns such as:
      Date, P/E, P/B, Div Yield
    Standardise to: date, pe, pb, div_yield, index_name.
    """
    df = raw_df.copy()
    df.columns = [c.strip().upper().replace("/", "_").replace(" ", "_")
                  for c in df.columns]

    rename_map = {
        "DATE":      "date",
        "P_E":       "pe",
        "P_B":       "pb",
        "DIV_YIELD": "div_yield",
    }
    # Also handle variants nsepython has used historically
    for col in df.columns:
        if "PE" in col or "P_E" in col:
            rename_map.setdefault(col, "pe")
        if "PB" in col or "P_B" in col:
            rename_map.setdefault(col, "pb")
        if "DIV" in col:
            rename_map.setdefault(col, "div_yield")

    df.rename(columns=rename_map, inplace=True)

    keep = [c for c in ["date", "pe", "pb", "div_yield"] if c in df.columns]
    df = df[keep]

    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df.dropna(subset=["date"], inplace=True)

    for col in ["pe", "pb", "div_yield"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["index_name"] = index_name

    # Resample to month-end (keep last observation of each month)
    df.set_index("date", inplace=True)
    df = df.resample("ME").last()
    df.reset_index(inplace=True)
    df["index_name"] = index_name  # resample drops it

    return df


def fetch_fundamentals(
    index_name: str,
    start_date: str,
    end_date: str,
    output_dir: Path,
    refresh: bool,
    logger: logging.Logger,
) -> pd.DataFrame | None:
    """
    Fetch P/E, P/B, Div Yield for one index.
    Month-end resampled. Returns None gracefully if NSE doesn't publish for that index.
    """
    cache_path = _cache_path(output_dir, index_name, "fundamentals")

    if not refresh:
        cached = _load_cached(cache_path)
        if cached is not None:
            logger.info(f"  [CACHE HIT]  {index_name} (fundamentals)")
            return cached

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            raw = index_pe_pb_div(index_name, start_date, end_date)

            if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
                logger.warning(f"  [EMPTY]      {index_name} fundamentals — no data")
                return None

            if isinstance(raw, dict):
                if "data" in raw:
                    raw = pd.DataFrame(raw["data"])
                else:
                    return None

            df = _parse_fundamental_response(raw, index_name)
            _save_cache(df, cache_path)
            logger.info(
                f"  [OK]         {index_name} fundamentals — "
                f"{len(df)} months "
                f"({df['date'].min().date()} → {df['date'].max().date()})"
            )
            return df

        except Exception as exc:
            wait = RETRY_DELAY_SECONDS * attempt
            logger.warning(
                f"  [RETRY {attempt}/{RETRY_ATTEMPTS}]  {index_name} fundamentals — {exc}  "
                f"(waiting {wait}s)"
            )
            time.sleep(wait)

    logger.error(f"  [FAILED]     {index_name} fundamentals — all retries exhausted")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_price_data(df: pd.DataFrame, index_name: str, logger: logging.Logger) -> dict:
    """
    Run quality checks on a fetched price DataFrame.
    Returns a dict of validation results.
    """
    issues = []

    # 1. Missing close prices
    null_close = df["close"].isna().sum()
    if null_close > 0:
        issues.append(f"{null_close} null close prices")

    # 2. Zero or negative close
    bad_price = (df["close"] <= 0).sum()
    if bad_price > 0:
        issues.append(f"{bad_price} zero/negative close prices")

    # 3. Duplicate dates
    dup_dates = df["date"].duplicated().sum()
    if dup_dates > 0:
        issues.append(f"{dup_dates} duplicate dates")

    # 4. Suspicious price gaps (>30% single-day change — likely data error)
    pct_change = df["close"].pct_change().abs()
    big_jumps = (pct_change > 0.30).sum()
    if big_jumps > 0:
        issues.append(f"{big_jumps} single-day price moves >30%")

    # 5. Data freshness — warn if latest date is >10 calendar days ago
    latest = df["date"].max()
    staleness = (datetime.now() - latest).days
    if staleness > 10:
        issues.append(f"data may be stale — latest date: {latest.date()} ({staleness} days ago)")

    status = "WARN" if issues else "OK"
    return {
        "index":    index_name,
        "rows":     len(df),
        "start":    str(df["date"].min().date()),
        "end":      str(df["date"].max().date()),
        "status":   status,
        "issues":   issues,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ASSEMBLY: COMBINE ALL FETCHED DATA
# ═══════════════════════════════════════════════════════════════════════════════

def assemble_price_panel(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Stack all individual index DataFrames into a single panel:
    columns: date, index_name, open, high, low, close, volume, turnover
    Sorted by (date, index_name).
    """
    panel = pd.concat(dfs, ignore_index=True)
    panel.sort_values(["date", "index_name"], inplace=True)
    panel.reset_index(drop=True, inplace=True)
    return panel


def assemble_fundamental_panel(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    panel = pd.concat(dfs, ignore_index=True)
    panel.sort_values(["date", "index_name"], inplace=True)
    panel.reset_index(drop=True, inplace=True)
    return panel


# ═══════════════════════════════════════════════════════════════════════════════
#  EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def export_data(df: pd.DataFrame, output_dir: Path, base_name: str, logger: logging.Logger) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = output_dir / f"{base_name}.parquet"
    csv_path     = output_dir / f"{base_name}.csv"

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)

    logger.info(f"  Saved: {parquet_path}  ({len(df):,} rows)")
    logger.info(f"  Saved: {csv_path}")


def export_fetch_log(log_data: dict, output_dir: Path, logger: logging.Logger) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "fetch_log.json"
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2, default=str)
    logger.info(f"  Saved: {log_path}")


# ═══════════════════════════════════════════════════════════════════════════════
#  SUMMARY REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary(fetch_log: dict) -> None:
    price_results = fetch_log.get("prices", {})
    total     = len(price_results)
    succeeded = sum(1 for v in price_results.values() if v["status"] in ("OK", "WARN"))
    failed    = sum(1 for v in price_results.values() if v["status"] == "FAILED")
    warned    = sum(1 for v in price_results.values() if v["status"] == "WARN")

    print(f"\n{'═'*60}")
    print(f"  DATA FETCH SUMMARY")
    print(f"{'═'*60}")
    print(f"  Total indices requested : {total}")
    print(f"  {GREEN}Successfully fetched    : {succeeded}{RESET}")
    print(f"  {YELLOW}With warnings           : {warned}{RESET}")
    print(f"  {RED}Failed                  : {failed}{RESET}")

    if failed > 0:
        print(f"\n  {RED}FAILED indices:{RESET}")
        for name, result in price_results.items():
            if result["status"] == "FAILED":
                print(f"    - {name}")

    if warned > 0:
        print(f"\n  {YELLOW}WARNING indices:{RESET}")
        for name, result in price_results.items():
            if result["status"] == "WARN":
                print(f"    - {name}: {'; '.join(result.get('issues', []))}")

    print(f"{'═'*60}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # ── CLI Arguments ──────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="Fetch NSE index price and fundamental data for the sector rotation model."
    )
    parser.add_argument(
        "--start", default=DEFAULT_START_DATE,
        help=f"Start date (YYYY-MM-DD or DD-MM-YYYY). Default: {DEFAULT_START_DATE}",
    )
    parser.add_argument(
        "--end", default=to_nse_date(datetime.today()),
        help="End date (YYYY-MM-DD or DD-MM-YYYY). Default: today",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Ignore cache and re-fetch all data from NSE",
    )
    parser.add_argument(
        "--indices", default=None,
        help='Comma-separated list of index names to fetch (subset mode). '
             'E.g. "NIFTY BANK,NIFTY IT"',
    )
    parser.add_argument(
        "--no-fundamentals", action="store_true",
        help="Skip fetching P/E, P/B, Dividend Yield (price data only)",
    )
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR),
        help=f"Directory to write output files. Default: {OUTPUT_DIR}",
    )
    args = parser.parse_args()

    # ── Setup ──────────────────────────────────────────────────────────────────
    logger     = setup_logging(LOG_DIR)
    output_dir = Path(args.output_dir)

    # Parse and convert dates to NSEPython format
    start_dt = parse_input_date(args.start)
    end_dt   = parse_input_date(args.end)
    start_nse = to_nse_date(start_dt)
    end_nse   = to_nse_date(end_dt)

    # Determine which indices to fetch
    if args.indices:
        indices_to_fetch = [i.strip().upper() for i in args.indices.split(",")]
        logger.info(f"Subset mode: fetching {len(indices_to_fetch)} indices")
    else:
        indices_to_fetch = ALL_INDICES
        logger.info(f"Full universe mode: fetching {len(indices_to_fetch)} indices")

    logger.info(f"Date range: {start_nse} → {end_nse}")
    logger.info(f"Refresh cache: {args.refresh}")

    # ── Fetch Price History ────────────────────────────────────────────────────
    print(f"\n{CYAN}{'─'*60}")
    print(f"  PHASE 1 OF 2 — PRICE HISTORY (OHLCV)")
    print(f"{'─'*60}{RESET}")

    price_dfs   = []
    fetch_log   = {"run_timestamp": str(datetime.now()), "prices": {}, "fundamentals": {}}
    validation_results = []

    for index_name in tqdm(indices_to_fetch, desc="Fetching prices", unit="index"):
        df = fetch_price_history(
            index_name, start_nse, end_nse, output_dir, args.refresh, logger
        )

        if df is not None:
            val = validate_price_data(df, index_name, logger)
            validation_results.append(val)
            fetch_log["prices"][index_name] = {
                "category": CATEGORY_MAP.get(index_name, "Unknown"),
                "status":   val["status"],
                "rows":     val["rows"],
                "start":    val["start"],
                "end":      val["end"],
                "issues":   val["issues"],
            }
            price_dfs.append(df)
        else:
            fetch_log["prices"][index_name] = {
                "category": CATEGORY_MAP.get(index_name, "Unknown"),
                "status":   "FAILED",
                "rows":     0,
                "issues":   ["fetch returned None"],
            }

        time.sleep(RATE_LIMIT_SECONDS)

    # ── Fetch Fundamentals ─────────────────────────────────────────────────────
    if not args.no_fundamentals:
        print(f"\n{CYAN}{'─'*60}")
        print(f"  PHASE 2 OF 2 — FUNDAMENTALS (P/E, P/B, DIV YIELD)")
        print(f"{'─'*60}{RESET}")

        fund_indices = [i for i in FUNDAMENTALS_INDICES if i in indices_to_fetch]
        fund_dfs = []

        for index_name in tqdm(fund_indices, desc="Fetching fundamentals", unit="index"):
            df = fetch_fundamentals(
                index_name, start_nse, end_nse, output_dir, args.refresh, logger
            )
            if df is not None:
                fund_dfs.append(df)
                fetch_log["fundamentals"][index_name] = {
                    "status": "OK",
                    "months": len(df),
                }
            else:
                fetch_log["fundamentals"][index_name] = {
                    "status": "FAILED",
                    "months": 0,
                }
            time.sleep(RATE_LIMIT_SECONDS)

    # ── Assemble & Export ──────────────────────────────────────────────────────
    print(f"\n{CYAN}{'─'*60}")
    print(f"  EXPORTING DATA")
    print(f"{'─'*60}{RESET}")

    if price_dfs:
        price_panel = assemble_price_panel(price_dfs)
        export_data(price_panel, output_dir, "prices_daily", logger)
    else:
        logger.error("No price data fetched — prices_daily not written.")

    if not args.no_fundamentals and fund_dfs:
        fund_panel = assemble_fundamental_panel(fund_dfs)
        export_data(fund_panel, output_dir, "pe_pb_div_monthly", logger)
    elif not args.no_fundamentals:
        logger.warning("No fundamental data fetched — pe_pb_div_monthly not written.")

    export_fetch_log(fetch_log, output_dir, logger)

    # ── Print Summary ──────────────────────────────────────────────────────────
    print_summary(fetch_log)

    # Exit with non-zero code if any index failed (useful for CI/scheduling)
    failed_count = sum(
        1 for v in fetch_log["prices"].values() if v["status"] == "FAILED"
    )
    sys.exit(1 if failed_count == len(indices_to_fetch) else 0)


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
