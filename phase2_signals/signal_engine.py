"""
india-sector-rotation | Phase 2 | Script 02
============================================
signal_engine.py

PURPOSE
-------
Reads the price and fundamental data produced by data_fetcher.py and computes
all four signal blocks defined in the strategy document.  Outputs a ranked
monthly sector scorecard with traffic-light classifications.

SIGNAL BLOCKS (all normalised 0–100)
--------------------------------------
  Block 1 — Momentum Score        (weight 35%)
  Block 2 — Trend & Technical     (weight 20%)
  Block 3 — Macro-Regime Alignment (weight 30%)   ← requires manual macro input
  Block 4 — Fundamental Valuation (weight 15%)

OUTPUTS  (all written to  data/processed/)
-------------------------------------------
  scorecard_latest.csv       — Current ranked scorecard for all indices
  scorecard_history.parquet  — Full history of all scores, all months
  scorecard_history.csv      — Same, CSV copy
  signal_components.csv      — All sub-signal values (diagnostic use)

USAGE
------
  python signal_engine.py                            # score as of today
  python signal_engine.py --as-of 2024-06-30        # score as of specific date
  python signal_engine.py --macro-score 0.4         # pass live macro composite
  python signal_engine.py --macro-stage 2           # pass stage directly
  python signal_engine.py --history                 # compute full monthly history
  python signal_engine.py --no-block4               # skip valuation (data unavailable)

DEPENDENCIES
------------
  pip install pandas numpy pyarrow scipy
"""

import argparse
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import percentileofscore

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Try coloured output ────────────────────────────────────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

INPUT_DIR     = Path("data/raw")
OUTPUT_DIR    = Path("data/processed")
LOG_DIR       = Path("logs")

BENCHMARK     = "NIFTY 50"          # used for REL_STR in Block 1

# Composite score weights (must sum to 1.0)
WEIGHTS = {
    "momentum":  0.35,
    "trend":     0.20,
    "regime":    0.30,
    "valuation": 0.15,
}

# Traffic light thresholds
SIGNAL_GREEN  = 65   # BUY / OVERWEIGHT
SIGNAL_AMBER  = 40   # HOLD / NEUTRAL
# Below SIGNAL_AMBER → RED / AVOID

# Lookback days for momentum sub-signals
MOM_1M_DAYS  = 21
MOM_3M_DAYS  = 63
MOM_6M_DAYS  = 126
MOM_12M_DAYS = 252

# Valuation z-score window (trading days ~ 5 years)
VAL_WINDOW_MONTHS = 60

# ═══════════════════════════════════════════════════════════════════════════════
#  REGIME ALIGNMENT MATRIX
#  Source: Section 3, Step 3C of the strategy document
#  Values: 100 = Favour, 50 = Neutral, 0 = Avoid
# ═══════════════════════════════════════════════════════════════════════════════

