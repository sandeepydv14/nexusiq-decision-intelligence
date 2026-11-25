import React from "react";
import { Menu, Moon, Sparkles, Sun, Upload } from "lucide-react";

const PAGE_TITLES = {
  dashboard: "Executive Dashboard",
  upload: "Data Upload & Explorer",
  profiling: "Automatic Data Profiling",
  quality: "Data Quality Analysis",
  cleaning: "Data Cleaning Studio",
  eda: "Exploratory Data Analysis",
  anomaly: "Anomaly Detection",
  ml: "Machine Learning Workbench",
  forecasting: "Time-Series Forecasting",
  ask: "Ask Your Data (Local Query Engine)",
  insights: "Automated Insights & Recommendations",
  reports: "Report Export Center",
  history: "Analysis & Persistence History",
};

export default function Header({
  activePage,
  activeDataset,
  theme,
  onToggleTheme,
  onOpenMobileMenu,
  onQuickUpload,
  onLoadDemo,
  loadingDemo,
}) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="btn btn-secondary btn-sm mobile-menu-btn" onClick={onOpenMobileMenu} aria-label="Menu">
          <Menu size={16} />
        </button>
        <div>
          <h1 className="topbar-title">{PAGE_TITLES[activePage] || "Decision Intelligence"}</h1>
        </div>
        {activeDataset && (
          <div className="row-wrap" style={{ gap: 6 }}>
            <span className="badge badge-accent">
              {activeDataset.row_count.toLocaleString()} rows × {activeDataset.col_count} cols
            </span>
            {activeDataset.is_demo && <span className="badge badge-warning">Sample Demo Data</span>}
            {activeDataset.sheet_name && <span className="badge badge-neutral">Sheet: {activeDataset.sheet_name}</span>}
          </div>
        )}
      </div>

      <div className="topbar-right">
        {!activeDataset?.is_demo && (
          <button className="btn btn-secondary btn-sm" onClick={onLoadDemo} disabled={loadingDemo}>
            <Sparkles size={14} /> {loadingDemo ? "Loading..." : "Demo Data"}
          </button>
        )}
        <button className="btn btn-primary btn-sm" onClick={onQuickUpload}>
          <Upload size={14} /> Upload
        </button>
        <button
          className="btn btn-secondary btn-sm"
          onClick={onToggleTheme}
          title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </header>
  );
}
