#!/usr/bin/env python3
"""
MTF Tracker CLI — command-line interface for margin trading facility analysis.

Usage:
    python -m mtf_tracker.cli overview
    python -m mtf_tracker.cli top [--limit 50]
    python -m mtf_tracker.cli movers [--limit 30]
    python -m mtf_tracker.cli crowding [--min-dtc 5]
    python -m mtf_tracker.cli risk-scan [--limit 50]
    python -m mtf_tracker.cli flush [--threshold -10]
    python -m mtf_tracker.cli stock TICKER
    python -m mtf_tracker.cli risk-score TICKER
    python -m mtf_tracker.cli breadth [--days 30]
    python -m mtf_tracker.cli composition [--days 90]
    python -m mtf_tracker.cli brokers
    python -m mtf_tracker.cli snapshot [--date 2026-10-22]
"""

import argparse
import json
import sys
from datetime import datetime

import pandas as pd

from mtf_tracker.analyzer import MTFAnalyzer
from mtf_tracker.client import MTFClient


def fmt_json(data) -> str:
    if isinstance(data, pd.DataFrame):
        return data.to_string(index=False, max_rows=60)
    return json.dumps(data, indent=2, default=str)


def cmd_overview(analyzer: MTFAnalyzer, args):
    result = analyzer.market_overview()
    print("=" * 60)
    print("  MTF MARKET OVERVIEW — Indian Margin Trading Facility")
    print("=" * 60)
    print(fmt_json(result))


def cmd_top(analyzer: MTFAnalyzer, args):
    df = analyzer.top_funded_stocks(limit=args.limit)
    print(f"\nTop {args.limit} Stocks by MTF Book Size")
    print("-" * 60)
    if df.empty:
        print("No data available")
    else:
        print(df.to_string(index=False))


def cmd_movers(analyzer: MTFAnalyzer, args):
    result = analyzer.biggest_movers(limit=args.limit)
    print("\nBIGGEST MTF GAINERS (margin building)")
    print("-" * 60)
    gainers = result.get("gainers", pd.DataFrame())
    if not gainers.empty:
        print(gainers.to_string(index=False))
    else:
        print("No data")

    print("\nBIGGEST MTF LOSERS (margin unwinding)")
    print("-" * 60)
    losers = result.get("losers", pd.DataFrame())
    if not losers.empty:
        print(losers.to_string(index=False))
    else:
        print("No data")


def cmd_crowding(analyzer: MTFAnalyzer, args):
    df = analyzer.crowding_screen(min_days_to_cover=args.min_dtc, limit=args.limit)
    print(f"\nMOST CROWDED MTF POSITIONS (days to cover >= {args.min_dtc})")
    print("-" * 60)
    if df.empty:
        print("No data available")
    else:
        print(df.to_string(index=False))


def cmd_risk_scan(analyzer: MTFAnalyzer, args):
    df = analyzer.leverage_risk_scan(limit=args.limit)
    print(f"\nLEVERAGE RISK SCAN — Non-F&O Stocks with High MTF Exposure")
    print("-" * 60)
    if df.empty:
        print("No data available")
    else:
        print(df.to_string(index=False))


def cmd_flush(analyzer: MTFAnalyzer, args):
    result = analyzer.flush_detection(threshold_pct=args.threshold)
    print("\nMARGIN FLUSH DETECTION — Potential Forced Selling")
    print("-" * 60)
    print(f"Threshold: {args.threshold}% | Lookback: {result['lookback_days']} days")
    print()

    flow = result.get("market_flow", [])
    if flow:
        print("Recent market-level flow:")
        print(pd.DataFrame(flow).to_string(index=False))

    declining = result.get("stocks_declining", pd.DataFrame())
    if not declining.empty:
        print("\nStocks with declining MTF books:")
        print(declining.to_string(index=False))


def cmd_stock(analyzer: MTFAnalyzer, args):
    result = analyzer.stock_deep_dive(args.ticker)
    print(f"\nMTF DEEP DIVE: {args.ticker.upper()}")
    print("=" * 60)
    print(fmt_json(result))


def cmd_risk_score(analyzer: MTFAnalyzer, args):
    result = analyzer.compute_risk_score(args.ticker)
    print(f"\nMTF RISK SCORE: {args.ticker.upper()}")
    print("=" * 60)
    print(fmt_json(result))


def cmd_breadth(analyzer: MTFAnalyzer, args):
    df = analyzer.market_breadth(days=args.days)
    print(f"\nMTF MARKET BREADTH (last {args.days} days)")
    print("-" * 60)
    if df.empty:
        print("No data available")
    else:
        print(df.to_string(index=False))


def cmd_composition(analyzer: MTFAnalyzer, args):
    df = analyzer.book_composition_trend(days=args.days)
    print(f"\nMTF BOOK COMPOSITION — F&O / Non-F&O / ETF (last {args.days} days)")
    print("-" * 60)
    if df.empty:
        print("No data available")
    else:
        print(df.to_string(index=False))


def cmd_brokers(analyzer: MTFAnalyzer, args):
    df = analyzer.broker_analysis()
    print("\nBROKER-LEVEL MTF ANALYSIS")
    print("-" * 60)
    if df.empty:
        print("No data available")
    else:
        print(df.to_string(index=False))


def cmd_snapshot(analyzer: MTFAnalyzer, args):
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = analyzer.client.get_daily_snapshot(date)
        print(f"\nMTF DAILY SNAPSHOT: {date}")
        print("=" * 60)
        print(fmt_json(data))
    except Exception as e:
        print(f"Error fetching snapshot for {date}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="MTF Tracker — Indian Margin Trading Facility Analyzer"
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    sub.add_parser("overview", help="Market-level MTF overview")

    p = sub.add_parser("top", help="Top stocks by MTF book size")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("movers", help="Biggest MTF gainers and losers")
    p.add_argument("--limit", type=int, default=30)

    p = sub.add_parser("crowding", help="Most crowded MTF positions")
    p.add_argument("--min-dtc", type=float, default=5.0, help="Min days to cover")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("risk-scan", help="Non-F&O stocks with high leverage")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("flush", help="Detect margin flush / forced selling")
    p.add_argument("--threshold", type=float, default=-10.0)

    p = sub.add_parser("stock", help="Deep dive on a single stock")
    p.add_argument("ticker", help="NSE ticker symbol")

    p = sub.add_parser("risk-score", help="Composite risk score for a stock")
    p.add_argument("ticker", help="NSE ticker symbol")

    p = sub.add_parser("breadth", help="MTF market breadth")
    p.add_argument("--days", type=int, default=30)

    p = sub.add_parser("composition", help="Book composition trend")
    p.add_argument("--days", type=int, default=90)

    sub.add_parser("brokers", help="Broker-level MTF analysis")

    p = sub.add_parser("snapshot", help="Daily snapshot for a specific date")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    analyzer = MTFAnalyzer()
    commands = {
        "overview": cmd_overview,
        "top": cmd_top,
        "movers": cmd_movers,
        "crowding": cmd_crowding,
        "risk-scan": cmd_risk_scan,
        "flush": cmd_flush,
        "stock": cmd_stock,
        "risk-score": cmd_risk_score,
        "breadth": cmd_breadth,
        "composition": cmd_composition,
        "brokers": cmd_brokers,
        "snapshot": cmd_snapshot,
    }
    commands[args.command](analyzer, args)


if __name__ == "__main__":
    main()
