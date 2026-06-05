#!/usr/bin/env pwsh
<# 
ShrimplySmart Real Data Setup Script
PowerShell version for Windows
Usage: .\setup_real_data.ps1 -CsvFile "path\to\file.csv"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$CsvFile,
    
    [switch]$SkipClear
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvScript = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $CsvFile)) {
    Write-Host "ERROR: CSV file not found: $CsvFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $VenvScript)) {
    Write-Host "ERROR: Virtual environment not found at $VenvScript" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ShrimplySmart Real Data Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Activate environment
Write-Host "[1/5] Activating Python environment..." -ForegroundColor Yellow
& $VenvScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not activate virtual environment" -ForegroundColor Red
    exit 1
}
Write-Host "Done!" -ForegroundColor Green

# Step 2: Clear old data
if (-not $SkipClear) {
    Write-Host ""
    Write-Host "[2/5] Clearing old dummy data from database..." -ForegroundColor Yellow
    Push-Location $BackendDir
    python -c "import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','aquaculture_api.settings'); django.setup(); from api.models import SensorReading; SensorReading.objects.all().delete(); print('Cleared old data')" 2>$null
    Pop-Location
    Write-Host "Done!" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "[2/5] Skipping data clear..." -ForegroundColor Yellow
}

# Step 3: Import sensor data
Write-Host ""
Write-Host "[3/5] Importing real sensor data from CSV..." -ForegroundColor Yellow
Push-Location $BackendDir
python scripts\import_live_sensor_data.py $CsvFile
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to import sensor data" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "Done!" -ForegroundColor Green

# Step 4: Apply migrations
Write-Host ""
Write-Host "[4/5] Applying database migrations..." -ForegroundColor Yellow
Push-Location $BackendDir
python manage.py migrate api
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to apply migrations" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "Done!" -ForegroundColor Green

# Step 5: Retrain models
Write-Host ""
Write-Host "[5/5] Retraining ML models with real data..." -ForegroundColor Yellow
Push-Location $BackendDir
python scripts\retrain_with_real_data.py --export-only
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Model retraining had issues" -ForegroundColor Yellow
    Write-Host "Check requirements: pip install xgboost scikit-learn pandas" -ForegroundColor Yellow
}
Pop-Location
Write-Host "Done!" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start backend:  cd backend && python manage.py runserver" -ForegroundColor White
Write-Host "  2. Start frontend: cd frontend && npm run dev" -ForegroundColor White
Write-Host "  3. Open browser:   http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Your system is now using REAL sensor data!" -ForegroundColor Green
Write-Host ""
