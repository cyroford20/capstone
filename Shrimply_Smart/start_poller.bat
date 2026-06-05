@echo off
setlocal

REM Poll ESP8266 /api/status from the PC and push into Django (same as firmware GET /api/status).
REM No inbound firewall rule needed on the PC — the PC connects outbound to the ESP.
REM WEMOS_HOST must match the ESP IP printed in Serial Monitor after WiFi connects,
REM and match backend WEMOS_BASE_URL (see backend .env).

cd /d "%~dp0"

REM If not set externally, default to the WeMos/ESP IP used by the backend proxy.
if "%WEMOS_HOST%"=="" set WEMOS_HOST=10.254.243.33
if "%WEMOS_PORT%"=="" set WEMOS_PORT=80
set INTERVAL_SEC=6

REM Default HTTP timeout for polling (seconds)
if "%WEMOS_TIMEOUT_SEC%"=="" set WEMOS_TIMEOUT_SEC=5

REM Configure backend proxy base URL for the poller
set WEMOS_BASE_URL=http://%WEMOS_HOST%:%WEMOS_PORT%
set WEMOS_PROXY_TIMEOUT_SEC=%WEMOS_TIMEOUT_SEC%

if exist ".venv\Scripts\python.exe" (
	".venv\Scripts\python.exe" backend\manage.py poll_feeder_telemetry --interval %INTERVAL_SEC% --timeout %WEMOS_TIMEOUT_SEC% --enable-servo-scheduler --schedule-interval 0.5
) else (
	py -3 backend\manage.py poll_feeder_telemetry --interval %INTERVAL_SEC% --timeout %WEMOS_TIMEOUT_SEC% --enable-servo-scheduler --schedule-interval 0.5
)

endlocal
