import React from "react";
import { Database, Sparkles, Upload } from "lucide-react";

export default function EmptyState({ onUploadClick, onLoadDemo, loadingDemo }) {
  return (
    <div className="card" style={{ maxWidth: 680, margin: "40px auto", textAlign: "center", padding: "36px 28px" }}>
      <div
        style={{
          width: 52,
          height: 52,
          borderRadius: 12,
          background: "var(--accent-soft)",
          color: "var(--accent)",
          display: "grid",
          placeItems: "center",
          margin: "0 auto 14px",
        }}
      >
        <Database size={24} />
      </div>
      <h2 style={{ margin: "0 0 8px", fontSize: 20 }}>Welcome to NexusIQ Decision Intelligence</h2>
      <p style={{ color: "var(--text-secondary)", margin: "0 auto 22px", maxWidth: 500 }}>
        Upload a CSV or Excel dataset to launch automated data profiling, quality scoring, interactive cleaning,
        exploratory analytics, anomaly detection, machine learning, forecasting, and executive reporting.
      </p>
      <div className="row-wrap" style={{ justifyContent: "center" }}>
        <button className="btn btn-primary" onClick={onUploadClick}>
          <Upload size={16} /> Upload CSV / Excel Dataset
        </button>
        <button className="btn btn-secondary" onClick={onLoadDemo} disabled={loadingDemo}>
          <Sparkles size={16} /> {loadingDemo ? "Generating Sample Data..." : "Load Demo Retail Dataset"}
        </button>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 16 }}>
        The demo dataset includes realistic sales records along with intentional missing values, duplicates, whitespace,
        and outliers so you can test the entire cleaning & intelligence pipeline immediately.
      </p>
    </div>
  );
}
