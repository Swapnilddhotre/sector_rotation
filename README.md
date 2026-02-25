# India Sector Rotation Strategy

**Discretionary Strategy with Quantitative Support**  
Early Trend Detection for Indian Equity Markets | February 2026

---

## Overview

A 4-layer quantitative framework for sector rotation across NSE sectoral and thematic indices, designed for discretionary implementation with quantitative signal support.

### Framework Architecture

| Layer | Name | Purpose |
|-------|------|---------|
| 1 | Macro Regime Classification | Identify India business cycle phase (5 stages) |
| 2 | Sector Scoring Engine | Score all sectors on momentum, trend, regime fit, valuation |
| 3 | ML Ensemble Refinement | 16-model ensemble to sharpen return predictions |
| 4 | Portfolio Construction & Risk | Translate scores into allocations with drawdown controls |

### Universe
- **47 Active Rotation Indices**: 14 core sectoral + 8 sectoral variants + 25 thematic
- **2 Reference Indices**: Nifty 50, Nifty 500
- **Data Source**: NSE via NSEPython

---

## Repository Structure

```
india-sector-rotation/
├── config/
│   └── index_universe.py        # All 49 indices, symbols, categories
├── data/                        # Raw fetched data (git-ignored)
├── outputs/                     # CSV scorecards, reports (git-ignored)
├── logs/                        # Run logs (git-ignored)
├── phase1_macro/
│   └── macro_scorecard.py       # 10-indicator macro composite & regime classification
├── phase2_signals/
│   ├── data_fetcher.py          # Script 01: Fetch OHLCV for all indices [ACTIVE]
│   ├── momentum_score.py        # Script 02: Signal Block 1 — Momentum
│   ├── trend_score.py           # Script 03: Signal Block 2 — Trend & Technical
│   ├── regime_alignment.py      # Script 04: Signal Block 3 — Macro-Regime Alignment
│   └── valuation_score.py       # Script 05: Signal Block 4 — Fundamental Valuation
├── phase3_backtest/
│   └── backtest_engine.py       # Expanding window walk-forward backtest
├── phase4_dashboard/
│   └── dashboard_builder.py     # Master Excel dashboard generator
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Signal Construction

### Composite Sector Score
```
Composite_Score = (0.35 × Momentum_Score)
                + (0.20 × Trend_Score)
                + (0.30 × Regime_Alignment_Score)
                + (0.15 × Valuation_Score)
```

### Traffic Light System
| Signal | Composite Score | Action |
|--------|----------------|--------|
| 🟢 GREEN — BUY/OVERWEIGHT | > 65 | Active overweight vs benchmark |
| 🟡 AMBER — HOLD/NEUTRAL | 40–65 | Market weight, monitor closely |
| 🔴 RED — AVOID/UNDERWEIGHT | < 40 | Underweight or exit |

---

## India-Specific Calibrations

1. **RBI Dominates Cycle Timing** — Yield curve steepening leads RBI cuts by 3–6 months
2. **FII Flows Override** — INR depreciation + FII outflows → rotate to IT/Pharma (USD earners)
3. **Monsoon Variable** — IMD forecast affects FMCG, Rural Banking, Auto (tractors)
4. **Budget & Earnings Calendar** — Reduce signal weight 30% during key event windows
5. **Global Commodity Sensitivity** — Crude, Gold, Copper, DXY mapped to sector impact

---

## Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/india-sector-rotation.git
cd india-sector-rotation

# Install dependencies
pip install -r requirements.txt

# Run data fetcher
python phase2_signals/data_fetcher.py
```

---

## Build Roadmap

- [x] Phase 1: Repository structure & configuration
- [ ] Phase 2: Price Signal Engine (data_fetcher → momentum → trend → regime → valuation)
- [ ] Phase 3: Backtest Validation (expanding window walk-forward, IC analysis)
- [ ] Phase 4: Master Excel Dashboard

---

## Disclaimer

This framework is for research and discretionary investment strategy development only. It is not investment advice.
