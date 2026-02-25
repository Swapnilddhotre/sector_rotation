"""
config/index_universe.py
========================
Master index universe for India Sector Rotation Strategy.

Universe:
  - 14 Core Sectoral Indices
  -  8 Sectoral Variant Indices
  - 25 Thematic Indices
  -  2 Reference Indices (Nifty 50, Nifty 500)
  ─────────────────────────────────────────────
  Total: 49 indices (47 active rotation + 2 reference)

NSE symbol format used by NSEPython: index name string as accepted by
nsepython.index_history() and nse_eq_symbols().

Last updated: February 2026
"""

# ─────────────────────────────────────────────────────────────
# REFERENCE INDICES (benchmark — not rotated into directly)
# ─────────────────────────────────────────────────────────────
REFERENCE_INDICES = {
    "NIFTY 50": {
        "symbol": "NIFTY 50",
        "category": "reference",
        "description": "Broad market benchmark — 50 large-cap stocks",
    },
    "NIFTY 500": {
        "symbol": "NIFTY 500",
        "category": "reference",
        "description": "Broad market benchmark — 500 stocks",
    },
}

# ─────────────────────────────────────────────────────────────
# CORE SECTORAL INDICES (14) — Primary rotation universe
# ─────────────────────────────────────────────────────────────
CORE_SECTORAL = {
    "NIFTY BANK": {
        "symbol": "NIFTY BANK",
        "category": "core_sectoral",
        "sector": "Financials",
        "description": "12 most liquid & large banking stocks",
    },
    "NIFTY AUTO": {
        "symbol": "NIFTY AUTO",
        "category": "core_sectoral",
        "sector": "Automobile",
        "description": "Automobile & auto ancillary sector",
    },
    "NIFTY IT": {
        "symbol": "NIFTY IT",
        "category": "core_sectoral",
        "sector": "Information Technology",
        "description": "IT & IT-enabled services",
    },
    "NIFTY INFRA": {
        "symbol": "NIFTY INFRA",
        "category": "core_sectoral",
        "sector": "Infrastructure",
        "description": "Infrastructure companies",
    },
    "NIFTY METAL": {
        "symbol": "NIFTY METAL",
        "category": "core_sectoral",
        "sector": "Metals",
        "description": "Metal & mining sector",
    },
    "NIFTY ENERGY": {
        "symbol": "NIFTY ENERGY",
        "category": "core_sectoral",
        "sector": "Energy",
        "description": "Energy sector — oil, gas, power",
    },
    "NIFTY REALTY": {
        "symbol": "NIFTY REALTY",
        "category": "core_sectoral",
        "sector": "Real Estate",
        "description": "Real estate sector",
    },
    "NIFTY FMCG": {
        "symbol": "NIFTY FMCG",
        "category": "core_sectoral",
        "sector": "FMCG",
        "description": "Fast moving consumer goods",
    },
    "NIFTY PHARMA": {
        "symbol": "NIFTY PHARMA",
        "category": "core_sectoral",
        "sector": "Pharmaceuticals",
        "description": "Pharmaceutical sector",
    },
    "NIFTY CONSUMER DURABLES": {
        "symbol": "NIFTY CONSUMER DURABLES",
        "category": "core_sectoral",
        "sector": "Consumer Durables",
        "description": "Consumer durables sector",
    },
    "NIFTY FINANCIAL SERVICES": {
        "symbol": "NIFTY FINANCIAL SERVICES",
        "category": "core_sectoral",
        "sector": "Financial Services",
        "description": "Banks + NBFCs + insurance + exchanges",
    },
    "NIFTY MEDIA": {
        "symbol": "NIFTY MEDIA",
        "category": "core_sectoral",
        "sector": "Media",
        "description": "Media & entertainment sector",
    },
    "NIFTY OIL & GAS": {
        "symbol": "NIFTY OIL & GAS",
        "category": "core_sectoral",
        "sector": "Oil & Gas",
        "description": "Oil, gas & petroleum sector",
    },
    "NIFTY HEALTHCARE INDEX": {
        "symbol": "NIFTY HEALTHCARE INDEX",
        "category": "core_sectoral",
        "sector": "Healthcare",
        "description": "Healthcare sector (broader than pharma)",
    },
}

