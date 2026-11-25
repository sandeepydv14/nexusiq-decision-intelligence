import React, { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Lightbulb } from "lucide-react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import StatCard from "../components/StatCard";

export default function InsightsPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDataset) return;
    setLoading(true);
    api
      .getInsights(activeDataset.id)
      .then(setData)
      .finally(() => setLoading(false));
  }, [activeDataset?.id, activeDataset?.row_count, activeDataset?.col_count]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }
  if (loading || !data) {
    return (
      <div className="card loading-box">
        <div className="spinner" /> Synthesizing evidence-backed insights and recommendations...
      </div>
    );
  }

  return (
    <div className="stack-md">
      <div className="grid-kpi">
        <StatCard label="Calculated Insights" value={data.summary_counts.total_insights} sub="Derived from real statistics" icon={Lightbulb} tone="accent" />
        <StatCard label="Actionable Recommendations" value={data.summary_counts.total_recommendations} sub={`${data.summary_counts.high_priority} High Priority`} icon={CheckCircle2} tone="success" />
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Automated Statistical Insights</h3>
              <p className="card-subtitle">Every finding includes supporting quantitative evidence</p>
            </div>
          </div>
          <div className="stack-sm">
            {data.insights.map((ins) => (
              <div
                key={ins.id}
                style={{
                  padding: "12px 14px",
                  borderRadius: 8,
                  background: "var(--bg-subtle)",
                  borderLeft: `4px solid ${
                    ins.severity === "positive"
                      ? "var(--success)"
                      : ins.severity === "warning"
                      ? "var(--warning)"
                      : "var(--accent)"
                  }`,
                }}
              >
                <div className="row-wrap" style={{ justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 13.5 }}>{ins.title}</span>
                  <span className="badge badge-neutral">{ins.type}</span>
                </div>
                <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 5 }}>{ins.summary}</div>
                <div className="mono" style={{ fontSize: 11.5, color: "var(--text-muted)" }}>
                  Evidence: {ins.evidence}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Decision Recommendations</h3>
              <p className="card-subtitle">Prioritized actions grounded in detected findings</p>
            </div>
          </div>
          <div className="stack-sm">
            {data.recommendations.map((rec) => (
              <div
                key={rec.id}
                style={{
                  padding: "12px 14px",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              >
                <div className="row-wrap" style={{ justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 13.5 }}>{rec.title}</span>
                  <span
                    className={`badge ${
                      rec.priority === "High" ? "badge-danger" : rec.priority === "Medium" ? "badge-warning" : "badge-info"
                    }`}
                  >
                    {rec.priority} Priority
                  </span>
                </div>
                <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginBottom: 6 }}>
                  <strong>Finding:</strong> {rec.rationale}
                </div>
                <div className="row-wrap" style={{ justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 12.5, color: "var(--accent)", fontWeight: 500, flex: 1 }}>
                    Action: {rec.action}
                  </span>
                  <button className="btn btn-secondary btn-sm" onClick={() => onNavigate(rec.target_page || "dashboard")}>
                    Launch <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
