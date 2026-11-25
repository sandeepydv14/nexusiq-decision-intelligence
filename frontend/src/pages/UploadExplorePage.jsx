import React, { useEffect, useRef, useState } from "react";
import {
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  Search,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { api } from "../services/api";

export default function UploadExplorePage({
  datasets,
  activeDataset,
  onSelectDataset,
  onRefreshDatasets,
  onLoadDemo,
  loadingDemo,
  notify,
}) {
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [customName, setCustomName] = useState("");

  // Server-side paginated preview state
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("");
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    setPage(1);
    setSearch("");
    setSortBy("");
  }, [activeDataset?.id]);

  useEffect(() => {
    if (!activeDataset) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    setLoadingPreview(true);
    api
      .previewDataset(activeDataset.id, { page, page_size: pageSize, search, sort_by: sortBy, sort_dir: sortDir })
      .then((res) => {
        if (!cancelled) setPreview(res);
      })
      .catch((err) => {
        if (!cancelled) notify("error", "Preview Failed", err.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingPreview(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeDataset?.id, activeDataset?.row_count, activeDataset?.col_count, activeDataset?.sheet_name, page, pageSize, search, sortBy, sortDir]);

  const handleFileUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await api.uploadDataset(file, customName);
      setCustomName("");
      await onRefreshDatasets(res.dataset.id);
      notify("success", "Dataset Uploaded", `Loaded '${res.dataset.name}' (${res.dataset.row_count} rows).`);
    } catch (err) {
      notify("error", "Upload Error", err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleSheetChange = async (sheet) => {
    try {
      const res = await api.switchSheet(activeDataset.id, sheet);
      await onRefreshDatasets(res.dataset.id);
      notify("success", "Sheet Switched", `Loaded sheet '${sheet}'.`);
    } catch (err) {
      notify("error", "Sheet Switch Failed", err.message);
    }
  };

  const handleDelete = async (id, name) => {
    try {
      await api.deleteDataset(id);
      await onRefreshDatasets();
      notify("info", "Dataset Deleted", `Removed '${name}'.`);
    } catch (err) {
      notify("error", "Delete Failed", err.message);
    }
  };

  const toggleSort = (colName) => {
    if (sortBy === colName) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(colName);
      setSortDir("asc");
    }
  };

  return (
    <div className="stack-md">
      {/* Upload & Dataset Management */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Upload Dataset</h3>
              <p className="card-subtitle">Supports CSV, XLSX, and XLS files up to 50 MB</p>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={onLoadDemo} disabled={loadingDemo}>
              <Sparkles size={14} /> {loadingDemo ? "Loading..." : "Load Demo Dataset"}
            </button>
          </div>

          <div style={{ marginBottom: 12 }}>
            <label className="form-label">Optional Dataset Label</label>
            <input
              className="input"
              placeholder="e.g. Q3 Regional Sales"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
            />
          </div>

          <div
            className={`dropzone ${dragOver ? "drag-over" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) handleFileUpload(f);
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFileUpload(f);
                e.target.value = "";
              }}
            />
            <UploadCloud size={28} style={{ color: "var(--accent)", marginBottom: 8 }} />
            <div style={{ fontWeight: 600 }}>
              {uploading ? "Uploading and profiling dataset..." : "Click to choose or drag & drop a file"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
              Automatic schema inference, date detection, and non-destructive storage
            </div>
          </div>
        </div>

        {/* Dataset Manager */}
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Loaded Datasets ({datasets.length})</h3>
              <p className="card-subtitle">Switch active dataset, select Excel sheets, or manage files</p>
            </div>
          </div>

          {!datasets.length ? (
            <div style={{ padding: 28, textAlign: "center", color: "var(--text-muted)" }}>
              No datasets loaded yet. Upload a CSV/Excel file or click "Load Demo Dataset".
            </div>
          ) : (
            <div className="stack-sm" style={{ maxHeight: 260, overflowY: "auto" }}>
              {datasets.map((d) => {
                const isActive = activeDataset?.id === d.id;
                return (
                  <div
                    key={d.id}
                    style={{
                      padding: "10px 12px",
                      borderRadius: 8,
                      border: `1px solid ${isActive ? "var(--accent)" : "var(--border)"}`,
                      background: isActive ? "var(--accent-soft)" : "var(--bg-subtle)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <div style={{ minWidth: 0, cursor: "pointer", flex: 1 }} onClick={() => onSelectDataset(d.id)}>
                      <div style={{ fontWeight: 600, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
                        <FileSpreadsheet size={14} />
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name}</span>
                        {d.is_demo && <span className="badge badge-warning">Sample</span>}
                      </div>
                      <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 2 }}>
                        {d.file_type} • {d.row_count.toLocaleString()} rows × {d.col_count} cols
                        {d.quality_score !== null && d.quality_score !== undefined && ` • Quality: ${d.quality_score}/100`}
                      </div>
                    </div>
                    <div className="row-wrap" style={{ gap: 6 }}>
                      {!isActive && (
                        <button className="btn btn-secondary btn-sm" onClick={() => onSelectDataset(d.id)}>
                          Select
                        </button>
                      )}
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(d.id, d.name)}
                        title="Delete dataset"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {activeDataset?.available_sheets?.length > 1 && (
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
              <label className="form-label">Excel Worksheet Selection</label>
              <select
                className="select"
                value={activeDataset.sheet_name || ""}
                onChange={(e) => handleSheetChange(e.target.value)}
              >
                {activeDataset.available_sheets.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Data Explorer Table */}
      {activeDataset && preview && (
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Dataset Inspector — {activeDataset.name}</h3>
              <p className="card-subtitle">
                Click any column header to sort. Search matches across all columns.
              </p>
            </div>
            <div className="row-wrap">
              <div style={{ position: "relative", width: 240 }}>
                <Search size={14} style={{ position: "absolute", left: 10, top: 10, color: "var(--text-muted)" }} />
                <input
                  className="input"
                  style={{ paddingLeft: 30 }}
                  placeholder="Filter rows..."
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                />
              </div>
              <select
                className="select"
                style={{ width: 110 }}
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
              >
                <option value={15}>15 / page</option>
                <option value={25}>25 / page</option>
                <option value={50}>50 / page</option>
                <option value={100}>100 / page</option>
              </select>
            </div>
          </div>

          {loadingPreview ? (
            <div className="loading-box">
              <div className="spinner" /> Loading rows...
            </div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 60 }}>#</th>
                      {preview.columns.map((col) => (
                        <th
                          key={col.name}
                          onClick={() => toggleSort(col.name)}
                          style={{ cursor: "pointer", userSelect: "none" }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                            <span>{col.name}</span>
                            <ArrowUpDown size={11} style={{ opacity: sortBy === col.name ? 1 : 0.4 }} />
                          </div>
                          <div style={{ fontSize: 10, fontWeight: 500, color: "var(--text-muted)", marginTop: 2 }}>
                            {col.role} • {col.dtype}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, idx) => (
                      <tr key={idx}>
                        <td className="mono" style={{ color: "var(--text-muted)" }}>
                          {row._row_index}
                        </td>
                        {preview.columns.map((col) => (
                          <td key={col.name} title={row[col.name] === null ? "NULL" : String(row[col.name])}>
                            {row[col.name] === null || row[col.name] === undefined ? (
                              <span style={{ color: "var(--danger)", fontStyle: "italic", fontSize: 11 }}>NULL</span>
                            ) : (
                              String(row[col.name])
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="row-wrap" style={{ justifyContent: "space-between", marginTop: 12 }}>
                <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
                  Showing page {preview.pagination.page} of {preview.pagination.total_pages} (
                  {preview.pagination.total_rows.toLocaleString()} matching rows)
                </span>
                <div className="row-wrap">
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    <ChevronLeft size={14} /> Previous
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={page >= preview.pagination.total_pages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
