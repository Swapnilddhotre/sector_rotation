# MTF Tracker — Indian Margin Trading Facility Analyzer

Track which stocks in Indian markets are being bought on margin funding. Compiles NSE & BSE daily MTF disclosure data into actionable screens, risk signals, and stock-level analysis.

## Data Sources

All data comes from mandatory NSE/BSE exchange disclosures, compiled by two free public APIs:

| Source | Base URL | Auth | Notes |
|--------|----------|------|-------|
| **margintradingfacility.com** | `https://margintradingfacility.com/api` | None (key-less) | Per-stock JSON API, real-time-ish |
| **mtf.trading** | `https://mtf.trading` | None | CSV/JSON downloads, daily snapshots since 2017 |
| **NSE Direct** | `nsearchives.nseindia.com` | None | Raw exchange Excel files |

Attribution required: link back to margintradingfacility.com and/or mtf.trading when displaying data.

## Available Commands

Run from the repo root: `python -m mtf_tracker.cli <command>`

### Market-Level Analysis

| Command | What it does |
|---------|-------------|
| `overview` | Total MTF book, daily change, fresh/liquidated, recent trend |
| `breadth --days 30` | Daily count of stocks with rising vs falling MTF books |
| `composition --days 90` | Book split: F&O / non-F&O / ETF over time |
| `snapshot --date 2026-10-22` | Full per-day snapshot from mtf.trading |
| `brokers` | Per-broker MTF book history |

### Stock-Level Screens

| Command | What it does |
|---------|-------------|
| `top --limit 50` | Largest MTF positions by book size |
| `movers --limit 30` | Where margin funding is building/declining fastest |
| `crowding --min-dtc 5` | Stocks hardest to unwind (highest days-to-cover) |
| `risk-scan --limit 50` | Non-F&O stocks with high leverage (unhedgeable risk) |
| `flush --threshold -10` | Detect forced selling / margin call liquidations |
| `sectors` | Sector-level MTF concentration (maps to sector rotation) |
| `danger-zone --limit 50` | Stocks with rising MTF book + falling price (margin averaging down) |
| `non-fno --limit 50` | Non-F&O stocks ranked by MTF/free-float (unhedgeable tail risk) |

### Single-Stock Analysis

| Command | What it does |
|---------|-------------|
| `stock TICKER` | Full MTF detail: book, rank, 1D/1W/1M/3M/6M changes, price-vs-book series |
| `risk-score TICKER` | Composite risk score (0-100) based on book size, crowding, leverage, growth |

## API Endpoints Reference

### margintradingfacility.com (primary — per-stock JSON)

```
GET /api/latest              → whole-market overview
GET /api/stocks?limit=50     → top funded stocks with 7D/30D changes
GET /api/stock/{TICKER}      → single-stock detail + 3-month price-vs-book
GET /api/sectors             → sector-level MTF aggregation & breakdown
GET /api/openapi.json        → OpenAPI spec — full endpoint documentation
```

### mtf.trading (richer datasets — CSV/JSON)

```
GET /data/daily-totals.csv     → daily outstanding, fresh, liquidated since 2017
GET /data/leverage-flow.csv    → net flow, churn, flush events
GET /data/daily-breadth.csv    → rising vs falling books per day
GET /data/book-composition.csv → F&O / non-F&O / ETF daily split
GET /data/stock-universe.csv   → ~3,400 stocks: symbol, ISIN, book, mcap, leverage%, class
GET /data/broker-history.csv   → per-broker MTF book history
GET /{YYYY-MM-DD}/.json        → full daily snapshot (any day since June 2017)
GET /feed.xml                  → Atom feed of daily book
GET /events.xml                → threshold alerts, milestones, flushes
GET /api/v1/summary            → market summary JSON (REST API v1)
GET /api/v1/brokers            → broker-level data JSON
GET /api/v1/global             → global MTF metrics JSON
GET /api/v1/bhavcopy           → MTF-enriched bhavcopy data
```

## Key Metrics Glossary

