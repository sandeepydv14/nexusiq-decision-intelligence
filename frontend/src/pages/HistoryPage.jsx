import React, { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "../services/api";

export default function HistoryPage({ onSelectDataset, onNavigate }) {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api
      .getHistory()
      .then(setHistory)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  if (loading || !history) {
    return (
      <div className="card loading-box">
        <div className="spinner" /> Loading persistent SQLite history...
      </div>
    );
  }

  return (
    <div className="stack-md">
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Stored Datasets ({history.datasets.length})</h3>
            <p className="card-subtitle">All datasets persist locally in SQLite across application restarts</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Source File</th>
                <th>Shape</th>
                <th>Quality Score</th>
                <th>Updated</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {history.datasets.map((d) => (
                <tr key={d.id}>
                  <td style={{ fontWeight: 600 }}>
                    {d.name} {d.is_demo && <span className="badge badge-warning">Demo</span>}
                  </td>
                  <td className="mono">{d.original_filename}</td>
                  <td className="mono">
                    {d.row_count} × {d.col_count}
                  </td>
                  <td>{d.quality_score !== null ? `${d.quality_score}/100` : "—"}</td>
                  <td className="mono" style={{ fontSize: 11.5 }}>{d.updated_at}</td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        onSelectDataset(d.id);
                        onNavigate("dashboard");
                      }}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
              {!history.datasets.length && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "var(--text-muted)", padding: 20 }}>
                    No datasets stored yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 10 }}>
            Analysis Runs ({history.analyses.length})
          </h3>
          {!history.analyses.length ? (
            <div style={{ color: "var(--text-muted)", padding: 16 }}>No ML, Forecasting, or Anomaly runs recorded yet.</div>
          ) : (
            <div className="stack-sm" style={{ maxHeight: 320, overflowY: "auto" }}>
              {history.analyses.map((a) => (
                <div key={a.id} style={{ padding: "9px 12px", borderRadius: 8, background: "var(--bg-subtle)", fontSize: 12.5 }}>
                  <div className="row-wrap" style={{ justifyContent: "space-between", fontWeight: 600 }}>
                    <span>{a.title}</span>
                    <span className="badge badge-accent">{a.analysis_type}</span>
                  </div>
                  <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 2 }}>
                    Dataset: {a.dataset_name || a.dataset_id} • {a.created_at}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 10 }}>
            Platform Activity Log ({history.activity.length})
          </h3>
          {!history.activity.length ? (
            <div style={{ color: "var(--text-muted)", padding: 16 }}>No activity logged yet.</div>
          ) : (
            <div className="stack-sm" style={{ maxHeight: 320, overflowY: "auto" }}>
              {history.activity.map((act) => (
                <div key={act.id} style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
                  <div className="row-wrap" style={{ justifyContent: "space-between" }}>
                    <span style={{ fontWeight: 500 }}>{act.details}</span>
                    <span className="badge badge-neutral">{act.action}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>{act.created_at}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
