"""
india-sector-rotation | Phase 2 | Script 03
============================================
backtest_engine.py

PURPOSE
-------
Validates signal quality and portfolio performance through an expanding-window
walk-forward backtest.  Implements the full methodology from Section 4 of the
strategy document.

THREE ANALYSIS MODULES
-----------------------
  Module A — Signal Quality (IC Analysis)
    · Information Coefficient per block and composite
    · IC mean, IC IR, hit rate by signal
    · Rolling 12-month IC to track signal decay

  Module B — Portfolio Performance
    · Top-N sector portfolio vs Nifty 50 benchmark
    · Expanding-window walk-forward (3 training windows)
    · Annualised alpha, Sharpe, max drawdown, hit rate, turnover
    · Transaction-cost-adjusted returns

  Module C — Regime-Conditional Analysis
    · Break all metrics down by India macro regime stage (1–5)
    · Validate model outperforms in Stages 1–2, defends in Stages 4–5

OUTPUTS  (all written to  data/backtest/)
------------------------------------------
  ic_analysis.csv              — Monthly IC per block, rolling stats
  ic_summary.csv               — IC mean, IC IR, hit rate per block
  portfolio_returns.csv        — Monthly portfolio vs benchmark returns
  performance_summary.csv      — Top-level performance metrics table
  regime_performance.csv       — Metrics broken down by regime stage
  drawdown_series.csv          — Rolling drawdown for portfolio and benchmark
  backtest_report.txt          — Human-readable full report

USAGE
------
  python backtest_engine.py                          # full backtest
  python backtest_engine.py --top-n 3               # top-3 sectors (default)
  python backtest_engine.py --top-n 5               # top-5 sectors
  python backtest_engine.py --start 2015-01-01       # custom start
  python backtest_engine.py --cost-bps 30            # round-trip cost override
  python backtest_engine.py --no-regime              # skip Module C

DEPENDENCIES
------------
  pip install pandas numpy scipy pyarrow
"""

import argparse
import logging
import sys
import warnings
from datetime import datetime
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, ttest_1samp

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ── Optional colour ────────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    GREEN  = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED    = Fore.RED
    CYAN   = Fore.CYAN
    BOLD   = Style.BRIGHT
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = YELLOW = RED = CYAN = BOLD = RESET = ""


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

INPUT_PRICE_DIR    = Path("data/raw")
INPUT_SCORE_DIR    = Path("data/processed")
OUTPUT_DIR         = Path("data/backtest")
LOG_DIR            = Path("logs")

BENCHMARK          = "NIFTY 50"
DEFAULT_TOP_N      = 3          # number of sectors held each month
ROUND_TRIP_BPS     = 30         # 0.30% round-trip transaction cost (per strategy doc)
TRADING_DAYS_YEAR  = 252

# Expanding window training periods (from strategy document Section 4.1)
# Each tuple: (train_start, train_end, test_start, test_end)
WALK_FORWARD_WINDOWS = [
    ("2005-01-01", "2015-12-31", "2016-01-01", "2016-12-31"),
    ("2005-01-01", "2020-12-31", "2021-01-01", "2021-12-31"),
    ("2005-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
]

# IC target benchmarks (from strategy document Section 4.2)
IC_MEAN_TARGET   = 0.05
IC_IR_TARGET     = 0.30

# Portfolio performance targets (from strategy document Section 4.3)
TARGET_ALPHA     = 0.04    # 4% p.a.
TARGET_SHARPE    = 0.80
TARGET_DRAWDOWN  = 0.25    # max 25%
TARGET_HIT_RATE  = 0.55
TARGET_TURNOVER  = 1.50    # avg sector changes per month


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"backtest_{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("backtest_engine")


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_prices(price_dir: Path, logger: logging.Logger) -> pd.DataFrame:
    """Load daily close prices. Returns wide DataFrame: date × index_name."""
    path = price_dir / "prices_daily.parquet"
    if not path.exists():
        path = price_dir / "prices_daily.csv"
        if not path.exists():
            logger.error(f"Price data not found at {price_dir}. Run data_fetcher.py first.")
            sys.exit(1)
        df = pd.read_csv(path, parse_dates=["date"])
    else:
        df = pd.read_parquet(path)

    df["date"] = pd.to_datetime(df["date"])
    close = df.pivot_table(index="date", columns="index_name", values="close")
    close.sort_index(inplace=True)
    logger.info(
        f"Loaded prices: {len(close)} days, {close.shape[1]} indices, "
        f"{close.index.min().date()} → {close.index.max().date()}"
    )
    return close


def load_scorecard_history(score_dir: Path, logger: logging.Logger) -> pd.DataFrame:
    """
    Load the full monthly scorecard history produced by signal_engine.py.
    Falls back to generating synthetic scores if file doesn't exist (for standalone testing).
    """
    path = score_dir / "scorecard_history.parquet"
    if not path.exists():
        path = score_dir / "scorecard_history.csv"

    if path.exists():
        if str(path).endswith(".parquet"):
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path, parse_dates=["as_of"])
        df["as_of"] = pd.to_datetime(df["as_of"])
        logger.info(
            f"Loaded scorecard history: {df['as_of'].nunique()} months, "
            f"{df['index_name'].nunique()} indices"
        )
        return df

    logger.warning(
        "scorecard_history not found. "
        "Run: python signal_engine.py --history  to generate it first.\n"
        "Proceeding with synthetic scores for structure validation only."
    )
    return pd.DataFrame()   # caller handles empty case


