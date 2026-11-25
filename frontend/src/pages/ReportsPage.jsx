import React, { useEffect, useState } from "react";
import { Download, FileSpreadsheet, FileText, FileType } from "lucide-react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";

export default function ReportsPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo, notify }) {
  const [reports, setReports] = useState([]);
  const [downloading, setDownloading] = useState("");

  const loadReports = () => {
    api.getReportHistory().then((res) => setReports(res.reports || []));
  };

  useEffect(() => {
    loadReports();
  }, [activeDataset?.id]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }

  const triggerExport = async (fmt) => {
    setDownloading(fmt);
    try {
      const url = api.getDownloadUrl(activeDataset.id, fmt);
      const res = await fetch(url);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Download failed");
      }
      const blob = await res.blob();
      const cd = res.headers.get("content-disposition") || "";
      const match = cd.match(/filename="?([^";]+)"?/i);
      const ext = fmt === "excel" ? "xlsx" : fmt;
      const filename = match ? match[1] : `${activeDataset.id}_report.${ext}`;

      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);

      notify("success", "Export Complete", `Downloaded ${filename}`);
      loadReports();
    } catch (err) {
      notify("error", "Export Failed", err.message);
    } finally {
      setDownloading("");
    }
  };

  return (
    <div className="stack-md">
      <div className="grid-3">
        <div className="card stack-sm">
          <div className="row-wrap" style={{ gap: 10 }}>
            <div className="stat-icon" style={{ background: "var(--info-soft)", color: "var(--info)" }}>
              <FileType size={18} />
            </div>
            <div>
              <h3 className="card-title">Cleaned Dataset (CSV)</h3>
              <p className="card-subtitle">UTF-8 CSV of your working dataset</p>
            </div>
          </div>
          <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0 }}>
            Exports all rows and columns after your Cleaning Studio transformations without modifying the original upload.
          </p>
          <button
            className="btn btn-secondary"
            onClick={() => triggerExport("csv")}
            disabled={!!downloading}
          >
            <Download size={15} /> {downloading === "csv" ? "Preparing CSV..." : "Download Cleaned CSV"}
          </button>
        </div>

        <div className="card stack-sm">
          <div className="row-wrap" style={{ gap: 10 }}>
            <div className="stat-icon" style={{ background: "var(--success-soft)", color: "var(--success)" }}>
              <FileSpreadsheet size={18} />
            </div>
            <div>
              <h3 className="card-title">Excel Analysis Workbook</h3>
              <p className="card-subtitle">Multi-sheet styled .xlsx report</p>
            </div>
          </div>
          <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0 }}>
            Includes Executive Summary, Insights & Recommendations, Column Profile, Quality Issues, and Cleaned Data sheets.
          </p>
          <button
            className="btn btn-secondary"
            onClick={() => triggerExport("excel")}
            disabled={!!downloading}
          >
            <Download size={15} /> {downloading === "excel" ? "Building Excel..." : "Download Excel Report"}
          </button>
        </div>

        <div className="card stack-sm">
          <div className="row-wrap" style={{ gap: 10 }}>
            <div className="stat-icon" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
              <FileText size={18} />
            </div>
            <div>
              <h3 className="card-title">Executive PDF Report</h3>
              <p className="card-subtitle">Publication-grade PDF with charts</p>
            </div>
          </div>
          <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0 }}>
            Contains dataset metrics, quality score breakdown, statistical profile, generated charts, insights, recommendations, and methodology.
          </p>
          <button
            className="btn btn-primary"
            onClick={() => triggerExport("pdf")}
            disabled={!!downloading}
          >
            <Download size={15} /> {downloading === "pdf" ? "Rendering PDF..." : "Download PDF Report"}
          </button>
        </div>
      </div>

      {/* Saved Reports History */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Generated Report Archive ({reports.length})</h3>
            <p className="card-subtitle">Persisted in SQLite across sessions</p>
          </div>
        </div>
        {!reports.length ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
            No reports exported yet. Click any download button above to generate one.
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Dataset</th>
                  <th>Format</th>
                  <th>File Size</th>
                  <th>Created At</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id}>
                    <td className="mono">#{r.id}</td>
                    <td style={{ fontWeight: 600 }}>{r.dataset_name}</td>
                    <td>
                      <span className="badge badge-accent">{r.report_type}</span>
                    </td>
                    <td className="mono">{(r.file_size / 1024).toFixed(1)} KB</td>
                    <td className="mono" style={{ fontSize: 12 }}>{r.created_at}</td>
                    <td>
                      <a
                        className="btn btn-secondary btn-sm"
                        href={api.getSavedReportDownloadUrl(r.id)}
                        style={{ textDecoration: "none" }}
                      >
                        <Download size={13} /> Download
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
