import React, { useCallback, useEffect, useState } from "react";
import { api } from "./services/api";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import ToastContainer from "./components/ToastContainer";
import DashboardPage from "./pages/DashboardPage";
import UploadExplorePage from "./pages/UploadExplorePage";
import ProfilingPage from "./pages/ProfilingPage";
import QualityPage from "./pages/QualityPage";
import CleaningStudioPage from "./pages/CleaningStudioPage";
import EdaPage from "./pages/EdaPage";
import AnomalyPage from "./pages/AnomalyPage";
import MachineLearningPage from "./pages/MachineLearningPage";
import ForecastingPage from "./pages/ForecastingPage";
import AskDataPage from "./pages/AskDataPage";
import InsightsPage from "./pages/InsightsPage";
import ReportsPage from "./pages/ReportsPage";
import HistoryPage from "./pages/HistoryPage";

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem("nexusiq_theme") || "light");
  const [activePage, setActivePage] = useState("dashboard");
  const [datasets, setDatasets] = useState([]);
  const [activeDatasetId, setActiveDatasetId] = useState(() => localStorage.getItem("nexusiq_dataset") || "");
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [suggestedFix, setSuggestedFix] = useState(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("nexusiq_theme", theme);
  }, [theme]);

  const notify = useCallback((type, title, message) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const refreshDatasets = useCallback(
    async (preferId = null) => {
      try {
        const res = await api.listDatasets();
        const list = res.datasets || [];
        setDatasets(list);

        const targetId = preferId || activeDatasetId;
        if (targetId && list.some((d) => d.id === targetId)) {
          setActiveDatasetId(targetId);
          localStorage.setItem("nexusiq_dataset", targetId);
        } else if (list.length > 0) {
          setActiveDatasetId(list[0].id);
          localStorage.setItem("nexusiq_dataset", list[0].id);
        } else {
          setActiveDatasetId("");
          localStorage.removeItem("nexusiq_dataset");
        }
      } catch (err) {
        notify("error", "Backend Connection Error", err.message);
      }
    },
    [activeDatasetId, notify]
  );

  useEffect(() => {
    refreshDatasets();
  }, []);

  const handleSelectDataset = (id) => {
    setActiveDatasetId(id);
    if (id) localStorage.setItem("nexusiq_dataset", id);
  };

  const handleLoadDemo = async () => {
    setLoadingDemo(true);
    try {
      const res = await api.loadDemo();
      await refreshDatasets(res.dataset.id);
      notify("success", "Demo Dataset Loaded", "Sample retail dataset is ready for analysis.");
    } catch (err) {
      notify("error", "Demo Load Failed", err.message);
    } finally {
      setLoadingDemo(false);
    }
  };

  const handleSuggestFix = (action) => {
    setSuggestedFix(action);
    setActivePage("cleaning");
  };

  const activeDataset = datasets.find((d) => d.id === activeDatasetId) || null;

  const commonProps = {
    activeDataset,
    onNavigate: setActivePage,
    onLoadDemo: handleLoadDemo,
    loadingDemo,
    notify,
    theme,
  };

  return (
    <div className="app-shell">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        datasets={datasets}
        activeDatasetId={activeDatasetId}
        onSelectDataset={handleSelectDataset}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="main-wrapper">
        <Header
          activePage={activePage}
          activeDataset={activeDataset}
          theme={theme}
          onToggleTheme={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
          onOpenMobileMenu={() => setMobileOpen((o) => !o)}
          onQuickUpload={() => setActivePage("upload")}
          onLoadDemo={handleLoadDemo}
          loadingDemo={loadingDemo}
        />

        <main className="page-content">
          {activePage === "dashboard" && <DashboardPage {...commonProps} />}
          {activePage === "upload" && (
            <UploadExplorePage
              {...commonProps}
              datasets={datasets}
              onSelectDataset={handleSelectDataset}
              onRefreshDatasets={refreshDatasets}
            />
          )}
          {activePage === "profiling" && <ProfilingPage {...commonProps} />}
          {activePage === "quality" && <QualityPage {...commonProps} onSuggestFix={handleSuggestFix} />}
          {activePage === "cleaning" && (
            <CleaningStudioPage
              {...commonProps}
              onDatasetMutated={() => refreshDatasets(activeDatasetId)}
              suggestedFix={suggestedFix}
              clearSuggestedFix={() => setSuggestedFix(null)}
            />
          )}
          {activePage === "eda" && <EdaPage {...commonProps} />}
          {activePage === "anomaly" && <AnomalyPage {...commonProps} />}
          {activePage === "ml" && <MachineLearningPage {...commonProps} />}
          {activePage === "forecasting" && <ForecastingPage {...commonProps} />}
          {activePage === "ask" && <AskDataPage {...commonProps} />}
          {activePage === "insights" && <InsightsPage {...commonProps} />}
          {activePage === "reports" && <ReportsPage {...commonProps} />}
          {activePage === "history" && (
            <HistoryPage onSelectDataset={handleSelectDataset} onNavigate={setActivePage} />
          )}
        </main>
      </div>

      <ToastContainer
        toasts={toasts}
        onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))}
      />
    </div>
  );
}
