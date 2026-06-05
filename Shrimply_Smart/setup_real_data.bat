@echo off
REM Quick setup script for ShrimplySmart real data migration
REM This script automates the entire migration process

setlocal enabledelayedexpansion

echo.
echo =========================================
echo ShrimplySmart Real Data Setup
echo =========================================
echo.

REM Check if user provided CSV file
if "%1"=="" (
    echo Usage: setup_real_data.bat ^<csv_file^>
    echo.
    echo Example:
    echo   setup_real_data.bat "input\small-aquaculture-fishpond\pond_iot_2023.csv"
    echo.
    exit /b 1
)

set CSV_FILE=%1
set BACKEND_DIR=%~dp0backend

REM Check if CSV file exists
if not exist "%CSV_FILE%" (
    echo ERROR: CSV file not found: %CSV_FILE%
    exit /b 1
)

echo [1/5] Activating Python environment...
call "%~dp0.venv\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo ERROR: Could not activate virtual environment
    exit /b 1
)
echo Done!

echo.
echo [2/5] Clearing old dummy data from database...
cd /d "%BACKEND_DIR%"
python -c "import django; django.setup(); from api.models import SensorReading; SensorReading.objects.all().delete(); print('Cleared old data')" 2>nul || (
    echo WARNING: Could not clear old data (database may not be initialized)
)
echo Done!

echo.
echo [3/5] Importing real sensor data from CSV...
python scripts\import_live_sensor_data.py "%CSV_FILE%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to import sensor data
    exit /b 1
)
echo Done!

echo.
echo [4/5] Applying database migrations...
python manage.py migrate api
if %errorlevel% neq 0 (
    echo ERROR: Failed to apply migrations
    exit /b 1
)
echo Done!

echo.
echo [5/5] Retraining ML models with real data...
python scripts\retrain_with_real_data.py --export-only
if %errorlevel% neq 0 (
    echo WARNING: Model retraining may have issues
    echo Check requirements: pip install xgboost scikit-learn openpyxl
)
echo Done!

echo.
echo =========================================
echo Setup Complete!
echo =========================================
echo.
echo Next steps:
echo   1. Start backend:  python manage.py runserver
echo   2. Start frontend: cd frontend ^&^& npm run dev
echo   3. Open browser:   http://localhost:5173
echo.
echo Your system is now using REAL sensor data!
echo.

endlocal