| Metric | Definition | Risk Signal |
|--------|-----------|-------------|
| **MTF Book** | Total value of shares held under MTF (client margin + broker funding) in INR | Larger = more leveraged exposure |
| **Fresh Exposure** | New margin positions opened on a day | Spike = euphoria building |
| **Exposure Liquidated** | Margin positions closed on a day | Spike = forced selling |
| **% of Free Float** | MTF book as share of freely-tradable market cap | >5% = crowded |
| **Days to Cover** | MTF shares / avg daily volume | >10 = very hard to unwind |
| **Net Flow** | Fresh - Liquidated | Negative = deleveraging |
| **Margin Flush** | Sharp coordinated drop in MTF book | Forced selling event |

## Risk Score Components (0-100)

| Component | Weight | Calculation |
|-----------|--------|------------|
| Book size rank | 15% | Higher rank among all MTF stocks = riskier |
| % of free float | 30% | More of float funded on margin = riskier |
| Days to cover | 25% | Harder to unwind = riskier |
| 30-day growth rate | 30% | Faster margin buildup = riskier |

**Interpretation:**
- 75-100: HIGH RISK — heavily leveraged, crowded, hard to unwind
- 50-74: ELEVATED — significant margin exposure, monitor closely
- 25-49: MODERATE — some margin activity, manageable
- 0-24: LOW — minimal margin exposure

## Integration with Sector Rotation Framework

MTF data plugs into the sector rotation strategy as a **leverage risk overlay**:

1. **Avoid overweighting sectors where MTF is concentrated** — if small-caps have 50% of the MTF book but only 20% of free-float market cap, a correction will hit them hardest
2. **Flush events are early sell signals** — rapid MTF book decline in a sector = forced selling about to cascade
3. **Non-F&O MTF concentration = tail risk** — 50.8% of the book sits in stocks that cannot be hedged; these freeze in lower circuits during sell-offs
4. **Rising MTF + falling prices = danger zone** — investors averaging down on margin; eventual forced unwind amplifies the decline

## Programmatic Usage

```python
from mtf_tracker import MTFClient, MTFAnalyzer

client = MTFClient()
analyzer = MTFAnalyzer(client)

# Market overview
overview = analyzer.market_overview()

# Top 20 stocks by MTF book
top = analyzer.top_funded_stocks(limit=20)

# Biggest movers (where margin is building/unwinding)
movers = analyzer.biggest_movers(limit=30)

# Crowding screen (hardest to unwind)
crowded = analyzer.crowding_screen(min_days_to_cover=5)

# Leverage risk: non-F&O stocks with high margin exposure
risky = analyzer.leverage_risk_scan(limit=50)

# Flush detection: forced selling signals
flushes = analyzer.flush_detection(threshold_pct=-10)

# Single stock deep dive
stock = analyzer.stock_deep_dive("NAZARA")

# Composite risk score
score = analyzer.compute_risk_score("NAZARA")

# Historical snapshot (any day since June 2017)
snapshot = client.get_daily_snapshot("2026-10-22")

# Full stock universe (~3,400 stocks)
universe = client.get_stock_universe()

# Sector-level MTF overlay (plugs into sector rotation)
sectors = analyzer.sector_mtf_overlay()

# Danger zone: rising MTF + falling price
danger = analyzer.danger_zone_screen(limit=50)

# Non-F&O concentration (unhedgeable tail risk)
tail_risk = analyzer.non_fno_concentration(limit=50)

# Sector breakdown (raw API)
sector_data = client.get_sector_breakdown()

# MTF-enriched bhavcopy
bhavcopy = client.get_mtf_bhavcopy()
```

## Network Requirements

The APIs need outbound HTTPS access to:
- `margintradingfacility.com`
- `mtf.trading`
- `nsearchives.nseindia.com` (fallback, raw NSE files)

If running in a restricted environment (e.g., Claude Code cloud), add these to the network allow-list, or run the CLI locally.

## Caching

Results are cached locally in `data/mtf_cache/` for 12 hours (MTF data updates once per trading day after market close). Clear cache: `rm -rf data/mtf_cache/`.
