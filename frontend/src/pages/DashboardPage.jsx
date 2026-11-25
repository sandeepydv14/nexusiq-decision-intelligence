import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Columns3,
  Copy,
  Database,
  FileDown,
  Lightbulb,
  MessageSquareText,
  Rows3,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { api } from "../services/api";
import StatCard from "../components/StatCard";
import EmptyState from "../components/EmptyState";

export default function DashboardPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!activeDataset) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .getDashboard(activeDataset.id)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeDataset]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }

  if (loading) {
    return (
      <div className="card loading-box">
        <div className="spinner" /> Calculating real-time dataset analytics...
      </div>
    );
  }

  if (error) {
    return <div className="card" style={{ color: "var(--danger)" }}>Error loading dashboard: {error}</div>;
  }

  if (!data) return null;

  const { overview, quality, insights, recommendations, recent_activity, dataset } = data;
  const qColor =
    quality.score >= 90
      ? "var(--success)"
      : quality.score >= 75
      ? "var(--accent)"
      : quality.score >= 55
      ? "var(--warning)"
      : "var(--danger)";

  return (
    <div className="stack-md">
      {/* KPI Row */}
      <div className="grid-kpi">
        <StatCard
          label="Total Datasets"
          value={data.total_datasets}
          sub="Stored in SQLite"
          icon={Database}
          tone="info"
        />
        <StatCard
          label="Rows × Columns"
          value={`${overview.row_count.toLocaleString()} × ${overview.col_count}`}
          sub={`${overview.memory_kb} KB in memory`}
          icon={Rows3}
          tone="accent"
        />
        <StatCard
          label="Missing Values"
          value={overview.missing_cells.toLocaleString()}
          sub={`${overview.missing_pct}% of ${overview.total_cells.toLocaleString()} cells`}
          icon={AlertTriangle}
          tone={overview.missing_cells > 0 ? "warning" : "success"}
        />
        <StatCard
          label="Duplicate Rows"
          value={overview.duplicate_rows.toLocaleString()}
          sub={`${overview.duplicate_pct}% duplicate rate`}
          icon={Copy}
          tone={overview.duplicate_rows > 0 ? "danger" : "success"}
        />
        <StatCard
          label="Data Quality Score"
          value={`${quality.score}/100`}
          sub={`${quality.grade} • ${quality.total_issues} issue(s)`}
          icon={ShieldCheck}
          tone={quality.score >= 85 ? "success" : quality.score >= 65 ? "warning" : "danger"}
        />
      </div>

      {/* Quick Actions */}
      <div className="card">
        <div className="card-header" style={{ marginBottom: 10 }}>
          <div>
            <h3 className="card-title">Quick Actions</h3>
            <p className="card-subtitle">Jump directly to any analytical stage for "{dataset.name}"</p>
          </div>
        </div>
        <div className="row-wrap">
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate("cleaning")}>
            <Wrench size={14} /> Clean Dataset ({quality.total_issues} issues)
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate("eda")}>
            <BarChart3 size={14} /> Explore Visuals
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate("ml")}>
            <BrainCircuit size={14} /> Train ML Models
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate("ask")}>
            <MessageSquareText size={14} /> Ask Your Data
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => onNavigate("reports")}>
            <FileDown size={14} /> Export PDF / Excel
          </button>
        </div>
      </div>

      {/* Quality Breakdown & Dataset Info */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Quality & Structure Overview</h3>
              <p className="card-subtitle">Transparent weighted score across 4 data health pillars</p>
            </div>
            <span className="badge badge-accent" style={{ fontSize: 13 }}>
              {quality.score}%
            </span>
          </div>

          <div className="stack-sm">
            {quality.score_breakdown.map((item) => (
              <div key={item.dimension} style={{ marginBottom: 4 }}>
                <div className="row-wrap" style={{ justifyContent: "space-between", fontSize: 12.5, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600 }}>
                    {item.dimension} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>({item.weight})</span>
                  </span>
                  <span className="mono">{item.score}/100</span>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${item.score}%`,
                      background: item.score >= 85 ? "var(--success)" : item.score >= 65 ? "var(--warning)" : "var(--danger)",
                    }}
                  />
                </div>
                <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 2 }}>{item.detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Dataset Metadata & Schema</h3>
              <p className="card-subtitle">Detected column roles and file properties</p>
            </div>
            <Columns3 size={18} color="var(--text-muted)" />
          </div>

          <div className="stack-sm" style={{ fontSize: 13 }}>
            <div className="row-wrap" style={{ justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Source File</span>
              <span className="mono">{dataset.original_filename}</span>
            </div>
            <div className="row-wrap" style={{ justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Format & Type</span>
              <span>
                {dataset.file_type} {dataset.is_demo ? "(Sample Demo)" : "(User Upload)"}
              </span>
            </div>
            <div className="row-wrap" style={{ justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Original Dimensions</span>
              <span>
                {dataset.original_row_count.toLocaleString()} rows × {dataset.original_col_count} cols
              </span>
            </div>
            <div className="row-wrap" style={{ justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Applied Cleaning Steps</span>
              <span className="badge badge-neutral">{data.cleaning_steps_count} active step(s)</span>
            </div>
            <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10, marginTop: 4 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: "var(--text-secondary)" }}>
                Detected Column Types
              </div>
              <div className="row-wrap" style={{ gap: 6 }}>
                <span className="badge badge-accent">{overview.numeric_columns.length} Numeric</span>
                <span className="badge badge-info">{overview.categorical_columns.length} Categorical</span>
                <span className="badge badge-success">{overview.datetime_columns.length} Datetime</span>
                {overview.text_columns.length > 0 && (
                  <span className="badge badge-neutral">{overview.text_columns.length} Text</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Important Insights & Recent Activity */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Important Automated Insights</h3>
              <p className="card-subtitle">Real statistical findings calculated from your dataset</p>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate("insights")}>
              All Insights <ArrowRight size={13} />
            </button>
          </div>
          <div className="stack-sm">
            {insights.map((ins) => (
              <div
                key={ins.id}
                style={{
                  padding: "10px 12px",
                  borderRadius: 8,
                  background: "var(--bg-subtle)",
                  borderLeft: `3px solid ${
                    ins.severity === "positive"
                      ? "var(--success)"
                      : ins.severity === "warning"
                      ? "var(--warning)"
                      : "var(--accent)"
                  }`,
                }}
              >
                <div className="row-wrap" style={{ justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{ins.title}</span>
                  <span className="badge badge-neutral">{ins.type}</span>
                </div>
                <div style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{ins.summary}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Top Recommendations & Recent Activity</h3>
              <p className="card-subtitle">Suggested next actions and SQLite audit log</p>
            </div>
            <Lightbulb size={18} color={qColor} />
          </div>
          <div className="stack-sm">
            {recommendations.slice(0, 3).map((rec) => (
              <div
                key={rec.id}
                style={{
                  padding: "9px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12.5 }}>
                    <span
                      className={`badge ${rec.priority === "High" ? "badge-danger" : "badge-warning"}`}
                      style={{ marginRight: 6 }}
                    >
                      {rec.priority}
                    </span>
                    {rec.title}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{rec.action}</div>
                </div>
                <button className="btn btn-secondary btn-sm" onClick={() => onNavigate(rec.target_page || "insights")}>
                  Open
                </button>
              </div>
            ))}

            <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10, marginTop: 4 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: "var(--text-secondary)" }}>
                Recent Platform Activity
              </div>
              {recent_activity.slice(0, 5).map((act) => (
                <div
                  key={act.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 8,
                    fontSize: 12,
                    padding: "4px 0",
                    color: "var(--text-secondary)",
                  }}
                >
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <CheckCircle2 size={12} style={{ verticalAlign: "middle", marginRight: 5, color: "var(--accent)" }} />
                    {act.details}
                  </span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)", flexShrink: 0 }}>
                    {act.action}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