# ═══════════════════════════════════════════════════════════════════════════════
#  RETURN COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════════

def compute_monthly_returns(close: pd.DataFrame) -> pd.DataFrame:
    """
    Compute month-end to month-end returns for all indices.
    Returns DataFrame indexed by month-end date.
    """
    monthly_close = close.resample("ME").last()
    returns = monthly_close.pct_change()
    returns.sort_index(inplace=True)
    return returns


def forward_return(returns: pd.DataFrame, date: pd.Timestamp, horizon: int = 1) -> pd.Series:
    """Return the h-month forward return for all indices from a given date."""
    future_dates = returns.index[returns.index > date]
    if len(future_dates) < horizon:
        return pd.Series(dtype=float)
    target_date = future_dates[horizon - 1]
    return returns.loc[target_date]


# ═══════════════════════════════════════════════════════════════════════════════
#  MODULE A — IC ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ic_series(
    scorecard: pd.DataFrame,
    monthly_returns: pd.DataFrame,
    score_col: str,
    horizon: int = 1,
) -> pd.Series:
    """
    Compute the monthly Information Coefficient (Spearman rank correlation)
    between a score column at time t and forward returns at t+horizon.

    IC_t = Spearman(score[t], return[t+1])
    """
    ic_values = {}

    for date in scorecard["as_of"].unique():
        date = pd.Timestamp(date)
        month_scores = (
            scorecard[scorecard["as_of"] == date]
            .set_index("index_name")[score_col]
            .dropna()
        )
        fwd_ret = forward_return(monthly_returns, date, horizon)

        # Align on common indices, exclude benchmark from IC calc
        common = month_scores.index.intersection(fwd_ret.index)
        common = common[common != BENCHMARK]
        if len(common) < 5:
            continue

        s = month_scores[common]
        r = fwd_ret[common]

        if s.std() == 0 or r.std() == 0:
            continue

        ic, _ = spearmanr(s, r)
        if not np.isnan(ic):
            ic_values[date] = ic

    return pd.Series(ic_values, name=score_col).sort_index()


