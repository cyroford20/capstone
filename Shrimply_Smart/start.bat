@echo off
REM ============================================================
REM  Shrimply Smart — Start Backend + Frontend in one terminal
REM ============================================================
title Shrimply Smart

REM -- Store project root --
set "ROOT=%~dp0"

echo.
echo ========================================
echo   Shrimply Smart — Starting Services
echo ========================================
echo.

REM -- Kill stale processes on ports 8000 and 5173 --
echo [0/2] Cleaning up stale processes ...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM -- 1) Start Django backend in background --
echo [1/2] Starting Django backend (port 8000) ...
cd /d "%ROOT%backend"
start "" /B cmd /c "call \"%ROOT%.venv\Scripts\activate.bat\" && python manage.py runserver 0.0.0.0:8000"

REM -- 1b) Start feeder telemetry poller in background --
REM This polls the ESP /api/status and saves FeederTelemetry rows continuously.
echo [1b/2] Starting feeder telemetry poller ...
start "" /B cmd /c "\"%ROOT%start_poller.bat\""

REM Give Django a moment to boot
timeout /t 3 /nobreak >nul

REM -- 2) Start Vite frontend (foreground — shows logs) --
echo [2/2] Starting Vite frontend  (port 5173) ...
echo.
echo  Backend  → http://127.0.0.1:8000/api/
echo  Frontend → http://localhost:5173/
echo.
echo  Press Ctrl+C to stop both servers.
echo ========================================
echo.
cd /d "%ROOT%frontend"
call npm run dev
