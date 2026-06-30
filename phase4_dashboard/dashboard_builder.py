"""
phase4_dashboard/dashboard_builder.py
=======================================
Phase 4: Master Excel Dashboard Generator
India Sector Rotation Strategy

Output: Excel workbook with five tabs:
  1. MACRO SCORECARD   — 10 macro indicators, composite score, regime stage
  2. SECTOR SIGNALS    — Ranked scorecard with Green / Amber / Red traffic lights
  3. PORTFOLIO         — Current holdings vs signal recommendations
  4. OVERRIDES         — India-specific flags (FII, INR, Monsoon, Calendar)
  5. BACKTEST          — IC analysis, walk-forward performance, regime breakdown

USAGE
------
  python dashboard_builder.py                        # use latest data files
  python dashboard_builder.py --synthetic            # demo mode (no NSE data needed)
  python dashboard_builder.py --macro-stage 2        # set current regime stage
  python dashboard_builder.py --top-n 5              # top-5 sectors in Portfolio tab
  python dashboard_builder.py --output my_dash.xlsx  # custom output path

DEPENDENCIES
  pip install openpyxl pandas numpy scipy
"""

import argparse
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, LineChart, Reference
except ImportError:
    print("ERROR: openpyxl not found.  Run:  pip install openpyxl")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  PATHS
# ═══════════════════════════════════════════════════════════════════════════════

ROOT_DIR       = Path(__file__).resolve().parent.parent
PROCESSED_DIR  = ROOT_DIR / "data" / "processed"
BACKTEST_DIR   = ROOT_DIR / "data" / "backtest"
LOG_DIR        = ROOT_DIR / "logs"
DEFAULT_OUTPUT = ROOT_DIR / "India_Sector_Rotation_Dashboard.xlsx"


# ═══════════════════════════════════════════════════════════════════════════════
#  COLOUR PALETTE  (openpyxl uses ARGB hex without '#')
# ═══════════════════════════════════════════════════════════════════════════════

C_NAVY      = "FF1F3864"
C_BLUE      = "FF2E75B6"
C_LIGHT     = "FFD6E4F0"
C_WHITE     = "FFFFFFFF"
C_BLACK     = "FF000000"
C_GREEN     = "FF00B050"
C_AMBER     = "FFFFC000"
C_RED       = "FFFF0000"
C_GREEN_TXT = "FF006400"
C_AMBER_TXT = "FF7F5F00"
C_RED_TXT   = "FF8B0000"
C_GREY      = "FFF2F2F2"
C_DARK_GREY = "FFD9D9D9"

SIGNAL_GREEN = 65
SIGNAL_AMBER = 40

STAGE_LABELS = {
    1: "Stage 1 — Early Expansion",
    2: "Stage 2 — Mid Expansion",
    3: "Stage 3 — Late Expansion / Transition",
    4: "Stage 4 — Early Contraction",
    5: "Stage 5 — Deep Contraction",
}

STAGE_PLAYBOOK = {
    1: "Overweight: Banks, Auto, Infra, Realty, Fin Services | Underweight: FMCG, Pharma",
    2: "Overweight: IT, Metal, Energy, Consumer Durables | Balanced on Banks | Reduce Defensive",
    3: "Overweight: Energy, IT, Metal | Reduce Cyclicals | Start adding Pharma/Healthcare",
    4: "Overweight: FMCG, Pharma, Healthcare | Reduce Banks, Auto, Realty",
    5: "Overweight: FMCG, Pharma, Rural Index | Minimal cyclical exposure",
}

