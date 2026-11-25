import React, { useState } from "react";
import { MessageSquareText, Send } from "lucide-react";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import PlotlyChart from "../components/PlotlyChart";
import DataTable from "../components/DataTable";

const EXAMPLE_QUESTIONS = [
  "What is the average revenue?",
  "Which product has the highest sales?",
  "Which category performs best?",
  "What are the top five products?",
  "Show monthly trends.",
  "Which columns contain missing values?",
  "Compare sales between regions.",
  "Find unusual records.",
  "What is the correlation between Revenue and Profit?",
];

export default function AskDataPage({ activeDataset, onNavigate, onLoadDemo, loadingDemo, notify, theme }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [asking, setAsking] = useState(false);

  if (!activeDataset) {
    return <EmptyState onUploadClick={() => onNavigate("upload")} onLoadDemo={onLoadDemo} loadingDemo={loadingDemo} />;
  }

  const handleAsk = async (qText = question) => {
    const cleanQ = qText.trim();
    if (!cleanQ) return;
    setAsking(true);
    setQuestion("");
    try {
      const res = await api.askData(activeDataset.id, cleanQ);
      setHistory((prev) => [{ id: Date.now(), question: cleanQ, response: res }, ...prev]);
    } catch (err) {
      notify("error", "Query Error", err.message);
    } finally {
      setAsking(false);
    }
  };

  const renderChart = (chart) => {
    if (!chart) return null;
    if (chart.type === "bar") {
      return (
        <PlotlyChart
          theme={theme}
          height={280}
          data={[{ type: "bar", x: chart.x, y: chart.y, marker: { color: "#2563eb" } }]}
          layout={{ title: chart.title, xaxis: { title: chart.x_title }, yaxis: { title: chart.y_title } }}
        />
      );
    }
    if (chart.type === "line") {
      return (
        <PlotlyChart
          theme={theme}
          height={280}
          data={[{ type: "scatter", mode: "lines+markers", x: chart.x, y: chart.y, line: { color: "#0ea5e9", width: 2.5 } }]}
          layout={{ title: chart.title, xaxis: { title: chart.x_title }, yaxis: { title: chart.y_title } }}
        />
      );
    }
    if (chart.type === "scatter") {
      return (
        <PlotlyChart
          theme={theme}
          height={280}
          data={[{ type: "scatter", mode: "markers", x: chart.x, y: chart.y, marker: { color: "#6366f1", opacity: 0.7 } }]}
          layout={{ title: chart.title, xaxis: { title: chart.x_title }, yaxis: { title: chart.y_title } }}
        />
      );
    }
    return null;
  };

  return (
    <div className="stack-md">
      <div className="card stack-md">
        <div>
          <h3 className="card-title">Ask Your Data — Local Deterministic Query Engine</h3>
          <p className="card-subtitle">
            Ask analytical questions in plain English. Executed locally via Pandas and SciPy with zero external AI keys or fabricated answers.
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk();
          }}
          style={{ display: "flex", gap: 10 }}
        >
          <input
            className="input"
            placeholder="Ask a question about your active dataset (e.g., Compare sales between regions)..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={asking}
          />
          <button className="btn btn-primary" type="submit" disabled={asking || !question.trim()}>
            <Send size={15} /> {asking ? "Analyzing..." : "Ask"}
          </button>
        </form>

        <div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>Try an example query:</div>
          <div className="row-wrap" style={{ gap: 6 }}>
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                className="btn btn-secondary btn-sm"
                onClick={() => handleAsk(q)}
                disabled={asking}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {history.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: 36, color: "var(--text-muted)" }}>
          <MessageSquareText size={28} style={{ marginBottom: 8, opacity: 0.6 }} />
          <div>Click any example prompt or type your own question above to compute live answers.</div>
        </div>
      ) : (
        <div className="stack-md">
          {history.map((item) => (
            <div className="card stack-md" key={item.id}>
              <div className="row-wrap" style={{ justifyContent: "space-between" }}>
                <div style={{ fontWeight: 600, fontSize: 14.5 }}>Q: {item.question}</div>
                <span className={`badge ${item.response.supported ? "badge-success" : "badge-warning"}`}>
                  {item.response.supported ? item.response.intent : "Unsupported"}
                </span>
              </div>

              <div
                style={{
                  padding: "12px 14px",
                  borderRadius: 8,
                  background: "var(--bg-subtle)",
                  fontSize: 13.5,
                }}
              >
                {item.response.answer}
              </div>

              {item.response.chart && renderChart(item.response.chart)}

              {item.response.table && item.response.table.length > 0 && (
                <DataTable rows={item.response.table} searchable={false} pageSize={10} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
