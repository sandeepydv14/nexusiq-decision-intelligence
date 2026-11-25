import React, { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";

export default function DataTable({ columns = [], rows = [], pageSize = 10, searchable = true, emptyText = "No records found." }) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  const inferredCols = useMemo(() => {
    if (columns.length) return columns;
    if (!rows.length) return [];
    return Object.keys(rows[0]).filter((k) => !k.startsWith("_"));
  }, [columns, rows]);

  const filtered = useMemo(() => {
    if (!query.trim()) return rows;
    const q = query.toLowerCase();
    return rows.filter((r) => inferredCols.some((c) => String(r[c] ?? "").toLowerCase().includes(q)));
  }, [rows, query, inferredCols]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  return (
    <div className="stack-sm">
      {searchable && (
        <div className="row-wrap" style={{ justifyContent: "space-between" }}>
          <div style={{ position: "relative", maxWidth: 280, width: "100%" }}>
            <Search size={14} style={{ position: "absolute", left: 10, top: 10, color: "var(--text-muted)" }} />
            <input
              className="input"
              style={{ paddingLeft: 30 }}
              placeholder="Search table..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
            Showing {pageRows.length} of {filtered.length} rows
          </span>
        </div>
      )}

      {pageRows.length === 0 ? (
        <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", border: "1px solid var(--border)", borderRadius: 8 }}>
          {emptyText}
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {inferredCols.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r, idx) => (
                <tr key={idx}>
                  {inferredCols.map((c) => (
                    <td key={c} title={r[c] === null || r[c] === undefined ? "NULL" : String(r[c])}>
                      {r[c] === null || r[c] === undefined ? (
                        <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>null</span>
                      ) : (
                        String(r[c])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="row-wrap" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-secondary btn-sm" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>
            <ChevronLeft size={14} /> Prev
          </button>
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            Page {safePage} of {totalPages}
          </span>
          <button className="btn btn-secondary btn-sm" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>
            Next <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