MACRO_INDICATORS = [
    ("IIP (Industrial Production MoM%)",     ">3%: +1  |  −1 to 3%: 0  |  <−1%: −1"),
    ("PMI Manufacturing",                    ">52: +1  |  50–52: 0  |  <50: −1"),
    ("PMI Services",                         ">54: +1  |  52–54: 0  |  <52: −1"),
    ("RBI Repo Rate (direction)",            "Falling/Hold: +1  |  Hiking: −1  |  Neutral: 0"),
    ("Yield Spread (10yr − 3m T-Bill)",     ">1.5%: +1  |  0–1.5%: 0  |  <0% (inverted): −1"),
    ("Bank Credit Growth (YoY%)",            ">15%: +1  |  10–15%: 0  |  <10%: −1"),
    ("CPI Inflation",                        "<4.5%: +1  |  4.5–6%: 0  |  >6%: −1"),
    ("FII Net Flows (USD mn, 30d rolling)",  "Positive: +1  |  Small/zero: 0  |  Outflow: −1"),
    ("GST Collections (YoY%)",               ">12%: +1  |  6–12%: 0  |  <6%: −1"),
    ("INR/USD (trend)",                      "Stable/appreciating: +1  |  Depreciating: −1  |  Volatile: 0"),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    fmt = "%(asctime)s | %(levelname)-8s | %(message)s"
    logging.basicConfig(
        level=logging.INFO, format=fmt,
        handlers=[
            logging.FileHandler(LOG_DIR / f"dashboard_{ts}.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("dashboard_builder")


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _fill(c: str) -> PatternFill:
    return PatternFill("solid", fgColor=c)


def _font(bold=False, color=C_BLACK, size=10, italic=False) -> Font:
    return Font(bold=bold, color=color, size=size, italic=italic)


def _border(style="thin", color="FFB8B8B8") -> Border:
    s = Side(border_style=style, color=color)
    return Border(left=s, right=s, top=s, bottom=s)


def _align(h="left", v="center", wrap=False) -> Alignment:
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


def _hdr(ws, r, c, val, bg=C_NAVY, fg=C_WHITE, bold=True, sz=10, h_align="center", wrap=False):
    cell = ws.cell(row=r, column=c, value=val)
    cell.fill    = _fill(bg)
    cell.font    = _font(bold=bold, color=fg, size=sz)
    cell.alignment = _align(h_align, "center", wrap)
    cell.border  = _border()
    return cell


def _dat(ws, r, c, val, bg=None, bold=False, h_align="left", fmt=None, fg=C_BLACK, wrap=False):
    cell = ws.cell(row=r, column=c, value=val)
    if bg:
        cell.fill = _fill(bg)
    cell.font      = _font(bold=bold, color=fg, size=10)
    cell.alignment = _align(h_align, "center", wrap)
    cell.border    = _border()
    if fmt:
        cell.number_format = fmt
    return cell


def _title_block(ws, row: int, title: str, subtitle: str, ncols: int):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=title)
    c.fill = _fill(C_NAVY); c.font = _font(bold=True, color=C_WHITE, size=14)
    c.alignment = _align("center", "center")
    ws.row_dimensions[row].height = 30

    ws.merge_cells(start_row=row+1, start_column=1, end_row=row+1, end_column=ncols)
    c2 = ws.cell(row=row+1, column=1, value=subtitle)
    c2.fill = _fill(C_BLUE); c2.font = _font(color=C_WHITE, size=10, italic=True)
    c2.alignment = _align("center", "center")
    ws.row_dimensions[row+1].height = 16


def _signal_style(score: float):
    if score >= SIGNAL_GREEN:
        return C_GREEN, C_WHITE, "BUY"
    elif score >= SIGNAL_AMBER:
        return C_AMBER, C_AMBER_TXT, "HOLD"
    else:
        return C_RED, C_WHITE, "AVOID"


def _col_w(ws, col: int, width: float):
    ws.column_dimensions[get_column_letter(col)].width = width


def _row_h(ws, row: int, height: float):
    ws.row_dimensions[row].height = height


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA LOADERS
# ═══════════════════════════════════════════════════════════════════════════════

def load_scorecard(logger: logging.Logger) -> pd.DataFrame | None:
    for ext in ("parquet", "csv"):
        p = PROCESSED_DIR / f"scorecard_latest.{ext}"
        if p.exists():
            df = pd.read_parquet(p) if ext == "parquet" else pd.read_csv(p)
            logger.info(f"Loaded scorecard: {len(df)} rows from {p}")
            return df
    logger.warning("scorecard_latest not found — will use synthetic data")
    return None


def load_backtest(logger: logging.Logger) -> dict:
    result = {}
    files = {
        "ic_summary":       "ic_summary",
        "perf_summary":     "performance_summary",
        "regime_perf":      "regime_performance",
        "portfolio":        "portfolio_returns",
        "drawdown":         "drawdown_series",
    }
    for key, name in files.items():
        for ext in ("parquet", "csv"):
            p = BACKTEST_DIR / f"{name}.{ext}"
            if p.exists():
                df = pd.read_parquet(p) if ext == "parquet" else pd.read_csv(p)
                result[key] = df
                logger.info(f"Loaded {name}: {len(df)} rows")
                break
        else:
            result[key] = pd.DataFrame()
    return result


def generate_synthetic_scorecard(regime_stage: int = 2) -> pd.DataFrame:
    """Create a plausible synthetic scorecard for demo purposes."""
    np.random.seed(42)
    indices = [
        "NIFTY BANK", "NIFTY AUTO", "NIFTY IT", "NIFTY FMCG", "NIFTY PHARMA",
        "NIFTY METAL", "NIFTY REALTY", "NIFTY ENERGY", "NIFTY INFRA", "NIFTY MEDIA",
        "NIFTY FINANCIAL SERVICES", "NIFTY CONSUMER DURABLES", "NIFTY HEALTHCARE INDEX",
        "NIFTY OIL AND GAS", "NIFTY PSU BANK", "NIFTY PRIVATE BANK",
        "NIFTY INDIA DEFENCE", "NIFTY INDIA MANUFACTURING", "NIFTY INDIA CONSUMPTION",
        "NIFTY CAPITAL MARKETS", "NIFTY HOUSING", "NIFTY TRANSPORT & LOGISTICS",
        "NIFTY COMMODITIES", "NIFTY MOBILITY", "NIFTY MIDCAP 150",
        "NIFTY SMALLCAP 250", "NIFTY TOTAL MARKET", "NIFTY LARGE MIDCAP 250",
    ]

    regime_map = {
        "NIFTY BANK": [100, 100, 50, 0, 0],
        "NIFTY AUTO": [100, 100, 50, 0, 0],
        "NIFTY IT": [50, 100, 100, 50, 50],
        "NIFTY FMCG": [0, 50, 50, 100, 100],
        "NIFTY PHARMA": [0, 50, 50, 100, 100],
        "NIFTY METAL": [50, 100, 100, 0, 0],
        "NIFTY REALTY": [100, 100, 50, 0, 0],
        "NIFTY ENERGY": [50, 50, 100, 50, 50],
        "NIFTY INFRA": [100, 100, 50, 0, 0],
        "NIFTY MEDIA": [0, 50, 50, 50, 0],
        "NIFTY FINANCIAL SERVICES": [100, 100, 50, 0, 0],
        "NIFTY CONSUMER DURABLES": [50, 100, 50, 0, 0],
        "NIFTY HEALTHCARE INDEX": [0, 50, 50, 100, 100],
        "NIFTY OIL AND GAS": [50, 50, 100, 50, 50],
        "NIFTY PSU BANK": [100, 100, 50, 0, 0],
        "NIFTY PRIVATE BANK": [100, 100, 50, 0, 0],
        "NIFTY INDIA DEFENCE": [100, 100, 50, 50, 50],
        "NIFTY INDIA MANUFACTURING": [100, 100, 50, 0, 0],
        "NIFTY INDIA CONSUMPTION": [50, 100, 50, 50, 50],
        "NIFTY CAPITAL MARKETS": [100, 100, 50, 0, 0],
        "NIFTY HOUSING": [100, 100, 50, 0, 0],
        "NIFTY TRANSPORT & LOGISTICS": [100, 100, 50, 0, 0],
        "NIFTY COMMODITIES": [50, 100, 100, 0, 0],
        "NIFTY MOBILITY": [100, 100, 50, 0, 0],
        "NIFTY MIDCAP 150": [50, 100, 50, 0, 0],
        "NIFTY SMALLCAP 250": [50, 100, 50, 0, 0],
        "NIFTY TOTAL MARKET": [50, 100, 50, 50, 50],
        "NIFTY LARGE MIDCAP 250": [50, 100, 50, 50, 50],
    }

    rows = []
    for idx in indices:
        mom  = round(np.random.uniform(20, 95), 1)
        trd  = round(np.random.uniform(20, 95), 1)
        reg  = float(regime_map.get(idx, [50]*5)[regime_stage - 1])
        val  = round(np.random.uniform(20, 85), 1)
        comp = round(0.35*mom + 0.20*trd + 0.30*reg + 0.15*val, 1)
        rows.append({
            "index_name":      idx,
            "momentum_score":  mom,
            "trend_score":     trd,
            "regime_score":    reg,
            "valuation_score": val,
            "composite_score": comp,
            "regime_stage":    regime_stage,
        })

    df = pd.DataFrame(rows).sort_values("composite_score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    return df


def generate_synthetic_backtest() -> dict:
    """Generate synthetic backtest data for demo mode."""
    from scipy.stats import spearmanr

    np.random.seed(42)
    months = pd.date_range("2015-01-31", "2024-12-31", freq="ME")

    # IC series
    ic_monthly = pd.DataFrame({
        "date":              months,
        "momentum_score":    np.random.normal(0.07, 0.12, len(months)),
        "trend_score":       np.random.normal(0.05, 0.14, len(months)),
        "regime_score":      np.random.normal(0.09, 0.11, len(months)),
        "composite_score":   np.random.normal(0.11, 0.10, len(months)),
    })

    ic_summary = []
    for col in ["momentum_score", "trend_score", "regime_score", "composite_score"]:
        vals = ic_monthly[col]
        mu = vals.mean(); sd = vals.std()
        ir = mu / sd if sd > 0 else np.nan
        from scipy.stats import ttest_1samp
        t, p = ttest_1samp(vals, 0)
        ic_summary.append({
            "signal":            col.replace("_score","").replace("_"," ").title(),
            "ic_mean":           round(mu, 4),
            "ic_std":            round(sd, 4),
            "ic_ir":             round(ir, 3) if not np.isnan(ir) else np.nan,
            "hit_rate":          round((vals > 0).mean(), 3),
            "t_stat":            round(t, 2),
            "p_value":           round(p, 4),
            "n_months":          len(vals),
            "target_mean_0.05":  "✓" if mu >= 0.05 else "✗",
            "target_ir_0.30":    "✓" if (not np.isnan(ir) and ir >= 0.30) else "✗",
        })

    perf_summary = [
        {"period": "Full Period", "n_months": 120, "ann_return_port": 16.8,
         "ann_return_bench": 12.1, "ann_alpha": 4.7, "sharpe": 0.91,
         "info_ratio": 0.62, "max_drawdown": -21.3, "hit_rate": 58.3,
         "avg_turnover": 1.2, "avg_cost_bps": 10.8,
         "alpha_target_4pct": "✓", "sharpe_target_0.8": "✓",
         "dd_target_lt25pct": "✓", "hit_rate_target_55pct": "✓",
         "turnover_target_lt1.5": "✓"},
        {"period": "OOS 2016", "n_months": 12, "ann_return_port": 18.2,
         "ann_return_bench": 13.5, "ann_alpha": 4.7, "sharpe": 1.05,
         "info_ratio": 0.71, "max_drawdown": -12.1, "hit_rate": 63.6,
         "avg_turnover": 0.9, "avg_cost_bps": 8.1,
         "alpha_target_4pct": "✓", "sharpe_target_0.8": "✓",
         "dd_target_lt25pct": "✓", "hit_rate_target_55pct": "✓",
         "turnover_target_lt1.5": "✓"},
        {"period": "OOS 2021", "n_months": 12, "ann_return_port": 38.1,
         "ann_return_bench": 24.1, "ann_alpha": 14.0, "sharpe": 1.82,
         "info_ratio": 1.15, "max_drawdown": -9.8, "hit_rate": 72.7,
         "avg_turnover": 1.3, "avg_cost_bps": 11.7,
         "alpha_target_4pct": "✓", "sharpe_target_0.8": "✓",
         "dd_target_lt25pct": "✓", "hit_rate_target_55pct": "✓",
         "turnover_target_lt1.5": "✓"},
        {"period": "OOS 2024", "n_months": 12, "ann_return_port": 14.2,
         "ann_return_bench": 11.1, "ann_alpha": 3.1, "sharpe": 0.74,
         "info_ratio": 0.48, "max_drawdown": -18.6, "hit_rate": 50.0,
         "avg_turnover": 1.6, "avg_cost_bps": 14.4,
         "alpha_target_4pct": "✗", "sharpe_target_0.8": "✗",
         "dd_target_lt25pct": "✓", "hit_rate_target_55pct": "✗",
         "turnover_target_lt1.5": "✗"},
    ]

    regime_perf = [
        {"regime_stage": 1, "regime_label": "Early Expansion",
         "n_months": 22, "ann_alpha": 8.2, "sharpe": 1.21, "hit_rate": 68.2,
         "expected_edge": "Strong outperform"},
        {"regime_stage": 2, "regime_label": "Mid Expansion",
         "n_months": 34, "ann_alpha": 6.1, "sharpe": 1.08, "hit_rate": 64.7,
         "expected_edge": "Strong outperform"},
        {"regime_stage": 3, "regime_label": "Late Expansion",
         "n_months": 28, "ann_alpha": 2.3, "sharpe": 0.64, "hit_rate": 53.6,
         "expected_edge": "Moderate"},
        {"regime_stage": 4, "regime_label": "Early Contraction",
         "n_months": 24, "ann_alpha": 1.8, "sharpe": 0.41, "hit_rate": 54.2,
         "expected_edge": "Defensive"},
        {"regime_stage": 5, "regime_label": "Deep Contraction",
         "n_months": 12, "ann_alpha": 3.4, "sharpe": 0.58, "hit_rate": 58.3,
         "expected_edge": "Defensive"},
    ]

    # Portfolio returns
    bench_rets = np.random.normal(0.01, 0.04, len(months))
    port_rets  = bench_rets + np.random.normal(0.004, 0.015, len(months))
    portfolio  = pd.DataFrame({
        "date":                  months,
        "portfolio_return_net":  port_rets,
        "benchmark_return":      bench_rets,
    })
    portfolio["cum_port"]  = (1 + portfolio["portfolio_return_net"]).cumprod()
    portfolio["cum_bench"] = (1 + portfolio["benchmark_return"]).cumprod()

    return {
        "ic_summary":   pd.DataFrame(ic_summary),
        "perf_summary": pd.DataFrame(perf_summary),
        "regime_perf":  pd.DataFrame(regime_perf),
        "portfolio":    portfolio,
        "drawdown":     pd.DataFrame(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — MACRO SCORECARD
# ═══════════════════════════════════════════════════════════════════════════════

def build_tab_macro(wb: Workbook, as_of: str, regime_stage: int):
    ws = wb.create_sheet("1. Macro Scorecard")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"
    NCOLS = 5

    _title_block(ws, 1, "INDIA MACRO SCORECARD", f"As of: {as_of}  |  Update monthly", NCOLS)

    # ── Section header ─────────────────────────────────────────────────────────
    r = 4
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value="Step 1: Score each indicator  (+1 = Bullish | 0 = Neutral | −1 = Bearish)")
    c.fill = _fill(C_BLUE); c.font = _font(bold=True, color=C_WHITE, size=10)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 18)

    # Column headers
    r = 5
    headers = ["#", "Indicator", "Scoring Rule", "Current Value", "Score (+1/0/−1)"]
    widths  = [4,    38,           42,              18,              18]
    for ci, (h, w) in enumerate(zip(headers, widths), 1):
        _hdr(ws, r, ci, h)
        _col_w(ws, ci, w)
    _row_h(ws, r, 18)

    # Indicator rows
    for i, (name, rule) in enumerate(MACRO_INDICATORS):
        r = 6 + i
        bg = C_GREY if i % 2 == 0 else C_WHITE
        _dat(ws, r, 1, i + 1, bg=bg, h_align="center", bold=True)
        _dat(ws, r, 2, name, bg=bg)
        _dat(ws, r, 3, rule, bg=bg, wrap=True)
        _dat(ws, r, 4, None, bg=C_LIGHT)  # user fills in
        _dat(ws, r, 5, None, bg=C_LIGHT)  # user fills score
        _row_h(ws, r, 22)

    # Composite row
    r = 16
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    _hdr(ws, r, 1, "MACRO COMPOSITE SCORE  (average of 10 scores)", bg=C_NAVY, sz=11)
    _dat(ws, r, 4, "=AVERAGE(E6:E15)", bg=C_LIGHT, bold=True, h_align="center", fmt="0.00")
    _dat(ws, r, 5, None, bg=C_LIGHT)
    _row_h(ws, r, 22)

    # Regime stage
    r = 17
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    _hdr(ws, r, 1, "MACRO REGIME STAGE  (auto from composite)", bg=C_NAVY, sz=11)
    _dat(ws, r, 4, None, bg=C_LIGHT, bold=True, h_align="center")
    _dat(ws, r, 5, STAGE_LABELS.get(regime_stage, "—"), bg=C_GREEN, bold=True, fg=C_WHITE, h_align="center")
    _row_h(ws, r, 22)

    # Stage reference table
    r = 19
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value="Step 2: Regime → Sector Playbook")
    c.fill = _fill(C_BLUE); c.font = _font(bold=True, color=C_WHITE, size=10)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 18)

    r = 20
    _hdr(ws, r, 1, "Stage", bg=C_NAVY)
    _hdr(ws, r, 2, "Label", bg=C_NAVY)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=NCOLS)
    _hdr(ws, r, 3, "Sector Playbook", bg=C_NAVY)
    _row_h(ws, r, 18)

    for stage, label in STAGE_LABELS.items():
        r = 20 + stage
        playbook = STAGE_PLAYBOOK.get(stage, "")
        is_current = stage == regime_stage
        bg = C_GREEN if is_current else (C_GREY if stage % 2 == 0 else C_WHITE)
        fg = C_WHITE if is_current else C_BLACK
        _dat(ws, r, 1, stage, bg=bg, h_align="center", bold=is_current, fg=fg)
        _dat(ws, r, 2, label, bg=bg, bold=is_current, fg=fg)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=NCOLS)
        _dat(ws, r, 3, playbook, bg=bg, bold=is_current, fg=fg, wrap=True)
        _row_h(ws, r, 24)

    # Note
    r = 27
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    ws.cell(row=r, column=1, value=(
        "Note: Macro composite > 0.6 → Stage 2 | 0.2–0.6 → Stage 1 | −0.2 to 0.2 → Stage 3 "
        "| −0.6 to −0.2 → Stage 4 | < −0.6 → Stage 5"
    )).font = _font(italic=True, size=9, color="FF555555")
    _row_h(ws, r, 16)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — SECTOR SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

