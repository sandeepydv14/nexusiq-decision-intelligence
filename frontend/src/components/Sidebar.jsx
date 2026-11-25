import React from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  Database,
  FileDown,
  History,
  LayoutDashboard,
  Lightbulb,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Upload,
  Wrench,
} from "lucide-react";

const NAV_GROUPS = [
  {
    label: "Workspace",
    items: [
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
      { id: "upload", label: "Upload & Explore", icon: Upload },
    ],
  },
  {
    label: "Diagnostics & Prep",
    items: [
      { id: "profiling", label: "Data Profiling", icon: Activity },
      { id: "quality", label: "Data Quality", icon: ShieldCheck },
      { id: "cleaning", label: "Cleaning Studio", icon: Wrench },
    ],
  },
  {
    label: "Analytics & AI",
    items: [
      { id: "eda", label: "Exploratory Analysis", icon: BarChart3 },
      { id: "anomaly", label: "Anomaly Detection", icon: AlertTriangle },
      { id: "ml", label: "Machine Learning", icon: BrainCircuit },
      { id: "forecasting", label: "Forecasting", icon: TrendingUp },
      { id: "ask", label: "Ask Your Data", icon: MessageSquareText },
    ],
  },
  {
    label: "Decisions & Archive",
    items: [
      { id: "insights", label: "Insights & Actions", icon: Lightbulb },
      { id: "reports", label: "Reports & Export", icon: FileDown },
      { id: "history", label: "History & Logs", icon: History },
    ],
  },
];

export default function Sidebar({ activePage, onNavigate, datasets, activeDatasetId, onSelectDataset, mobileOpen, onCloseMobile }) {
  return (
    <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
      <div className="sidebar-brand">
        <div className="brand-mark">
          <Sparkles size={18} />
        </div>
        <div>
          <div className="brand-title">NexusIQ</div>
          <div className="brand-sub">Decision Intelligence</div>
        </div>
      </div>

      <div style={{ padding: "12px 14px 4px" }}>
        <div className="sidebar-label" style={{ padding: "0 2px 6px" }}>
          Active Dataset
        </div>
        <div style={{ position: "relative" }}>
          <select
            className="select"
            value={activeDatasetId || ""}
            onChange={(e) => {
              onSelectDataset(e.target.value);
              onCloseMobile();
            }}
            style={{
              background: "rgba(255,255,255,0.06)",
              color: "#f8fafc",
              borderColor: "rgba(255,255,255,0.14)",
              fontSize: 12.5,
            }}
          >
            {!datasets.length && <option value="">No dataset loaded</option>}
            {datasets.map((d) => (
              <option key={d.id} value={d.id} style={{ color: "#0f172a" }}>
                {d.is_demo ? `[Demo] ${d.name.replace("Demo: ", "")}` : d.name} ({d.row_count}×{d.col_count})
              </option>
            ))}
          </select>
        </div>
      </div>

      {NAV_GROUPS.map((group) => (
        <div className="sidebar-section" key={group.label}>
          <div className="sidebar-label">{group.label}</div>
          {group.items.map((item) => {
            const Icon = item.icon;
            const active = activePage === item.id;
            return (
              <button
                key={item.id}
                className={`nav-item ${active ? "active" : ""}`}
                onClick={() => {
                  onNavigate(item.id);
                  onCloseMobile();
                }}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      ))}

      <div className="sidebar-footer">
        <div className="row-wrap" style={{ gap: 8, fontSize: 11.5, color: "#94a3b8" }}>
          <Database size={14} />
          <span>SQLite Local Persistence</span>
        </div>
      </div>
    </aside>
  );
}
