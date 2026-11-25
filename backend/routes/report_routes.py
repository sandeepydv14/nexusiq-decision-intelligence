import os
from flask import Blueprint, jsonify, send_file

from database.db import get_saved_report_by_id, get_saved_reports
from services.report_exporter import export_cleaned_csv, export_excel_report, export_pdf_report

report_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@report_bp.route("/history", methods=["GET"])
def api_report_history():
    return jsonify({"reports": get_saved_reports()})


@report_bp.route("/<dataset_id>/download/<fmt>", methods=["GET"])
def api_export_and_download(dataset_id: str, fmt: str):
    fmt_lower = fmt.lower()
    try:
        if fmt_lower == "csv":
            res = export_cleaned_csv(dataset_id)
            mime = "text/csv"
        elif fmt_lower in ("excel", "xlsx"):
            res = export_excel_report(dataset_id)
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif fmt_lower == "pdf":
            res = export_pdf_report(dataset_id)
            mime = "application/pdf"
        else:
            return jsonify({"error": "Unsupported export format. Use csv, excel, or pdf."}), 400

        return send_file(res["file_path"], mimetype=mime, as_attachment=True, download_name=res["filename"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"Report export failed: {exc}"}), 500


@report_bp.route("/saved/<int:report_id>/download", methods=["GET"])
def api_download_saved_report(report_id: int):
    rep = get_saved_report_by_id(report_id)
    if not rep or not os.path.exists(rep["file_path"]):
        return jsonify({"error": "Saved report file not found."}), 404
    return send_file(rep["file_path"], as_attachment=True, download_name=os.path.basename(rep["file_path"]))
