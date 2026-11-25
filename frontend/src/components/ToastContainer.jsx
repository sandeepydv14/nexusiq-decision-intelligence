import React from "react";
import { X } from "lucide-react";

export default function ToastContainer({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type || "info"}`}>
          <div style={{ flex: 1 }}>
            {t.title && <div style={{ fontWeight: 600, marginBottom: 2 }}>{t.title}</div>}
            <div style={{ color: "var(--text-secondary)" }}>{t.message}</div>
          </div>
          <button
            onClick={() => onDismiss(t.id)}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 2 }}
            aria-label="Close notification"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
