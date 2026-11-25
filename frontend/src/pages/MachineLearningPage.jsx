import React, { useEffect, useState } from "react";
import { BrainCircuit, Play, ShieldAlert } from "lucide-react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import PlotlyChart from "../components/PlotlyChart";
import StatCard from "../components/StatCard";

export default function MachineLearningPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo, notify, theme }) {
  const [meta, setMeta] = useState(null);
  const [target, setTarget] = useState("");
  const [taskType, setTaskType] = useState("auto");
  const [selectedFeatures, setSelectedFeatures] = useState([]);
  const [testSize, setTestSize] = useState(0.2);
  const [result, setResult] = useState(null);
  const [training, setTraining] = useState(false);

  useEffect(() => {
    if (!activeDataset) return;
    setResult(null);
    api.getMlMetadata(activeDataset.id).then((m) => {
      setMeta(m);
      if (m.targets?.length) {
        const pref = m.targets.find((t) => /profit|revenue|category|segment/i.test(t.column)) || m.targets[0];
        setTarget(pref.column);
        setTaskType(pref.suggested_task);
        const feats = m.features
          .map((f) => f.column)
          .filter((c) => c !== pref.column && !c.toLowerCase().includes("order_id"));
        setSelectedFeatures(feats);
      }
    });
  }, [activeDataset?.id, activeDataset?.row_count, activeDataset?.col_count]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }

  const handleTargetChange = (newTarget) => {
    setTarget(newTarget);
    const tObj = meta?.targets.find((t) => t.column === newTarget);
    if (tObj) setTaskType(tObj.suggested_task);
    setSelectedFeatures((prev) => prev.filter((f) => f !== newTarget));
  };

  const toggleFeature = (col) => {
    setSelectedFeatures((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]));
  };

  const handleTrain = async () => {
    setTraining(true);
    try {
      const res = await api.trainMl(activeDataset.id, {
        target_column: target,
        feature_columns: selectedFeatures,
        task_type: taskType,
        test_size: testSize,
      });
      setResult(res);
      notify("success", "Models Trained", `Evaluated ${res.models.length} ${res.task_type} models on '${target}'.`);
    } catch (err) {
      notify("error", "Training Failed", err.message);
    } finally {
      setTraining(false);
    }
  };

  const best = result?.best_model;

  return (
    <div className="stack-md">
      <div className="card stack-md">
        <div className="card-header" style={{ marginBottom: 0 }}>
          <div>
            <h3 className="card-title">Supervised Machine Learning Workbench</h3>
            <p className="card-subtitle">
              Leakage-free Scikit-Learn pipelines: train/test split occurs prior to imputation, scaling, and one-hot encoding
            </p>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleTrain}
            disabled={training || !target || !selectedFeatures.length}
          >
            <Play size={15} /> {training ? "Training Models..." : "Train & Compare Models"}
          </button>
        </div>

        {meta && (
          <div className="grid-3">
            <div>
              <label className="form-label">Target Column (Predict)</label>
              <select className="select" value={target} onChange={(e) => handleTargetChange(e.target.value)}>
                {meta.targets.map((t) => (
                  <option key={t.column} value={t.column}>
                    {t.column} ({t.suggested_task})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">Problem Type</label>
              <select className="select" value={taskType} onChange={(e) => setTaskType(e.target.value)}>
                <option value="regression">Regression (Continuous Target)</option>
                <option value="classification">Classification (Discrete Classes)</option>
              </select>
            </div>
            <div>
              <label className="form-label">Test Split Ratio ({Math.round(testSize * 100)}% Test)</label>
              <input
                type="range"
                min="0.1"
                max="0.4"
                step="0.05"
                value={testSize}
                onChange={(e) => setTestSize(Number(e.target.value))}
                style={{ width: "100%", marginTop: 8 }}
              />
            </div>
          </div>
        )}

        {meta && (
          <div>
            <div className="row-wrap" style={{ justifyContent: "space-between", marginBottom: 6 }}>
              <label className="form-label" style={{ marginBottom: 0 }}>
                Feature Columns ({selectedFeatures.length} selected)
              </label>
              <div className="row-wrap" style={{ gap: 6 }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setSelectedFeatures(meta.features.map((f) => f.column).filter((c) => c !== target))}
                >
                  Select All
                </button>
                <button className="btn btn-secondary btn-sm" onClick={() => setSelectedFeatures([])}>
                  Clear
                </button>
              </div>
            </div>
            <div className="row-wrap" style={{ gap: 8, padding: 10, border: "1px solid var(--border)", borderRadius: 8 }}>
              {meta.features
                .filter((f) => f.column !== target)
                .map((f) => (
                  <label key={f.column} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12.5, cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={selectedFeatures.includes(f.column)}
                      onChange={() => toggleFeature(f.column)}
                    />
                    {f.column} <span style={{ color: "var(--text-muted)", fontSize: 11 }}>({f.role})</span>
                  </label>
                ))}
            </div>
          </div>
        )}
      </div>

      {result && best && (
        <>
          <div className="grid-kpi">
            <StatCard label="Best Model" value={best.algorithm} sub={`Task: ${result.task_type}`} icon={BrainCircuit} tone="accent" />
            {result.task_type === "regression" ? (
              <>
                <StatCard label="R² Score" value={best.r2_score} sub="Variance explained on test set" tone="success" />
                <StatCard label="RMSE" value={best.rmse} sub="Root Mean Squared Error" tone="info" />
                <StatCard label="MAE" value={best.mae} sub="Mean Absolute Error" tone="warning" />
              </>
            ) : (
              <>
                <StatCard label="Accuracy" value={`${(best.accuracy * 100).toFixed(1)}%`} sub="Test set accuracy" tone="success" />
                <StatCard label="F1 Score (Weighted)" value={best.f1_score} sub={`Precision: ${best.precision}`} tone="info" />
                <StatCard label="Recall (Weighted)" value={best.recall} sub={`${result.train_rows} train / ${result.test_rows} test`} tone="warning" />
              </>
            )}
          </div>

          <div className="card" style={{ padding: "12px 16px", background: "var(--bg-subtle)" }}>
            <div className="row-wrap" style={{ fontSize: 12.5 }}>
              <ShieldAlert size={15} color="var(--success)" />
              <strong>Data Leakage Prevention:</strong>
              <span style={{ color: "var(--text-secondary)" }}>
                {result.leakage_prevention} ({result.train_rows} train rows, {result.test_rows} test rows)
              </span>
            </div>
          </div>

          {/* Model Comparison Table */}
          <div className="card">
            <h3 className="card-title" style={{ marginBottom: 10 }}>
              Model Comparison Results
            </h3>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Algorithm</th>
                    {result.task_type === "regression" ? (
                      <>
                        <th>R² Score</th>
                        <th>MAE</th>
                        <th>RMSE</th>
                      </>
                    ) : (
                      <>
                        <th>Accuracy</th>
                        <th>Precision</th>
                        <th>Recall</th>
                        <th>F1 Score</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {result.models.map((m) => (
                    <tr key={m.algorithm_key} style={{ fontWeight: m.algorithm_key === best.algorithm_key ? 600 : 400 }}>
                      <td>
                        {m.algorithm}
                        {m.algorithm_key === best.algorithm_key && (
                          <span className="badge badge-success" style={{ marginLeft: 8 }}>
                            Best
                          </span>
                        )}
                      </td>
                      {result.task_type === "regression" ? (
                        <>
                          <td className="mono">{m.r2_score}</td>
                          <td className="mono">{m.mae}</td>
                          <td className="mono">{m.rmse}</td>
                        </>
                      ) : (
                        <>
                          <td className="mono">{(m.accuracy * 100).toFixed(2)}%</td>
                          <td className="mono">{m.precision}</td>
                          <td className="mono">{m.recall}</td>
                          <td className="mono">{m.f1_score}</td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Actual vs Predicted + Feature Importance */}
          <div className="grid-2">
            <div className="card">
              {result.task_type === "regression" ? (
                <PlotlyChart
                  theme={theme}
                  height={330}
                  data={[
                    {
                      type: "scatter",
                      mode: "markers",
                      name: "Test Predictions",
                      x: best.actual_vs_predicted.actual,
                      y: best.actual_vs_predicted.predicted,
                      marker: { color: "#2563eb", size: 7, opacity: 0.7 },
                    },
                    {
                      type: "scatter",
                      mode: "lines",
                      name: "Ideal (y = x)",
                      x: [Math.min(...best.actual_vs_predicted.actual), Math.max(...best.actual_vs_predicted.actual)],
                      y: [Math.min(...best.actual_vs_predicted.actual), Math.max(...best.actual_vs_predicted.actual)],
                      line: { color: "#16a34a", dash: "dash" },
                    },
                  ]}
                  layout={{
                    title: `Actual vs Predicted (${best.algorithm})`,
                    xaxis: { title: `Actual ${result.target_column}` },
                    yaxis: { title: `Predicted ${result.target_column}` },
                  }}
                />
              ) : (
                <PlotlyChart
                  theme={theme}
                  height={330}
                  data={[
                    {
                      type: "heatmap",
                      z: best.confusion_matrix.matrix,
                      x: best.confusion_matrix.labels,
                      y: best.confusion_matrix.labels,
                      colorscale: "Blues",
                    },
                  ]}
                  layout={{
                    title: `Confusion Matrix (${best.algorithm})`,
                    xaxis: { title: "Predicted Class" },
                    yaxis: { title: "Actual Class" },
                  }}
                />
              )}
            </div>

            <div className="card">
              {best.feature_importance?.length ? (
                <PlotlyChart
                  theme={theme}
                  height={330}
                  data={[
                    {
                      type: "bar",
                      orientation: "h",
                      y: [...best.feature_importance].reverse().map((f) => f.feature),
                      x: [...best.feature_importance].reverse().map((f) => f.importance),
                      marker: { color: "#0ea5e9" },
                    },
                  ]}
                  layout={{
                    title: `Feature Importance (${best.algorithm})`,
                    xaxis: { title: "Relative Importance" },
                    margin: { l: 130 },
                  }}
                />
              ) : (
                <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)" }}>
                  Feature importance is not directly exposed for {best.algorithm} (e.g., KNN). Switch to Random Forest or Decision Tree to inspect feature weights.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
