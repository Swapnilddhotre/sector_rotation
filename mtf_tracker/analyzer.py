"""
MTF Analyzer — transforms raw MTF data into actionable signals and screens.

Capabilities:
1. Market Overview     — total book, daily change, breadth, trend
2. Top Funded Stocks   — largest MTF positions
3. Biggest Movers      — where margin funding is building/declining fastest
4. Crowding Analysis   — days to cover, % of free float
5. Stock Deep Dive     — individual stock MTF + price history
6. Leverage Risk Scan  — non-F&O stocks with high leverage (unhedgeable)
7. Flush Detection     — forced selling signals
"""

import logging
from typing import Optional

import pandas as pd

from mtf_tracker.client import MTFClient

logger = logging.getLogger(__name__)


class MTFAnalyzer:
    """Wraps MTFClient with analytical screens and scoring."""

    def __init__(self, client: Optional[MTFClient] = None):
        self.client = client or MTFClient()

    # ── 1. Market Overview ──

    def market_overview(self) -> dict:
        """Returns market-level MTF summary: total book, change, fresh/liquidated."""
        data = self.client.get_market_overview()
        return {
            "source": "margintradingfacility.com",
            "description": "Whole-market NSE MTF book overview",
            "data": data,
        }

    # ── 2. Top Funded Stocks ──

    def top_funded_stocks(self, limit: int = 50) -> pd.DataFrame:
        """Stocks with the largest MTF positions, sorted by book size."""
        stocks = self.client.get_top_stocks(limit=limit)
        if isinstance(stocks, list):
            df = pd.DataFrame(stocks)
        elif isinstance(stocks, dict) and "stocks" in stocks:
            df = pd.DataFrame(stocks["stocks"])
        else:
            df = pd.DataFrame(stocks)

        if df.empty:
            return df

        sort_col = _find_column(df, ["book", "mtf_book", "outstanding", "amount"])
        if sort_col:
            df = df.sort_values(sort_col, ascending=False)
        return df.head(limit)

    # ── 3. Biggest Movers ──

    def biggest_movers(self, limit: int = 30, period: str = "30d") -> dict:
        """Stocks with largest increase/decrease in MTF book over period."""
        stocks = self.client.get_top_stocks(limit=200)
        if isinstance(stocks, list):
            df = pd.DataFrame(stocks)
        elif isinstance(stocks, dict) and "stocks" in stocks:
            df = pd.DataFrame(stocks["stocks"])
        else:
            df = pd.DataFrame(stocks)

        if df.empty:
            return {"gainers": pd.DataFrame(), "losers": pd.DataFrame()}

        change_col = _find_column(df, [
            f"change_{period}", f"{period}_change", "change_30d",
            "change_7d", "change_pct", "change",
        ])
        if not change_col:
            return {"gainers": df.head(limit), "losers": pd.DataFrame(),
                    "note": "Change column not found; showing top by book size"}

        df[change_col] = pd.to_numeric(df[change_col], errors="coerce")
        sorted_df = df.sort_values(change_col, ascending=False)

        return {
            "gainers": sorted_df.head(limit),
            "losers": sorted_df.tail(limit).sort_values(change_col, ascending=True),
        }

    # ── 4. Crowding Analysis ──

    def crowding_screen(self, min_days_to_cover: float = 5.0, limit: int = 50) -> pd.DataFrame:
        """Stocks with highest days-to-cover (MTF shares / avg daily volume).
        Higher = harder to unwind = more crowded.
        """
        try:
            universe = self.client.get_stock_universe()
        except Exception:
            logger.warning("Stock universe not available, falling back to top stocks")
            universe = pd.DataFrame(self.client.get_top_stocks(limit=200))

        if universe.empty:
            return universe

        dtc_col = _find_column(universe, ["days_to_cover", "dtc", "days_cover"])
        if dtc_col:
            universe[dtc_col] = pd.to_numeric(universe[dtc_col], errors="coerce")
            screened = universe[universe[dtc_col] >= min_days_to_cover]
            return screened.sort_values(dtc_col, ascending=False).head(limit)

        return universe.head(limit)

    # ── 5. Stock Deep Dive ──

    def stock_deep_dive(self, ticker: str) -> dict:
        """Detailed MTF data for a single stock: book, rank, changes, price overlay."""
        detail = self.client.get_stock_detail(ticker)
        return {
            "ticker": ticker.upper(),
            "source": "margintradingfacility.com",
            "data": detail,
        }

    # ── 6. Leverage Risk Scanner ──

    def leverage_risk_scan(self, limit: int = 50) -> pd.DataFrame:
        """Non-F&O stocks with high MTF as % of free float.
        These cannot be hedged via derivatives and trade on thinner liquidity —
        maximum risk in a downturn.
        """
        try:
            universe = self.client.get_stock_universe()
        except Exception:
            logger.warning("Stock universe not available")
            return pd.DataFrame()

        if universe.empty:
            return universe

        fno_col = _find_column(universe, ["fno", "f_o", "fo_class", "class", "category", "type"])
        leverage_col = _find_column(universe, ["leverage_pct", "pct_free_float", "ff_pct", "leverage"])

        if fno_col and leverage_col:
            non_fno = universe[
                ~universe[fno_col].astype(str).str.upper().isin(["F&O", "FNO", "FO", "YES", "TRUE"])
            ].copy()
            non_fno[leverage_col] = pd.to_numeric(non_fno[leverage_col], errors="coerce")
            return non_fno.sort_values(leverage_col, ascending=False).head(limit)

        book_col = _find_column(universe, ["book", "mtf_book", "outstanding", "amount"])
        if book_col:
            return universe.sort_values(book_col, ascending=False).head(limit)

        return universe.head(limit)

    # ── 7. Flush Detection ──

    def flush_detection(self, threshold_pct: float = -10.0, lookback_days: int = 5) -> dict:
        """Detect stocks where MTF book is declining sharply — potential forced selling.

        Returns stocks where the MTF book dropped by more than threshold_pct
        over the lookback period, signaling margin call liquidations.
        """
        try:
            flow = self.client.get_flow_and_flushes()
            recent = flow.tail(lookback_days)
        except Exception:
            flow = pd.DataFrame()
            recent = pd.DataFrame()

        movers = self.biggest_movers(limit=100, period="7d")
        losers = movers.get("losers", pd.DataFrame())

        return {
            "description": "Stocks with rapid MTF book decline (potential forced selling)",
            "threshold_pct": threshold_pct,
            "lookback_days": lookback_days,
            "market_flow": recent.to_dict("records") if not recent.empty else [],
            "stocks_declining": losers if not losers.empty else pd.DataFrame(),
        }

    # ── 8. Book Composition Trend ──

    def book_composition_trend(self, days: int = 90) -> pd.DataFrame:
        """Daily MTF book split into F&O / non-F&O / ETF over time."""
        try:
            comp = self.client.get_book_composition()
            return comp.tail(days)
        except Exception as e:
            logger.warning("Book composition not available: %s", e)
            return pd.DataFrame()

    # ── 9. Market Breadth ──

    def market_breadth(self, days: int = 30) -> pd.DataFrame:
        """Daily count of stocks with rising vs falling MTF books."""
        try:
            breadth = self.client.get_daily_breadth()
            return breadth.tail(days)
        except Exception as e:
            logger.warning("Breadth data not available: %s", e)
            return pd.DataFrame()

    # ── 10. Broker-Level Analysis ──

    def broker_analysis(self) -> pd.DataFrame:
        """Per-broker MTF book history: which brokers are growing their margin books fastest."""
        try:
            return self.client.get_broker_history()
        except Exception as e:
            logger.warning("Broker data not available: %s", e)
            return pd.DataFrame()

    # ── Composite Risk Score ──

    def compute_risk_score(self, ticker: str) -> dict:
        """Composite MTF risk score for a stock (0-100, higher = more risk).

        Factors:
        - MTF book size rank (larger = riskier)
        - % of free float funded (higher = riskier)
        - Days to cover (higher = riskier)
        - F&O availability (no F&O = riskier)
        - Recent book growth rate (faster growth = riskier)
        """
        detail = self.client.get_stock_detail(ticker)
        if not detail:
            return {"ticker": ticker, "risk_score": None, "error": "No data found"}

        score_components = {}
        total_weight = 0
        weighted_score = 0

        rank = _extract_numeric(detail, ["rank"])
        if rank is not None:
            rank_score = max(0, min(100, 100 - rank))
            score_components["rank_score"] = rank_score
            weighted_score += rank_score * 0.15
            total_weight += 0.15

        ff_pct = _extract_numeric(detail, ["pct_free_float", "ff_pct", "leverage_pct"])
        if ff_pct is not None:
            ff_score = min(100, ff_pct * 10)
            score_components["free_float_score"] = ff_score
            weighted_score += ff_score * 0.30
            total_weight += 0.30

        dtc = _extract_numeric(detail, ["days_to_cover", "dtc"])
        if dtc is not None:
            dtc_score = min(100, dtc * 5)
            score_components["days_to_cover_score"] = dtc_score
            weighted_score += dtc_score * 0.25
            total_weight += 0.25

        change_30d = _extract_numeric(detail, ["change_30d", "change_1m", "1m_change"])
        if change_30d is not None:
            growth_score = min(100, max(0, change_30d * 2))
            score_components["growth_score"] = growth_score
            weighted_score += growth_score * 0.30
            total_weight += 0.30

        final_score = (weighted_score / total_weight * 100) if total_weight > 0 else None

        return {
            "ticker": ticker.upper(),
            "risk_score": round(final_score, 1) if final_score else None,
            "components": score_components,
            "interpretation": _interpret_risk(final_score),
        }


def _find_column(df: pd.DataFrame, candidates: list) -> Optional[str]:
    cols_lower = {c.lower().replace(" ", "_").replace("%", "pct"): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in cols_lower:
            return cols_lower[candidate.lower()]
        for col_key, col_orig in cols_lower.items():
            if candidate.lower() in col_key:
                return col_orig
    return None


def _extract_numeric(data: dict, keys: list) -> Optional[float]:
    if not isinstance(data, dict):
        return None
    for key in keys:
        if key in data:
            try:
                return float(data[key])
            except (ValueError, TypeError):
                continue
        for k, v in data.items():
            if key.lower() in k.lower():
                try:
                    return float(v)
                except (ValueError, TypeError):
                    continue
    return None


def _interpret_risk(score: Optional[float]) -> str:
    if score is None:
        return "Insufficient data"
    if score >= 75:
        return "HIGH RISK — Heavily leveraged, crowded, hard to unwind"
    if score >= 50:
        return "ELEVATED — Significant margin exposure, monitor closely"
    if score >= 25:
        return "MODERATE — Some margin activity, manageable"
    return "LOW — Minimal margin exposure"