REGIME_MATRIX = {
    #                          Stage:  1     2     3     4     5
    "NIFTY BANK":                    [100, 100,  50,   0,   0],
    "NIFTY AUTO":                    [100, 100,  50,   0,   0],
    "NIFTY IT":                      [ 50, 100, 100,  50,  50],
    "NIFTY INFRA":                   [100, 100,  50,   0,   0],
    "NIFTY METAL":                   [ 50, 100, 100,   0,   0],
    "NIFTY ENERGY":                  [ 50,  50, 100,  50,  50],
    "NIFTY REALTY":                  [100, 100,  50,   0,   0],
    "NIFTY FMCG":                    [  0,  50,  50, 100, 100],
    "NIFTY PHARMA":                  [  0,  50,  50, 100, 100],
    "NIFTY CONSUMER DURABLES":       [ 50, 100,  50,   0,   0],
    "NIFTY FINANCIAL SERVICES":      [100, 100,  50,   0,   0],
    "NIFTY MEDIA":                   [  0,  50,  50,  50,   0],
    # Extended core sectoral
    "NIFTY HEALTHCARE INDEX":        [  0,  50,  50, 100, 100],
    "NIFTY OIL AND GAS":             [ 50,  50, 100,  50,  50],
    # Sectoral variants — interpolated from parent sectors
    "NIFTY PSU BANK":                [100, 100,  50,   0,   0],
    "NIFTY PRIVATE BANK":            [100, 100,  50,   0,   0],
    "NIFTY MIDSMALL FINANCIAL SERVICES": [100, 100, 50, 0, 0],
    "NIFTY TOTAL MARKET":            [ 50, 100,  50,  50,  50],
    "NIFTY LARGE MIDCAP 250":        [ 50, 100,  50,  50,  50],
    "NIFTY MIDCAP 150":              [ 50, 100,  50,   0,   0],
    "NIFTY SMALLCAP 250":            [ 50, 100,  50,   0,   0],
    "NIFTY MICROCAP 250":            [ 50, 100,  50,   0,   0],
    # Thematic — mapped to closest sector analogue
    "NIFTY INDIA DEFENCE":           [100, 100,  50,  50,  50],
    "NIFTY INDIA DIGITAL":           [ 50, 100, 100,  50,  50],
    "NIFTY INDIA MANUFACTURING":     [100, 100,  50,   0,   0],
    "NIFTY INDIA CONSUMPTION":       [ 50, 100,  50,  50,  50],
    "NIFTY COMMODITIES":             [ 50, 100, 100,   0,   0],
    "NIFTY CPSE":                    [ 50, 100,  50,  50,  50],
    "NIFTY PSE":                     [ 50, 100,  50,  50,  50],
    "NIFTY MNC":                     [ 50, 100,  50,  50,  50],
    "NIFTY SERV SECTOR":             [ 50, 100,  50,  50,  50],
    "NIFTY TRANSPORT & LOGISTICS":   [100, 100,  50,   0,   0],
    "NIFTY MOBILITY":                [100, 100,  50,   0,   0],
    "NIFTY TATA GROUP":              [ 50, 100,  50,  50,  50],
    "NIFTY100 QUALITY 30":           [ 50, 100,  50,  50,  50],
    "NIFTY ALPHA 50":                [ 50, 100,  50,  50,  50],
    "NIFTY200 ALPHA 30":             [ 50, 100,  50,  50,  50],
    "NIFTY500 MULTICAP INDIA LEADING": [50, 100, 50, 50, 50],
    "NIFTY INDIA CORPORATE GROUP INDEX": [50, 100, 50, 50, 50],
    "NIFTY CAPITAL MARKETS":         [100, 100,  50,   0,   0],
    "NIFTY HOUSING":                 [100, 100,  50,   0,   0],
    "NIFTY NEW INDIA MANUFACTURING": [100, 100,  50,   0,   0],
    "NIFTY RURAL INDEX":             [ 50,  50,  50,  50, 100],
    "NIFTY INDIA TOURISM":           [100, 100,  50,   0,   0],
    "NIFTY TECH INDEX":              [ 50, 100, 100,  50,  50],
    "NIFTY ENVIRONMENT":             [ 50, 100,  50,  50,  50],
    "NIFTY100 ESG SECTOR LEADERS":   [ 50, 100,  50,  50,  50],
    # Reference indices — neutral across all stages
    "NIFTY 50":                      [ 50,  50,  50,  50,  50],
    "NIFTY 500":                     [ 50,  50,  50,  50,  50],
}


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"signal_{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("signal_engine")


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_prices(input_dir: Path, logger: logging.Logger) -> pd.DataFrame:
    """
    Load prices_daily.parquet.  Pivot to wide format with MultiLevel columns:
      columns = (metric, index_name)
      index   = date
    """
    path = input_dir / "prices_daily.parquet"
    if not path.exists():
        # Fallback to CSV
        path = input_dir / "prices_daily.csv"
        if not path.exists():
            logger.error(f"Price data not found at {input_dir}. Run data_fetcher.py first.")
            sys.exit(1)
        df = pd.read_csv(path, parse_dates=["date"])
    else:
        df = pd.read_parquet(path)

    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["date", "index_name"], inplace=True)

    # Pivot to wide: rows = date, cols = (metric, index_name)
    metrics = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    wide = df.pivot_table(index="date", columns="index_name", values=metrics)
    wide.sort_index(inplace=True)

    logger.info(
        f"Loaded prices: {len(wide)} trading days, "
        f"{wide['close'].shape[1]} indices, "
        f"{wide.index.min().date()} → {wide.index.max().date()}"
    )
    return wide


