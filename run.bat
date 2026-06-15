@echo off
echo.
echo ======================================================
echo   MAINTENANCE WIZARD -- Tata Steel AI System
echo   Starting up...
echo ======================================================
echo.

REM Check if .env exists
if not exist backend\.env (
    echo [SETUP] Copying .env.example to .env...
    copy backend\.env.example backend\.env
    echo [ACTION REQUIRED] Open backend\.env and set your GEMINI_API_KEY
    echo Get your free key at: https://aistudio.google.com/app/apikey
    echo.
    pause
)

REM Find Python
set PYTHON_CMD=python
where python >nul 2>nul
if %errorlevel% neq 0 (
    set PYTHON_CMD=py
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Python not found! Please install Python 3.9+ from https://python.org
        pause
        exit /b 1
    )
)

echo [INFO] Using Python: %PYTHON_CMD%
echo.

REM Install dependencies if needed
echo [SETUP] Checking dependencies...
%PYTHON_CMD% -c "import fastapi" >nul 2>nul
if %errorlevel% neq 0 (
    echo [SETUP] Installing dependencies (first time only, may take a few minutes)...
    %PYTHON_CMD% -m pip install -r backend\requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )
)

echo [INFO] Dependencies OK
echo.
echo ======================================================
echo   Starting Maintenance Wizard on http://localhost:8000
echo   Press Ctrl+C to stop
echo ======================================================
echo.

REM Start the server
cd backend
%PYTHON_CMD% -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
