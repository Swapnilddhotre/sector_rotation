"""
MTF (Model Trading Framework) — India Sector Rotation Strategy
PDF Report Generator

Generates a comprehensive A4 PDF report covering the full 4-layer
quantitative framework: macro regime, sector scoring, ML ensemble,
and portfolio construction.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics import renderPDF

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.index_universe import (
    CORE_SECTORAL, SECTORAL_VARIANTS, THEMATIC, REFERENCE_INDICES,
    REGIME_ALIGNMENT_MATRIX, SIGNAL_WEIGHTS, MOMENTUM_WEIGHTS,
    SIGNAL_THRESHOLDS, REGIME_STAGES, ALL_ROTATION_INDICES,
)

# ── Colors ────────────────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#0B1D3A")
DARK_NAVY  = colors.HexColor("#061224")
GOLD       = colors.HexColor("#C8A951")
MUTED_GOLD = colors.HexColor("#A8893C")
LIGHT_GOLD = colors.HexColor("#F5ECD7")
SLATE      = colors.HexColor("#4A5568")
LIGHT_GRAY = colors.HexColor("#F7FAFC")
MED_GRAY   = colors.HexColor("#E2E8F0")
GREEN_SIG  = colors.HexColor("#276749")
GREEN_BG   = colors.HexColor("#F0FFF4")
AMBER_SIG  = colors.HexColor("#975A16")
AMBER_BG   = colors.HexColor("#FFFFF0")
RED_SIG    = colors.HexColor("#9B2C2C")
RED_BG     = colors.HexColor("#FFF5F5")
WHITE      = colors.white
BLACK      = colors.HexColor("#1A202C")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

TODAY = datetime.now()
DATE_STR = TODAY.strftime("%d %B %Y")
DATE_FILE = TODAY.strftime("%Y-%m-%d")


def build_styles():
    ss = getSampleStyleSheet()

    ss.add(ParagraphStyle(
        "CoverTitle", parent=ss["Title"],
        fontName="Helvetica-Bold", fontSize=32, leading=38,
        textColor=WHITE, alignment=TA_LEFT, spaceAfter=6,
    ))
    ss.add(ParagraphStyle(
        "CoverSubtitle", parent=ss["Normal"],
        fontName="Helvetica", fontSize=14, leading=18,
        textColor=LIGHT_GOLD, alignment=TA_LEFT, spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        "CoverDate", parent=ss["Normal"],
        fontName="Helvetica-Oblique", fontSize=11, leading=14,
        textColor=colors.HexColor("#CBD5E0"), alignment=TA_LEFT,
    ))
    ss.add(ParagraphStyle(
        "SectionTitle", parent=ss["Heading1"],
        fontName="Helvetica-Bold", fontSize=18, leading=22,
        textColor=NAVY, spaceBefore=18, spaceAfter=10,
        borderPadding=(0, 0, 4, 0),
    ))
    ss.add(ParagraphStyle(
        "SubSection", parent=ss["Heading2"],
        fontName="Helvetica-Bold", fontSize=13, leading=16,
        textColor=SLATE, spaceBefore=12, spaceAfter=6,
    ))
    ss.add(ParagraphStyle(
        "BodyText2", parent=ss["Normal"],
        fontName="Helvetica", fontSize=9.5, leading=13,
        textColor=BLACK, alignment=TA_JUSTIFY, spaceAfter=6,
    ))
    ss.add(ParagraphStyle(
        "SmallItalic", parent=ss["Normal"],
        fontName="Helvetica-Oblique", fontSize=8, leading=10,
        textColor=SLATE, spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        "TableHeader", parent=ss["Normal"],
        fontName="Helvetica-Bold", fontSize=8.5, leading=11,
        textColor=WHITE, alignment=TA_CENTER,
    ))
    ss.add(ParagraphStyle(
        "TableCell", parent=ss["Normal"],
        fontName="Helvetica", fontSize=8, leading=10,
        textColor=BLACK, alignment=TA_LEFT,
    ))
    ss.add(ParagraphStyle(
        "TableCellCenter", parent=ss["Normal"],
        fontName="Helvetica", fontSize=8, leading=10,
        textColor=BLACK, alignment=TA_CENTER,
    ))
    ss.add(ParagraphStyle(
        "KPIValue", parent=ss["Normal"],
        fontName="Helvetica-Bold", fontSize=20, leading=24,
        textColor=NAVY, alignment=TA_CENTER,
    ))
    ss.add(ParagraphStyle(
        "KPILabel", parent=ss["Normal"],
        fontName="Helvetica", fontSize=8, leading=10,
        textColor=SLATE, alignment=TA_CENTER,
    ))
    ss.add(ParagraphStyle(
        "Footer", parent=ss["Normal"],
        fontName="Helvetica", fontSize=7, leading=9,
        textColor=SLATE, alignment=TA_CENTER,
    ))
    ss.add(ParagraphStyle(
        "BulletItem", parent=ss["Normal"],
        fontName="Helvetica", fontSize=9.5, leading=13,
        textColor=BLACK, leftIndent=16, bulletIndent=4,
        spaceAfter=3,
    ))
    return ss


def section_divider():
    return HRFlowable(
        width="100%", thickness=1, color=MED_GRAY,
        spaceBefore=6, spaceAfter=10,
    )


def gold_accent_bar():
    return HRFlowable(
        width="30%", thickness=2.5, color=GOLD,
        spaceBefore=2, spaceAfter=8,
    )


# ══════════════════════════════════════════════════════════════════════════════
# COVER PAGE
# ══════════════════════════════════════════════════════════════════════════════

def build_cover(styles):
    d = Drawing(CONTENT_W, 260)
    d.add(Rect(0, 0, CONTENT_W, 260, fillColor=NAVY, strokeColor=None))
    d.add(Rect(0, 0, 6, 260, fillColor=GOLD, strokeColor=None))
    d.add(Line(20, 80, CONTENT_W - 20, 80, strokeColor=MUTED_GOLD, strokeWidth=0.5))

    elements = []
    elements.append(Spacer(1, 40))
    elements.append(d)
    elements.append(Spacer(1, -240))

    cover_title_block = []
    cover_title_block.append(Spacer(1, 50))
    cover_title_block.append(Paragraph(
        "India Sector Rotation<br/>Model Trading Framework",
        styles["CoverTitle"],
    ))
    cover_title_block.append(Spacer(1, 8))
    cover_title_block.append(Paragraph(
        "Discretionary Strategy with Quantitative Support",
        styles["CoverSubtitle"],
    ))
    cover_title_block.append(Paragraph(
        "Early Trend Detection for Indian Equity Markets",
        styles["CoverSubtitle"],
    ))
    cover_title_block.append(Spacer(1, 16))
    cover_title_block.append(Paragraph(
        f"Report Date: {DATE_STR}",
        styles["CoverDate"],
    ))
    cover_title_block.append(Paragraph(
        "Universe: 47 Active Rotation Indices + 2 Reference | NSE",
        styles["CoverDate"],
    ))

    cover_table = Table(
        [[cover_title_block]],
        colWidths=[CONTENT_W - 30],
    )
    cover_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 30),
    ]))
    elements.append(cover_table)
    elements.append(Spacer(1, 100))
    elements.append(PageBreak())
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# TABLE OF CONTENTS
# ══════════════════════════════════════════════════════════════════════════════

def build_toc(styles):
    elements = []
    elements.append(Paragraph("Table of Contents", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    toc_items = [
        ("1", "Executive Summary"),
        ("2", "Framework Architecture"),
        ("3", "Index Universe (49 Indices)"),
        ("4", "Signal Block 1: Momentum Score"),
        ("5", "Signal Block 2: Trend & Technical Score"),
        ("6", "Signal Block 3: Macro-Regime Alignment"),
        ("7", "Signal Block 4: Fundamental Valuation"),
        ("8", "Composite Scoring & Traffic Light System"),
        ("9", "Regime Alignment Matrix"),
        ("10", "India-Specific Calibrations"),
        ("11", "Backtest Architecture"),
        ("12", "Portfolio Construction & Risk"),
        ("13", "Implementation Roadmap"),
        ("14", "Disclaimer"),
    ]

    for num, title in toc_items:
        elements.append(Paragraph(
            f'<b>{num}.</b>&nbsp;&nbsp;{title}',
            styles["BodyText2"],
        ))
    elements.append(Spacer(1, 10))
    elements.append(PageBreak())
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def build_executive_summary(styles):
    elements = []
    elements.append(Paragraph("1. Executive Summary", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    # KPI strip
    kpi_data = [
        ("47", "Active Rotation\nIndices"),
        ("14", "Core Sectoral\nIndices"),
        ("4", "Signal\nBlocks"),
        ("5", "Macro Regime\nStages"),
        ("10", "Macro\nIndicators"),
        ("16", "ML Ensemble\nModels"),
    ]
    kpi_cells = []
    for val, label in kpi_data:
        kpi_cells.append([
            Paragraph(val, styles["KPIValue"]),
            Paragraph(label, styles["KPILabel"]),
        ])
    kpi_table = Table(
        [kpi_cells],
        colWidths=[CONTENT_W / 6] * 6,
        rowHeights=[60],
    )
    kpi_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("BACKGROUND", (0, 0), (0, 0), LIGHT_GOLD),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 12))

    summary = (
        "The India Sector Rotation Model Trading Framework (MTF) is a 4-layer quantitative "
        "system designed for discretionary implementation with quantitative signal support. "
        "It covers 47 actively rotated NSE sectoral and thematic indices, scored across "
        "momentum, trend, macro-regime alignment, and fundamental valuation dimensions."
    )
    elements.append(Paragraph(summary, styles["BodyText2"]))

    summary2 = (
        "The framework classifies India's business cycle into 5 macro stages using a "
        "10-indicator composite (IIP, PMI Manufacturing, PMI Services, RBI Repo Rate, "
        "Yield Spread, Bank Credit Growth, CPI, FII Flows, GST Collections, INR/USD). "
        "Each sector receives a composite score from 0–100, mapped to a traffic light "
        "system: GREEN (>65) for overweight, AMBER (40–65) for neutral, RED (<40) for "
        "underweight. India-specific calibrations for RBI policy, FII flows, monsoon "
        "impact, and budget/earnings calendar are embedded throughout."
    )
    elements.append(Paragraph(summary2, styles["BodyText2"]))

    summary3 = (
        "The composite sector score is calculated as: Momentum (35%) + Regime Alignment "
        "(30%) + Trend (20%) + Valuation (15%). A 16-model ML ensemble (Phase 3) sharpens "
        "return predictions via expanding-window walk-forward validation. The system targets "
        "annualised alpha >4% vs Nifty 50 with a Sharpe >0.8, max drawdown <25%, and "
        "sector turnover <1.5/month."
    )
    elements.append(Paragraph(summary3, styles["BodyText2"]))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: FRAMEWORK ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════

def build_framework_arch(styles):
    elements = []
    elements.append(Paragraph("2. Framework Architecture", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    arch_data = [
        [
            Paragraph("<b>Layer</b>", styles["TableHeader"]),
            Paragraph("<b>Name</b>", styles["TableHeader"]),
            Paragraph("<b>Purpose</b>", styles["TableHeader"]),
            Paragraph("<b>Status</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("1", styles["TableCellCenter"]),
            Paragraph("Macro Regime Classification", styles["TableCell"]),
            Paragraph("Identify India business cycle phase (5 stages) using 10-indicator composite", styles["TableCell"]),
            Paragraph("Architecture defined", styles["TableCellCenter"]),
        ],
        [
            Paragraph("2", styles["TableCellCenter"]),
            Paragraph("Sector Scoring Engine", styles["TableCell"]),
            Paragraph("Score all 47 sectors on momentum, trend, regime fit, valuation (0–100)", styles["TableCell"]),
            Paragraph("Data fetcher active", styles["TableCellCenter"]),
        ],
        [
            Paragraph("3", styles["TableCellCenter"]),
            Paragraph("ML Ensemble Refinement", styles["TableCell"]),
            Paragraph("16-model ensemble to sharpen return predictions via walk-forward validation", styles["TableCell"]),
            Paragraph("Pending Phase 3", styles["TableCellCenter"]),
        ],
        [
            Paragraph("4", styles["TableCellCenter"]),
            Paragraph("Portfolio Construction & Risk", styles["TableCell"]),
            Paragraph("Translate scores into allocations with drawdown controls and India overrides", styles["TableCell"]),
            Paragraph("Pending Phase 4", styles["TableCellCenter"]),
        ],
    ]
    t = Table(arch_data, colWidths=[35, 130, CONTENT_W - 35 - 130 - 90, 90])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("BACKGROUND", (0, 1), (-1, -1), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        "The framework operates on a monthly rebalancing cycle with 6 discrete steps: "
        "(1) Macro Update, (2) Signal Compute, (3) Composite Score + Traffic Light, "
        "(4) India Overrides (FII, INR, Monsoon, Calendar), (5) Discretionary Human Review, "
        "(6) Portfolio weights vs signals + rotation candidates.",
        styles["BodyText2"],
    ))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: INDEX UNIVERSE
# ══════════════════════════════════════════════════════════════════════════════

def build_universe_section(styles):
    elements = []
    elements.append(Paragraph("3. Index Universe (49 Indices)", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        f"The rotation universe spans <b>{len(ALL_ROTATION_INDICES)} active indices</b> "
        f"across 3 tiers, benchmarked against {len(REFERENCE_INDICES)} reference indices. "
        "All data is sourced from NSE via NSEPython.",
        styles["BodyText2"],
    ))

    # Core Sectoral
    elements.append(Paragraph("3.1 Core Sectoral Indices (14)", styles["SubSection"]))
    core_data = [[
        Paragraph("<b>Index</b>", styles["TableHeader"]),
        Paragraph("<b>Sector</b>", styles["TableHeader"]),
        Paragraph("<b>Description</b>", styles["TableHeader"]),
    ]]
    for name, info in sorted(CORE_SECTORAL.items()):
        core_data.append([
            Paragraph(name, styles["TableCell"]),
            Paragraph(info.get("sector", ""), styles["TableCellCenter"]),
            Paragraph(info["description"], styles["TableCell"]),
        ])
    t = Table(core_data, colWidths=[140, 90, CONTENT_W - 230])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))

    # Sectoral Variants
    elements.append(Paragraph("3.2 Sectoral Variant Indices (8)", styles["SubSection"]))
    var_data = [[
        Paragraph("<b>Index</b>", styles["TableHeader"]),
        Paragraph("<b>Sector</b>", styles["TableHeader"]),
        Paragraph("<b>Description</b>", styles["TableHeader"]),
    ]]
    for name, info in sorted(SECTORAL_VARIANTS.items()):
        var_data.append([
            Paragraph(name, styles["TableCell"]),
            Paragraph(info.get("sector", ""), styles["TableCellCenter"]),
            Paragraph(info["description"], styles["TableCell"]),
        ])
    t = Table(var_data, colWidths=[175, 90, CONTENT_W - 265])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))

    # Thematic
    elements.append(Paragraph("3.3 Thematic Indices (25)", styles["SubSection"]))
    them_data = [[
        Paragraph("<b>Index</b>", styles["TableHeader"]),
        Paragraph("<b>Theme</b>", styles["TableHeader"]),
        Paragraph("<b>Description</b>", styles["TableHeader"]),
    ]]
    for name, info in sorted(THEMATIC.items()):
        them_data.append([
            Paragraph(name, styles["TableCell"]),
            Paragraph(info.get("theme", ""), styles["TableCellCenter"]),
            Paragraph(info["description"], styles["TableCell"]),
        ])
    t = Table(them_data, colWidths=[195, 80, CONTENT_W - 275])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: MOMENTUM SCORE
# ══════════════════════════════════════════════════════════════════════════════

def build_momentum_section(styles):
    elements = []
    elements.append(Paragraph("4. Signal Block 1: Momentum Score (35%)", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "The momentum score captures price return across multiple time horizons, "
        "cross-sectionally ranked and weighted to produce a 0–100 normalised score. "
        "Longer horizons are weighted more heavily to capture sustained trends while "
        "the 1-month component provides responsiveness to recent shifts.",
        styles["BodyText2"],
    ))

    mom_data = [[
        Paragraph("<b>Component</b>", styles["TableHeader"]),
        Paragraph("<b>Weight</b>", styles["TableHeader"]),
        Paragraph("<b>Lookback</b>", styles["TableHeader"]),
        Paragraph("<b>Description</b>", styles["TableHeader"]),
    ]]
    mom_items = [
        ("MOM_1M", "15%", "21 trading days", "1-month price return — recent momentum shift"),
        ("MOM_3M", "20%", "63 trading days", "3-month return — short-term trend confirmation"),
        ("MOM_6M", "25%", "126 trading days", "6-month return — medium-term trend strength"),
        ("MOM_12M", "30%", "252 trading days", "12-month return — primary trend signal"),
        ("REL_STR", "10%", "63 trading days", "Relative strength vs Nifty 500 benchmark"),
    ]
    for comp, wt, lb, desc in mom_items:
        mom_data.append([
            Paragraph(f"<b>{comp}</b>", styles["TableCell"]),
            Paragraph(wt, styles["TableCellCenter"]),
            Paragraph(lb, styles["TableCellCenter"]),
            Paragraph(desc, styles["TableCell"]),
        ])
    t = Table(mom_data, colWidths=[70, 50, 90, CONTENT_W - 210])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(
        "<b>Formula:</b> Raw_Momentum = (0.15 × MOM_1M) + (0.20 × MOM_3M) + "
        "(0.25 × MOM_6M) + (0.30 × MOM_12M) + (0.10 × REL_STR)",
        styles["BodyText2"],
    ))
    elements.append(Paragraph(
        "Each component is percentile-ranked cross-sectionally across the 47-index "
        "universe. The final momentum score is the weighted sum, normalised to 0–100.",
        styles["SmallItalic"],
    ))
    elements.append(Paragraph(
        "<b>Sources:</b> Mamais (2024), Rothe (2023)",
        styles["SmallItalic"],
    ))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: TREND SCORE
# ══════════════════════════════════════════════════════════════════════════════

def build_trend_section(styles):
    elements = []
    elements.append(Paragraph("5. Signal Block 2: Trend & Technical Score (20%)", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "The trend score provides technical confirmation of momentum signals using "
        "moving averages, RSI, rate of change, and volume analysis. This block acts "
        "as a filter to prevent overweighting sectors with deteriorating technical structure.",
        styles["BodyText2"],
    ))

    trend_data = [[
        Paragraph("<b>Component</b>", styles["TableHeader"]),
        Paragraph("<b>Weight</b>", styles["TableHeader"]),
        Paragraph("<b>Calculation</b>", styles["TableHeader"]),
    ]]
    trend_items = [
        ("MA_SIGNAL", "35%", "Binary: Price > 50-DMA > 200-DMA = 1 (bullish); 50-DMA < 200-DMA = 0 (bearish); else 0.5"),
        ("RSI_14", "30%", "14-day RSI mapped to score: 50–70 = full, <30 or >80 = low, scaled proportionally"),
        ("ROC_20", "20%", "20-day rate of change, cross-sectionally percentile-ranked"),
        ("VOL_CONFIRM", "15%", "Volume confirmation: ratio of avg volume on up-days vs down-days over 20 days"),
    ]
    for comp, wt, desc in trend_items:
        trend_data.append([
            Paragraph(f"<b>{comp}</b>", styles["TableCell"]),
            Paragraph(wt, styles["TableCellCenter"]),
            Paragraph(desc, styles["TableCell"]),
        ])
    t = Table(trend_data, colWidths=[80, 50, CONTENT_W - 130])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(
        "<b>Formula:</b> Trend_Score = (0.35 × MA_SIGNAL × 100) + (0.30 × RSI_SCORE) + "
        "(0.20 × rank(ROC_20)) + (0.15 × VOL_CONFIRM × 100)",
        styles["BodyText2"],
    ))
    elements.append(Paragraph(
        "<b>Source:</b> Rothe (2023)",
        styles["SmallItalic"],
    ))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: MACRO-REGIME ALIGNMENT
# ══════════════════════════════════════════════════════════════════════════════

def build_regime_section(styles):
    elements = []
    elements.append(Paragraph("6. Signal Block 3: Macro-Regime Alignment (30%)", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "The macro-regime alignment block is the core differentiator of this framework. "
        "It classifies India's business cycle into 5 stages using a 10-indicator composite, "
        "then maps each sector's historical performance affinity to the current regime stage.",
        styles["BodyText2"],
    ))

    elements.append(Paragraph("6.1 Macro Indicators (10)", styles["SubSection"]))
    ind_data = [[
        Paragraph("<b>#</b>", styles["TableHeader"]),
        Paragraph("<b>Indicator</b>", styles["TableHeader"]),
        Paragraph("<b>Bullish (+1)</b>", styles["TableHeader"]),
        Paragraph("<b>Neutral (0)</b>", styles["TableHeader"]),
        Paragraph("<b>Bearish (–1)</b>", styles["TableHeader"]),
    ]]
    indicators = [
        ("1", "IIP (Index of Industrial Production)", "YoY > 5%", "2–5%", "< 2%"),
        ("2", "PMI Manufacturing", "> 52", "49–52", "< 49"),
        ("3", "PMI Services", "> 53", "50–53", "< 50"),
        ("4", "RBI Repo Rate", "Cutting cycle", "On hold", "Hiking cycle"),
        ("5", "Yield Spread (10Y–2Y)", "Steepening", "Flat", "Inverting"),
        ("6", "Bank Credit Growth", "YoY > 14%", "10–14%", "< 10%"),
        ("7", "CPI Inflation", "< 4%", "4–6%", "> 6%"),
        ("8", "FII Flows (net monthly)", "Net buyer", "Mixed", "Net seller"),
        ("9", "GST Collections", "YoY > 12%", "8–12%", "< 8%"),
        ("10", "INR/USD", "Appreciating", "Stable", "Depreciating"),
    ]
    for num, name, bull, neut, bear in indicators:
        ind_data.append([
            Paragraph(num, styles["TableCellCenter"]),
            Paragraph(name, styles["TableCell"]),
            Paragraph(bull, styles["TableCellCenter"]),
            Paragraph(neut, styles["TableCellCenter"]),
            Paragraph(bear, styles["TableCellCenter"]),
        ])
    t = Table(ind_data, colWidths=[25, 160, (CONTENT_W - 185) / 3, (CONTENT_W - 185) / 3, (CONTENT_W - 185) / 3])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("6.2 Regime Stage Classification", styles["SubSection"]))
    elements.append(Paragraph(
        "<b>Macro_Composite</b> = Average of 10 indicator scores (range: –1.0 to +1.0)",
        styles["BodyText2"],
    ))

    stage_data = [[
        Paragraph("<b>Stage</b>", styles["TableHeader"]),
        Paragraph("<b>Composite Range</b>", styles["TableHeader"]),
        Paragraph("<b>Characteristics</b>", styles["TableHeader"]),
        Paragraph("<b>Favoured Sectors</b>", styles["TableHeader"]),
    ]]
    stage_info = [
        ("Stage 1: Early Expansion", "+0.2 to +0.6", "RBI cutting, credit picking up, PMI rising", "Banks, Auto, Infra, Realty, FinServ"),
        ("Stage 2: Mid Expansion", "+0.6 to +1.0", "Broad-based growth, strong FII flows", "Bank, Auto, IT, Infra, Metals, Realty, ConDurables"),
        ("Stage 3: Late Expansion", "–0.2 to +0.2", "Growth peaking, inflation pressures", "IT, Metals, Energy"),
        ("Stage 4: Early Contraction", "–0.6 to –0.2", "RBI hiking, demand slowing", "FMCG, Pharma"),
        ("Stage 5: Deep Contraction", "–1.0 to –0.6", "Recession indicators, FII outflows", "FMCG, Pharma (defensives)"),
    ]
    for stage, rng, chars, favoured in stage_info:
        stage_data.append([
            Paragraph(f"<b>{stage}</b>", styles["TableCell"]),
            Paragraph(rng, styles["TableCellCenter"]),
            Paragraph(chars, styles["TableCell"]),
            Paragraph(favoured, styles["TableCell"]),
        ])
    t = Table(stage_data, colWidths=[110, 80, (CONTENT_W - 190) / 2, (CONTENT_W - 190) / 2])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "<b>Sources:</b> Garg &amp; Sah (2025), Fidelity AART Framework, Jacobsen et al. (2009)",
        styles["SmallItalic"],
    ))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: VALUATION SCORE
# ══════════════════════════════════════════════════════════════════════════════

def build_valuation_section(styles):
    elements = []
    elements.append(Paragraph("7. Signal Block 4: Fundamental Valuation (15%)", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "The valuation block provides a mean-reversion overlay using z-scores of P/E, "
        "P/B, and dividend yield relative to their 5-year rolling averages. Cheaper "
        "sectors (negative PE/PB z-scores, positive DY z-scores) score higher.",
        styles["BodyText2"],
    ))

    val_data = [[
        Paragraph("<b>Metric</b>", styles["TableHeader"]),
        Paragraph("<b>Z-Score Calculation</b>", styles["TableHeader"]),
        Paragraph("<b>Interpretation</b>", styles["TableHeader"]),
    ]]
    val_items = [
        ("PE Z-Score", "(Current PE – 5yr avg PE) / 5yr std PE", "Negative = cheap relative to history"),
        ("PB Z-Score", "(Current PB – 5yr avg PB) / 5yr std PB", "Negative = cheap relative to history"),
        ("DY Z-Score", "(Current DY – 5yr avg DY) / 5yr std DY", "Positive = higher yield = cheap"),
    ]
    for metric, calc, interp in val_items:
        val_data.append([
            Paragraph(f"<b>{metric}</b>", styles["TableCell"]),
            Paragraph(calc, styles["TableCell"]),
            Paragraph(interp, styles["TableCell"]),
        ])
    t = Table(val_data, colWidths=[80, (CONTENT_W - 80) / 2, (CONTENT_W - 80) / 2])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(
        "<b>Formula:</b> Valuation_Score = 100 – percentile_rank(avg(PE_ZSCORE + PB_ZSCORE – DY_ZSCORE))",
        styles["BodyText2"],
    ))
    elements.append(Paragraph(
        "<b>Source:</b> Mateus et al. (2018)",
        styles["SmallItalic"],
    ))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8: COMPOSITE SCORING & TRAFFIC LIGHT
# ══════════════════════════════════════════════════════════════════════════════

def build_composite_section(styles):
    elements = []
    elements.append(Paragraph("8. Composite Scoring & Traffic Light System", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "The four signal blocks are combined into a single composite score per index, "
        "which drives the traffic light classification and rotation decisions.",
        styles["BodyText2"],
    ))

    elements.append(Paragraph("8.1 Composite Score Formula", styles["SubSection"]))
    wt_data = [[
        Paragraph("<b>Signal Block</b>", styles["TableHeader"]),
        Paragraph("<b>Weight</b>", styles["TableHeader"]),
        Paragraph("<b>Rationale</b>", styles["TableHeader"]),
    ]]
    wt_items = [
        ("Momentum Score", "35%", "Strongest single predictor of near-term sector returns; captures market pricing dynamics"),
        ("Regime Alignment", "30%", "Core differentiator; maps sector affinity to India business cycle stage"),
        ("Trend Score", "20%", "Technical confirmation filter; prevents overweighting deteriorating sectors"),
        ("Valuation Score", "15%", "Mean-reversion overlay; favours historically cheap sectors at margin"),
    ]
    for block, wt, rationale in wt_items:
        wt_data.append([
            Paragraph(f"<b>{block}</b>", styles["TableCell"]),
            Paragraph(wt, styles["TableCellCenter"]),
            Paragraph(rationale, styles["TableCell"]),
        ])
    t = Table(wt_data, colWidths=[100, 55, CONTENT_W - 155])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("8.2 Traffic Light Classification", styles["SubSection"]))
    tl_data = [[
        Paragraph("<b>Signal</b>", styles["TableHeader"]),
        Paragraph("<b>Composite Score</b>", styles["TableHeader"]),
        Paragraph("<b>Action</b>", styles["TableHeader"]),
        Paragraph("<b>Portfolio Implication</b>", styles["TableHeader"]),
    ]]
    tl_items = [
        ("GREEN — BUY", "> 65", "Overweight", "Active allocation above benchmark weight; primary rotation targets"),
        ("AMBER — HOLD", "40 – 65", "Neutral", "Market weight; monitor for upgrade/downgrade signals"),
        ("RED — AVOID", "< 40", "Underweight", "Below benchmark or zero allocation; exit candidates"),
    ]
    tl_colors = [GREEN_BG, AMBER_BG, RED_BG]
    tl_text_colors = [GREEN_SIG, AMBER_SIG, RED_SIG]
    for idx, (sig, score, action, impl) in enumerate(tl_items):
        tl_data.append([
            Paragraph(f"<b>{sig}</b>", ParagraphStyle(
                f"tl_{idx}", parent=styles["TableCell"],
                textColor=tl_text_colors[idx], fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            )),
            Paragraph(score, styles["TableCellCenter"]),
            Paragraph(f"<b>{action}</b>", styles["TableCellCenter"]),
            Paragraph(impl, styles["TableCell"]),
        ])
    t = Table(tl_data, colWidths=[95, 80, 70, CONTENT_W - 245])
    tl_style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, bg in enumerate(tl_colors):
        tl_style.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))
    t.setStyle(TableStyle(tl_style))
    elements.append(t)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(
        "<b>Rotation threshold:</b> A sector is only rotated into if the composite score "
        "differential vs the current holding exceeds 15 points. This prevents excessive "
        "turnover from marginal signal changes.",
        styles["BodyText2"],
    ))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9: REGIME ALIGNMENT MATRIX
# ══════════════════════════════════════════════════════════════════════════════

def build_regime_matrix(styles):
    elements = []
    elements.append(Paragraph("9. Regime Alignment Matrix", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "This matrix maps each core sector to Favour (100), Neutral (50), or Avoid (0) "
        "for each of the 5 macro stages. It encodes the historical cyclical affinity of "
        "Indian sectors to business cycle phases.",
        styles["BodyText2"],
    ))

    hdr = [
        Paragraph("<b>Sector Index</b>", styles["TableHeader"]),
        Paragraph("<b>S1\nEarly Exp.</b>", styles["TableHeader"]),
        Paragraph("<b>S2\nMid Exp.</b>", styles["TableHeader"]),
        Paragraph("<b>S3\nLate Exp.</b>", styles["TableHeader"]),
        Paragraph("<b>S4\nEarly Cont.</b>", styles["TableHeader"]),
        Paragraph("<b>S5\nDeep Cont.</b>", styles["TableHeader"]),
    ]
    matrix_data = [hdr]
    for sector, scores in sorted(REGIME_ALIGNMENT_MATRIX.items()):
        row = [Paragraph(sector, styles["TableCell"])]
        for s in scores:
            if s == 100:
                cell_style = ParagraphStyle("fav", parent=styles["TableCellCenter"],
                                            textColor=GREEN_SIG, fontName="Helvetica-Bold")
                label = "Favour"
            elif s == 50:
                cell_style = ParagraphStyle("neu", parent=styles["TableCellCenter"],
                                            textColor=AMBER_SIG, fontName="Helvetica")
                label = "Neutral"
            else:
                cell_style = ParagraphStyle("avo", parent=styles["TableCellCenter"],
                                            textColor=RED_SIG, fontName="Helvetica")
                label = "Avoid"
            row.append(Paragraph(label, cell_style))
        matrix_data.append(row)

    col_w = (CONTENT_W - 155) / 5
    t = Table(matrix_data, colWidths=[155] + [col_w] * 5)

    m_style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for row_idx in range(1, len(matrix_data)):
        for col_idx in range(1, 6):
            val = list(REGIME_ALIGNMENT_MATRIX.values())[row_idx - 1][col_idx - 1] if row_idx - 1 < len(REGIME_ALIGNMENT_MATRIX) else 50
            sector_name = sorted(REGIME_ALIGNMENT_MATRIX.keys())[row_idx - 1] if row_idx - 1 < len(REGIME_ALIGNMENT_MATRIX) else ""
            score = REGIME_ALIGNMENT_MATRIX.get(sector_name, [50]*5)[col_idx - 1]
            if score == 100:
                m_style.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), GREEN_BG))
            elif score == 0:
                m_style.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), RED_BG))
            else:
                m_style.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), AMBER_BG))
        bg = WHITE if row_idx % 2 == 1 else LIGHT_GRAY
        m_style.append(("BACKGROUND", (0, row_idx), (0, row_idx), bg))

    t.setStyle(TableStyle(m_style))
    elements.append(t)
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10: INDIA-SPECIFIC CALIBRATIONS
# ══════════════════════════════════════════════════════════════════════════════

def build_india_calibrations(styles):
    elements = []
    elements.append(Paragraph("10. India-Specific Calibrations", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "Global sector rotation frameworks require India-specific adjustments. "
        "The following calibrations override or modulate the quantitative signals "
        "based on structural features of the Indian market.",
        styles["BodyText2"],
    ))

    cal_data = [[
        Paragraph("<b>#</b>", styles["TableHeader"]),
        Paragraph("<b>Calibration</b>", styles["TableHeader"]),
        Paragraph("<b>Mechanism</b>", styles["TableHeader"]),
        Paragraph("<b>Impact</b>", styles["TableHeader"]),
    ]]
    cals = [
        ("1", "RBI Dominates Cycle Timing",
         "Yield curve steepening leads RBI rate cuts by 3–6 months. The 10Y–2Y spread is the primary lead indicator.",
         "Shifts regime classification earlier than other indicators suggest"),
        ("2", "FII Flows Override",
         "INR depreciation + sustained FII outflows trigger a defensive override regardless of other signals.",
         "Rotate to IT/Pharma (USD earners) during INR weakness"),
        ("3", "Monsoon Variable",
         "IMD monsoon forecast (released June) affects rural demand: FMCG, Rural Banking, Auto (tractors).",
         "Boost/penalise rural-linked sectors by ±10 pts on composite"),
        ("4", "Budget & Earnings Calendar",
         "Signal weight reduced by 30% during Union Budget week, results season (Jan/Apr/Jul/Oct).",
         "Prevents false signals from event-driven volatility"),
        ("5", "Global Commodity Sensitivity",
         "Crude, Gold, Copper, DXY mapped to sector impact. Rising crude = bearish Oil & Gas input costs but bullish Energy producers.",
         "Commodity-linked override on Metals, Energy, Oil & Gas"),
    ]
    for num, name, mech, impact in cals:
        cal_data.append([
            Paragraph(num, styles["TableCellCenter"]),
            Paragraph(f"<b>{name}</b>", styles["TableCell"]),
            Paragraph(mech, styles["TableCell"]),
            Paragraph(impact, styles["TableCell"]),
        ])
    t = Table(cal_data, colWidths=[25, 110, (CONTENT_W - 135) / 2, (CONTENT_W - 135) / 2])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11: BACKTEST ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════

def build_backtest_section(styles):
    elements = []
    elements.append(Paragraph("11. Backtest Architecture", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "The framework is validated via an expanding-window walk-forward backtest design. "
        "Three overlapping windows ensure the model generalises across different market regimes.",
        styles["BodyText2"],
    ))

    elements.append(Paragraph("11.1 Walk-Forward Windows", styles["SubSection"]))
    bt_data = [[
        Paragraph("<b>Window</b>", styles["TableHeader"]),
        Paragraph("<b>Training Period</b>", styles["TableHeader"]),
        Paragraph("<b>Test Period</b>", styles["TableHeader"]),
        Paragraph("<b>Regime Coverage</b>", styles["TableHeader"]),
    ]]
    windows = [
        ("Window 1", "Jan 2005 – Dec 2015", "12 months OOS", "GFC 2008, Recovery 2009–10, Taper 2013"),
        ("Window 2", "Jan 2013 – Dec 2020", "12 months OOS", "Demonetization 2016, COVID 2020"),
        ("Window 3", "Jan 2018 – Dec 2024", "12 months OOS", "COVID recovery, Rate hiking 2022–23"),
    ]
    for win, train, test, regime in windows:
        bt_data.append([
            Paragraph(f"<b>{win}</b>", styles["TableCell"]),
            Paragraph(train, styles["TableCellCenter"]),
            Paragraph(test, styles["TableCellCenter"]),
            Paragraph(regime, styles["TableCell"]),
        ])
    t = Table(bt_data, colWidths=[70, 120, 80, CONTENT_W - 270])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("11.2 Validation Targets", styles["SubSection"]))
    target_data = [[
        Paragraph("<b>Metric</b>", styles["TableHeader"]),
        Paragraph("<b>Target</b>", styles["TableHeader"]),
        Paragraph("<b>Description</b>", styles["TableHeader"]),
    ]]
    targets = [
        ("IC Mean", "> 0.05", "Information Coefficient: average rank correlation between predicted and realised returns"),
        ("IC IR", "> 0.3", "IC Information Ratio: consistency of IC across periods"),
        ("Annualised Alpha", "> 4% p.a.", "Excess return vs Nifty 50 buy-and-hold benchmark"),
        ("Sharpe Ratio", "> 0.8", "Risk-adjusted return on the rotation portfolio"),
        ("Max Drawdown", "< 25%", "Worst peak-to-trough decline in portfolio value"),
        ("Hit Rate", "> 55%", "Percentage of months where rotation outperforms benchmark"),
        ("Turnover", "< 1.5 sectors/month", "Average number of sector rotations per rebalancing"),
    ]
    for metric, target, desc in targets:
        target_data.append([
            Paragraph(f"<b>{metric}</b>", styles["TableCell"]),
            Paragraph(target, styles["TableCellCenter"]),
            Paragraph(desc, styles["TableCell"]),
        ])
    t = Table(target_data, colWidths=[100, 90, CONTENT_W - 190])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "<b>Sources:</b> Jacobsen et al. (2009), Miao &amp; Polak (2023), Mateus (2018)",
        styles["SmallItalic"],
    ))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 12: PORTFOLIO CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════

def build_portfolio_section(styles):
    elements = []
    elements.append(Paragraph("12. Portfolio Construction & Risk", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    elements.append(Paragraph(
        "The final portfolio allocation translates composite scores into sector weights "
        "subject to concentration limits and drawdown controls. The process is designed "
        "to support discretionary decision-making, not fully automated execution.",
        styles["BodyText2"],
    ))

    elements.append(Paragraph("12.1 Monthly Dashboard Process (6 Steps)", styles["SubSection"]))
    steps = [
        ("Step 1: Macro Update", "Update 10 macro indicators, compute composite, classify regime stage"),
        ("Step 2: Signal Compute", "Run all 4 signal blocks across 47 indices, produce ranked scorecard CSV"),
        ("Step 3: Composite Score", "Weighted sum of signal blocks, classify traffic light (Green/Amber/Red)"),
        ("Step 4: India Overrides", "Apply FII flow, INR trend, Monsoon, and Calendar event flags"),
        ("Step 5: Discretionary Review", "Human review layer — override signals based on qualitative judgment"),
        ("Step 6: Portfolio Action", "Compare current portfolio weights vs signals, identify rotation candidates"),
    ]
    step_data = [[
        Paragraph("<b>Step</b>", styles["TableHeader"]),
        Paragraph("<b>Description</b>", styles["TableHeader"]),
    ]]
    for step, desc in steps:
        step_data.append([
            Paragraph(f"<b>{step}</b>", styles["TableCell"]),
            Paragraph(desc, styles["TableCell"]),
        ])
    t = Table(step_data, colWidths=[120, CONTENT_W - 120])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("12.2 Risk Controls", styles["SubSection"]))
    elements.append(Paragraph(
        "• <b>Rotation threshold:</b> Minimum 15-point composite score differential to trigger rotation",
        styles["BulletItem"],
    ))
    elements.append(Paragraph(
        "• <b>Max drawdown control:</b> Target < 25% peak-to-trough; automatic de-risking at –20%",
        styles["BulletItem"],
    ))
    elements.append(Paragraph(
        "• <b>Turnover limit:</b> < 1.5 sector rotations per month to control transaction costs",
        styles["BulletItem"],
    ))
    elements.append(Paragraph(
        "• <b>Event window dampening:</b> 30% signal weight reduction during budget week and earnings seasons",
        styles["BulletItem"],
    ))
    elements.append(Paragraph(
        "• <b>Defensive override:</b> Automatic shift to FMCG/Pharma on sustained FII outflow + INR depreciation",
        styles["BulletItem"],
    ))
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 13: IMPLEMENTATION ROADMAP
# ══════════════════════════════════════════════════════════════════════════════

def build_roadmap_section(styles):
    elements = []
    elements.append(Paragraph("13. Implementation Roadmap", styles["SectionTitle"]))
    elements.append(gold_accent_bar())

    road_data = [[
        Paragraph("<b>Phase</b>", styles["TableHeader"]),
        Paragraph("<b>Component</b>", styles["TableHeader"]),
        Paragraph("<b>Deliverable</b>", styles["TableHeader"]),
        Paragraph("<b>Status</b>", styles["TableHeader"]),
    ]]
    phases = [
        ("Phase 1", "Repository Structure & Config", "index_universe.py, regime matrix, signal weights", "Complete"),
        ("Phase 2.1", "Data Fetcher", "OHLCV for 49 indices, quality checks, incremental refresh", "Active"),
        ("Phase 2.2", "Momentum Score", "5-component momentum block (1M/3M/6M/12M/REL_STR)", "Pending"),
        ("Phase 2.3", "Trend Score", "4-component trend block (MA/RSI/ROC/VOL)", "Pending"),
        ("Phase 2.4", "Regime Alignment", "10-indicator macro composite + stage classification", "Pending"),
        ("Phase 2.5", "Valuation Score", "PE/PB/DY z-score valuation block", "Pending"),
        ("Phase 3", "Backtest Validation", "Walk-forward backtest, IC analysis, 16-model ensemble", "Pending"),
        ("Phase 4", "Dashboard & Output", "Master Excel dashboard, automated scorecard generation", "Pending"),
    ]
    status_colors = {"Complete": GREEN_SIG, "Active": AMBER_SIG, "Pending": SLATE}
    for phase, comp, deliv, status in phases:
        status_style = ParagraphStyle(
            f"st_{phase}", parent=styles["TableCellCenter"],
            textColor=status_colors.get(status, SLATE),
            fontName="Helvetica-Bold",
        )
        road_data.append([
            Paragraph(f"<b>{phase}</b>", styles["TableCell"]),
            Paragraph(comp, styles["TableCell"]),
            Paragraph(deliv, styles["TableCell"]),
            Paragraph(status, status_style),
        ])
    t = Table(road_data, colWidths=[60, 120, CONTENT_W - 60 - 120 - 70, 70])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 14: DISCLAIMER
# ══════════════════════════════════════════════════════════════════════════════

def build_disclaimer(styles):
    elements = []
    elements.append(Paragraph("14. Disclaimer", styles["SectionTitle"]))
    elements.append(gold_accent_bar())
    elements.append(Paragraph(
        "This document describes a quantitative research framework for sector rotation in "
        "Indian equity markets. It is intended solely for research and discretionary investment "
        "strategy development purposes.",
        styles["BodyText2"],
    ))
    elements.append(Paragraph(
        "This is <b>not investment advice</b>. Past performance of any model, signal, or "
        "backtest does not guarantee future results. The framework has not yet completed "
        "full backtest validation (Phase 3 pending). No representation is made that any "
        "account will or is likely to achieve profits or losses similar to those discussed. "
        "Sector rotation strategies involve significant risks including but not limited to "
        "market risk, liquidity risk, and model risk.",
        styles["BodyText2"],
    ))
    elements.append(Paragraph(
        "Data sourced from NSE via NSEPython. Macro indicator thresholds are illustrative "
        "and subject to calibration based on ongoing research.",
        styles["SmallItalic"],
    ))
    elements.append(Spacer(1, 10))
    elements.append(section_divider())
    elements.append(Paragraph(
        f"Report generated: {DATE_STR} | India Sector Rotation — Model Trading Framework",
        styles["Footer"],
    ))
    elements.append(Paragraph(
        "Data: NSE via NSEPython | Universe: 47 Rotation + 2 Reference Indices",
        styles["Footer"],
    ))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# PAGE TEMPLATE (header/footer)
# ══════════════════════════════════════════════════════════════════════════════

def header_footer(canvas, doc):
    canvas.saveState()

    # Footer
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SLATE)
    canvas.drawString(MARGIN, 12 * mm,
                      f"India Sector Rotation — Model Trading Framework  |  {DATE_STR}")
    canvas.drawRightString(PAGE_W - MARGIN, 12 * mm,
                           f"Page {doc.page}")

    # Top accent line
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, PAGE_H - 14 * mm, PAGE_W - MARGIN, PAGE_H - 14 * mm)

    canvas.restoreState()


def first_page(canvas, doc):
    pass


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def generate_report():
    output_dir = ROOT_DIR / "outputs"
    output_dir.mkdir(exist_ok=True)
    pdf_path = output_dir / f"MTF_Sector_Rotation_Report_{DATE_FILE}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title="India Sector Rotation — Model Trading Framework",
        author="MTF Research",
    )

    styles = build_styles()
    elements = []

    elements.extend(build_cover(styles))
    elements.extend(build_toc(styles))
    elements.extend(build_executive_summary(styles))
    elements.append(PageBreak())
    elements.extend(build_framework_arch(styles))
    elements.append(PageBreak())
    elements.extend(build_universe_section(styles))
    elements.append(PageBreak())
    elements.extend(build_momentum_section(styles))
    elements.extend(build_trend_section(styles))
    elements.append(PageBreak())
    elements.extend(build_regime_section(styles))
    elements.append(PageBreak())
    elements.extend(build_valuation_section(styles))
    elements.extend(build_composite_section(styles))
    elements.append(PageBreak())
    elements.extend(build_regime_matrix(styles))
    elements.extend(build_india_calibrations(styles))
    elements.append(PageBreak())
    elements.extend(build_backtest_section(styles))
    elements.append(PageBreak())
    elements.extend(build_portfolio_section(styles))
    elements.extend(build_roadmap_section(styles))
    elements.append(PageBreak())
    elements.extend(build_disclaimer(styles))

    doc.build(elements, onFirstPage=first_page, onLaterPages=header_footer)
    print(f"PDF generated: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    generate_report()
