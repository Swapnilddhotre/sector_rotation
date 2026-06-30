"""
phase4_dashboard/sheets_sync.py
================================
Phase 4 - Google Sheets Sync (v2 with column mapping)
India Sector Rotation Strategy
"""

import argparse
import csv
import logging
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

ROOT_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = ROOT_DIR / "config" / "sheets_credentials.json"
DEFAULT_CSV_PATH = ROOT_DIR / "data" / "processed" / "scorecard_latest.csv"

SHEET_ID = "1-aZot-iKBbQYs6j1Nr9tfBUxA86_nNruHCrqOR-oj8w"
SCORECARD_TAB = "SCORECARD"

DATA_START_CELL = "A7"
DATA_RANGE_CLEAR = "A7:M55"
TIMESTAMP_CELL = "F4"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DASHBOARD_HEADER = [
    "Sector", "Rank", "Composite_A", "Momentum", "Trend", "Regime",
    "Valuation", "Composite_B", "Rank_B", "ML", "Signal_A", "Signal_B", "Delta",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)


def authenticate():
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Service account credentials not found at: {CREDENTIALS_PATH}"
        )
    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=SCOPES)
    client = gspread.authorize(creds)
    logger.info("Authenticated as service account")
    return client


def load_csv(csv_path):
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        raise ValueError(f"CSV is empty: {csv_path}")
    return rows[0], rows[1:]


def map_to_dashboard(header, data):
    """Map signal_engine.py's 11-col CSV to the dashboard's 13-col layout."""
    idx = {col.strip().lower(): i for i, col in enumerate(header)}
    required = ["index_name", "rank", "composite_score", "momentum_score",
                "trend_score", "regime_score", "valuation_score", "signal"]
    missing = [c for c in required if c not in idx]
    if missing:
        raise ValueError(f"Source CSV missing required columns: {missing}")

    mapped = []
    for row in data:
        sector = row[idx["index_name"]]
        rank = row[idx["rank"]]
        composite = row[idx["composite_score"]]
        momentum = row[idx["momentum_score"]]
        trend = row[idx["trend_score"]]
        regime = row[idx["regime_score"]]
        valuation = row[idx["valuation_score"]]
        signal = row[idx["signal"]]
        # In v1, ML/Composite_B mirror Composite_A and Delta = 0
        mapped.append([
            sector, rank, composite, momentum, trend, regime, valuation,
            composite, rank, composite, signal, signal, 0,
        ])
    return mapped


def coerce_numeric(rows):
    cleaned = []
    for row in rows:
        new_row = []
        for cell in row:
            cs = cell.strip() if isinstance(cell, str) else cell
            if cs in ("", "nan", "NaN", "None", "<NA>"):
                new_row.append("")
                continue
            try:
                if "." in str(cs):
                    new_row.append(float(cs))
                else:
                    new_row.append(int(cs))
            except (ValueError, TypeError):
                new_row.append(cs)
        cleaned.append(new_row)
    return cleaned


def push_to_sheet(csv_path=DEFAULT_CSV_PATH, sheet_id=SHEET_ID,
                  tab_name=SCORECARD_TAB, dry_run=False):
    logger.info("=" * 60)
    logger.info("Sector Rotation Sheets Sync")
    logger.info("Run time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    header, data = load_csv(csv_path)
    logger.info("Loaded %d data rows x %d columns from %s",
                len(data), len(header), csv_path.name)
    logger.info("Source header: %s", " | ".join(header))

    mapped = map_to_dashboard(header, data)
    mapped = coerce_numeric(mapped)
    logger.info("Mapped to dashboard: %d rows x %d columns", len(mapped), len(DASHBOARD_HEADER))
    logger.info("Dashboard header: %s", " | ".join(DASHBOARD_HEADER))

    if dry_run:
        logger.info("DRY RUN: skipping Sheets write")
        if mapped:
            logger.info("First mapped row: %s", mapped[0])
        return

    client = authenticate()
    spreadsheet = client.open_by_key(sheet_id)
    logger.info("Opened spreadsheet: %s", spreadsheet.title)

    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        available = [ws.title for ws in spreadsheet.worksheets()]
        raise RuntimeError(f"Tab '{tab_name}' not found. Available: {available}")
    logger.info("Selected worksheet: %s", worksheet.title)

    worksheet.batch_clear([DATA_RANGE_CLEAR])
    logger.info("Cleared range: %s", DATA_RANGE_CLEAR)

    if not mapped:
        logger.warning("No rows to write")
        return

    worksheet.update(range_name=DATA_START_CELL, values=mapped, value_input_option="USER_ENTERED")
    logger.info("Wrote %d rows starting at %s", len(mapped), DATA_START_CELL)

    timestamp = datetime.now().strftime("Generated: %d %b %Y %H:%M")
    try:
        worksheet.update_acell(TIMESTAMP_CELL, timestamp)
        logger.info("Updated timestamp at %s: %s", TIMESTAMP_CELL, timestamp)
    except Exception as e:
        logger.warning("Could not update timestamp: %s", e)

    logger.info("=" * 60)
    logger.info("Sync complete: https://docs.google.com/spreadsheets/d/%s", sheet_id)
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV_PATH))
    parser.add_argument("--sheet-id", type=str, default=SHEET_ID)
    parser.add_argument("--tab", type=str, default=SCORECARD_TAB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    push_to_sheet(csv_path=Path(args.csv), sheet_id=args.sheet_id,
                  tab_name=args.tab, dry_run=args.dry_run)


if __name__ == "__main__":
    main()