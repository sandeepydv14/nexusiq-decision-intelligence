@echo off
setlocal enabledelayedexpansion
echo ========================================================================
echo   NexusIQ - Autonomous Data Analysis ^& Decision Intelligence Platform
echo   Windows Setup Script
echo ========================================================================
echo.

cd /d "%~dp0"

REM Locate Python executable (prefers standard Python or Local\Python\bin)
set "PY_CMD="
where python >nul 2>nul
if %errorlevel%==0 (
    python -c "import sys; print(sys.version)" >nul 2>nul
    if %errorlevel%==0 set "PY_CMD=python"
)
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Python\bin\python.exe"
)
if "%PY_CMD%"=="" (
    echo [ERROR] Python 3.10+ was not found on PATH. Please install Python from python.org.
    pause
    exit /b 1
)

echo [1/4] Creating Python virtual environment using %PY_CMD%...
if not exist "backend\.venv\Scripts\python.exe" (
    "%PY_CMD%" -m venv backend\.venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [2/4] Installing Python backend dependencies...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install backend dependencies.
    pause
    exit /b 1
)

echo [3/4] Checking Node.js and installing frontend packages...
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm is not installed or not on PATH. Install Node.js LTS from nodejs.org.
    pause
    exit /b 1
)
call npm --prefix frontend install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install frontend dependencies.
    pause
    exit /b 1
)

echo [4/4] Setup complete! Run start.bat to launch the application.
pause
