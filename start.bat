@echo off
setlocal enabledelayedexpansion
title FinAuditPro - AI-Assisted CA Auditing Workstation

echo ==============================================================================
echo   Starting FinAuditPro - Offline AI-Assisted Audit Assistant
echo   Access URL: http://127.0.0.1:8000
echo ==============================================================================
echo.

:: 1. Activate Python Environment if venv exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: 2. Ensure Database Exists
if not exist "backend\finauditpro.db" (
    echo Initializing database...
    python -m backend.app.database
)

:: 3. Inform User of LM Studio Status
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:1234/v1/models' -TimeoutSec 2 -UseBasicParsing; Write-Host '[AI Status] LM Studio Connected (http://localhost:1234)' -ForegroundColor Green } catch { Write-Host '[AI Status] LM Studio is not running. Core auditing will run in offline deterministic mode.' -ForegroundColor Yellow }"

:: 4. Start FinAuditPro Desktop Server via run.py
echo.
echo Launching standalone server and opening default browser...
python run.py

pause
