import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import PlotlyChart from "../components/PlotlyChart";
import StatCard from "../components/StatCard";
import { Activity, AlertCircle, Columns3, Copy } from "lucide-react";

export default function ProfilingPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo, theme }) {
  const [profile, setProfile] = useState(null);
  const [selectedCol, setSelectedCol] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDataset) return;
    setLoading(true);
    api
      .getProfile(activeDataset.id)
      .then((res) => {
        setProfile(res);
        if (res.columns?.length) setSelectedCol(res.columns[0].name);
      })
      .finally(() => setLoading(false));
  }, [activeDataset?.id, activeDataset?.row_count, activeDataset?.col_count]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }
  if (loading || !profile) {
    return (
      <div className="card loading-box">
        <div className="spinner" /> Profiling dataset columns and distributions...
      </div>
    );
  }

  const { overview, columns, correlation } = profile;
  const activeColObj = columns.find((c) => c.name === selectedCol) || columns[0];

  const renderSelectedChart = () => {
    if (!activeColObj) return null;
    if (activeColObj.histogram) {
      const { counts, edges } = activeColObj.histogram;
      const labels = counts.map((_, i) => `${edges[i]} – ${edges[i + 1]}`);
      return (
        <PlotlyChart
          theme={theme}
          height={310}
          data={[
            {
              type: "bar",
              x: labels,
              y: counts,
              marker: { color: "#2563eb" },
              name: activeColObj.name,
            },
          ]}
          layout={{
            title: `Distribution of ${activeColObj.name}`,
            xaxis: { title: "Value Bins" },
            yaxis: { title: "Frequency" },
          }}
        />
      );
    }
    if (activeColObj.top_values?.length) {
      return (
        <PlotlyChart
          theme={theme}
          height={310}
          data={[
            {
              type: "bar",
              x: activeColObj.top_values.map((t) => t.value),
              y: activeColObj.top_values.map((t) => t.count),
              marker: { color: "#0ea5e9" },
            },
          ]}
          layout={{
            title: `Top Values in ${activeColObj.name}`,
            xaxis: { title: activeColObj.name },
            yaxis: { title: "Count" },
          }}
        />
      );
    }
    return <div style={{ padding: 30, color: "var(--text-muted)", textAlign: "center" }}>No chart available for this column type.</div>;
  };

  return (
    <div className="stack-md">
      <div className="grid-kpi">
        <StatCard label="Total Columns" value={overview.col_count} sub={`${overview.numeric_columns.length} numeric, ${overview.categorical_columns.length} categorical`} icon={Columns3} />
        <StatCard label="Total Rows" value={overview.row_count.toLocaleString()} sub={`${overview.memory_kb} KB`} icon={Activity} tone="info" />
        <StatCard label="Missing Cells" value={overview.missing_cells} sub={`${overview.missing_pct}% missing`} icon={AlertCircle} tone={overview.missing_cells > 0 ? "warning" : "success"} />
        <StatCard label="Duplicate Records" value={overview.duplicate_rows} sub={`${overview.duplicate_pct}% duplicate`} icon={Copy} tone={overview.duplicate_rows > 0 ? "danger" : "success"} />
      </div>

      {/* Column Statistical Matrix */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Automated Column Statistics</h3>
            <p className="card-subtitle">Mean, median, mode, standard deviation, min/max, missing values, unique counts, and IQR outliers</p>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Column</th>
                <th>Role</th>
                <th>Type</th>
                <th>Missing</th>
                <th>Unique</th>
                <th>Mean</th>
                <th>Median</th>
                <th>Mode</th>
                <th>Std Dev</th>
                <th>Min</th>
                <th>Max</th>
                <th>Outliers</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((c) => (
                <tr
                  key={c.name}
                  onClick={() => setSelectedCol(c.name)}
                  style={{
                    cursor: "pointer",
                    background: selectedCol === c.name ? "var(--accent-soft)" : undefined,
                  }}
                >
                  <td style={{ fontWeight: 600 }}>{c.name}</td>
                  <td>
                    <span className="badge badge-neutral">{c.role}</span>
                  </td>
                  <td className="mono" style={{ fontSize: 11.5 }}>{c.dtype}</td>
                  <td>
                    {c.missing_count > 0 ? (
                      <span className="badge badge-warning">
                        {c.missing_count} ({c.missing_pct}%)
                      </span>
                    ) : (
                      "0"
                    )}
                  </td>
                  <td>{c.unique_count}</td>
                  <td className="mono">{c.mean ?? "—"}</td>
                  <td className="mono">{c.median ?? "—"}</td>
                  <td>{c.mode !== null && c.mode !== undefined ? String(c.mode) : "—"}</td>
                  <td className="mono">{c.std ?? "—"}</td>
                  <td className="mono">{c.min !== undefined ? String(c.min).slice(0, 10) : "—"}</td>
                  <td className="mono">{c.max !== undefined ? String(c.max).slice(0, 10) : "—"}</td>
                  <td>
                    {c.outlier_count ? (
                      <span className="badge badge-danger">
                        {c.outlier_count} ({c.outlier_pct}%)
                      </span>
                    ) : (
                      c.role === "numeric" ? "0" : "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Column Distribution + Correlation Matrix */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Column Distribution Inspector</h3>
              <p className="card-subtitle">Click a row above or choose a column to inspect its distribution</p>
            </div>
            <select
              className="select"
              style={{ width: 190 }}
              value={selectedCol}
              onChange={(e) => setSelectedCol(e.target.value)}
            >
              {columns.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({c.role})
                </option>
              ))}
            </select>
          </div>
          {renderSelectedChart()}
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Numeric Correlation Matrix</h3>
              <p className="card-subtitle">Pearson correlation coefficients across numeric features</p>
            </div>
          </div>
          {correlation.columns.length >= 2 ? (
            <PlotlyChart
              theme={theme}
              height={310}
              data={[
                {
                  type: "heatmap",
                  z: correlation.matrix,
                  x: correlation.columns,
                  y: correlation.columns,
                  colorscale: "RdBu",
                  zmin: -1,
                  zmax: 1,
                },
              ]}
              layout={{ title: "Pearson Correlation Heatmap" }}
            />
          ) : (
            <div style={{ padding: 30, textAlign: "center", color: "var(--text-muted)" }}>
              Need at least 2 numeric columns to compute correlations.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