# ─────────────────────────────────────────────────────────────
# SECTORAL VARIANT INDICES (8)
# ─────────────────────────────────────────────────────────────
SECTORAL_VARIANTS = {
    "NIFTY PRIVATE BANK": {
        "symbol": "NIFTY PRIVATE BANK",
        "category": "sectoral_variant",
        "sector": "Financials",
        "description": "Private sector banks only",
    },
    "NIFTY PSU BANK": {
        "symbol": "NIFTY PSU BANK",
        "category": "sectoral_variant",
        "sector": "Financials",
        "description": "Public sector banks",
    },
    "NIFTY FINANCIAL SERVICES 25/50": {
        "symbol": "NIFTY FINANCIAL SERVICES 25/50",
        "category": "sectoral_variant",
        "sector": "Financial Services",
        "description": "Financial services with concentration cap",
    },
    "NIFTY FINANCIAL SERVICES EX-BANK": {
        "symbol": "NIFTY FINANCIAL SERVICES EX-BANK",
        "category": "sectoral_variant",
        "sector": "Financial Services",
        "description": "Financial services excluding banks",
    },
    "NIFTY MIDSMALL HEALTHCARE": {
        "symbol": "NIFTY MIDSMALL HEALTHCARE",
        "category": "sectoral_variant",
        "sector": "Healthcare",
        "description": "Mid & small cap healthcare",
    },
    "NIFTY MIDSMALL IT & TELECOM": {
        "symbol": "NIFTY MIDSMALL IT & TELECOM",
        "category": "sectoral_variant",
        "sector": "Information Technology",
        "description": "Mid & small cap IT and telecom",
    },
    "NIFTY MIDSMALL FINANCIAL SERVICES": {
        "symbol": "NIFTY MIDSMALL FINANCIAL SERVICES",
        "category": "sectoral_variant",
        "sector": "Financial Services",
        "description": "Mid & small cap financial services",
    },
    "NIFTY MIDSMALL INDIA CONSUMPTION": {
        "symbol": "NIFTY MIDSMALL INDIA CONSUMPTION",
        "category": "sectoral_variant",
        "sector": "Consumption",
        "description": "Mid & small cap consumption theme",
    },
}