def load_fundamentals(input_dir: Path, logger: logging.Logger) -> pd.DataFrame | None:
    """Load pe_pb_div_monthly.parquet if it exists."""
    path = input_dir / "pe_pb_div_monthly.parquet"
    if not path.exists():
        path = input_dir / "pe_pb_div_monthly.csv"
        if not path.exists():
            logger.warning("Fundamental data not found — Block 4 will be skipped.")
            return None
        df = pd.read_csv(path, parse_dates=["date"])
    else:
        df = pd.read_parquet(path)

    df["date"] = pd.to_datetime(df["date"])
    logger.info(f"Loaded fundamentals: {len(df)} rows, {df['index_name'].nunique()} indices")
    return df


def get_close(wide: pd.DataFrame) -> pd.DataFrame:
    """Extract the 'close' price sub-DataFrame."""
    return wide["close"].copy()


def get_volume(wide: pd.DataFrame) -> pd.DataFrame | None:
    """Extract the 'volume' sub-DataFrame if available."""
    if "volume" in wide.columns.get_level_values(0):
        return wide["volume"].copy()
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def cross_sectional_rank_score(series: pd.Series) -> pd.Series:
    """
    Rank a cross-sectional Series and normalise to 0–100.
    NaN values are assigned 50 (neutral) to avoid data gaps disabling indices.
    """
    valid = series.dropna()
    if valid.empty:
        return pd.Series(50.0, index=series.index)
    ranks = valid.rank(pct=True) * 100
    return ranks.reindex(series.index).fillna(50.0)


def rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """Standard Wilder RSI."""
    delta = prices.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def score_rsi(rsi_val: float) -> float:
    """
    RSI scoring as per strategy document:
      50–70  → 100 (bullish, not overbought)
      40–50 or 70–80 → 70
      <40 or >80  → 30
    """
    if pd.isna(rsi_val):
        return 50.0
    if 50 <= rsi_val <= 70:
        return 100.0
    if (40 <= rsi_val < 50) or (70 < rsi_val <= 80):
        return 70.0
    return 30.0


def macro_score_to_stage(macro_composite: float) -> int:
    """
    Convert Macro Composite score (−1 to +1) to regime stage (1–5).
    Stage boundaries from strategy document Section 3, Step 3B.
    """
    if macro_composite >= 0.6:
        return 2   # Mid Expansion
    elif macro_composite >= 0.2:
        return 1   # Early Expansion
    elif macro_composite >= -0.2:
        return 3   # Late Expansion / Transition
    elif macro_composite >= -0.6:
        return 4   # Early Contraction
    else:
        return 5   # Deep Contraction


def signal_label(score: float) -> str:
    if score >= SIGNAL_GREEN:
        return "BUY"
    elif score >= SIGNAL_AMBER:
        return "HOLD"
    else:
        return "AVOID"


def traffic_light(score: float) -> str:
    if score >= SIGNAL_GREEN:
        return "GREEN"
    elif score >= SIGNAL_AMBER:
        return "AMBER"
    else:
        return "RED"


# ═══════════════════════════════════════════════════════════════════════════════
#  BLOCK 1 — MOMENTUM SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_block1_momentum(
    close: pd.DataFrame,
    as_of: pd.Timestamp,
    logger: logging.Logger,
) -> pd.Series:
    """
    Compute momentum scores for all indices as of a given date.

    Sub-signals:
      MOM_1M   = price return over 21 trading days   (weight 0.15)
      MOM_3M   = price return over 63 trading days   (weight 0.20)
      MOM_6M   = price return over 126 trading days  (weight 0.25)
      MOM_12M  = price return over 252 trading days  (weight 0.30)
      REL_STR  = MOM_6M(sector) − MOM_6M(NIFTY 50)  (weight 0.10)

    Raw score is cross-sectionally ranked and normalised to 0–100.
    """
    # Slice data up to as_of date
    hist = close[close.index <= as_of]

    def mom(n: int) -> pd.Series:
        """Return n-day momentum for all indices at as_of."""
        if len(hist) <= n:
            return pd.Series(np.nan, index=close.columns)
        current = hist.iloc[-1]
        past    = hist.iloc[-(n + 1)] if len(hist) > n else hist.iloc[0]
        return (current / past) - 1

    m1m  = mom(MOM_1M_DAYS)
    m3m  = mom(MOM_3M_DAYS)
    m6m  = mom(MOM_6M_DAYS)
    m12m = mom(MOM_12M_DAYS)

    # Relative strength vs benchmark
    bench_6m = m6m.get(BENCHMARK, np.nan)
    rel_str  = m6m - bench_6m

    # Raw composite (weighted sum)
    raw = (
        0.15 * m1m  +
        0.20 * m3m  +
        0.25 * m6m  +
        0.30 * m12m +
        0.10 * rel_str
    )

    # Cross-sectional rank → 0–100
    score = cross_sectional_rank_score(raw)

    logger.debug(f"Block 1 computed for {as_of.date()}: "
                 f"{score.notna().sum()} indices scored")
    return score.rename("momentum_score")