def build_tab_signals(wb: Workbook, scorecard: pd.DataFrame, as_of: str, regime_stage: int):
    ws = wb.create_sheet("2. Sector Signals")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A6"

    NCOLS = 9
    _title_block(ws, 1, "SECTOR SIGNAL SCORECARD", f"As of: {as_of}  |  Regime: {STAGE_LABELS.get(regime_stage, '—')}", NCOLS)

    # Legend row
    r = 3
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    _dat(ws, r, 1, "Traffic Light Legend:", bold=True, bg=C_WHITE)
    _dat(ws, r, 4, "BUY (Score ≥ 65)", bg=C_GREEN, fg=C_WHITE, bold=True, h_align="center")
    _dat(ws, r, 5, "HOLD (40–64)", bg=C_AMBER, fg=C_AMBER_TXT, bold=True, h_align="center")
    _dat(ws, r, 6, "AVOID (< 40)", bg=C_RED, fg=C_WHITE, bold=True, h_align="center")
    ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=NCOLS)
    ws.cell(row=r, column=7)
    _row_h(ws, r, 18)

    # Summary counts
    r = 4
    n_buy   = len(scorecard[scorecard["composite_score"] >= SIGNAL_GREEN])
    n_hold  = len(scorecard[(scorecard["composite_score"] >= SIGNAL_AMBER) &
                             (scorecard["composite_score"] < SIGNAL_GREEN)])
    n_avoid = len(scorecard[scorecard["composite_score"] < SIGNAL_AMBER])

    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    _dat(ws, r, 1, f"BUY: {n_buy}", bg=C_GREEN, fg=C_WHITE, bold=True, h_align="center")
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
    _dat(ws, r, 3, f"HOLD: {n_hold}", bg=C_AMBER, fg=C_AMBER_TXT, bold=True, h_align="center")
    ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=6)
    _dat(ws, r, 5, f"AVOID: {n_avoid}", bg=C_RED, fg=C_WHITE, bold=True, h_align="center")
    ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=NCOLS)
    _dat(ws, r, 7, f"Total: {len(scorecard)} indices scored", bg=C_GREY, h_align="left")
    _row_h(ws, r, 18)

    # Column headers
    r = 5
    cols    = ["Rank", "Index / Sector", "Momentum\n(35%)", "Trend\n(20%)",
               "Regime\n(30%)", "Valuation\n(15%)", "Composite\nScore", "Signal", "Traffic\nLight"]
    widths  = [6,       36,               12,               12,            12,
               12,       14,               10,                12]
    for ci, (h, w) in enumerate(zip(cols, widths), 1):
        _hdr(ws, r, ci, h, wrap=True)
        _col_w(ws, ci, w)
    _row_h(ws, r, 30)

    # Data rows
    for i, row in scorecard.iterrows():
        r = 6 + i
        comp  = float(row.get("composite_score", 50))
        bg_c, fg_c, sig_lbl = _signal_style(comp)
        row_bg = C_GREY if i % 2 == 0 else C_WHITE

        _dat(ws, r, 1, int(row.get("rank", i+1)), bg=row_bg, h_align="center", bold=True)
        _dat(ws, r, 2, str(row.get("index_name", "")), bg=row_bg)

        val_score = row.get("valuation_score")
        for ci, col_key in enumerate(["momentum_score","trend_score","regime_score"], 3):
            v = row.get(col_key)
            _dat(ws, r, ci, round(float(v), 1) if pd.notna(v) else "N/A",
                 bg=row_bg, h_align="center", fmt="0.0")

        _dat(ws, r, 6, round(float(val_score), 1) if pd.notna(val_score) else "N/A",
             bg=row_bg, h_align="center", fmt="0.0")
        _dat(ws, r, 7, round(comp, 1), bg=bg_c, fg=fg_c, bold=True, h_align="center", fmt="0.0")
        _dat(ws, r, 8, sig_lbl, bg=bg_c, fg=fg_c, bold=True, h_align="center")
        # Traffic light emoji column
        emoji = "🟢" if comp >= SIGNAL_GREEN else ("🟡" if comp >= SIGNAL_AMBER else "🔴")
        _dat(ws, r, 9, emoji, bg=bg_c, fg=fg_c, bold=True, h_align="center")
        _row_h(ws, r, 18)

    # Bar chart: composite scores (top 15 indices)
    chart_start_row = 6
    chart_end_row   = min(chart_start_row + len(scorecard) - 1, chart_start_row + 14)
    last_data_row   = 6 + len(scorecard) - 1

    chart = BarChart()
    chart.type    = "bar"
    chart.title   = "Composite Scores — Top Sectors"
    chart.y_axis.title = "Composite Score (0–100)"
    chart.height  = 14
    chart.width   = 22

    data_ref  = Reference(ws, min_col=7, min_row=5, max_row=chart_start_row + 14)
    cats_ref  = Reference(ws, min_col=2, min_row=6, max_row=chart_start_row + 14)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.series[0].graphicalProperties.solidFill = "2E75B6"

    anchor_col = get_column_letter(NCOLS + 1)
    ws.add_chart(chart, f"{anchor_col}5")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — PORTFOLIO
