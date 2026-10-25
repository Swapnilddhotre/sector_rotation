"""
MTF data client — fetches margin trading facility data from public APIs.

Primary source: margintradingfacility.com (free, key-less, CORS-enabled JSON API)
Fallback source: mtf.trading (CSV/JSON downloads, Atom feeds, per-day JSON snapshots)

Both sources compile NSE & BSE daily MTF disclosure files into structured data.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

API_PRIMARY = "https://margintradingfacility.com/api"
API_FEED = "https://mtf.trading"

CACHE_DIR = Path("data/mtf_cache")
CACHE_TTL_HOURS = 12


class MTFClient:
    """Fetches and caches MTF data from public APIs."""

    def __init__(self, cache_dir: Optional[Path] = None, timeout: int = 30):
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "sector-rotation-mtf-tracker/1.0",
            "Accept": "application/json",
        })

    def _cache_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace("?", "_").replace("&", "_")
        return self.cache_dir / f"{safe_key}.json"

    def _read_cache(self, key: str) -> Optional[dict]:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            if datetime.now() - cached_at > timedelta(hours=CACHE_TTL_HOURS):
                return None
            return data.get("payload")
        except (json.JSONDecodeError, ValueError):
            return None

    def _write_cache(self, key: str, payload):
        path = self._cache_path(key)
        path.write_text(json.dumps({
            "_cached_at": datetime.now().isoformat(),
            "payload": payload,
        }, default=str, indent=2))

    def _get(self, url: str, cache_key: Optional[str] = None) -> dict:
        key = cache_key or url
        cached = self._read_cache(key)
        if cached is not None:
            logger.info("Cache hit: %s", key)
            return cached

        logger.info("Fetching: %s", url)
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        self._write_cache(key, data)
        return data

    def _get_csv(self, url: str, cache_key: Optional[str] = None) -> pd.DataFrame:
        key = cache_key or url
        cache_path = self._cache_path(key).with_suffix(".csv")

        if cache_path.exists():
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
            if datetime.now() - mtime < timedelta(hours=CACHE_TTL_HOURS):
                return pd.read_csv(cache_path)

        logger.info("Fetching CSV: %s", url)
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        cache_path.write_bytes(resp.content)
        return pd.read_csv(cache_path)

    # ── Market-level endpoints (margintradingfacility.com) ──

    def get_market_overview(self) -> dict:
        """Whole-market NSE MTF book: total outstanding, change, fresh/liquidated, daily series."""
        return self._get(f"{API_PRIMARY}/latest", "market_overview")

    # ── Stock-level endpoints (margintradingfacility.com) ──

    def get_top_stocks(self, limit: int = 150) -> list:
        """Per-stock MTF book, close price, 7D/30D changes for largest funded stocks."""
        return self._get(f"{API_PRIMARY}/stocks?limit={limit}", f"top_stocks_{limit}")

    def get_stock_detail(self, ticker: str) -> dict:
        """Full detail for one stock: book, rank, change windows, price-vs-book series."""
        return self._get(f"{API_PRIMARY}/stock/{ticker.upper()}", f"stock_{ticker.upper()}")

    # ── mtf.trading endpoints (richer datasets) ──

    def get_daily_snapshot(self, date: str) -> dict:
        """Full per-day snapshot from mtf.trading: book, top stocks, movers, breadth.
        date format: YYYY-MM-DD
        """
        return self._get(f"{API_FEED}/{date}/.json", f"snapshot_{date}")

    def get_daily_totals(self) -> pd.DataFrame:
        """Daily MTF totals since 2017: outstanding, fresh, liquidated, count. CSV."""
        url = f"{API_FEED}/data/daily-totals.csv"
        return self._get_csv(url, "daily_totals")

    def get_flow_and_flushes(self) -> pd.DataFrame:
        """Daily net margin flow, churn, margin-flush events. CSV."""
        url = f"{API_FEED}/data/leverage-flow.csv"
        return self._get_csv(url, "flow_flushes")

    def get_daily_breadth(self) -> pd.DataFrame:
        """Daily count of stocks with rising vs falling margin books. CSV."""
        url = f"{API_FEED}/data/daily-breadth.csv"
        return self._get_csv(url, "daily_breadth")

    def get_book_composition(self) -> pd.DataFrame:
        """Daily MTF split: F&O / non-F&O / ETF. CSV."""
        url = f"{API_FEED}/data/book-composition.csv"
        return self._get_csv(url, "book_composition")

    def get_stock_universe(self) -> pd.DataFrame:
        """Full ~3,400-stock snapshot: symbol, ISIN, book, mcap, leverage %, 30d change, class. CSV."""
        url = f"{API_FEED}/data/stock-universe.csv"
        return self._get_csv(url, "stock_universe")

    def get_broker_history(self) -> pd.DataFrame:
        """Per-broker MTF book history. CSV."""
        url = f"{API_FEED}/data/broker-history.csv"
        return self._get_csv(url, "broker_history")

    # ── NSE Direct (raw exchange files) ──

    def get_nse_mtf_daily(self, date: str) -> pd.DataFrame:
        """Fetch raw NSE MTF disclosure Excel for a given date (DDMMYYYY).
        Fallback if APIs are down. Format: one row per stock.
        """
        nse_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d%m%Y")
        url = f"https://nsearchives.nseindia.com/content/nsccl/MCIRMarginTradingOpenPositions_{nse_date}.csv"
        return self._get_csv(url, f"nse_raw_{date}")
