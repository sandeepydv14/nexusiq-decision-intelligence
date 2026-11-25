import React, { useEffect, useState } from "react";
import { ShieldCheck, Wrench } from "lucide-react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";

export default function QualityPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo, onSuggestFix }) {
  const [quality, setQuality] = useState(null);
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDataset) return;
    setLoading(true);
    api
      .getQuality(activeDataset.id)
      .then(setQuality)
      .finally(() => setLoading(false));
  }, [activeDataset?.id, activeDataset?.row_count, activeDataset?.col_count]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }
  if (loading || !quality) {
    return (
      <div className="card loading-box">
        <div className="spinner" /> Auditing dataset integrity...
      </div>
    );
  }

  const filteredIssues = quality.issues.filter(
    (iss) => severityFilter === "ALL" || iss.severity === severityFilter
  );

  const badgeClass = (sev) => (sev === "High" ? "badge-danger" : sev === "Medium" ? "badge-warning" : "badge-info");

  return (
    <div className="stack-md">
      {/* Score Card */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Transparent Data Quality Score</h3>
            <p className="card-subtitle">Formula: {quality.formula}</p>
          </div>
          <div className="row-wrap">
            <span className="badge badge-accent" style={{ fontSize: 15, padding: "6px 14px" }}>
              <ShieldCheck size={16} /> {quality.quality_score} / 100 ({quality.grade})
            </span>
          </div>
        </div>

        <div className="grid-kpi" style={{ marginBottom: 0 }}>
          {quality.score_breakdown.map((dim) => (
            <div key={dim.dimension} style={{ padding: 12, borderRadius: 8, background: "var(--bg-subtle)" }}>
              <div className="row-wrap" style={{ justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{dim.dimension}</span>
                <span className="badge badge-neutral">{dim.weight}</span>
              </div>
              <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>{dim.score}/100</div>
              <div className="progress-track" style={{ marginBottom: 6 }}>
                <div
                  className="progress-fill"
                  style={{
                    width: `${dim.score}%`,
                    background: dim.score >= 85 ? "var(--success)" : dim.score >= 65 ? "var(--warning)" : "var(--danger)",
                  }}
                />
              </div>
              <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>{dim.detail}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Issues List */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Detected Quality Issues ({quality.total_issues})</h3>
            <p className="card-subtitle">
              High: {quality.severity_counts.High} • Medium: {quality.severity_counts.Medium} • Low: {quality.severity_counts.Low}
            </p>
          </div>
          <div className="row-wrap">
            {["ALL", "High", "Medium", "Low"].map((sev) => (
              <button
                key={sev}
                className={`btn btn-sm ${severityFilter === sev ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setSeverityFilter(sev)}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>

        {filteredIssues.length === 0 ? (
          <div style={{ padding: 28, textAlign: "center", color: "var(--success)", fontWeight: 500 }}>
            No issues match the selected filter. Your dataset is in great shape!
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Category</th>
                  <th>Column</th>
                  <th>Affected</th>
                  <th>Problem Description</th>
                  <th>Recommended Solution</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredIssues.map((iss) => (
                  <tr key={iss.id}>
                    <td>
                      <span className={`badge ${badgeClass(iss.severity)}`}>{iss.severity}</span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{iss.category}</td>
                    <td className="mono">{iss.column}</td>
                    <td className="mono">{iss.affected_records.toLocaleString()}</td>
                    <td style={{ whiteSpace: "normal", minWidth: 220 }}>{iss.problem}</td>
                    <td style={{ whiteSpace: "normal", minWidth: 240, color: "var(--text-secondary)" }}>
                      {iss.recommended_solution}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onSuggestFix(iss.suggested_action)}
                      >
                        <Wrench size={13} /> Fix in Studio
                      </button>
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
