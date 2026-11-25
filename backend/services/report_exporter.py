import io
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import REPORT_DIR, ensure_directories
from database.db import add_saved_report, get_cleaning_operations, get_dataset, log_activity
from services.dataset_manager import load_working_df
from services.insights import generate_insights_and_recommendations
from services.profiler import profile_dataset
from services.quality import analyze_data_quality
from services.utils import get_categorical_columns, get_datetime_columns, get_numeric_columns


def export_cleaned_csv(dataset_id: str) -> Dict[str, str]:
    ensure_directories()
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError("Dataset not found.")
    df = load_working_df(dataset_id)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{dataset_id}_cleaned_{stamp}.csv"
    out_path = REPORT_DIR / filename
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    size = out_path.stat().st_size
    add_saved_report(dataset_id, ds["name"], "CSV", str(out_path), size)
    log_activity("EXPORT_CSV", f"Exported cleaned CSV '{filename}'", dataset_id)
    return {"file_path": str(out_path), "filename": filename}


def export_excel_report(dataset_id: str) -> Dict[str, str]:
    ensure_directories()
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError("Dataset not found.")
    df = load_working_df(dataset_id)
    profile = profile_dataset(df)
    quality = analyze_data_quality(df)
    intel = generate_insights_and_recommendations(df)
    cleaning_ops = get_cleaning_operations(dataset_id, active_only=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{dataset_id}_report_{stamp}.xlsx"
    out_path = REPORT_DIR / filename

    wb = openpyxl.Workbook()
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    section_font = Font(color="0F172A", bold=True, size=13)

    # Sheet 1: Executive Summary
    ws = wb.active
    ws.title = "Executive Summary"
    ws.append(["Autonomous Data Analysis & Decision Intelligence Report"])
    ws["A1"].font = Font(bold=True, size=15, color="1D4ED8")
    ws.append(["Dataset Name", ds["name"]])
    ws.append(["Source File", ds["original_filename"]])
    ws.append(["Rows / Columns", f"{df.shape[0]} rows × {df.shape[1]} columns"])
    ws.append(["Data Quality Score", f"{quality['quality_score']}/100 ({quality['grade']})"])
    ws.append(["Quality Formula", quality["formula"]])
    ws.append(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    ws.append([])

    ws.append(["Key Automated Insights"])
    ws[f"A{ws.max_row}"].font = section_font
    ws.append(["Type", "Title", "Summary", "Supporting Evidence"])
    for cell in ws[ws.max_row]:
        cell.fill = header_fill
        cell.font = header_font
    for ins in intel["insights"]:
        ws.append([ins["type"], ins["title"], ins["summary"], ins["evidence"]])

    ws.append([])
    ws.append(["Actionable Recommendations"])
    ws[f"A{ws.max_row}"].font = section_font
    ws.append(["Priority", "Category", "Recommendation", "Rationale", "Suggested Action"])
    for cell in ws[ws.max_row]:
        cell.fill = header_fill
        cell.font = header_font
    for rec in intel["recommendations"]:
        ws.append([rec["priority"], rec["category"], rec["title"], rec["rationale"], rec["action"]])

    ws.append([])
    ws.append(["Applied Cleaning Operations"])
    ws[f"A{ws.max_row}"].font = section_font
    ws.append(["Operation", "Summary", "Rows Before -> After", "Applied At"])
    for cell in ws[ws.max_row]:
        cell.fill = header_fill
        cell.font = header_font
    for op in cleaning_ops:
        ws.append([op["operation"], op["summary"], f"{op['rows_before']} -> {op['rows_after']}", op["created_at"]])

    # Sheet 2: Data Profile
    ws_prof = wb.create_sheet("Data Profile")
    prof_headers = ["Column", "Role", "Dtype", "Count", "Missing", "Missing %", "Unique", "Mean", "Median", "Std", "Min", "Max", "Outliers"]
    ws_prof.append(prof_headers)
    for cell in ws_prof[1]:
        cell.fill = header_fill
        cell.font = header_font
    for col in profile["columns"]:
        ws_prof.append([
            col["name"],
            col["role"],
            col["dtype"],
            col["count"],
            col["missing_count"],
            col["missing_pct"],
            col["unique_count"],
            col.get("mean", ""),
            col.get("median", ""),
            col.get("std", ""),
            col.get("min", ""),
            col.get("max", ""),
            col.get("outlier_count", ""),
        ])

    # Sheet 3: Quality Issues
    ws_qual = wb.create_sheet("Quality Issues")
    qual_headers = ["Severity", "Category", "Column", "Affected Records", "Problem", "Recommended Solution"]
    ws_qual.append(qual_headers)
    for cell in ws_qual[1]:
        cell.fill = header_fill
        cell.font = header_font
    for iss in quality["issues"]:
        ws_qual.append([
            iss["severity"],
            iss["category"],
            iss["column"],
            iss["affected_records"],
            iss["problem"],
            iss["recommended_solution"],
        ])

    # Sheet 4: Cleaned Data
    ws_data = wb.create_sheet("Cleaned Data")
    ws_data.append(list(df.columns))
    for cell in ws_data[1]:
        cell.fill = header_fill
        cell.font = header_font
    for row in df.itertuples(index=False, name=None):
        safe_row = [str(v) if isinstance(v, pd.Timestamp) else (None if pd.isna(v) else v) for v in row]
        ws_data.append(safe_row)

    # Auto-fit columns reasonably
    for sheet in wb.worksheets:
        for col_cells in sheet.columns:
            max_len = max((len(str(c.value or "")) for c in list(col_cells)[:50]), default=10)
            sheet.column_dimensions[col_cells[0].column_letter].width = min(45, max(12, max_len + 3))

    wb.save(out_path)
    size = out_path.stat().st_size
    add_saved_report(dataset_id, ds["name"], "EXCEL", str(out_path), size)
    log_activity("EXPORT_EXCEL", f"Exported Excel analysis report '{filename}'", dataset_id)
    return {"file_path": str(out_path), "filename": filename}


def _build_pdf_charts(df: pd.DataFrame, tmp_dir: Path) -> list:
    chart_paths = []
    num_cols = [c for c in get_numeric_columns(df) if "id" not in c.lower()] or get_numeric_columns(df)
    cat_cols = [c for c in get_categorical_columns(df) if "id" not in c.lower() and 2 <= df[c].nunique(dropna=True) <= 20]
    dt_cols = get_datetime_columns(df)

    plt.style.use("seaborn-v0_8-whitegrid")

    # Chart 1: Categorical breakdown by primary numeric metric (or counts)
    if cat_cols:
        ccol = cat_cols[0]
        fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=150)
        if num_cols:
            vcol = num_cols[0]
            grp = df.dropna(subset=[ccol, vcol]).groupby(df[ccol].astype(str))[vcol].sum().sort_values(ascending=False).head(8)
            ax.bar(grp.index, grp.values, color="#2563EB")
            ax.set_title(f"Total {vcol} by {ccol}", fontsize=11, fontweight="bold")
            ax.set_ylabel(vcol)
        else:
            vc = df[ccol].dropna().astype(str).value_counts().head(8)
            ax.bar(vc.index, vc.values, color="#2563EB")
            ax.set_title(f"Distribution of {ccol}", fontsize=11, fontweight="bold")
            ax.set_ylabel("Count")
        plt.xticks(rotation=25, ha="right", fontsize=8)
        plt.tight_layout()
        p1 = tmp_dir / "chart_cat.png"
        fig.savefig(p1)
        plt.close(fig)
        chart_paths.append(("Categorical Performance Breakdown", p1))

    # Chart 2: Time series trend or numeric histogram
    if dt_cols and num_cols:
        dcol, vcol = dt_cols[0], num_cols[0]
        ts = pd.DataFrame({"dt": pd.to_datetime(df[dcol], errors="coerce"), "val": pd.to_numeric(df[vcol], errors="coerce")}).dropna()
        if len(ts) >= 5:
            span = (ts["dt"].max() - ts["dt"].min()).days
            freq = "ME" if span >= 120 else ("W" if span >= 28 else "D")
            grouped = ts.set_index("dt")["val"].resample(freq).sum().dropna()
            fig, ax = plt.subplots(figsize=(6.4, 2.9), dpi=150)
            ax.plot(grouped.index, grouped.values, marker="o", color="#0EA5E9", linewidth=2)
            ax.set_title(f"{vcol} Trend Over Time", fontsize=11, fontweight="bold")
            ax.set_ylabel(vcol)
            plt.xticks(rotation=25, ha="right", fontsize=8)
            plt.tight_layout()
            p2 = tmp_dir / "chart_ts.png"
            fig.savefig(p2)
            plt.close(fig)
            chart_paths.append(("Temporal Trend Visualization", p2))
    elif num_cols:
        vcol = num_cols[0]
        clean = pd.to_numeric(df[vcol], errors="coerce").dropna()
        if not clean.empty:
            fig, ax = plt.subplots(figsize=(6.4, 2.9), dpi=150)
            ax.hist(clean, bins=20, color="#6366F1", edgecolor="white")
            ax.set_title(f"Distribution of {vcol}", fontsize=11, fontweight="bold")
            ax.set_xlabel(vcol)
            ax.set_ylabel("Frequency")
            plt.tight_layout()
            p2 = tmp_dir / "chart_hist.png"
            fig.savefig(p2)
            plt.close(fig)
            chart_paths.append((f"Distribution of {vcol}", p2))

    return chart_paths


def export_pdf_report(dataset_id: str) -> Dict[str, str]:
    ensure_directories()
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError("Dataset not found.")
    df = load_working_df(dataset_id)
    profile = profile_dataset(df)
    quality = analyze_data_quality(df)
    intel = generate_insights_and_recommendations(df)
    cleaning_ops = get_cleaning_operations(dataset_id, active_only=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{dataset_id}_report_{stamp}.pdf"
    out_path = REPORT_DIR / filename

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#0F172A"), spaceAfter=6)
    h2_style = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor("#1D4ED8"), spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("BodyCustom", parent=styles["BodyText"], fontSize=9.5, leading=13)

    story = []
    story.append(Paragraph("Autonomous Data Analysis & Decision Intelligence Report", title_style))
    story.append(Paragraph(f"<b>Dataset:</b> {ds['name']} &nbsp;|&nbsp; <b>Source:</b> {ds['original_filename']} &nbsp;|&nbsp; <b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
    story.append(Spacer(1, 10))

    # Overview table
    ov = profile["overview"]
    meta_table = Table(
        [
            ["Rows", "Columns", "Missing Cells", "Duplicate Rows", "Quality Score"],
            [
                str(ov["row_count"]),
                str(ov["col_count"]),
                f"{ov['missing_cells']} ({ov['missing_pct']}%)",
                f"{ov['duplicate_rows']} ({ov['duplicate_pct']}%)",
                f"{quality['quality_score']}/100 ({quality['grade']})",
            ],
        ],
        colWidths=[1.1 * inch, 1.1 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Data Quality Breakdown
    story.append(Paragraph("1. Data Quality Assessment", h2_style))
    story.append(Paragraph(f"<b>Scoring Formula:</b> {quality['formula']}", body_style))
    story.append(Spacer(1, 4))
    q_rows = [["Dimension", "Weight", "Score", "Calculated Detail"]]
    for d in quality["score_breakdown"]:
        q_rows.append([d["dimension"], d["weight"], f"{d['score']}/100", Paragraph(d["detail"], body_style)])
    q_table = Table(q_rows, colWidths=[1.5 * inch, 0.7 * inch, 0.8 * inch, 3.7 * inch])
    q_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(q_table)

    # Numeric Statistical Summary
    story.append(Paragraph("2. Statistical Column Profile", h2_style))
    prof_rows = [["Column", "Role", "Missing", "Unique", "Mean", "Median", "Std Dev"]]
    for col in profile["columns"][:14]:
        prof_rows.append(
            [
                col["name"][:22],
                col["role"],
                f"{col['missing_count']} ({col['missing_pct']}%)",
                str(col["unique_count"]),
                str(col.get("mean", "-")),
                str(col.get("median", "-")),
                str(col.get("std", "-")),
            ]
        )
    p_table = Table(prof_rows, colWidths=[1.5 * inch, 0.85 * inch, 1.0 * inch, 0.65 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch])
    p_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ]
        )
    )
    story.append(p_table)

    # Charts
    with tempfile.TemporaryDirectory() as tmp_str:
        charts = _build_pdf_charts(df, Path(tmp_str))
        if charts:
            story.append(Paragraph("3. Exploratory Visualizations", h2_style))
            for caption, cpath in charts:
                story.append(Paragraph(f"<b>{caption}</b>", body_style))
                story.append(Image(str(cpath), width=6.2 * inch, height=2.85 * inch))
                story.append(Spacer(1, 6))

        # Insights
        story.append(Paragraph("4. Automated Evidence-Backed Insights", h2_style))
        for ins in intel["insights"]:
            story.append(Paragraph(f"• <b>[{ins['type']}] {ins['title']}:</b> {ins['summary']} <i>({ins['evidence']})</i>", body_style))
            story.append(Spacer(1, 3))

        # Recommendations
        story.append(Paragraph("5. Actionable Recommendations", h2_style))
        for rec in intel["recommendations"]:
            story.append(Paragraph(f"• <b>[{rec['priority']} Priority] {rec['title']}:</b> {rec['rationale']} <b>Action:</b> {rec['action']}", body_style))
            story.append(Spacer(1, 3))

        # Methodology & Cleaning History
        story.append(Paragraph("6. Methodology & Audit Trail", h2_style))
        story.append(
            Paragraph(
                "Profiling uses Pandas/NumPy/SciPy for parametric and non-parametric statistics. "
                "Anomaly detection combines IQR fences (1.5×IQR), Z-score standardization (|z|>3), and Scikit-Learn Isolation Forest. "
                "Supervised ML pipelines apply train/test splitting prior to imputation, StandardScaler, and OneHotEncoder to prevent data leakage. "
                f"Applied cleaning steps on this dataset: {len(cleaning_ops)}.",
                body_style,
            )
        )

        doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch, bottomMargin=0.55 * inch)
        doc.build(story)

    size = out_path.stat().st_size
    add_saved_report(dataset_id, ds["name"], "PDF", str(out_path), size)
    log_activity("EXPORT_PDF", f"Exported PDF analysis report '{filename}'", dataset_id)
    return {"file_path": str(out_path), "filename": filename}