# ═══════════════════════════════════════════════════════════════════════════════
#  BLOCK 2 — TREND & TECHNICAL SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_block2_trend(
    close: pd.DataFrame,
    volume: pd.DataFrame | None,
    as_of: pd.Timestamp,
    logger: logging.Logger,
) -> pd.Series:
    """
    Trend & Technical Score.

    Components:
      MA_SIGNAL    — price vs 50-DMA vs 200-DMA        (weight 35%)
      RSI_SCORE    — 14-day RSI in bullish zone         (weight 30%)
      ROC_20_RANK  — 20-day rate-of-change, ranked      (weight 20%)
      VOL_CONFIRM  — volume confirmation on up-days     (weight 15%)
    """
    hist_c = close[close.index <= as_of]

    scores = {}

    for col in close.columns:
        prices = hist_c[col].dropna()
        if len(prices) < 200:
            # Insufficient history — assign neutral
            scores[col] = 50.0
            continue

        p   = prices.iloc[-1]
        ma50  = prices.iloc[-50:].mean()
        ma200 = prices.iloc[-200:].mean()

        # MA Signal
        if p > ma50 > ma200:
            ma_sig = 1.0
        elif p > ma200:
            ma_sig = 0.5
        else:
            ma_sig = 0.0

        # RSI
        rsi_val   = rsi(prices).iloc[-1]
        rsi_score = score_rsi(rsi_val)

        # ROC-20 (raw — will be ranked cross-sectionally after)
        roc20 = ((p / prices.iloc[-20]) - 1) * 100 if len(prices) >= 20 else np.nan

        # Volume confirmation
        vol_confirm = 0.0
        if volume is not None and col in volume.columns:
            vol_hist  = volume[volume.index <= as_of][col].dropna()
            up_days   = prices.diff() > 0
            if len(vol_hist) >= 50:
                vol_20d   = vol_hist.iloc[-20:][up_days.iloc[-20:]]
                vol_50d   = vol_hist.iloc[-50:]
                if len(vol_20d) > 0 and vol_50d.mean() > 0:
                    vol_confirm = 1.0 if vol_20d.mean() > vol_50d.mean() else 0.0

        scores[col] = {
            "ma_sig":       ma_sig,
            "rsi_score":    rsi_score,
            "roc20":        roc20,
            "vol_confirm":  vol_confirm,
        }

    # Cross-sectional rank of ROC-20
    roc_vals = pd.Series(
        {k: v["roc20"] for k, v in scores.items() if isinstance(v, dict)}
    )
    roc_ranked = cross_sectional_rank_score(roc_vals)

    # Assemble final trend score
    final_scores = {}
    for col, v in scores.items():
        if isinstance(v, float):
            final_scores[col] = v   # neutral placeholder
        else:
            ts = (
                0.35 * v["ma_sig"]    * 100 +
                0.30 * v["rsi_score"]       +
                0.20 * roc_ranked.get(col, 50.0) +
                0.15 * v["vol_confirm"] * 100
            )
            final_scores[col] = ts

    result = pd.Series(final_scores, name="trend_score")
    logger.debug(f"Block 2 computed for {as_of.date()}: {result.notna().sum()} indices scored")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  BLOCK 3 — MACRO-REGIME ALIGNMENT SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_block3_regime(
    indices: list[str],
    regime_stage: int,
    logger: logging.Logger,
) -> pd.Series:
    """
    Look up each index in the Regime Matrix and return its alignment score
    for the given regime_stage (1–5).

    Indices not in the matrix receive a neutral score of 50.
    """
    scores = {}
    for idx in indices:
        row = REGIME_MATRIX.get(idx)
        if row is not None:
            scores[idx] = float(row[regime_stage - 1])
        else:
            scores[idx] = 50.0   # neutral for unknown / new indices

    result = pd.Series(scores, name="regime_score")
    logger.debug(f"Block 3 computed for Stage {regime_stage}: {len(result)} indices")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  BLOCK 4 — FUNDAMENTAL VALUATION SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_block4_valuation(
    fund_df: pd.DataFrame,
    as_of: pd.Timestamp,
    window_months: int,
    logger: logging.Logger,
) -> pd.Series:
    """
    Valuation score: cheaper sectors score higher (more favoured).

    For each index:
      PE_ZSCORE  = (PE_current  − PE_5yr_mean)  / PE_5yr_std    ← negative = cheap
      PB_ZSCORE  = (PB_current  − PB_5yr_mean)  / PB_5yr_std    ← negative = cheap
      DY_ZSCORE  = (DY_current  − DY_5yr_mean)  / DY_5yr_std    ← positive = cheap

      composite_z = PE_ZSCORE + PB_ZSCORE − DY_ZSCORE
      Valuation_Score = 100 − percentile_rank(composite_z)
    """
    # Slice to history up to as_of
    hist = fund_df[fund_df["date"] <= as_of].copy()
    hist.sort_values("date", inplace=True)

    # Only keep last window_months months
    cutoff = as_of - pd.DateOffset(months=window_months)
    hist   = hist[hist["date"] >= cutoff]

    scores = {}

    for idx_name, grp in hist.groupby("index_name"):
        grp = grp.sort_values("date")
        if len(grp) < 12:
            scores[idx_name] = 50.0   # insufficient history
            continue

        latest = grp.iloc[-1]

        def zscore(col: str, direction: int = 1) -> float:
            """direction: +1 = higher is worse (PE, PB), −1 = higher is better (DY)."""
            if col not in grp.columns or pd.isna(latest.get(col)):
                return 0.0
            mu  = grp[col].mean()
            std = grp[col].std()
            if std == 0 or pd.isna(std):
                return 0.0
            return direction * (latest[col] - mu) / std

        pe_z = zscore("pe",       direction=+1)
        pb_z = zscore("pb",       direction=+1)
        dy_z = zscore("div_yield", direction=-1)   # note: DY positive = cheap → subtract

        scores[idx_name] = pe_z + pb_z + dy_z   # raw composite z (lower = cheaper)

    if not scores:
        logger.warning("Block 4: no valuation data available — returning neutral 50 for all")
        return pd.Series(name="valuation_score")

    raw_series = pd.Series(scores)

    # Convert to percentile rank, then invert so cheap = high score
    def to_pct_rank(val, series):
        return percentileofscore(series.dropna(), val, kind="rank")

    pct_ranks = raw_series.apply(lambda v: to_pct_rank(v, raw_series))
    val_scores = 100 - pct_ranks   # invert: low composite_z (cheap) → high score

    val_scores.name = "valuation_score"
    logger.debug(f"Block 4 computed for {as_of.date()}: {val_scores.notna().sum()} indices")
    return val_scores


