import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import PlotlyChart from "../components/PlotlyChart";
import DataTable from "../components/DataTable";

export default function EdaPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo, theme }) {
  const [eda, setEda] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    num_col: "",
    cat_col: "",
    scatter_x: "",
    scatter_y: "",
    date_col: "",
    agg_metric: "sum",
  });

  const fetchEda = (override = filters) => {
    if (!activeDataset) return;
    setLoading(true);
    api
      .getEda(activeDataset.id, override)
      .then((res) => {
        setEda(res);
        if (res.selectors?.selected) {
          setFilters((prev) => ({
            num_col: prev.num_col || res.selectors.selected.num_col || "",
            cat_col: prev.cat_col || res.selectors.selected.cat_col || "",
            scatter_x: prev.scatter_x || res.selectors.selected.scatter_x || "",
            scatter_y: prev.scatter_y || res.selectors.selected.scatter_y || "",
            date_col: prev.date_col || res.selectors.selected.date_col || "",
            agg_metric: prev.agg_metric || "sum",
          }));
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setFilters({ num_col: "", cat_col: "", scatter_x: "", scatter_y: "", date_col: "", agg_metric: "sum" });
    if (activeDataset) {
      fetchEda({ num_col: "", cat_col: "", scatter_x: "", scatter_y: "", date_col: "", agg_metric: "sum" });
    }
  }, [activeDataset?.id, activeDataset?.row_count, activeDataset?.col_count]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }
  if (loading && !eda) {
    return (
      <div className="card loading-box">
        <div className="spinner" /> Generating automated exploratory visualizations...
      </div>
    );
  }
  if (!eda) return null;

  const { selectors } = eda;

  const updateFilter = (key, val) => {
    const next = { ...filters, [key]: val };
    setFilters(next);
    fetchEda(next);
  };

  return (
    <div className="stack-md">
      {/* Interactive EDA Controls */}
      <div className="card">
        <div className="card-header" style={{ marginBottom: 10 }}>
          <div>
            <h3 className="card-title">Automated EDA Controls</h3>
            <p className="card-subtitle">Customize dimensions and metrics; charts update interactively from real data</p>
          </div>
          {loading && <div className="spinner" />}
        </div>

        <div className="grid-kpi" style={{ marginBottom: 0 }}>
          <div>
            <label className="form-label">Primary Numeric Metric</label>
            <select className="select" value={filters.num_col} onChange={(e) => updateFilter("num_col", e.target.value)}>
              {selectors.numeric_columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">Primary Category</label>
            <select className="select" value={filters.cat_col} onChange={(e) => updateFilter("cat_col", e.target.value)}>
              {selectors.categorical_columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">Scatter X Axis</label>
            <select className="select" value={filters.scatter_x} onChange={(e) => updateFilter("scatter_x", e.target.value)}>
              {selectors.numeric_columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">Scatter Y Axis</label>
            <select className="select" value={filters.scatter_y} onChange={(e) => updateFilter("scatter_y", e.target.value)}>
              {selectors.numeric_columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">Time Aggregation</label>
            <select className="select" value={filters.agg_metric} onChange={(e) => updateFilter("agg_metric", e.target.value)}>
              <option value="sum">Sum</option>
              <option value="mean">Average (Mean)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Time Series + Group Comparison */}
      <div className="grid-2">
        {eda.time_series && (
          <div className="card">
            <PlotlyChart
              theme={theme}
              height={320}
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers",
                  x: eda.time_series.dates,
                  y: eda.time_series.values,
                  line: { color: "#2563eb", width: 2.5 },
                  marker: { size: 6 },
                  name: eda.time_series.value_col,
                },
              ]}
              layout={{
                title: `${eda.time_series.granularity} ${eda.time_series.value_col} (${eda.time_series.aggregation})`,
                xaxis: { title: eda.time_series.date_col },
                yaxis: { title: eda.time_series.value_col },
              }}
            />
          </div>
        )}

        {eda.group_comparison && (
          <div className="card">
            <PlotlyChart
              theme={theme}
              height={320}
              data={[
                {
                  type: "bar",
                  x: eda.group_comparison.rows.map((r) => r.category),
                  y: eda.group_comparison.rows.map((r) => r[filters.agg_metric === "mean" ? "mean" : "sum"]),
                  marker: { color: "#0ea5e9" },
                  name: eda.group_comparison.numeric_col,
                },
              ]}
              layout={{
                title: `${filters.agg_metric === "mean" ? "Average" : "Total"} ${eda.group_comparison.numeric_col} by ${eda.group_comparison.category_col}`,
                xaxis: { title: eda.group_comparison.category_col },
                yaxis: { title: eda.group_comparison.numeric_col },
              }}
            />
          </div>
        )}
      </div>

      {/* Scatter + Box Plot */}
      <div className="grid-2">
        {eda.scatter_plot && (
          <div className="card">
            <PlotlyChart
              theme={theme}
              height={320}
              data={[
                {
                  type: "scatter",
                  mode: "markers",
                  x: eda.scatter_plot.x,
                  y: eda.scatter_plot.y,
                  text: eda.scatter_plot.color || undefined,
                  marker: { size: 7, opacity: 0.7, color: "#6366f1" },
                },
              ]}
              layout={{
                title: `${eda.scatter_plot.x_col} vs ${eda.scatter_plot.y_col} (r = ${eda.scatter_plot.correlation ?? "N/A"})`,
                xaxis: { title: eda.scatter_plot.x_col },
                yaxis: { title: eda.scatter_plot.y_col },
              }}
            />
          </div>
        )}

        {eda.box_plot && (
          <div className="card">
            <PlotlyChart
              theme={theme}
              height={320}
              data={eda.box_plot.groups.map((g) => ({
                type: "box",
                name: g.name,
                y: g.values,
                boxpoints: "outliers",
              }))}
              layout={{
                title: eda.box_plot.category
                  ? `${eda.box_plot.numeric} Spread by ${eda.box_plot.category}`
                  : "Numeric Feature Spread (Box Plots)",
                yaxis: { title: eda.box_plot.numeric },
              }}
            />
          </div>
        )}
      </div>

      {/* Numeric Histograms + Categorical Bars */}
      <div className="grid-2">
        {eda.numeric_distributions.slice(0, 2).map((dist) => (
          <div className="card" key={dist.column}>
            <PlotlyChart
              theme={theme}
              height={290}
              data={[
                {
                  type: "histogram",
                  x: dist.values,
                  marker: { color: "#2563eb" },
                  nbinsx: 20,
                },
              ]}
              layout={{
                title: `Histogram: ${dist.column} (mean=${dist.mean}, median=${dist.median})`,
                xaxis: { title: dist.column },
                yaxis: { title: "Count" },
              }}
            />
          </div>
        ))}
      </div>

      {/* Top & Bottom Categories + Summary Table */}
      {eda.top_bottom && (
        <div className="grid-2">
          <div className="card">
            <h3 className="card-title" style={{ marginBottom: 10 }}>
              Top Performing {eda.top_bottom.category_col} ({eda.top_bottom.metric_col})
            </h3>
            <DataTable rows={eda.top_bottom.top} searchable={false} pageSize={5} />
          </div>
          <div className="card">
            <h3 className="card-title" style={{ marginBottom: 10 }}>
              Lowest Performing {eda.top_bottom.category_col} ({eda.top_bottom.metric_col})
            </h3>
            <DataTable rows={eda.top_bottom.bottom} searchable={false} pageSize={5} />
          </div>
        </div>
      )}

      {eda.correlation && (
        <div className="card">
          <PlotlyChart
            theme={theme}
            height={340}
            data={[
              {
                type: "heatmap",
                z: eda.correlation.matrix,
                x: eda.correlation.columns,
                y: eda.correlation.columns,
                colorscale: "RdBu",
                zmin: -1,
                zmax: 1,
              },
            ]}
            layout={{ title: "Correlation Heatmap Across Numeric Features" }}
          />
        </div>
      )}

      <div className="card">
        <h3 className="card-title" style={{ marginBottom: 10 }}>
          Numeric Summary Statistics
        </h3>
        <DataTable rows={eda.summary_table} searchable={false} pageSize={15} />
      </div>
    </div>
  );
}
