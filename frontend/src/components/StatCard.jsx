import React from "react";

export default function StatCard({ label, value, sub, icon: Icon, tone = "accent" }) {
  const toneColors = {
    accent: { bg: "var(--accent-soft)", fg: "var(--accent)" },
    success: { bg: "var(--success-soft)", fg: "var(--success)" },
    warning: { bg: "var(--warning-soft)", fg: "var(--warning)" },
    danger: { bg: "var(--danger-soft)", fg: "var(--danger)" },
    info: { bg: "var(--info-soft)", fg: "var(--info)" },
  }[tone] || { bg: "var(--accent-soft)", fg: "var(--accent)" };

  return (
    <div className="stat-card">
      <div>
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
      {Icon && (
        <div className="stat-icon" style={{ background: toneColors.bg, color: toneColors.fg }}>
          <Icon size={18} />
        </div>
      )}
    </div>
  );
}