# ═══════════════════════════════════════════════════════════════════════════════
#  COMPOSITE SCORE ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════

def compute_composite(
    momentum:   pd.Series,
    trend:      pd.Series,
    regime:     pd.Series,
    valuation:  pd.Series | None,
    weights:    dict,
    logger:     logging.Logger,
) -> pd.Series:
    """
    Combine the four block scores into the Composite Sector Score.
    If valuation is None, redistribute its weight proportionally across
    the other three blocks.
    """
    if valuation is None or valuation.empty:
        # Redistribute the 15% valuation weight proportionally
        total_w  = weights["momentum"] + weights["trend"] + weights["regime"]
        w_mom    = weights["momentum"] / total_w
        w_trd    = weights["trend"]    / total_w
        w_reg    = weights["regime"]   / total_w
        w_val    = 0.0
        logger.info("Block 4 unavailable — valuation weight redistributed to other blocks")
    else:
        w_mom = weights["momentum"]
        w_trd = weights["trend"]
        w_reg = weights["regime"]
        w_val = weights["valuation"]

    # Align indices
    all_idx = momentum.index.union(trend.index).union(regime.index)
    m = momentum.reindex(all_idx).fillna(50.0)
    t = trend.reindex(all_idx).fillna(50.0)
    r = regime.reindex(all_idx).fillna(50.0)

    composite = w_mom * m + w_trd * t + w_reg * r

    if w_val > 0 and valuation is not None:
        v = valuation.reindex(all_idx).fillna(50.0)
        composite += w_val * v

    composite.name = "composite_score"
    return composite.round(2)


