@echo off
echo ========================================================================
echo   Starting NexusIQ - Autonomous Data Analysis ^& Decision Intelligence
echo ========================================================================
echo.

cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Running setup.bat first...
    call setup.bat
)

echo Launching Flask Backend API on http://127.0.0.1:5000 ...
start "NexusIQ Backend (Flask)" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe app.py"

timeout /t 3 /nobreak >nul

echo Launching Vite React Frontend on http://localhost:5173 ...
start "NexusIQ Frontend (Vite)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo Both servers started in separate windows.
echo Open http://localhost:5173 in your browser if it did not open automatically.