# ─────────────────────────────────────────────────────────────
# THEMATIC INDICES (25)
# ─────────────────────────────────────────────────────────────
THEMATIC = {
    "NIFTY INDIA DEFENCE": {
        "symbol": "NIFTY INDIA DEFENCE",
        "category": "thematic",
        "theme": "Defence",
        "description": "Defence & aerospace sector",
    },
    "NIFTY INDIA DIGITAL": {
        "symbol": "NIFTY INDIA DIGITAL",
        "category": "thematic",
        "theme": "Digital Economy",
        "description": "Digital economy companies",
    },
    "NIFTY INDIA MANUFACTURING": {
        "symbol": "NIFTY INDIA MANUFACTURING",
        "category": "thematic",
        "theme": "Manufacturing",
        "description": "Manufacturing sector",
    },
    "NIFTY INDIA CONSUMPTION": {
        "symbol": "NIFTY INDIA CONSUMPTION",
        "category": "thematic",
        "theme": "Consumption",
        "description": "India consumption theme",
    },
    "NIFTY CAPITAL MARKETS": {
        "symbol": "NIFTY CAPITAL MARKETS",
        "category": "thematic",
        "theme": "Capital Markets",
        "description": "Brokers, exchanges, AMCs, depositories",
    },
    "NIFTY COMMODITIES": {
        "symbol": "NIFTY COMMODITIES",
        "category": "thematic",
        "theme": "Commodities",
        "description": "Commodity-linked companies",
    },
    "NIFTY INDIA CORPORATE GROUP 25": {
        "symbol": "NIFTY INDIA CORPORATE GROUP 25",
        "category": "thematic",
        "theme": "Corporate Groups",
        "description": "Top 25 corporate group companies",
    },
    "NIFTY PSE": {
        "symbol": "NIFTY PSE",
        "category": "thematic",
        "theme": "PSU",
        "description": "Public sector enterprises",
    },
    "NIFTY CPSE": {
        "symbol": "NIFTY CPSE",
        "category": "thematic",
        "theme": "PSU",
        "description": "Central public sector enterprises",
    },
    "NIFTY MNC": {
        "symbol": "NIFTY MNC",
        "category": "thematic",
        "theme": "MNC",
        "description": "Multinational corporations listed in India",
    },
    "NIFTY SERVICES SECTOR": {
        "symbol": "NIFTY SERVICES SECTOR",
        "category": "thematic",
        "theme": "Services",
        "description": "Services sector broad index",
    },
    "NIFTY SHARIAH 25": {
        "symbol": "NIFTY SHARIAH 25",
        "category": "thematic",
        "theme": "Shariah",
        "description": "Shariah-compliant top 25 stocks",
    },
    "NIFTY INDIA RAILWAYS & NEW AGE MOBILITY": {
        "symbol": "NIFTY INDIA RAILWAYS & NEW AGE MOBILITY",
        "category": "thematic",
        "theme": "Mobility",
        "description": "Railways & new-age mobility",
    },
    "NIFTY MOBILITY": {
        "symbol": "NIFTY MOBILITY",
        "category": "thematic",
        "theme": "Mobility",
        "description": "Mobility sector",
    },
    "NIFTY NON-CYCLICAL CONSUMER": {
        "symbol": "NIFTY NON-CYCLICAL CONSUMER",
        "category": "thematic",
        "theme": "Defensives",
        "description": "Non-cyclical consumer companies",
    },
    "NIFTY HOUSING": {
        "symbol": "NIFTY HOUSING",
        "category": "thematic",
        "theme": "Real Estate",
        "description": "Housing finance & real estate ecosystem",
    },
    "NIFTY RURAL ECONOMY": {
        "symbol": "NIFTY RURAL ECONOMY",
        "category": "thematic",
        "theme": "Rural",
        "description": "Rural economy beneficiaries",
    },
    "NIFTY TOTAL MARKET": {
        "symbol": "NIFTY TOTAL MARKET",
        "category": "thematic",
        "theme": "Broad Market",
        "description": "Total market index",
    },
    "NIFTY MSCI INDIA DOMESTIC & WORLD HEALTHCARE": {
        "symbol": "NIFTY MSCI INDIA DOMESTIC & WORLD HEALTHCARE",
        "category": "thematic",
        "theme": "Healthcare",
        "description": "MSCI-linked healthcare index",
    },
    "NIFTY EV & NEW AGE AUTOMOTIVE": {
        "symbol": "NIFTY EV & NEW AGE AUTOMOTIVE",
        "category": "thematic",
        "theme": "EV",
        "description": "Electric vehicle & new-age auto",
    },
    "NIFTY INDIA NEW AGE CONSUMPTION": {
        "symbol": "NIFTY INDIA NEW AGE CONSUMPTION",
        "category": "thematic",
        "theme": "Consumption",
        "description": "New-age consumption companies",
    },
    "NIFTY TRANSPORTATION & LOGISTICS": {
        "symbol": "NIFTY TRANSPORTATION & LOGISTICS",
        "category": "thematic",
        "theme": "Logistics",
        "description": "Transportation & logistics sector",
    },
    "NIFTY INDIA TOURISM": {
        "symbol": "NIFTY INDIA TOURISM",
        "category": "thematic",
        "theme": "Tourism",
        "description": "Tourism, hotels, travel sector",
    },
    "NIFTY GROWSECTORS 15": {
        "symbol": "NIFTY GROWSECTORS 15",
        "category": "thematic",
        "theme": "Growth",
        "description": "15 high-growth sector index",
    },
    "NIFTY500 MULTICAP MOMENTUM QUALITY 50": {
        "symbol": "NIFTY 500 MULTICAP MOMENTUM QUALITY 50",
        "category": "thematic",
        "theme": "Factor",
        "description": "Momentum + quality factor index",
    },
}

