const API_BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const message = (isJson && payload?.error) || (typeof payload === "string" ? payload : "Request failed");
    throw new Error(message);
  }
  return payload;
}

export const api = {
  health: () => request("/health"),

  // Datasets
  listDatasets: () => request("/datasets"),
  loadDemo: () => request("/datasets/demo", { method: "POST" }),
  uploadDataset: (file, name) => {
    const formData = new FormData();
    formData.append("file", file);
    if (name) formData.append("name", name);
    return request("/datasets/upload", { method: "POST", body: formData });
  },
  switchSheet: (datasetId, sheetName) =>
    request(`/datasets/${datasetId}/sheet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sheet_name: sheetName }),
    }),
  deleteDataset: (datasetId) => request(`/datasets/${datasetId}`, { method: "DELETE" }),
  previewDataset: (datasetId, params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/datasets/${datasetId}/preview?${qs}`);
  },

  // Analysis
  getDashboard: (datasetId) => request(`/analysis/${datasetId}/dashboard`),
  getProfile: (datasetId) => request(`/analysis/${datasetId}/profile`),
  getQuality: (datasetId) => request(`/analysis/${datasetId}/quality`),
  getEda: (datasetId, params = {}) => {
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    const qs = new URLSearchParams(clean).toString();
    return request(`/analysis/${datasetId}/eda${qs ? `?${qs}` : ""}`);
  },
  runAnomaly: (datasetId, body) =>
    request(`/analysis/${datasetId}/anomaly`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getInsights: (datasetId) => request(`/analysis/${datasetId}/insights`),

  // Cleaning
  getCleaningHistory: (datasetId) => request(`/cleaning/${datasetId}/history`),
  previewCleaning: (datasetId, operation, params) =>
    request(`/cleaning/${datasetId}/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operation, params }),
    }),
  applyCleaning: (datasetId, operation, params) =>
    request(`/cleaning/${datasetId}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operation, params }),
    }),
  undoCleaning: (datasetId) => request(`/cleaning/${datasetId}/undo`, { method: "POST" }),
  resetCleaning: (datasetId) => request(`/cleaning/${datasetId}/reset`, { method: "POST" }),

  // ML & Forecasting
  getMlMetadata: (datasetId) => request(`/ml/${datasetId}/metadata`),
  trainMl: (datasetId, body) =>
    request(`/ml/${datasetId}/train`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getForecastSuitability: (datasetId) => request(`/forecast/${datasetId}/suitability`),
  runForecast: (datasetId, body) =>
    request(`/forecast/${datasetId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // Ask Your Data
  askData: (datasetId, question) =>
    request(`/query/${datasetId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),

  // Reports & History
  getHistory: (datasetId) => request(`/history${datasetId ? `?dataset_id=${datasetId}` : ""}`),
  getReportHistory: () => request("/reports/history"),
  getDownloadUrl: (datasetId, fmt) => `${API_BASE}/reports/${datasetId}/download/${fmt}`,
  getSavedReportDownloadUrl: (reportId) => `${API_BASE}/reports/saved/${reportId}/download`,
};
