#!/usr/bin/env bash
set -e

# Change directory to project root
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=============================================================================="
echo "  Starting FinAuditPro - Offline AI-Assisted Audit Assistant"
echo "  Access URL: http://127.0.0.1:8000"
echo "=============================================================================="
echo ""

# 1. Activate venv if present
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "../0 - BACKUP/FinAuditPro/.venv/bin/activate" ]; then
    source "../0 - BACKUP/FinAuditPro/.venv/bin/activate"
fi

# 2. Ensure database exists
if [ ! -f "backend/finauditpro.db" ]; then
    echo "Initializing database schema..."
    python -m backend.app.database
fi

# 3. Check AI Server
if curl -s --connect-timeout 2 http://localhost:1234/v1/models >/dev/null 2>&1; then
    echo "[AI Status] LM Studio Connected (http://localhost:1234)"
else
    echo "[AI Status] LM Studio is not running. Core auditing will run in offline deterministic mode."
fi

# 4. Launch Application
echo ""
echo "Launching standalone server and opening default browser..."
python run.py
