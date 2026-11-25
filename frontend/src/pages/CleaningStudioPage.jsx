import React, { useEffect, useState } from "react";
import { Check, Eye, RotateCcw, Undo2, Wrench } from "lucide-react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import DataTable from "../components/DataTable";

const OPERATIONS = [
  { id: "remove_duplicates", label: "Remove Duplicate Rows" },
  { id: "fill_missing", label: "Fill Missing Values (Mean/Median/Mode)" },
  { id: "drop_missing", label: "Remove Rows with Missing Values" },
  { id: "trim_spaces", label: "Trim Extra Spaces & Normalize Case" },
  { id: "handle_outliers", label: "Handle Outliers (Cap or Remove IQR)" },
  { id: "drop_columns", label: "Remove Unnecessary Columns" },
  { id: "rename_column", label: "Rename Column" },
  { id: "change_dtype", label: "Change Data Type" },
  { id: "convert_dates", label: "Convert Column to Date/Time" },
  { id: "filter_rows", label: "Filter Rows by Condition" },
];

export default function CleaningStudioPage({
  activeDataset,
  onNavigate,
  onLoadDemo,
  loadingDemo,
  onDatasetMutated,
  suggestedFix,
  clearSuggestedFix,
  notify,
}) {
  const [columns, setColumns] = useState([]);
  const [history, setHistory] = useState([]);
  const [operation, setOperation] = useState("remove_duplicates");
  const [params, setParams] = useState({});
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadContext = async () => {
    if (!activeDataset) return;
    const [prof, hist] = await Promise.all([
      api.getProfile(activeDataset.id),
      api.getCleaningHistory(activeDataset.id),
    ]);
    setColumns(prof.columns || []);
    setHistory(hist.operations || []);
  };

  useEffect(() => {
    if (!activeDataset) return;
    loadContext().catch((err) => notify("error", "Load Failed", err.message));
  }, [activeDataset?.id, activeDataset?.row_count, activeDataset?.col_count]);

  useEffect(() => {
    if (suggestedFix && suggestedFix.operation) {
      setOperation(suggestedFix.operation);
      setParams(suggestedFix.params || {});
      setPreview(null);
      clearSuggestedFix();
    }
  }, [suggestedFix]);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }

  const numericCols = columns.filter((c) => c.role === "numeric").map((c) => c.name);
  const allColNames = columns.map((c) => c.name);

  const handleOperationChange = (op) => {
    setOperation(op);
    setPreview(null);
    const firstCol = allColNames[0] || "";
    const firstNum = numericCols[0] || firstCol;
    const defaults = {
      remove_duplicates: {},
      fill_missing: { column: "__all__", strategy: "median", value: "" },
      drop_missing: { column: "__all__" },
      trim_spaces: { column: "__all__", normalize_case: "none" },
      handle_outliers: { column: firstNum, method: "cap_iqr", factor: 1.5 },
      drop_columns: { columns: [] },
      rename_column: { column: firstCol, new_name: "" },
      change_dtype: { column: firstCol, target_dtype: "numeric" },
      convert_dates: { column: firstCol, date_format: "" },
      filter_rows: { column: firstCol, operator: "not_null", value: "" },
    };
    setParams(defaults[op] || {});
  };

  const handlePreview = async () => {
    setBusy(true);
    try {
      const res = await api.previewCleaning(activeDataset.id, operation, params);
      setPreview(res);
    } catch (err) {
      notify("error", "Preview Failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleApply = async () => {
    setBusy(true);
    try {
      const res = await api.applyCleaning(activeDataset.id, operation, params);
      setPreview(null);
      setHistory(res.history || []);
      await onDatasetMutated();
      notify("success", "Cleaning Applied", res.summary);
    } catch (err) {
      notify("error", "Cleaning Failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleUndo = async () => {
    setBusy(true);
    try {
      const res = await api.undoCleaning(activeDataset.id);
      setPreview(null);
      setHistory(res.history || []);
      await onDatasetMutated();
      notify("info", "Operation Undone", res.undone);
    } catch (err) {
      notify("error", "Undo Failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    try {
      const res = await api.resetCleaning(activeDataset.id);
      setPreview(null);
      setHistory([]);
      await onDatasetMutated();
      notify("info", "Dataset Reset", res.summary);
    } catch (err) {
      notify("error", "Reset Failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleDropColumn = (colName) => {
    const current = params.columns || [];
    const next = current.includes(colName) ? current.filter((c) => c !== colName) : [...current, colName];
    setParams({ ...params, columns: next });
  };

  return (
    <div className="stack-md">
      {/* Safety Banner & Undo/Reset Bar */}
      <div className="card">
        <div className="row-wrap" style={{ justifyContent: "space-between" }}>
          <div>
            <h3 className="card-title">Non-Destructive Data Cleaning Studio</h3>
            <p className="card-subtitle">
              All changes modify a working copy while preserving your original uploaded file. Preview changes before applying.
            </p>
          </div>
          <div className="row-wrap">
            <button className="btn btn-secondary btn-sm" onClick={handleUndo} disabled={busy || !history.length}>
              <Undo2 size={14} /> Undo Last ({history.length})
            </button>
            <button className="btn btn-danger btn-sm" onClick={handleReset} disabled={busy || !history.length}>
              <RotateCcw size={14} /> Reset to Original
            </button>
          </div>
        </div>
      </div>

      {/* Operation Builder */}
      <div className="grid-2">
        <div className="card stack-md">
          <div>
            <label className="form-label">1. Select Cleaning Operation</label>
            <select className="select" value={operation} onChange={(e) => handleOperationChange(e.target.value)}>
              {OPERATIONS.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.label}
                </option>
              ))}
            </select>
          </div>

          {/* Dynamic Parameters */}
          {operation === "remove_duplicates" && (
            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              Removes exact duplicate rows while keeping the first occurrence.
            </div>
          )}

          {operation === "fill_missing" && (
            <div className="stack-sm">
              <div>
                <label className="form-label">Target Column</label>
                <select
                  className="select"
                  value={params.column || "__all__"}
                  onChange={(e) => setParams({ ...params, column: e.target.value })}
                >
                  <option value="__all__">All Eligible Columns</option>
                  {allColNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="form-label">Imputation Strategy</label>
                <select
                  className="select"
                  value={params.strategy || "median"}
                  onChange={(e) => setParams({ ...params, strategy: e.target.value })}
                >
                  <option value="median">Median (Numeric)</option>
                  <option value="mean">Mean (Numeric)</option>
                  <option value="mode">Mode (Most Frequent)</option>
                  <option value="constant">Custom Constant Value</option>
                </select>
              </div>
              {params.strategy === "constant" && (
                <div>
                  <label className="form-label">Constant Value</label>
                  <input
                    className="input"
                    value={params.value || ""}
                    onChange={(e) => setParams({ ...params, value: e.target.value })}
                    placeholder="e.g. Unknown or 0"
                  />
                </div>
              )}
            </div>
          )}

          {operation === "drop_missing" && (
            <div>
              <label className="form-label">Scope</label>
              <select
                className="select"
                value={params.column || "__all__"}
                onChange={(e) => setParams({ ...params, column: e.target.value })}
              >
                <option value="__all__">Any column has missing value</option>
                {allColNames.map((c) => (
                  <option key={c} value={c}>
                    Missing in '{c}'
                  </option>
                ))}
              </select>
            </div>
          )}

          {operation === "trim_spaces" && (
            <div className="stack-sm">
              <div>
                <label className="form-label">Target Column</label>
                <select
                  className="select"
                  value={params.column || "__all__"}
                  onChange={(e) => setParams({ ...params, column: e.target.value })}
                >
                  <option value="__all__">All Text / Categorical Columns</option>
                  {allColNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="form-label">Case Normalization</label>
                <select
                  className="select"
                  value={params.normalize_case || "none"}
                  onChange={(e) => setParams({ ...params, normalize_case: e.target.value })}
                >
                  <option value="none">Keep Original Case</option>
                  <option value="title">Title Case</option>
                  <option value="upper">UPPERCASE</option>
                  <option value="lower">lowercase</option>
                </select>
              </div>
            </div>
          )}

          {operation === "handle_outliers" && (
            <div className="stack-sm">
              <div>
                <label className="form-label">Numeric Column</label>
                <select
                  className="select"
                  value={params.column || numericCols[0] || ""}
                  onChange={(e) => setParams({ ...params, column: e.target.value })}
                >
                  {numericCols.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid-2">
                <div>
                  <label className="form-label">Action</label>
                  <select
                    className="select"
                    value={params.method || "cap_iqr"}
                    onChange={(e) => setParams({ ...params, method: e.target.value })}
                  >
                    <option value="cap_iqr">Cap to IQR Bounds (Winsorize)</option>
                    <option value="remove_iqr">Remove Outlier Rows</option>
                  </select>
                </div>
                <div>
                  <label className="form-label">IQR Multiplier</label>
                  <input
                    className="input"
                    type="number"
                    step="0.5"
                    min="1"
                    max="5"
                    value={params.factor ?? 1.5}
                    onChange={(e) => setParams({ ...params, factor: Number(e.target.value) })}
                  />
                </div>
              </div>
            </div>
          )}

          {operation === "drop_columns" && (
            <div>
              <label className="form-label">Select Columns to Remove</label>
              <div className="row-wrap" style={{ gap: 8, maxHeight: 150, overflowY: "auto", padding: 6, border: "1px solid var(--border)", borderRadius: 7 }}>
                {allColNames.map((c) => {
                  const checked = (params.columns || []).includes(c);
                  return (
                    <label key={c} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12.5, cursor: "pointer" }}>
                      <input type="checkbox" checked={checked} onChange={() => toggleDropColumn(c)} />
                      {c}
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {operation === "rename_column" && (
            <div className="grid-2">
              <div>
                <label className="form-label">Column</label>
                <select
                  className="select"
                  value={params.column || allColNames[0] || ""}
                  onChange={(e) => setParams({ ...params, column: e.target.value })}
                >
                  {allColNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="form-label">New Column Name</label>
                <input
                  className="input"
                  value={params.new_name || ""}
                  onChange={(e) => setParams({ ...params, new_name: e.target.value })}
                  placeholder="Enter new name"
                />
              </div>
            </div>
          )}

          {operation === "change_dtype" && (
            <div className="grid-2">
              <div>
                <label className="form-label">Column</label>
                <select
                  className="select"
                  value={params.column || allColNames[0] || ""}
                  onChange={(e) => setParams({ ...params, column: e.target.value })}
                >
                  {allColNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="form-label">Target Data Type</label>
                <select
                  className="select"
                  value={params.target_dtype || "numeric"}
                  onChange={(e) => setParams({ ...params, target_dtype: e.target.value })}
                >
                  <option value="numeric">Float / Numeric</option>
                  <option value="integer">Integer (Nullable Int64)</option>
                  <option value="string">String / Text</option>
                  <option value="datetime">Datetime</option>
                  <option value="boolean">Boolean</option>
                </select>
              </div>
            </div>
          )}

          {operation === "convert_dates" && (
            <div className="grid-2">
              <div>
                <label className="form-label">Date Column</label>
                <select
                  className="select"
                  value={params.column || allColNames[0] || ""}
                  onChange={(e) => setParams({ ...params, column: e.target.value })}
                >
                  {allColNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="form-label">Format (Optional)</label>
                <input
                  className="input"
                  value={params.date_format || ""}
                  onChange={(e) => setParams({ ...params, date_format: e.target.value })}
                  placeholder="Auto or e.g. %Y-%m-%d"
                />
              </div>
            </div>
          )}

          {operation === "filter_rows" && (
            <div className="grid-3">
              <div>
                <label className="form-label">Column</label>
                <select
                  className="select"
                  value={params.column || allColNames[0] || ""}
                  onChange={(e) => setParams({ ...params, column: e.target.value })}
                >
                  {allColNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="form-label">Keep Rows Where</label>
                <select
                  className="select"
                  value={params.operator || "not_null"}
                  onChange={(e) => setParams({ ...params, operator: e.target.value })}
                >
                  <option value="not_null">Is Not Null</option>
                  <option value="gte">&gt;= (Greater or Equal)</option>
                  <option value="gt">&gt; (Greater Than)</option>
                  <option value="lte">&lt;= (Less or Equal)</option>
                  <option value="lt">&lt; (Less Than)</option>
                  <option value="eq">== (Equals)</option>
                  <option value="neq">!= (Not Equals)</option>
                  <option value="contains">Contains Text</option>
                </select>
              </div>
              {params.operator !== "not_null" && (
                <div>
                  <label className="form-label">Value</label>
                  <input
                    className="input"
                    value={params.value ?? ""}
                    onChange={(e) => setParams({ ...params, value: e.target.value })}
                    placeholder="e.g. 0"
                  />
                </div>
              )}
            </div>
          )}

          <div className="row-wrap" style={{ paddingTop: 6 }}>
            <button className="btn btn-secondary" onClick={handlePreview} disabled={busy}>
              <Eye size={15} /> Preview Impact
            </button>
            <button className="btn btn-primary" onClick={handleApply} disabled={busy}>
              <Check size={15} /> Apply Operation
            </button>
          </div>
        </div>

        {/* Applied Operation History */}
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Applied Cleaning Pipeline ({history.length})</h3>
              <p className="card-subtitle">Audited step-by-step transformations saved in SQLite</p>
            </div>
            <Wrench size={16} color="var(--text-muted)" />
          </div>

          {!history.length ? (
            <div style={{ padding: 28, textAlign: "center", color: "var(--text-muted)" }}>
              No cleaning operations applied yet. Working copy matches original dataset.
            </div>
          ) : (
            <div className="stack-sm" style={{ maxHeight: 260, overflowY: "auto" }}>
              {history.map((op, i) => (
                <div
                  key={op.id}
                  style={{
                    padding: "9px 12px",
                    borderRadius: 7,
                    background: "var(--bg-subtle)",
                    fontSize: 12.5,
                  }}
                >
                  <div className="row-wrap" style={{ justifyContent: "space-between", fontWeight: 600 }}>
                    <span>
                      #{i + 1} • {op.operation}
                    </span>
                    <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {op.rows_before}→{op.rows_after} rows
                    </span>
                  </div>
                  <div style={{ color: "var(--text-secondary)", marginTop: 2 }}>{op.summary}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Preview Panel */}
      {preview && (
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Operation Impact Preview</h3>
              <p className="card-subtitle">{preview.summary}</p>
            </div>
            <button className="btn btn-primary btn-sm" onClick={handleApply} disabled={busy}>
              <Check size={14} /> Confirm & Apply
            </button>
          </div>

          <div className="grid-kpi">
            <div style={{ padding: 12, borderRadius: 8, background: "var(--bg-subtle)" }}>
              <div className="stat-label">Rows</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>
                {preview.before.rows} → {preview.after.rows}
              </div>
            </div>
            <div style={{ padding: 12, borderRadius: 8, background: "var(--bg-subtle)" }}>
              <div className="stat-label">Columns</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>
                {preview.before.cols} → {preview.after.cols}
              </div>
            </div>
            <div style={{ padding: 12, borderRadius: 8, background: "var(--bg-subtle)" }}>
              <div className="stat-label">Missing Cells</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>
                {preview.before.missing} → {preview.after.missing}
              </div>
            </div>
            <div style={{ padding: 12, borderRadius: 8, background: "var(--bg-subtle)" }}>
              <div className="stat-label">Duplicates</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>
                {preview.before.duplicates} → {preview.after.duplicates}
              </div>
            </div>
          </div>

          <DataTable columns={preview.preview_columns} rows={preview.preview_rows} searchable={false} pageSize={8} />
        </div>
      )}
    </div>
  );
}
