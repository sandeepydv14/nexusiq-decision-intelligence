import React, { useEffect, useState } from "react";
import { AlertCircle, Play, TrendingUp } from "lucide-react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import PlotlyChart from "../components/PlotlyChart";
import StatCard from "../components/StatCard";

export default function ForecastingPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo, notify, theme }) {
  const [suitability, setSuitability] = useState(null);
  const [dateCol, setDateCol] = useState("");
  const [targetCol, setTargetCol] = useState("");
  const [horizon, setHorizon] = useState(6);
  const [freq, setFreq] = useState("auto");
  const [agg, setAgg] = useState("sum");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDataset) return;
    setResult(null);
    api.getForecastSuitability(activeDataset.id).then((s) => {
      setSuitability(s);
      if (s.suitable) {
        const dCol = s.date_columns[0];
        const tCol = s.numeric_columns.find((c) => /revenue|sales|profit/i.test(c)) || s.numeric_columns[0];
        setDateCol(dCol);
        setTargetCol(tCol);
      }
    });
  }, [activeDataset?.id, activeDataset?.row_count, activeDataset?.col_count]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }

  const handleRun = async () => {
    setLoading(true);
    try {
      const res = await api.runForecast(activeDataset.id, {
        date_column: dateCol,
        target_column: targetCol,
        horizon,
        freq,
        agg,
      });
      setResult(res);
      notify("success", "Forecast Generated", `Projected ${res.horizon} ${res.granularity.toLowerCase()} periods for '${targetCol}'.`);
    } catch (err) {
      notify("error", "Forecasting Error", err.message);
    } finally {
      setLoading(false);
    }
  };

  if (suitability && !suitability.suitable) {
    return (
      <div className="card" style={{ maxWidth: 620, margin: "24px auto" }}>
        <div className="row-wrap" style={{ gap: 10, color: "var(--warning)", marginBottom: 8 }}>
          <AlertCircle size={20} />
          <h3 className="card-title" style={{ margin: 0 }}>Dataset Not Suitable for Forecasting</h3>
        </div>
        <p style={{ color: "var(--text-secondary)", margin: "0 0 14px" }}>{suitability.reason}</p>
        <button className="btn btn-secondary btn-sm" onClick={() => onNavigate("cleaning")}>
          Go to Cleaning Studio (Convert Dates)
        </button>
      </div>
    );
  }

  return (
    <div className="stack-md">
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Time-Series Forecasting Engine</h3>
            <p className="card-subtitle">Compares Naive Baseline, Moving Average, and Holt-Winters Exponential Smoothing with holdout validation</p>
          </div>
          <button className="btn btn-primary" onClick={handleRun} disabled={loading || !dateCol || !targetCol}>
            <Play size={15} /> {loading ? "Forecasting..." : "Generate Forecast"}
          </button>
        </div>

        {suitability && (
          <div className="grid-kpi" style={{ marginBottom: 0 }}>
            <div>
              <label className="form-label">Date Column</label>
              <select className="select" value={dateCol} onChange={(e) => setDateCol(e.target.value)}>
                {suitability.date_columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">Target Metric</label>
              <select className="select" value={targetCol} onChange={(e) => setTargetCol(e.target.value)}>
                {suitability.numeric_columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">Granularity</label>
              <select className="select" value={freq} onChange={(e) => setFreq(e.target.value)}>
                <option value="auto">Auto-Detect</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
            <div>
              <label className="form-label">Aggregation</label>
              <select className="select" value={agg} onChange={(e) => setAgg(e.target.value)}>
                <option value="sum">Sum</option>
                <option value="mean">Mean (Average)</option>
              </select>
            </div>
            <div>
              <label className="form-label">Forecast Horizon (Periods)</label>
              <input
                className="input"
                type="number"
                min="1"
                max="24"
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
              />
            </div>
          </div>
        )}
      </div>

      {result && (
        <>
          <div className="grid-kpi">
            <StatCard label="Observed Periods" value={result.periods_observed} sub={`Granularity: ${result.granularity}`} icon={TrendingUp} />
            <StatCard label="Historical Trend" value={result.trend.direction} sub={`Change: ${result.trend.change_pct}% (slope ${result.trend.slope_per_period})`} tone={result.trend.direction === "Increasing" ? "success" : "warning"} />
            <StatCard label="Recommended Method" value={result.recommended_method} sub={`Lowest backtest RMSE (${result.backtest_periods} holdout periods)`} tone="accent" />
          </div>

          <div className="card">
            <PlotlyChart
              theme={theme}
              height={370}
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers",
                  name: "Historical Actuals",
                  x: result.historical.dates,
                  y: result.historical.values,
                  line: { color: "#2563eb", width: 2.5 },
                },
                ...result.models.map((m, idx) => ({
                  type: "scatter",
                  mode: "lines+markers",
                  name: m.method,
                  x: [result.historical.dates[result.historical.dates.length - 1], ...result.future_dates],
                  y: [result.historical.values[result.historical.values.length - 1], ...m.forecast],
                  line: {
                    dash: idx === 2 ? "solid" : "dot",
                    width: idx === 2 ? 2.5 : 2,
                    color: ["#94a3b8", "#f59e0b", "#16a34a"][idx],
                  },
                })),
              ]}
              layout={{
                title: `${result.granularity} ${result.target_column} Forecast (+${result.horizon} periods)`,
                xaxis: { title: result.date_column },
                yaxis: { title: result.target_column },
              }}
            />
          </div>

          <div className="card">
            <h3 className="card-title" style={{ marginBottom: 10 }}>
              Forecasting Model Evaluation & Projected Values
            </h3>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Backtest MAE</th>
                    <th>Backtest RMSE</th>
                    {result.future_dates.map((d) => (
                      <th key={d}>{d}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.models.map((m) => (
                    <tr key={m.key}>
                      <td style={{ fontWeight: 600 }}>{m.method}</td>
                      <td className="mono">{m.mae}</td>
                      <td className="mono">{m.rmse}</td>
                      {m.forecast.map((v, idx) => (
                        <td className="mono" key={idx}>
                          {v}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
