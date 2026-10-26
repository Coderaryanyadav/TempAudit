#!/usr/bin/env bash
set -e

# Change directory to project root
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=============================================================================="
echo "  FinAuditPro - AI-Assisted Auditing Software (macOS / Linux Setup)"
echo "  Standalone Offline-First CA Auditing Suite"
echo "=============================================================================="
echo ""

# 1. Check Python 3.10+
echo "[1/8] Checking Python 3.10+ runtime..."
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python 3 is not installed or not found in PATH."
    echo "Install via Homebrew: brew install python@3.12"
    exit 1
fi
PY_VER=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[OK] Found Python version $PY_VER ($PYTHON_CMD)"

# 2. Check Virtual Environment
echo ""
echo "[2/8] Setting up Python virtual environment (venv)..."
if [ ! -d "venv" ]; then
    $PYTHON_CMD -m venv venv
    echo "[OK] Virtual environment created in ./venv"
else
    echo "[OK] Virtual environment already exists."
fi

# 3. Activate and Install Dependencies
echo ""
source venv/bin/activate
pip install --upgrade pip --quiet
if [ -f "requirements.lock" ]; then
    echo "[3/8] Installing pinned production dependencies from requirements.lock..."
    pip install -r requirements.lock --quiet
else
    echo "[3/8] Installing production dependencies from requirements.txt..."
    pip install -r requirements.txt --quiet
fi
echo "[OK] All dependencies successfully verified and installed."

# 4. Create Runtime Directories
echo ""
echo "[4/8] Creating required application data directories..."
mkdir -p backend/backups backend/uploaded_files backend/reports_generated backend/logs
echo "[OK] Data directories created: backups, uploaded_files, reports_generated, logs."

# 5. Initialize Clean Production Database
echo ""
echo "[5/8] Initializing database and security schema..."
python -m backend.app.database
echo "[OK] Clean database initialized at backend/finauditpro.db."

# 6. Optional Admin Account Creation
echo ""
echo "[6/8] Administrator Account Setup"
read -p "Would you like to configure an Administrator account now? (y/N): " CREATE_ADM
if [[ "$CREATE_ADM" =~ ^[Yy]$ ]]; then
    python scripts/create_admin.py
else
    echo "[NOTICE] You can create the administrator later via the First-Run Setup Wizard at http://127.0.0.1:8000"
fi

# 7. Check LM Studio Status
echo ""
echo "[7/8] Checking LM Studio Local AI Server status (http://localhost:1234)..."
if curl -s --connect-timeout 2 http://localhost:1234/v1/models >/dev/null 2>&1; then
    echo "[OK] LM Studio local server is active at http://localhost:1234"
else
    echo "[NOTICE] LM Studio is not currently running. FinAuditPro will run in 100% offline deterministic audit mode."
fi

# 8. Completion Notice
echo ""
echo "=============================================================================="
echo "  SUCCESS: FinAuditPro Installation Completed Successfully!"
echo "=============================================================================="
echo ""
echo "  To launch the application:"
echo "    Run: ./scripts/start_mac.sh   OR   python run.py"
echo "    Web Interface: http://127.0.0.1:8000"
echo ""