# ═══════════════════════════════════════════════════════════════════════════════

def build_tab_portfolio(wb: Workbook, scorecard: pd.DataFrame, as_of: str, top_n: int):
    ws = wb.create_sheet("3. Portfolio")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A5"
    NCOLS = 8

    _title_block(ws, 1, "PORTFOLIO vs SIGNALS", f"As of: {as_of}  |  Top-{top_n} rotation targets", NCOLS)

    # ── Top-N recommendations ──────────────────────────────────────────────────
    r = 3
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value=f"Signal-Recommended Portfolio  (Top {top_n} by Composite Score)")
    c.fill = _fill(C_BLUE); c.font = _font(bold=True, color=C_WHITE, size=10)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 18)

    r = 4
    rec_headers = ["Rank", "Sector", "Composite", "Signal", "Equal Weight%",
                   "Regime Alignment", "Momentum", "Trend"]
    rec_widths  = [6,      34,        12,          10,       14,
                   18,      10,        10]
    for ci, (h, w) in enumerate(zip(rec_headers, rec_widths), 1):
        _hdr(ws, r, ci, h)
        _col_w(ws, ci, w)
    _row_h(ws, r, 18)

    # Exclude reference indices from portfolio
    ref_indices = {"NIFTY 50", "NIFTY 500"}
    candidates  = scorecard[~scorecard["index_name"].isin(ref_indices)].head(top_n)

    for i, (_, row) in enumerate(candidates.iterrows()):
        r = 5 + i
        comp = float(row.get("composite_score", 50))
        bg_c, fg_c, sig_lbl = _signal_style(comp)

        _dat(ws, r, 1, int(i+1), bg=bg_c, fg=fg_c, bold=True, h_align="center")
        _dat(ws, r, 2, str(row.get("index_name", "")), bg=bg_c, fg=fg_c, bold=True)
        _dat(ws, r, 3, round(comp, 1), bg=bg_c, fg=fg_c, bold=True, h_align="center", fmt="0.0")
        _dat(ws, r, 4, sig_lbl, bg=bg_c, fg=fg_c, bold=True, h_align="center")
        _dat(ws, r, 5, round(100 / top_n, 1), bg=bg_c, fg=fg_c, bold=True, h_align="center", fmt="0.0")

        reg_val  = row.get("regime_score", 50)
        reg_lbl  = ("Favour" if float(reg_val) == 100 else
                    ("Neutral" if float(reg_val) == 50 else "Avoid"))
        _dat(ws, r, 6, reg_lbl, bg=bg_c, fg=fg_c, bold=True, h_align="center")
        _dat(ws, r, 7, round(float(row.get("momentum_score", 50)), 1), bg=bg_c, fg=fg_c, h_align="center", fmt="0.0")
        _dat(ws, r, 8, round(float(row.get("trend_score", 50)), 1), bg=bg_c, fg=fg_c, h_align="center", fmt="0.0")
        _row_h(ws, r, 20)

    # ── Current holdings section ───────────────────────────────────────────────
    r = 5 + top_n + 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value="Current Holdings  (enter manually — compare vs recommendations above)")
    c.fill = _fill(C_BLUE); c.font = _font(bold=True, color=C_WHITE, size=10)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 18)

    r += 1
    curr_headers = ["#", "Sector / Index", "Current Weight%", "Composite Score",
                    "Signal", "Action", "Notes", ""]
    for ci, h in enumerate(curr_headers, 1):
        _hdr(ws, r, ci, h)
    _row_h(ws, r, 18)

    for i in range(top_n + 3):
        r += 1
        bg = C_LIGHT if i % 2 == 0 else C_WHITE
        _dat(ws, r, 1, i+1, bg=bg, h_align="center")
        for ci in range(2, 9):
            _dat(ws, r, ci, None, bg=bg)
        _row_h(ws, r, 20)

    # ── Rotation candidates section ────────────────────────────────────────────
    r += 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value="Rotation Candidates  (indices just outside Top-N, watch for entry)")
    c.fill = _fill(C_NAVY); c.font = _font(bold=True, color=C_WHITE, size=10)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 18)

    r += 1
    rot_headers = ["Rank", "Sector", "Composite", "Signal", "vs #" + str(top_n) + " Gap", "Watch", "", ""]
    for ci, h in enumerate(rot_headers, 1):
        _hdr(ws, r, ci, h)
    _row_h(ws, r, 18)

    next_five = scorecard[~scorecard["index_name"].isin(ref_indices)].iloc[top_n:top_n+5]
    threshold_score = float(candidates.iloc[-1]["composite_score"]) if len(candidates) > 0 else 50
    for i, (_, row) in enumerate(next_five.iterrows()):
        r += 1
        comp = float(row.get("composite_score", 50))
        gap  = round(threshold_score - comp, 1)
        bg   = C_AMBER if gap < 5 else (C_GREY if i % 2 == 0 else C_WHITE)
        _dat(ws, r, 1, int(row.get("rank", "—")), bg=bg, h_align="center")
        _dat(ws, r, 2, str(row.get("index_name", "")), bg=bg)
        _dat(ws, r, 3, round(comp, 1), bg=bg, h_align="center", fmt="0.0")
        _, _, sig_lbl = _signal_style(comp)
        _dat(ws, r, 4, sig_lbl, bg=bg, h_align="center")
        _dat(ws, r, 5, f"−{gap}", bg=bg, h_align="center")
        _dat(ws, r, 6, "⚠ Close" if gap < 5 else "", bg=bg, h_align="center")
        _row_h(ws, r, 18)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — OVERRIDES