def analyse_ic(
    scorecard: pd.DataFrame,
    monthly_returns: pd.DataFrame,
    logger: logging.Logger,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run IC analysis for all signal blocks and composite.
    Returns: (ic_monthly_df, ic_summary_df)
    """
    score_cols = [
        "momentum_score",
        "trend_score",
        "regime_score",
        "composite_score",
    ]
    if "valuation_score" in scorecard.columns and scorecard["valuation_score"].notna().any():
        score_cols.insert(3, "valuation_score")

    ic_series = {}
    for col in score_cols:
        if col not in scorecard.columns:
            continue
        logger.info(f"  Computing IC for: {col}")
        ic = compute_ic_series(scorecard, monthly_returns, col)
        if len(ic) > 0:
            ic_series[col] = ic

    if not ic_series:
        logger.warning("No IC series computed — check scorecard history data.")
        return pd.DataFrame(), pd.DataFrame()

    # Monthly IC DataFrame
    ic_df = pd.DataFrame(ic_series)
    ic_df.index.name = "date"

    # Rolling 12-month IC
    for col in ic_df.columns:
        ic_df[f"{col}_roll12"] = ic_df[col].rolling(12).mean()

    # IC Summary
    summary_rows = []
    for col in score_cols:
        if col not in ic_df.columns:
            continue
        ic_col = ic_df[col].dropna()
        if len(ic_col) < 3:
            continue

        ic_mean  = ic_col.mean()
        ic_std   = ic_col.std()
        ic_ir    = ic_mean / ic_std if ic_std > 0 else np.nan
        hit_rate = (ic_col > 0).mean()
        t_stat, p_val = ttest_1samp(ic_col, 0)

        meets_mean  = "✓" if ic_mean >= IC_MEAN_TARGET else "✗"
        meets_ir    = "✓" if (not np.isnan(ic_ir) and ic_ir >= IC_IR_TARGET) else "✗"

        summary_rows.append({
            "signal":           col.replace("_score", "").replace("_", " ").title(),
            "ic_mean":          round(ic_mean, 4),
            "ic_std":           round(ic_std, 4),
            "ic_ir":            round(ic_ir, 3) if not np.isnan(ic_ir) else np.nan,
            "hit_rate":         round(hit_rate, 3),
            "t_stat":           round(t_stat, 2),
            "p_value":          round(p_val, 4),
            "n_months":         len(ic_col),
            "target_mean_0.05": meets_mean,
            "target_ir_0.30":   meets_ir,
        })

    summary_df = pd.DataFrame(summary_rows)
    logger.info(f"IC analysis complete: {len(summary_df)} signals analysed")
    return ic_df, summary_df


# ═══════════════════════════════════════════════════════════════════════════════
#  MODULE B — PORTFOLIO PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════

def simulate_portfolio(
    scorecard: pd.DataFrame,
    monthly_returns: pd.DataFrame,
    top_n: int,
    round_trip_bps: int,
    logger: logging.Logger,
) -> pd.DataFrame:
    """
    Simulate the top-N sector equal-weight portfolio.

    At each month-end:
      1. Take the top-N indices by composite_score (excluding benchmark indices)
      2. Equal-weight them
      3. Measure their return over the next calendar month
      4. Deduct transaction costs for sectors that changed vs prior month

    Returns a DataFrame with columns:
      date, portfolio_return, benchmark_return, active_return,
      portfolio_return_net (after costs), sectors_held, sectors_changed, turnover
    """
    round_trip_cost = round_trip_bps / 10000

    # Indices that are benchmarks (excluded from rotation portfolio)
    benchmark_indices = {"NIFTY 50", "NIFTY 500"}

    dates_scored    = sorted(scorecard["as_of"].unique())
    prev_sectors    = set()
    portfolio_rows  = []

    for date in dates_scored:
        date = pd.Timestamp(date)

        # Get scores for this month, exclude reference indices
        month_sc = scorecard[scorecard["as_of"] == date].copy()
        month_sc = month_sc[~month_sc["index_name"].isin(benchmark_indices)]
        month_sc = month_sc.dropna(subset=["composite_score"])
        month_sc = month_sc.sort_values("composite_score", ascending=False)

        # Check we have enough indices
        if len(month_sc) < top_n:
            continue

        selected = set(month_sc.head(top_n)["index_name"].tolist())

        # Forward returns
        fwd_ret = forward_return(monthly_returns, date, horizon=1)
        if fwd_ret.empty:
            continue

        # Portfolio return (equal weight)
        available = [s for s in selected if s in fwd_ret.index]
        if len(available) == 0:
            continue

        port_ret = fwd_ret[available].mean()

        # Benchmark return
        bench_ret = fwd_ret.get(BENCHMARK, np.nan)

        # Active return
        active_ret = port_ret - bench_ret

        # Turnover and transaction costs
        if prev_sectors:
            changed  = len(selected.symmetric_difference(prev_sectors))
            turnover = changed / top_n
        else:
            changed  = top_n
            turnover = 1.0

        # Cost: pay round_trip for each sector that changed
        cost = (changed / top_n) * round_trip_cost
        port_ret_net = port_ret - cost

        portfolio_rows.append({
            "date":                  date,
            "portfolio_return":      port_ret,
            "portfolio_return_net":  port_ret_net,
            "benchmark_return":      bench_ret,
            "active_return":         port_ret - bench_ret,
            "active_return_net":     port_ret_net - bench_ret,
            "sectors_held":          "|".join(sorted(selected)),
            "sectors_changed":       changed,
            "turnover":              round(turnover, 3),
            "cost_deducted":         round(cost * 10000, 1),   # in bps
        })

        prev_sectors = selected

    port_df = pd.DataFrame(portfolio_rows)
    if not port_df.empty:
        port_df.sort_values("date", inplace=True)
        port_df.reset_index(drop=True, inplace=True)
        logger.info(
            f"Portfolio simulation: {len(port_df)} months, "
            f"avg turnover: {port_df['turnover'].mean():.2f} sectors/month"
        )
    return port_df


def compute_performance_metrics(
    port_df: pd.DataFrame,
    use_net: bool = True,
    label: str = "Full Period",
) -> dict:
    """
    Compute annualised performance metrics from the monthly portfolio return series.
    """
    if port_df.empty or len(port_df) < 3:
        return {}

    ret_col   = "portfolio_return_net" if use_net else "portfolio_return"
    bench_col = "benchmark_return"

    port_rets  = port_df[ret_col].dropna()
    bench_rets = port_df[bench_col].dropna()
    active_col = "active_return_net" if use_net else "active_return"
    act_rets   = port_df[active_col].dropna()

    n = len(port_rets)
    if n < 3:
        return {}

    # Annualised return
    ann_port  = (1 + port_rets).prod() ** (12 / n) - 1
    ann_bench = (1 + bench_rets).prod() ** (12 / n) - 1
    ann_alpha = ann_port - ann_bench

    # Sharpe (monthly risk-free ≈ 0 for relative comparison)
    sharpe = (port_rets.mean() / port_rets.std()) * np.sqrt(12) if port_rets.std() > 0 else np.nan

    # Information Ratio
    ir = (act_rets.mean() / act_rets.std()) * np.sqrt(12) if act_rets.std() > 0 else np.nan

    # Max Drawdown
    cum_returns = (1 + port_rets).cumprod()
    rolling_max = cum_returns.cummax()
    drawdown    = (cum_returns - rolling_max) / rolling_max
    max_dd      = drawdown.min()

    # Hit Rate — months portfolio beats benchmark
    hit_rate = (act_rets > 0).mean()

    # Average turnover
    avg_turnover = port_df["turnover"].mean() if "turnover" in port_df else np.nan

    # Avg monthly cost in bps
    avg_cost_bps = port_df["cost_deducted"].mean() if "cost_deducted" in port_df else np.nan

    return {
        "period":          label,
        "n_months":        n,
        "ann_return_port": round(ann_port * 100, 2),
        "ann_return_bench": round(ann_bench * 100, 2),
        "ann_alpha":       round(ann_alpha * 100, 2),
        "sharpe":          round(sharpe, 3) if not np.isnan(sharpe) else np.nan,
        "info_ratio":      round(ir, 3)     if not np.isnan(ir) else np.nan,
        "max_drawdown":    round(max_dd * 100, 2),
        "hit_rate":        round(hit_rate * 100, 1),
        "avg_turnover":    round(avg_turnover, 2),
        "avg_cost_bps":    round(avg_cost_bps, 1),
        # Target checks
        "alpha_target_4pct":    "✓" if ann_alpha >= TARGET_ALPHA else "✗",
        "sharpe_target_0.8":    "✓" if (not np.isnan(sharpe) and sharpe >= TARGET_SHARPE) else "✗",
        "dd_target_lt25pct":    "✓" if abs(max_dd) <= TARGET_DRAWDOWN else "✗",
        "hit_rate_target_55pct":"✓" if hit_rate >= TARGET_HIT_RATE else "✗",
        "turnover_target_lt1.5":"✓" if avg_turnover <= TARGET_TURNOVER else "✗",
    }


def compute_drawdown_series(port_df: pd.DataFrame) -> pd.DataFrame:
    """Return rolling drawdown series for portfolio and benchmark."""
    if port_df.empty:
        return pd.DataFrame()

    rows = []
    for col, label in [
        ("portfolio_return_net", "portfolio"),
        ("benchmark_return",     "benchmark"),
    ]:
        if col not in port_df.columns:
            continue
        rets = port_df.set_index("date")[col].dropna()
        cum  = (1 + rets).cumprod()
        peak = cum.cummax()
        dd   = (cum - peak) / peak
        for date, val in dd.items():
            rows.append({"date": date, "series": label, "drawdown": round(val * 100, 3)})

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
#  EXPANDING WINDOW WALK-FORWARD
# ═══════════════════════════════════════════════════════════════════════════════

def run_walk_forward(
    scorecard: pd.DataFrame,
    monthly_returns: pd.DataFrame,
    top_n: int,
    round_trip_bps: int,
    logger: logging.Logger,
) -> list[dict]:
    """
    Run the three expanding-window test periods defined in the strategy document.
    Returns a list of performance metric dicts — one per window.
    """
    wf_results = []

    for train_start, train_end, test_start, test_end in WALK_FORWARD_WINDOWS:
        logger.info(
            f"  Walk-forward: train {train_start}→{train_end} | "
            f"test {test_start}→{test_end}"
        )

        # Filter scorecard to test period
        test_mask = (
            (scorecard["as_of"] >= pd.Timestamp(test_start)) &
            (scorecard["as_of"] <= pd.Timestamp(test_end))
        )
        sc_test = scorecard[test_mask]

        if sc_test.empty:
            logger.warning(f"    No scorecard data for test period {test_start}→{test_end}")
            continue

        port_df = simulate_portfolio(sc_test, monthly_returns, top_n, round_trip_bps, logger)
        if port_df.empty:
            continue

        label = f"OOS {test_start[:4]}"
        metrics = compute_performance_metrics(port_df, use_net=True, label=label)
        wf_results.append(metrics)
        logger.info(
            f"    Alpha: {metrics.get('ann_alpha', 'N/A')}%  "
            f"Sharpe: {metrics.get('sharpe', 'N/A')}  "
            f"MaxDD: {metrics.get('max_drawdown', 'N/A')}%"
        )

    return wf_results


# ═══════════════════════════════════════════════════════════════════════════════
#  MODULE C — REGIME-CONDITIONAL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def regime_conditional_analysis(
    port_df: pd.DataFrame,
    scorecard: pd.DataFrame,
    logger: logging.Logger,
) -> pd.DataFrame:
    """
    Break portfolio performance down by India macro regime stage (1–5).
    Validates: outperformance in Stages 1–2, defence in Stages 4–5.
    """
    if port_df.empty or "date" not in port_df.columns:
        return pd.DataFrame()

    # Map each portfolio month to a regime stage
    stage_map = (
        scorecard[["as_of", "regime_stage"]]
        .drop_duplicates("as_of")
        .set_index("as_of")["regime_stage"]
        .to_dict()
    )

    port_df = port_df.copy()
    port_df["regime_stage"] = port_df["date"].map(stage_map)
    port_df.dropna(subset=["regime_stage"], inplace=True)

    stage_labels = {
        1: "Early Expansion",
        2: "Mid Expansion",
        3: "Late Expansion",
        4: "Early Contraction",
        5: "Deep Contraction",
    }

    rows = []
    for stage in sorted(port_df["regime_stage"].unique()):
        grp = port_df[port_df["regime_stage"] == stage]
        metrics = compute_performance_metrics(
            grp, use_net=True, label=f"Stage {int(stage)}: {stage_labels.get(int(stage), '')}"
        )
        metrics["regime_stage"]   = int(stage)
        metrics["regime_label"]   = stage_labels.get(int(stage), "")
        metrics["expected_edge"]  = "Strong outperform" if stage in (1, 2) else \
                                    "Defensive"        if stage in (4, 5) else \
                                    "Moderate"
        rows.append(metrics)

    regime_df = pd.DataFrame(rows)
    logger.info(f"Regime analysis: {len(regime_df)} stages with data")
    return regime_df


# ═══════════════════════════════════════════════════════════════════════════════
#  REPORT BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_report(
    ic_summary:   pd.DataFrame,
    ic_monthly:   pd.DataFrame,
    perf_summary: list[dict],
    wf_results:   list[dict],
    regime_df:    pd.DataFrame,
    top_n:        int,
    round_trip_bps: int,
) -> str:
    buf = StringIO()

    def line(char="─", width=72):
        buf.write(char * width + "\n")

    def h1(title):
        buf.write("\n")
        line("═")
        buf.write(f"  {title}\n")
        line("═")

    def h2(title):
        buf.write(f"\n  {title}\n")
        line("─")

    buf.write("\n")
    buf.write("  INDIA SECTOR ROTATION — BACKTEST REPORT\n")
    buf.write(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    buf.write(f"  Top-N sectors: {top_n}  |  Round-trip cost: {round_trip_bps}bps\n")

    # ── IC Analysis ────────────────────────────────────────────────────────────
    h1("MODULE A — SIGNAL QUALITY (IC ANALYSIS)")
    h2("IC Targets:  IC Mean > 0.05   |   IC IR > 0.30")

    if not ic_summary.empty:
        cols = ["signal", "ic_mean", "ic_std", "ic_ir", "hit_rate",
                "n_months", "target_mean_0.05", "target_ir_0.30"]
        cols = [c for c in cols if c in ic_summary.columns]
        buf.write("\n")
        buf.write(f"  {'Signal':<20} {'IC Mean':>8} {'IC Std':>8} {'IC IR':>7} "
                  f"{'Hit Rate':>9} {'Months':>7} {'Mean✓':>6} {'IR✓':>5}\n")
        line()
        for _, row in ic_summary.iterrows():
            ir_str   = f"{row['ic_ir']:7.3f}"   if pd.notna(row.get('ic_ir'))   else "    N/A"
            buf.write(
                f"  {str(row.get('signal','')):<20} "
                f"{row.get('ic_mean', 0):8.4f} "
                f"{row.get('ic_std', 0):8.4f} "
                f"{ir_str} "
                f"{row.get('hit_rate', 0):9.3f} "
                f"{row.get('n_months', 0):7.0f} "
                f"{str(row.get('target_mean_0.05','')): >6} "
                f"{str(row.get('target_ir_0.30','')): >5}\n"
            )
    else:
        buf.write("\n  [No IC data available — run with scorecard history]\n")

    # ── Walk-Forward OOS ───────────────────────────────────────────────────────
    h1("MODULE B — PORTFOLIO PERFORMANCE")
    h2("Walk-Forward Out-of-Sample Results")

    all_perf = (wf_results or []) + (perf_summary or [])
    if all_perf:
        buf.write(
            f"\n  {'Period':<25} {'Ann Ret%':>8} {'Bench%':>7} {'Alpha%':>7} "
            f"{'Sharpe':>7} {'MaxDD%':>7} {'Hit%':>6} {'Turn':>5} "
            f"  α✓  Sh✓  DD✓  HR✓  Tv✓\n"
        )
        line()
        for m in all_perf:
            if not m:
                continue
            buf.write(
                f"  {str(m.get('period','')):<25} "
                f"{m.get('ann_return_port', 0):8.1f} "
                f"{m.get('ann_return_bench', 0):7.1f} "
                f"{m.get('ann_alpha', 0):7.1f} "
                f"{m.get('sharpe', 0):7.3f} "
                f"{m.get('max_drawdown', 0):7.1f} "
                f"{m.get('hit_rate', 0):6.1f} "
                f"{m.get('avg_turnover', 0):5.2f}  "
                f"  {m.get('alpha_target_4pct','?'):>2} "
                f" {m.get('sharpe_target_0.8','?'):>2} "
                f" {m.get('dd_target_lt25pct','?'):>2} "
                f" {m.get('hit_rate_target_55pct','?'):>2} "
                f" {m.get('turnover_target_lt1.5','?'):>2}\n"
            )
        buf.write("\n  Targets: Alpha >4% | Sharpe >0.8 | MaxDD <25% | Hit >55% | Turnover <1.5\n")
    else:
        buf.write("\n  [No portfolio performance data available]\n")

    # ── Regime Conditional ────────────────────────────────────────────────────
    h1("MODULE C — REGIME-CONDITIONAL ANALYSIS")
    h2("Performance by India Macro Regime Stage")

    if not regime_df.empty:
        buf.write(
            f"\n  {'Stage & Label':<34} {'Alpha%':>7} {'Sharpe':>7} "
            f"{'Hit%':>6} {'Months':>7}  {'Expected Edge':<20}\n"
        )
        line()
        for _, row in regime_df.iterrows():
            stage_label = f"Stage {row.get('regime_stage','')} — {row.get('regime_label','')}"
            buf.write(
                f"  {stage_label:<34} "
                f"{row.get('ann_alpha', 0):7.1f} "
                f"{row.get('sharpe', 0):7.3f} "
                f"{row.get('hit_rate', 0):6.1f} "
                f"{row.get('n_months', 0):7.0f}  "
                f"{row.get('expected_edge',''):<20}\n"
            )

        # Validation narrative
        buf.write("\n  Interpretation:\n")
        exp_stages = regime_df[regime_df["regime_stage"].isin([1, 2])]
        def_stages = regime_df[regime_df["regime_stage"].isin([4, 5])]

        if not exp_stages.empty:
            avg_alpha_exp = exp_stages["ann_alpha"].mean()
            buf.write(
                f"  · Expansion (Stages 1–2): avg alpha = {avg_alpha_exp:.1f}%  "
                f"{'[MEETS EXPECTATION]' if avg_alpha_exp > 0 else '[BELOW EXPECTATION]'}\n"
            )
        if not def_stages.empty:
            avg_alpha_def = def_stages["ann_alpha"].mean()
            buf.write(
                f"  · Contraction (Stages 4–5): avg alpha = {avg_alpha_def:.1f}%  "
                f"{'[DEFENSIVE POSITIONING OK]' if avg_alpha_def >= -2 else '[REGIME WEIGHT MAY NEED RECALIBRATION]'}\n"
            )
    else:
        buf.write("\n  [No regime data available — check regime_stage column in scorecard]\n")

    # ── Transaction Cost Analysis ─────────────────────────────────────────────
    h1("SUPPLEMENTARY — TRANSACTION COST ANALYSIS")
    buf.write(f"\n  Round-trip cost assumption : {round_trip_bps}bps per trade\n")
    buf.write(f"  Target turnover            : ≤{TARGET_TURNOVER} sectors/month\n")
    buf.write(f"  At target turnover, annual cost drag: "
              f"~{round_trip_bps * TARGET_TURNOVER * 12 / 100:.1f}%\n")
    buf.write(f"  Strategy doc target        : <3.6% for discretionary model\n")

    if all_perf:
        avg_turn = np.mean([m.get("avg_turnover", 0) for m in all_perf if m])
        avg_cost = avg_turn * round_trip_bps * 12 / 100
        buf.write(f"  Actual avg turnover        : {avg_turn:.2f} sectors/month\n")
        buf.write(f"  Implied annual cost drag   : ~{avg_cost:.1f}%\n")

    line("═")
    buf.write("  End of Report\n")
    line("═")
    buf.write("\n")

    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
#  EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def export(df: pd.DataFrame, output_dir: Path, name: str, logger: logging.Logger) -> None:
    if df is None or df.empty:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{name}.csv"
    df.to_csv(csv_path, index=False)
    logger.info(f"  Saved: {csv_path}")
    if name not in ("backtest_report",):
        try:
            df.to_parquet(output_dir / f"{name}.parquet", index=False)
        except Exception:
            pass   # parquet can fail on mixed-type columns; CSV is the primary output


def export_report(report_text: str, output_dir: Path, logger: logging.Logger) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "backtest_report.txt"
    with open(path, "w") as f:
        f.write(report_text)
    logger.info(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
#  SYNTHETIC DATA GENERATOR  (for standalone testing without real NSE data)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_synthetic_data(
    start: str = "2015-01-01",
    end:   str = "2024-12-31",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates synthetic price and scorecard data for testing/demo.
    Embeds a mild signal (composite score weakly predicts returns) to
    give realistic IC values.
    """
    np.random.seed(99)
    dates   = pd.bdate_range(start, end)
    indices = [
        "NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY FMCG", "NIFTY PHARMA",
        "NIFTY AUTO", "NIFTY METAL", "NIFTY REALTY", "NIFTY ENERGY", "NIFTY INFRA",
        "NIFTY MEDIA", "NIFTY FINANCIAL SERVICES", "NIFTY CONSUMER DURABLES",
        "NIFTY HEALTHCARE INDEX", "NIFTY OIL AND GAS",
    ]

    # Build correlated returns with a latent "true alpha" factor
    n_idx = len(indices)
    true_alpha = np.random.normal(0.0002, 0.0004, (len(dates), n_idx))

    close_data = {}
    for i, idx in enumerate(indices):
        market = np.random.normal(0.0003, 0.012, len(dates))
        idio   = np.random.normal(0, 0.008, len(dates))
        rets   = 0.6 * market + 0.2 * true_alpha[:, i] + 0.2 * idio
        close_data[idx] = 1000 * np.cumprod(1 + rets)

    close = pd.DataFrame(close_data, index=dates)

    # Build monthly scorecard with signal embedded
    month_ends = pd.date_range(start, end, freq="ME")
    rows = []
    stage_cycle = [1, 1, 2, 2, 2, 3, 3, 4, 4, 5, 5, 1]  # synthetic regime cycle

    for m_idx, me in enumerate(month_ends):
        # Find nearest trading day
        actual_date = close.index[close.index <= me].max() if (close.index <= me).any() else None
        if actual_date is None:
            continue

        stage = stage_cycle[m_idx % len(stage_cycle)]

        # Compute 3-month forward returns (proxy for "true" signal)
        future_dates = close.index[close.index > actual_date]
        if len(future_dates) < 63:
            continue
        fwd_price = close.loc[future_dates[62]]
        fwd_ret   = (fwd_price / close.loc[actual_date]) - 1

        for i, idx in enumerate(indices):
            # Add mild noise to forward return to create imperfect signal
            noisy_signal = fwd_ret[idx] + np.random.normal(0, 0.05)
            # Normalise cross-sectionally to 0–100
            composite = noisy_signal  # will be ranked below

            rows.append({
                "as_of":              actual_date,
                "regime_stage":       stage,
                "index_name":         idx,
                "momentum_score":     np.nan,
                "trend_score":        np.nan,
                "regime_score":       np.nan,
                "valuation_score":    np.nan,
                "composite_score":    composite,
            })

    sc_df = pd.DataFrame(rows)

    # Cross-sectionally rank composite to 0–100 per month (vectorised to avoid apply issues)
    sc_df["composite_score"] = (
        sc_df.groupby("as_of")["composite_score"]
        .rank(pct=True) * 100
    )
    sc_df.reset_index(drop=True, inplace=True)

    return close, sc_df


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Walk-forward backtest and signal validation for the sector rotation model."
    )
    parser.add_argument("--top-n",    type=int, default=DEFAULT_TOP_N, choices=[1,2,3,4,5],
                        help=f"Number of top sectors to hold. Default: {DEFAULT_TOP_N}")
    parser.add_argument("--start",   default=None,
                        help="Backtest start date (YYYY-MM-DD). Default: full history.")
    parser.add_argument("--cost-bps", type=int, default=ROUND_TRIP_BPS,
                        help=f"Round-trip transaction cost in bps. Default: {ROUND_TRIP_BPS}")
    parser.add_argument("--no-regime", action="store_true",
                        help="Skip Module C regime-conditional analysis.")
    parser.add_argument("--synthetic", action="store_true",
                        help="Use synthetic data (for testing without real NSE data).")
    parser.add_argument("--input-price-dir",  default=str(INPUT_PRICE_DIR))
    parser.add_argument("--input-score-dir",  default=str(INPUT_SCORE_DIR))
    parser.add_argument("--output-dir",       default=str(OUTPUT_DIR))
    args = parser.parse_args()

    logger      = setup_logging(LOG_DIR)
    output_dir  = Path(args.output_dir)

    # ── Load or generate data ──────────────────────────────────────────────────
    if args.synthetic:
        logger.info("Using SYNTHETIC data for testing")
        close, scorecard = generate_synthetic_data()
    else:
        close    = load_prices(Path(args.input_price_dir), logger)
        scorecard = load_scorecard_history(Path(args.input_score_dir), logger)

        if scorecard.empty:
            logger.warning(
                "No scorecard history found.\n"
                "To generate it:  python signal_engine.py --history\n"
                "Re-running with synthetic data for structure validation."
            )
            close, scorecard = generate_synthetic_data()

    # ── Apply start date filter ────────────────────────────────────────────────
    if args.start:
        start_ts  = pd.Timestamp(args.start)
        scorecard = scorecard[scorecard["as_of"] >= start_ts]
        close     = close[close.index >= start_ts]
        logger.info(f"Filtered to start: {args.start}")

    # ── Compute monthly returns ────────────────────────────────────────────────
    monthly_returns = compute_monthly_returns(close)

    # ── MODULE A: IC Analysis ──────────────────────────────────────────────────
    print(f"\n{CYAN}{'─'*60}")
    print("  MODULE A — IC ANALYSIS")
    print(f"{'─'*60}{RESET}")

    ic_monthly, ic_summary = analyse_ic(scorecard, monthly_returns, logger)

    # ── MODULE B: Portfolio Simulation ────────────────────────────────────────
    print(f"\n{CYAN}{'─'*60}")
    print(f"  MODULE B — PORTFOLIO SIMULATION (Top-{args.top_n})")
    print(f"{'─'*60}{RESET}")

    # Full-period simulation
    port_df = simulate_portfolio(
        scorecard, monthly_returns, args.top_n, args.cost_bps, logger
    )
    full_metrics = []
    if not port_df.empty:
        m = compute_performance_metrics(port_df, use_net=True, label="Full Period")
        full_metrics = [m]

    # Walk-forward OOS
    logger.info("Running walk-forward out-of-sample windows...")
    wf_results = run_walk_forward(
        scorecard, monthly_returns, args.top_n, args.cost_bps, logger
    )

    # Drawdown series
    dd_series = compute_drawdown_series(port_df)

    # ── MODULE C: Regime Conditional ─────────────────────────────────────────
    regime_df = pd.DataFrame()
    if not args.no_regime:
        print(f"\n{CYAN}{'─'*60}")
        print("  MODULE C — REGIME-CONDITIONAL ANALYSIS")
        print(f"{'─'*60}{RESET}")
        regime_df = regime_conditional_analysis(port_df, scorecard, logger)

    # ── Build & print report ──────────────────────────────────────────────────
    all_perf = full_metrics + (wf_results or [])
    report   = build_report(
        ic_summary, ic_monthly, full_metrics, wf_results,
        regime_df, args.top_n, args.cost_bps
    )
    print(report)

    # ── Export ────────────────────────────────────────────────────────────────
    print(f"{CYAN}{'─'*60}")
    print("  EXPORTING RESULTS")
    print(f"{'─'*60}{RESET}")

    export(ic_monthly,  output_dir, "ic_analysis",          logger)
    export(ic_summary,  output_dir, "ic_summary",            logger)
    export(port_df,     output_dir, "portfolio_returns",     logger)

    if all_perf:
        export(pd.DataFrame(all_perf), output_dir, "performance_summary", logger)

    export(dd_series,   output_dir, "drawdown_series",       logger)
    export(regime_df,   output_dir, "regime_performance",    logger)
    export_report(report, output_dir, logger)

    logger.info("Backtest complete.")


if __name__ == "__main__":
    main()
