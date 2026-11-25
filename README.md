# NexusIQ — Autonomous Data Analysis & Decision Intelligence Platform

A full-stack, locally executed **Autonomous Data Analysis & Decision Intelligence Platform** built for final-year B.Tech Information Technology demonstration, viva defense, and portfolio showcase.

It allows users to upload CSV or Excel (`.xlsx` / `.xls`) datasets (or load a realistic built-in sample dataset) and automatically performs data profiling, transparent data quality scoring, non-destructive interactive cleaning, exploratory visualizations, anomaly detection, leakage-free machine learning, time-series forecasting, natural-language querying, insight generation, and PDF/Excel/CSV reporting—completely offline without paid APIs, Docker, or external keys.

---

## Technology Stack

| Layer | Technologies |
| --- | --- |
| **Frontend** | React 18, Vite, JavaScript, Custom CSS (Light & Dark themes), Plotly.js (`plotly.js-dist-min`), Lucide Icons |
| **Backend** | Python, Flask REST API, Flask-CORS |
| **Data Science & ML** | Pandas, NumPy, SciPy, Scikit-Learn, Statsmodels |
| **Database** | SQLite (`backend/data/platform.db`) |
| **Report Exports** | ReportLab + Matplotlib (PDF), OpenPyXL (Styled Multi-Sheet Excel), UTF-8 CSV |

---

## Project Architecture

```
├── setup.bat                      # One-click Windows dependency installer
├── start.bat                      # One-click Windows launcher (Backend + Frontend)
├── README.md
├── backend/
│   ├── app.py                     # Flask application entry point (port 5000)
│   ├── config.py                  # Paths, upload limits, SQLite DB configuration
│   ├── requirements.txt           # Python dependencies
│   ├── database/
│   │   └── db.py                  # SQLite schema & CRUD (datasets, cleaning, analyses, reports, activity)
│   ├── routes/
│   │   ├── dataset_routes.py      # Upload, demo loader, Excel sheet switch, paginated preview
│   │   ├── analysis_routes.py     # Dashboard, profiling, quality, EDA, anomaly, insights, history
│   │   ├── cleaning_routes.py     # Preview, apply, undo, reset cleaning operations
│   │   ├── ml_routes.py           # Supervised ML training & Time-series forecasting
│   │   ├── query_routes.py        # Ask Your Data local query endpoint
│   │   └── report_routes.py       # CSV, Excel, and PDF generation & download
│   ├── services/
│   │   ├── dataset_manager.py     # File validation, CSV/XLSX/XLS parsing, demo generator, search/pagination
│   │   ├── profiler.py            # Descriptive stats, skewness, correlations, distributions
│   │   ├── quality.py             # Transparent 4-pillar quality score & issue diagnostics
│   │   ├── cleaner.py             # Previewable cleaning studio with snapshot undo & reset
│   │   ├── eda.py                 # Automated histograms, bars, box plots, scatter, heatmaps, time series
│   │   ├── anomaly.py             # IQR, Z-Score, and Isolation Forest anomaly detection
│   │   ├── ml_engine.py           # Leakage-free Scikit-Learn pipelines (Classification & Regression)
│   │   ├── forecasting.py         # Naive, Moving Average & Exponential Smoothing with backtesting
│   │   ├── nl_query.py            # Safe deterministic Pandas NLP query engine
│   │   ├── insights.py            # Evidence-backed insights & prioritized recommendations
│   │   └── report_exporter.py     # CSV, multi-sheet Excel, and chart-embedded PDF generator
│   └── tests/
│       └── test_core.py           # End-to-end Pytest integration test suite
└── frontend/
    ├── package.json
    ├── vite.config.js             # Proxies /api -> http://127.0.0.1:5000
    └── src/
        ├── App.jsx
        ├── index.css
        ├── services/api.js
        ├── components/            # Sidebar, Header, PlotlyChart, StatCard, DataTable, EmptyState, Toasts
        └── pages/                 # All 13 interactive analytical workspaces
```

---

## Implemented Modules & Features

1. **Executive Dashboard**: Real-time KPIs (total datasets, rows/columns, missing cells, duplicate rows, quality score), 4-pillar quality breakdown, quick actions, top automated insights, recommendations, and recent audit activity.
2. **Data Upload & Explorer**: Drag-and-drop CSV/XLSX/XLS upload with validation, multi-sheet Excel selector, dataset switcher, deletion, and server-side paginated/searchable/sortable table inspection.
3. **Automatic Data Profiling**: Computes mean, median, mode, standard deviation, min/max, missing counts, unique counts, duplicates, inferred roles, histograms, and Pearson correlation matrix.
4. **Transparent Data Quality Analysis**: Audits missing values, duplicates, invalid negatives, whitespace inconsistencies, mixed data types, empty/constant columns, and outliers with an explicit weighted formula (`0.35×Completeness + 0.20×Uniqueness + 0.25×Validity + 0.20×Outlier Integrity`) and one-click "Fix in Studio" links.
5. **Non-Destructive Data Cleaning Studio**: Preview impact before applying (`remove_duplicates`, `fill_missing`, `drop_missing`, `trim_spaces`, `handle_outliers`, `drop_columns`, `rename_column`, `change_dtype`, `convert_dates`, `filter_rows`), undo step-by-step via snapshots, and reset to original uploaded file.
6. **Automated EDA**: Interactive Plotly histograms, categorical bars, grouped box plots, scatter plots, correlation heatmaps, time-series aggregations, group comparisons, and top/bottom category tables.
7. **Anomaly Detection**: IQR, Z-score, and Scikit-Learn Isolation Forest with feature selection, interactive scatter highlight charts, and row-level explanations.
8. **Machine Learning Workbench**: Leakage-free Scikit-Learn `Pipeline` + `ColumnTransformer` (train/test split occurs prior to imputation, scaling, and encoding). Compares Logistic Regression, Decision Tree, Random Forest, and KNN for Classification, and Linear Regression, Decision Tree, and Random Forest for Regression, plus Confusion Matrix / Actual vs Predicted plots and Feature Importance.
9. **Time-Series Forecasting**: Automatic suitability checks, Naive Baseline, Moving Average, and Holt-Winters Exponential Smoothing with holdout backtest MAE/RMSE and multi-step projections.
10. **Ask Your Data**: Local deterministic Pandas query engine answering natural-language questions (averages, totals, top/bottom groups, regional comparisons, monthly trends, missing columns, correlations, unusual records) with tables and charts.
11. **Insights & Recommendations**: Generates quantitative evidence-backed insights and prioritized action items.
12. **Report Export & Persistent History**: Exports cleaned CSV, styled multi-sheet Excel workbooks, and PDF reports with embedded Matplotlib charts, all tracked in SQLite.

---

## Windows Installation & Running

### Option A: One-Click Batch Scripts
1. Double-click **`setup.bat`** to create `backend\.venv`, install Python libraries, and install Node.js frontend packages.
2. Double-click **`start.bat`** to start the Flask API (`http://127.0.0.1:5000`) and Vite React UI (`http://localhost:5173`).

### Option B: Manual Commands
```powershell
# 1. Backend setup & run
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
.venv\Scripts\python.exe app.py

# 2. Frontend setup & run (in a second terminal)
cd frontend
npm install
npm run dev
```

---

## Running Tests

```powershell
# Backend integration test suite
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_core.py -v

# Frontend production build verification
npm --prefix frontend run build
```
