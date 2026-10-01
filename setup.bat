@echo off
setlocal enabledelayedexpansion
title FinAuditPro - Windows Production Setup & Installer

echo ==============================================================================
echo   FinAuditPro - AI-Assisted Auditing Software (Windows Setup)
echo   Standalone Offline-First CA Auditing Suite
echo ==============================================================================
echo.

:: 1. Verify Windows Environment
echo [1/7] Verifying Windows OS Environment...
if not "%OS%"=="Windows_NT" (
    echo [ERROR] This installer is designed for Windows operating systems.
    exit /b 1
)
echo [OK] Windows OS detected.

:: 2. Check Python Runtime
echo.
echo [2/7] Checking Python 3.10+ installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not found in PATH.
    echo Please install Python 3.10, 3.11, or 3.12 from https://www.python.org/
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Found Python version %PY_VER%

:: 3. Create Virtual Environment
echo.
echo [3/7] Setting up Python virtual environment (venv)...
if not exist "venv" (
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
    echo [OK] Virtual environment created in .\venv
) else (
    echo [OK] Virtual environment already exists.
)

:: 4. Install Dependencies
echo.
echo [4/7] Installing production dependencies from requirements.txt...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Dependency installation failed. Check internet connection or requirements.txt.
    exit /b 1
)
echo [OK] All dependencies successfully verified and installed.

:: 5. Create Application Runtime Directories
echo.
echo [5/7] Creating required application data directories...
if not exist "backend\backups" mkdir "backend\backups"
if not exist "backend\uploaded_files" mkdir "backend\uploaded_files"
if not exist "backend\reports_generated" mkdir "backend\reports_generated"
if not exist "backend\logs" mkdir "backend\logs"
echo [OK] Data directories created: backups, uploaded_files, reports_generated, logs.

:: 6. Initialize Clean Production Database
echo.
echo [6/7] Initializing clean production database and admin security...
python -m backend.app.database
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Database initialization failed.
    exit /b 1
)
echo [OK] Clean database initialized at backend\finauditpro.db (0 demo records).

:: 7. Detect LM Studio Local Server
echo.
echo [7/7] Checking LM Studio Local AI Server status (http://localhost:1234)...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:1234/v1/models' -TimeoutSec 2 -UseBasicParsing; Write-Host '[OK] LM Studio local server is active at http://localhost:1234' } catch { Write-Host '[NOTICE] LM Studio is not currently running. FinAuditPro will run in 100%% offline deterministic audit mode.' }"

echo.
echo ==============================================================================
echo   SUCCESS: FinAuditPro Installation Completed Successfully!
echo ==============================================================================
echo.
echo   To launch the application, run:
echo     start.bat   OR   python run.py
echo   First-Run Setup:
echo     Open http://127.0.0.1:8000 in your browser to complete the
echo     First-Run Administrator Setup Wizard and create your master credentials.
echo.
pause