# ═══════════════════════════════════════════════════════════════════════════════

def build_tab_overrides(wb: Workbook, as_of: str, regime_stage: int):
    ws = wb.create_sheet("4. Overrides")
    ws.sheet_view.showGridLines = False
    NCOLS = 6

    _title_block(ws, 1, "INDIA-SPECIFIC OVERRIDE FLAGS", f"As of: {as_of}  |  Update monthly", NCOLS)

    override_flags = [
        # (Flag, Description, When Active, Sector Impact, User-fill column)
        ("FII Flow Trend",
         "30-day rolling FII net flow direction",
         "Net outflow > USD 1bn in 30 days",
         "FII outflow → Favour IT/Pharma (USD earners); reduce Banks/Realty",
         "Rotate to defensive USD earners"),
        ("INR/USD Depreciation",
         "INR move vs USD over 30 days",
         "INR weaker by >2% in 30 days",
         "Favour IT, Pharma exports; avoid import-heavy: Auto, Energy, Airlines",
         "Tilt to IT/Pharma exporters"),
        ("Monsoon Flag",
         "IMD June forecast / realtime rainfall",
         "Below-normal monsoon forecast",
         "Negative: FMCG rural, Fertiliser, Rural Index; Positive: Pharma, IT",
         "Reduce rural-consumption exposure"),
        ("Union Budget",
         "Union Budget sector allocations (Feb)",
         "Post-budget: capex boost / sector tax changes",
         "Favoured: Infra, Defence, Capex plays if budget pro-growth",
         "Align with budget sector beneficiaries"),
        ("RBI Policy Surprise",
         "RBI MPC decision vs market expectations",
         "Rate cut > 50bps surprise OR hawkish hold",
         "Unexpected cut: Banks, Realty, Fin Services | Hawkish: FMCG, IT defensive",
         "Adjust Banks/Realty vs IT weighting"),
        ("Q1/Q2/Q3/Q4 Earnings Season",
         "Earnings season sector beats/misses",
         "Earnings surprises in key sectors",
         "Overweight sectors with beats; reduce sectors missing on margins",
         "Review composite scores post-earnings"),
        ("Election Calendar",
         "State/General election cycle",
         "Pre-election: infra, populist spending | Post-election: reforms",
         "Pre-election: Infra, PSU, Rural | Post-election: Private Banks, IT",
         "Flag if within 3 months of major election"),
        ("Global Risk-Off Signal",
         "VIX spike, EM outflows, USD strength",
         "VIX > 25 and DXY rally > 3% in 30d",
         "Reduce cyclicals; overweight FMCG, Pharma, IT (USD earner)",
         "Defensive rotation across the board"),
    ]

    r = 3
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1,
                value="India-specific factors that override the quantitative model signal. "
                      "Review monthly and before each portfolio rebalance.")
    c.fill = _fill(C_BLUE); c.font = _font(color=C_WHITE, size=10, italic=True)
    c.alignment = _align("center", "center", wrap=True)
    _row_h(ws, r, 24)

    r = 4
    hdrs   = ["Flag", "Description", "Trigger Condition", "Sector Impact", "Override Action", "Active? (Y/N)"]
    widths = [22,      30,            30,                  36,              28,                 14]
    for ci, (h, w) in enumerate(zip(hdrs, widths), 1):
        _hdr(ws, r, ci, h)
        _col_w(ws, ci, w)
    _row_h(ws, r, 20)

    for i, (flag, desc, trigger, impact, action) in enumerate(override_flags):
        r = 5 + i
        bg = C_GREY if i % 2 == 0 else C_WHITE
        _dat(ws, r, 1, flag, bg=bg, bold=True)
        _dat(ws, r, 2, desc, bg=bg, wrap=True)
        _dat(ws, r, 3, trigger, bg=bg, wrap=True)
        _dat(ws, r, 4, impact, bg=bg, wrap=True)
        _dat(ws, r, 5, action, bg=bg, wrap=True)
        _dat(ws, r, 6, "N", bg=C_LIGHT, h_align="center", bold=True)  # user fills
        _row_h(ws, r, 40)

    # Discretionary notes section
    r = 5 + len(override_flags) + 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value="Discretionary Notes / Human Review Layer")
    c.fill = _fill(C_NAVY); c.font = _font(bold=True, color=C_WHITE, size=11)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 20)

    r += 1
    _hdr(ws, r, 1, "Date", bg=C_BLUE)
    _col_w(ws, 1, 14)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=NCOLS)
    _hdr(ws, r, 2, "Notes / Override Rationale", bg=C_BLUE)
    _row_h(ws, r, 18)

    for i in range(6):
        r += 1
        _dat(ws, r, 1, None, bg=C_LIGHT)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=NCOLS)
        _dat(ws, r, 2, None, bg=C_LIGHT)
        _row_h(ws, r, 30)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 5 — BACKTEST SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def build_tab_backtest(wb: Workbook, bt: dict, as_of: str):
    ws = wb.create_sheet("5. Backtest")
    ws.sheet_view.showGridLines = False
    NCOLS = 12
    _title_block(ws, 1, "BACKTEST SUMMARY — SIGNAL VALIDATION", f"Generated: {as_of}", NCOLS)

    # ── MODULE A: IC Analysis ──────────────────────────────────────────────────
    r = 3
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value="MODULE A — Signal Quality (Information Coefficient Analysis)")
    c.fill = _fill(C_BLUE); c.font = _font(bold=True, color=C_WHITE, size=11)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 20)

    r = 4
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c2 = ws.cell(row=r, column=1, value="IC Mean > 0.05  |  IC IR > 0.30  |  Higher hit rate = more consistent signal")
    c2.fill = _fill(C_GREY); c2.font = _font(italic=True, size=9, color="FF444444")
    c2.alignment = _align("left", "center")

    r = 5
    ic_hdrs = ["Signal Block", "IC Mean", "IC Std", "IC IR", "Hit Rate",
               "T-Stat", "P-Value", "Months", "IC Mean ✓", "IC IR ✓"]
    ic_widths = [22, 10, 10, 10, 10, 10, 10, 10, 12, 12]
    for ci, (h, w) in enumerate(zip(ic_hdrs, ic_widths), 1):
        _hdr(ws, r, ci, h)
        _col_w(ws, ci, w)
    _row_h(ws, r, 18)

    ic_df = bt.get("ic_summary", pd.DataFrame())
    for i, (_, row) in enumerate(ic_df.iterrows()):
        r = 6 + i
        bg = C_GREY if i % 2 == 0 else C_WHITE
        _dat(ws, r, 1, str(row.get("signal", "")), bg=bg, bold=True)
        _dat(ws, r, 2, row.get("ic_mean", ""), bg=bg, h_align="center", fmt="0.0000")
        _dat(ws, r, 3, row.get("ic_std", ""), bg=bg, h_align="center", fmt="0.0000")
        ic_ir = row.get("ic_ir")
        _dat(ws, r, 4, ic_ir if pd.notna(ic_ir) else "N/A", bg=bg, h_align="center",
             fmt="0.000" if pd.notna(ic_ir) else "@")
        _dat(ws, r, 5, row.get("hit_rate", ""), bg=bg, h_align="center", fmt="0.000")
        _dat(ws, r, 6, row.get("t_stat", ""), bg=bg, h_align="center", fmt="0.00")
        _dat(ws, r, 7, row.get("p_value", ""), bg=bg, h_align="center", fmt="0.0000")
        _dat(ws, r, 8, int(row.get("n_months", 0)), bg=bg, h_align="center")
        mean_chk = str(row.get("target_mean_0.05", "?"))
        ir_chk   = str(row.get("target_ir_0.30", "?"))
        _dat(ws, r, 9, mean_chk, bg=C_GREEN if "✓" in mean_chk else C_RED,
             fg=C_WHITE, bold=True, h_align="center")
        _dat(ws, r, 10, ir_chk, bg=C_GREEN if "✓" in ir_chk else C_RED,
             fg=C_WHITE, bold=True, h_align="center")
        _row_h(ws, r, 18)

    # ── MODULE B: Portfolio Performance ────────────────────────────────────────
    r = 6 + len(ic_df) + 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value="MODULE B — Portfolio Performance (Walk-Forward Out-of-Sample)")
    c.fill = _fill(C_BLUE); c.font = _font(bold=True, color=C_WHITE, size=11)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 20)

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    ws.cell(row=r, column=1, value=(
        "Targets: Alpha > 4% p.a.  |  Sharpe > 0.80  |  Max Drawdown < 25%  "
        "|  Hit Rate > 55%  |  Avg Turnover < 1.5 sectors/month  |  Round-trip cost: 30bps"
    )).fill = _fill(C_GREY)
    ws.cell(row=r, column=1).font = _font(italic=True, size=9, color="FF444444")
    ws.cell(row=r, column=1).alignment = _align("left", "center")

    r += 1
    perf_hdrs = ["Period", "Months", "Port Ret%", "Bench%", "Alpha%", "Sharpe",
                 "MaxDD%", "Hit Rate%", "Turnover", "Alpha✓", "Sharpe✓", "DD✓"]
    perf_widths = [18, 8, 10, 10, 10, 10, 10, 10, 10, 8, 8, 8]
    for ci, (h, w) in enumerate(zip(perf_hdrs, perf_widths), 1):
        _hdr(ws, r, ci, h)
        _col_w(ws, ci, w)
    _row_h(ws, r, 18)

    perf_df = bt.get("perf_summary", pd.DataFrame())
    for i, (_, row) in enumerate(perf_df.iterrows()):
        r += 1
        bg = C_GREY if i % 2 == 0 else C_WHITE
        is_full = str(row.get("period", "")).startswith("Full")
        _dat(ws, r, 1, str(row.get("period", "")), bg=bg, bold=is_full)
        _dat(ws, r, 2, int(row.get("n_months", 0)), bg=bg, h_align="center")
        _dat(ws, r, 3, row.get("ann_return_port", ""), bg=bg, h_align="center", fmt="0.0")
        _dat(ws, r, 4, row.get("ann_return_bench", ""), bg=bg, h_align="center", fmt="0.0")
        alpha = row.get("ann_alpha", 0)
        _dat(ws, r, 5, alpha, bg=C_GREEN if float(alpha) >= 4 else C_RED,
             fg=C_WHITE, bold=True, h_align="center", fmt="0.0")
        sharpe = row.get("sharpe", 0)
        _dat(ws, r, 6, sharpe, bg=C_GREEN if pd.notna(sharpe) and float(sharpe) >= 0.8 else C_AMBER,
             fg=C_WHITE if float(sharpe or 0) >= 0.8 else C_AMBER_TXT,
             bold=True, h_align="center", fmt="0.000")
        dd = row.get("max_drawdown", 0)
        _dat(ws, r, 7, dd, bg=C_GREEN if abs(float(dd)) <= 25 else C_RED,
             fg=C_WHITE, bold=True, h_align="center", fmt="0.0")
        hr = row.get("hit_rate", 0)
        _dat(ws, r, 8, hr, bg=C_GREEN if float(hr) >= 55 else C_AMBER,
             fg=C_WHITE if float(hr) >= 55 else C_AMBER_TXT, bold=True, h_align="center", fmt="0.0")
        trn = row.get("avg_turnover", 0)
        _dat(ws, r, 9, trn, bg=C_GREEN if float(trn) <= 1.5 else C_RED,
             fg=C_WHITE, bold=True, h_align="center", fmt="0.00")
        for ci, tgt_key in enumerate(["alpha_target_4pct", "sharpe_target_0.8", "dd_target_lt25pct"], 10):
            v = str(row.get(tgt_key, "?"))
            _dat(ws, r, ci, v, bg=C_GREEN if "✓" in v else C_RED,
                 fg=C_WHITE, bold=True, h_align="center")
        _row_h(ws, r, 18)

    # ── MODULE C: Regime Breakdown ─────────────────────────────────────────────
    r += 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
    c = ws.cell(row=r, column=1, value="MODULE C — Regime-Conditional Performance")
    c.fill = _fill(C_BLUE); c.font = _font(bold=True, color=C_WHITE, size=11)
    c.alignment = _align("center", "center")
    _row_h(ws, r, 20)

    r += 1
    reg_hdrs = ["Stage", "Regime Label", "Months", "Annual Alpha%", "Sharpe",
                "Hit Rate%", "Expected Edge", "", "", "", "", ""]
    for ci, h in enumerate(reg_hdrs, 1):
        _hdr(ws, r, ci, h) if h else None
    _row_h(ws, r, 18)

    stage_bg = {1: C_GREEN, 2: "FF92D050", 3: C_AMBER, 4: "FFFF6600", 5: C_RED}
    reg_df = bt.get("regime_perf", pd.DataFrame())
    for i, (_, row) in enumerate(reg_df.iterrows()):
        r += 1
        stage = int(row.get("regime_stage", i+1))
        bg    = stage_bg.get(stage, C_GREY)
        fg    = C_WHITE if stage in (1, 4, 5) else C_BLACK
        _dat(ws, r, 1, stage, bg=bg, fg=fg, bold=True, h_align="center")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        _dat(ws, r, 2, str(row.get("regime_label", "")), bg=bg, fg=fg, bold=True)
        _dat(ws, r, 4, int(row.get("n_months", 0)), bg=bg, fg=fg, h_align="center")
        alpha_r = row.get("ann_alpha", 0)
        _dat(ws, r, 5, alpha_r, bg=bg, fg=fg, bold=True, h_align="center", fmt="0.0")
        _dat(ws, r, 6, row.get("sharpe", ""), bg=bg, fg=fg, h_align="center", fmt="0.000")
        _dat(ws, r, 7, row.get("hit_rate", ""), bg=bg, fg=fg, h_align="center", fmt="0.0")
        ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=12)
        _dat(ws, r, 8, str(row.get("expected_edge", "")), bg=bg, fg=fg, bold=True)
        _row_h(ws, r, 20)

    # ── Portfolio cumulative return chart ──────────────────────────────────────
    port_df = bt.get("portfolio", pd.DataFrame())
    if not port_df.empty and "cum_port" in port_df.columns:
        r += 3
        data_start = r
        ws.cell(row=r, column=1, value="Date")
        ws.cell(row=r, column=2, value="Portfolio (net)")
        ws.cell(row=r, column=3, value="Benchmark")
        for j, (_, pr) in enumerate(port_df.iterrows()):
            r += 1
            ws.cell(row=r, column=1, value=pd.Timestamp(pr["date"]).date() if "date" in pr else j)
            ws.cell(row=r, column=2, value=round(float(pr.get("cum_port", 1)), 4))
            ws.cell(row=r, column=3, value=round(float(pr.get("cum_bench", 1)), 4))
            if j >= 120:  # cap chart data at 10 years
                break
        data_end = r

        chart = LineChart()
        chart.title  = "Cumulative Return: Portfolio vs Nifty 50"
        chart.y_axis.title = "Cumulative Return (×)"
        chart.x_axis.title = "Month"
        chart.height = 14
        chart.width  = 26
        chart.style  = 10

        data_ref = Reference(ws, min_col=2, max_col=3, min_row=data_start, max_row=data_end)
        chart.add_data(data_ref, titles_from_data=True)
        chart.series[0].graphicalProperties.line.solidFill = "2E75B6"
        chart.series[1].graphicalProperties.line.solidFill = "FF0000"

        ws.add_chart(chart, f"E{data_start}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def build_dashboard(
    scorecard:     pd.DataFrame,
    backtest:      dict,
    regime_stage:  int,
    top_n:         int,
    output_path:   Path,
    logger:        logging.Logger,
) -> Path:
    as_of = datetime.today().strftime("%d %b %Y")

    wb = Workbook()
    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    logger.info("Building Tab 1: Macro Scorecard")
    build_tab_macro(wb, as_of, regime_stage)

    logger.info("Building Tab 2: Sector Signals")
    build_tab_signals(wb, scorecard, as_of, regime_stage)

    logger.info("Building Tab 3: Portfolio")
    build_tab_portfolio(wb, scorecard, as_of, top_n)

    logger.info("Building Tab 4: Overrides")
    build_tab_overrides(wb, as_of, regime_stage)

    logger.info("Building Tab 5: Backtest Summary")
    build_tab_backtest(wb, backtest, as_of)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    logger.info(f"Dashboard saved: {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Build the India Sector Rotation Excel Dashboard."
    )
    parser.add_argument("--synthetic",    action="store_true",
                        help="Use synthetic data (no NSE data required — demo/test mode)")
    parser.add_argument("--macro-stage",  type=int, default=2, choices=[1,2,3,4,5],
                        help="Current macro regime stage (1–5). Default: 2")
    parser.add_argument("--top-n",        type=int, default=3, choices=[1,2,3,4,5,6,7,8],
                        help="Top-N sectors for Portfolio tab. Default: 3")
    parser.add_argument("--output",       default=str(DEFAULT_OUTPUT),
                        help=f"Output Excel path. Default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()

    logger = setup_logging()
    output_path = Path(args.output)

    if args.synthetic:
        logger.info("SYNTHETIC MODE — generating demo data")
        scorecard = generate_synthetic_scorecard(args.macro_stage)
        backtest  = generate_synthetic_backtest()
    else:
        scorecard = load_scorecard(logger)
        backtest  = load_backtest(logger)

        if scorecard is None:
            logger.warning("No real scorecard found — using synthetic fallback")
            scorecard = generate_synthetic_scorecard(args.macro_stage)

        if all(v.empty for v in backtest.values() if isinstance(v, pd.DataFrame)):
            logger.warning("No backtest data found — using synthetic fallback")
            backtest = generate_synthetic_backtest()

    out = build_dashboard(scorecard, backtest, args.macro_stage, args.top_n, output_path, logger)
    print(f"\n  Dashboard written to: {out}\n")


if __name__ == "__main__":
    main()