# ─────────────────────────────────────────────────────────────
# REGIME ALIGNMENT MATRIX
# Maps core sectors to Favour/Neutral/Avoid for each macro stage
# Favour=100, Neutral=50, Avoid=0
# ─────────────────────────────────────────────────────────────
REGIME_ALIGNMENT_MATRIX = {
    #                           S1   S2   S3   S4   S5
    "NIFTY BANK":              [100, 100,  50,   0,   0],
    "NIFTY AUTO":              [100, 100,  50,   0,   0],
    "NIFTY IT":                [ 50, 100, 100,  50,  50],
    "NIFTY INFRA":             [100, 100,  50,   0,   0],
    "NIFTY METAL":             [ 50, 100, 100,   0,   0],
    "NIFTY ENERGY":            [ 50,  50, 100,  50,  50],
    "NIFTY REALTY":            [100, 100,  50,   0,   0],
    "NIFTY FMCG":              [  0,  50,  50, 100, 100],
    "NIFTY PHARMA":            [  0,  50,  50, 100, 100],
    "NIFTY CONSUMER DURABLES": [ 50, 100,  50,   0,   0],
    "NIFTY FINANCIAL SERVICES":[100, 100,  50,   0,   0],
    "NIFTY MEDIA":             [  0,  50,  50,  50,   0],
}

# ─────────────────────────────────────────────────────────────
# COMPOSITE LOOKUPS
# ─────────────────────────────────────────────────────────────

# All 47 active rotation indices (excludes reference)
ALL_ROTATION_INDICES = {
    **CORE_SECTORAL,
    **SECTORAL_VARIANTS,
    **THEMATIC,
}

# Full universe of 49
FULL_UNIVERSE = {
    **ALL_ROTATION_INDICES,
    **REFERENCE_INDICES,
}

# Symbols list (for data fetching loops)
ROTATION_SYMBOLS = list(ALL_ROTATION_INDICES.keys())
REFERENCE_SYMBOLS = list(REFERENCE_INDICES.keys())
ALL_SYMBOLS = ROTATION_SYMBOLS + REFERENCE_SYMBOLS

# Core sectoral symbols (used in regime alignment)
CORE_SYMBOLS = list(CORE_SECTORAL.keys())

# ─────────────────────────────────────────────────────────────
# SIGNAL BLOCK WEIGHTS (Composite Score)
# ─────────────────────────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "momentum":  0.35,
    "trend":     0.20,
    "regime":    0.30,
    "valuation": 0.15,
}

# ─────────────────────────────────────────────────────────────
# MOMENTUM SCORE WEIGHTS (Signal Block 1)
# ─────────────────────────────────────────────────────────────
MOMENTUM_WEIGHTS = {
    "MOM_1M":  0.15,
    "MOM_3M":  0.20,
    "MOM_6M":  0.25,
    "MOM_12M": 0.30,
    "REL_STR": 0.10,
}

# ─────────────────────────────────────────────────────────────
# TRADING THRESHOLDS
# ─────────────────────────────────────────────────────────────
SIGNAL_THRESHOLDS = {
    "BUY":   65,   # Composite > 65 → GREEN / BUY / OVERWEIGHT
    "HOLD":  40,   # Composite 40–65 → AMBER / HOLD / NEUTRAL
    # Below 40  → RED / AVOID / UNDERWEIGHT
    "MIN_SCORE_DIFF_TO_ROTATE": 15,  # Rotate only if differential > 15 pts
}

# ─────────────────────────────────────────────────────────────
# MACRO REGIME STAGE BOUNDARIES
# ─────────────────────────────────────────────────────────────
REGIME_STAGES = {
    "Stage 1: Early Expansion":      ( 0.2,  0.6),
    "Stage 2: Mid Expansion":        ( 0.6,  1.0),
    "Stage 3: Late Expansion":       (-0.2,  0.2),
    "Stage 4: Early Contraction":    (-0.6, -0.2),
    "Stage 5: Deep Contraction":     (-1.0, -0.6),
}


if __name__ == "__main__":
    print(f"Total universe     : {len(FULL_UNIVERSE)} indices")
    print(f"Active rotation    : {len(ALL_ROTATION_INDICES)} indices")
    print(f"  Core sectoral    : {len(CORE_SECTORAL)}")
    print(f"  Sectoral variants: {len(SECTORAL_VARIANTS)}")
    print(f"  Thematic         : {len(THEMATIC)}")
    print(f"Reference          : {len(REFERENCE_INDICES)}")
    print("\nAll symbols:")
    for sym in ALL_SYMBOLS:
        print(f"  {sym}")
