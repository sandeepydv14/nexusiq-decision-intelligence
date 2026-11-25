import React, { useEffect, useState } from "react";
import { AlertTriangle, Play } from "lucide-react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import PlotlyChart from "../components/PlotlyChart";
import StatCard from "../components/StatCard";
import DataTable from "../components/DataTable";

export default function AnomalyPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo, notify, theme }) {
  const [numericCols, setNumericCols] = useState([]);
  const [selectedCols, setSelectedCols] = useState([]);
  const [method, setMethod] = useState("iqr");
  const [threshold, setThreshold] = useState(1.5);
  const [contamination, setContamination] = useState(0.05);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDataset) return;
    setResult(null);
    api.getProfile(activeDataset.id).then((prof) => {
      const nums = prof.overview?.numeric_columns || [];
      setNumericCols(nums);
      const defaults = nums.filter((c) => !c.toLowerCase().includes("id")).slice(0, 3);
      const initCols = defaults.length ? defaults : nums.slice(0, 3);
      setSelectedCols(initCols);
      if (initCols.length) {
        runDetection("iqr", initCols, 1.5, 0.05);
      }
    });
  }, [activeDataset?.id, activeDataset?.row_count]);

  const runDetection = async (m = method, cols = selectedCols, thresh = threshold, contam = contamination) => {
    if (!activeDataset) return;
    setLoading(true);
    try {
      const res = await api.runAnomaly(activeDataset.id, {
        method: m,
        columns: cols,
        threshold: thresh,
        contamination: contam,
      });
      setResult(res);
    } catch (err) {
      notify("error", "Anomaly Scan Failed", err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }

  const toggleCol = (c) => {
    setSelectedCols((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  };

  return (
    <div className="stack-md">
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Anomaly Detection Configuration</h3>
            <p className="card-subtitle">Detect unusual records using IQR fences, Z-score standardization, or Isolation Forest</p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => runDetection()}
            disabled={loading || !selectedCols.length}
          >
            <Play size={15} /> {loading ? "Scanning..." : "Run Detection"}
          </button>
        </div>

        <div className="grid-3">
          <div>
            <label className="form-label">Detection Method</label>
            <select
              className="select"
              value={method}
              onChange={(e) => {
                const m = e.target.value;
                setMethod(m);
                if (m === "iqr") setThreshold(1.5);
                if (m === "zscore") setThreshold(3.0);
              }}
            >
              <option value="iqr">IQR (Interquartile Range)</option>
              <option value="zscore">Z-Score (Standard Deviations)</option>
              <option value="isolation_forest">Isolation Forest (Multivariate ML)</option>
            </select>
          </div>

          {method === "iqr" && (
            <div>
              <label className="form-label">IQR Multiplier (Default 1.5)</label>
              <input
                className="input"
                type="number"
                step="0.5"
                min="1"
                max="5"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
              />
            </div>
          )}

          {method === "zscore" && (
            <div>
              <label className="form-label">Z-Score Cutoff |z| &gt; (Default 3.0)</label>
              <input
                className="input"
                type="number"
                step="0.5"
                min="1.5"
                max="6"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
              />
            </div>
          )}

          {method === "isolation_forest" && (
            <div>
              <label className="form-label">Expected Contamination (0.01 – 0.30)</label>
              <input
                className="input"
                type="number"
                step="0.01"
                min="0.01"
                max="0.30"
                value={contamination}
                onChange={(e) => setContamination(Number(e.target.value))}
              />
            </div>
          )}

          <div>
            <label className="form-label">Numerical Columns ({selectedCols.length} selected)</label>
            <div className="row-wrap" style={{ gap: 8, padding: "6px 8px", border: "1px solid var(--border)", borderRadius: 7 }}>
              {numericCols.map((c) => (
                <label key={c} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, cursor: "pointer" }}>
                  <input type="checkbox" checked={selectedCols.includes(c)} onChange={() => toggleCol(c)} />
                  {c}
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>

      {result && (
        <>
          <div className="grid-kpi">
            <StatCard label="Anomalous Records" value={result.anomaly_count} sub={`Out of ${result.total_records} rows`} icon={AlertTriangle} tone="danger" />
            <StatCard label="Anomaly Percentage" value={`${result.anomaly_pct}%`} sub={`Method: ${result.method.toUpperCase()}`} tone="warning" />
            <StatCard label="Evaluated Features" value={result.selected_columns.length} sub={result.selected_columns.join(", ")} tone="info" />
          </div>

          <div className="card">
            <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 }}>
              <strong>Method Explanation:</strong> {result.explanation}
            </div>
            {result.chart && (
              <PlotlyChart
                theme={theme}
                height={340}
                data={[
                  {
                    type: "scatter",
                    mode: "markers",
                    name: "Normal Records",
                    x: result.chart.normal.x,
                    y: result.chart.normal.y,
                    marker: { color: "#64748b", size: 6, opacity: 0.45 },
                  },
                  {
                    type: "scatter",
                    mode: "markers",
                    name: "Detected Anomalies",
                    x: result.chart.anomaly.x,
                    y: result.chart.anomaly.y,
                    text: result.chart.anomaly.text,
                    marker: { color: "#dc2626", size: 10, symbol: "diamond" },
                  },
                ]}
                layout={{
                  title:
                    result.chart.type === "scatter2d"
                      ? `Anomaly Visualization: ${result.chart.x_col} vs ${result.chart.y_col}`
                      : `Anomaly Visualization: ${result.chart.y_col}`,
                  xaxis: { title: result.chart.x_col || "Row Index" },
                  yaxis: { title: result.chart.y_col },
                }}
              />
            )}
          </div>

          <div className="card">
            <h3 className="card-title" style={{ marginBottom: 10 }}>
              Flagged Anomalous Records (Sorted by Severity)
            </h3>
            <DataTable
              columns={["_row_index", "_anomaly_score", "_reason", ...result.columns.slice(0, 6)]}
              rows={result.anomalous_records}
              pageSize={10}
              emptyText="No anomalies detected with the current parameters."
            />
          </div>
        </>
      )}
    </div>
  );
}