# ═══════════════════════════════════════════════════════════════════════════════
#  SCORECARD BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_scorecard(
    close:        pd.DataFrame,
    volume:       pd.DataFrame | None,
    fund_df:      pd.DataFrame | None,
    as_of:        pd.Timestamp,
    regime_stage: int,
    weights:      dict,
    logger:       logging.Logger,
) -> pd.DataFrame:
    """
    Build a full ranked scorecard for all indices as of a given date.
    Returns a DataFrame with one row per index.
    """
    logger.info(f"Computing scorecard as of {as_of.date()} | Regime Stage: {regime_stage}")

    indices = close.columns.tolist()

    # Block 1
    b1 = compute_block1_momentum(close, as_of, logger)

    # Block 2
    b2 = compute_block2_trend(close, volume, as_of, logger)

    # Block 3
    b3 = compute_block3_regime(indices, regime_stage, logger)

    # Block 4
    b4 = None
    if fund_df is not None and not fund_df.empty:
        b4 = compute_block4_valuation(fund_df, as_of, VAL_WINDOW_MONTHS, logger)

    # Composite
    composite = compute_composite(b1, b2, b3, b4, weights, logger)

    # Assemble scorecard DataFrame
    df = pd.DataFrame({
        "as_of":            as_of.date(),
        "regime_stage":     regime_stage,
        "momentum_score":   b1.round(1),
        "trend_score":      b2.round(1),
        "regime_score":     b3.round(1),
        "valuation_score":  b4.round(1) if b4 is not None else np.nan,
        "composite_score":  composite,
    })

    df.index.name = "index_name"
    df.reset_index(inplace=True)

    df["signal"]        = df["composite_score"].apply(signal_label)
    df["traffic_light"] = df["composite_score"].apply(traffic_light)

    # Sort by composite score descending
    df.sort_values("composite_score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.insert(0, "rank", df.index + 1)

    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  HISTORY MODE — COMPUTE SCORECARD FOR EVERY MONTH-END
# ═══════════════════════════════════════════════════════════════════════════════

def compute_full_history(
    close:        pd.DataFrame,
    volume:       pd.DataFrame | None,
    fund_df:      pd.DataFrame | None,
    regime_stage: int,
    weights:      dict,
    logger:       logging.Logger,
) -> pd.DataFrame:
    """
    Compute scorecard for every month-end from the data start to today.
    NOTE: In history mode, a single static regime_stage is used throughout.
          For a proper historical backtest, regime_stage should be dynamic
          (sourced from the monthly macro scorecard) — that is handled in Script 03.
    """
    # Get all month-end dates within the data
    all_dates  = close.index
    start_date = all_dates.min() + pd.DateOffset(years=1)   # need at least 1yr of data
    month_ends = pd.date_range(start=start_date, end=all_dates.max(), freq="ME")
    # Snap to actual trading days (use last available date on or before each month-end)
    month_ends = [all_dates[all_dates <= me].max() for me in month_ends
                  if len(all_dates[all_dates <= me]) > 0]

    all_scorecards = []

    for me in tqdm(month_ends, desc="Computing history", unit="month"):
        try:
            sc = build_scorecard(close, volume, fund_df, me, regime_stage, weights, logger)
            all_scorecards.append(sc)
        except Exception as exc:
            logger.warning(f"Skipping {me.date()}: {exc}")

    if not all_scorecards:
        logger.error("No scorecards computed for history.")
        return pd.DataFrame()

    history = pd.concat(all_scorecards, ignore_index=True)
    return history


# ═══════════════════════════════════════════════════════════════════════════════
#  EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def export_scorecard(df: pd.DataFrame, output_dir: Path, base_name: str, logger: logging.Logger) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet = output_dir / f"{base_name}.parquet"
    csv     = output_dir / f"{base_name}.csv"
    df.to_parquet(parquet, index=False)
    df.to_csv(csv, index=False)
    logger.info(f"  Saved: {parquet}")
    logger.info(f"  Saved: {csv}")


# ═══════════════════════════════════════════════════════════════════════════════
#  DISPLAY
# ═══════════════════════════════════════════════════════════════════════════════

def print_scorecard(df: pd.DataFrame, regime_stage: int, as_of) -> None:
    stage_labels = {
        1: "Stage 1 — Early Expansion",
        2: "Stage 2 — Mid Expansion",
        3: "Stage 3 — Late Expansion / Transition",
        4: "Stage 4 — Early Contraction",
        5: "Stage 5 — Deep Contraction",
    }

    print(f"\n{'═'*78}")
    print(f"  INDIA SECTOR ROTATION — MONTHLY SCORECARD")
    print(f"  As of: {as_of}   |   Macro Regime: {stage_labels.get(regime_stage, regime_stage)}")
    print(f"{'═'*78}")
    print(f"  {'Rank':<5} {'Index':<38} {'Mom':>5} {'Trend':>5} {'Regime':>6} {'Val':>5} {'Comp':>5}  Signal")
    print(f"  {'─'*5} {'─'*38} {'─'*5} {'─'*5} {'─'*6} {'─'*5} {'─'*5}  {'─'*6}")

    for _, row in df.iterrows():
        sig = row["signal"]
        if sig == "BUY":
            colour = GREEN
        elif sig == "HOLD":
            colour = YELLOW
        else:
            colour = RED

        val_str = f"{row['valuation_score']:5.1f}" if pd.notna(row.get("valuation_score")) else "  N/A"

        print(
            f"  {int(row['rank']):<5} "
            f"{row['index_name']:<38} "
            f"{row['momentum_score']:5.1f} "
            f"{row['trend_score']:5.1f} "
            f"{row['regime_score']:6.1f} "
            f"{val_str} "
            f"{row['composite_score']:5.1f}  "
            f"{colour}{sig}{RESET}"
        )

    buys   = len(df[df["signal"] == "BUY"])
    holds  = len(df[df["signal"] == "HOLD"])
    avoids = len(df[df["signal"] == "AVOID"])
    print(f"\n  {GREEN}BUY: {buys}{RESET}  |  {YELLOW}HOLD: {holds}{RESET}  |  {RED}AVOID: {avoids}{RESET}")
    print(f"{'═'*78}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Compute sector rotation signal scores from NSE price data."
    )
    parser.add_argument(
        "--as-of", default=None,
        help="Score as of this date (YYYY-MM-DD). Default: latest available date in data.",
    )
    parser.add_argument(
        "--macro-score", type=float, default=None,
        help="Macro Composite score (−1.0 to +1.0). Overrides --macro-stage.",
    )
    parser.add_argument(
        "--macro-stage", type=int, default=2, choices=[1, 2, 3, 4, 5],
        help="Macro regime stage (1–5). Default: 2 (Mid Expansion). "
             "Used if --macro-score is not provided.",
    )
    parser.add_argument(
        "--history", action="store_true",
        help="Compute full monthly scorecard history (for back-testing).",
    )
    parser.add_argument(
        "--no-block4", action="store_true",
        help="Skip Block 4 valuation even if data is available.",
    )
    parser.add_argument(
        "--input-dir", default=str(INPUT_DIR),
        help=f"Directory containing fetched data. Default: {INPUT_DIR}",
    )
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR),
        help=f"Directory for output files. Default: {OUTPUT_DIR}",
    )
    args = parser.parse_args()

    logger     = setup_logging(LOG_DIR)
    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # ── Load data ──────────────────────────────────────────────────────────────
    wide   = load_prices(input_dir, logger)
    close  = get_close(wide)
    volume = get_volume(wide)
    fund_df = None if args.no_block4 else load_fundamentals(input_dir, logger)

    # ── Resolve as-of date ─────────────────────────────────────────────────────
    if args.as_of:
        as_of = pd.Timestamp(args.as_of)
    else:
        as_of = close.index.max()

    # ── Resolve regime stage ───────────────────────────────────────────────────
    if args.macro_score is not None:
        regime_stage = macro_score_to_stage(args.macro_score)
        logger.info(f"Macro composite {args.macro_score:.2f} → Stage {regime_stage}")
    else:
        regime_stage = args.macro_stage
        logger.info(f"Regime Stage: {regime_stage} (manual)")

    # ── Score ──────────────────────────────────────────────────────────────────
    if args.history:
        logger.info("Running in HISTORY MODE — computing full monthly scorecard series")
        history = compute_full_history(
            close, volume, fund_df, regime_stage, WEIGHTS, logger
        )
        if not history.empty:
            export_scorecard(history, output_dir, "scorecard_history", logger)
            logger.info(f"History: {len(history['as_of'].unique())} months × "
                        f"{close.shape[1]} indices")
    else:
        scorecard = build_scorecard(
            close, volume, fund_df, as_of, regime_stage, WEIGHTS, logger
        )
        export_scorecard(scorecard, output_dir, "scorecard_latest", logger)
        print_scorecard(scorecard, regime_stage, as_of.date())


if __name__ == "__main__":
    main()
