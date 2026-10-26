#!/usr/bin/env bash
set -e

# Change directory to project root
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=============================================================================="
echo "  Starting FinAuditPro - Offline AI-Assisted Audit Assistant"
echo "  Access URL: http://127.0.0.1:8000"
echo ""

# Load environment overrides from .env if present
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    set -a
    source .env
    set +a
fi

# 1. Activate venv if present
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# 2. Ensure database exists and schema is initialized
if [ ! -f "backend/finauditpro.db" ]; then
    echo "Initializing database schema..."
    python -m backend.app.database
fi

# 2b. Verify Administrator Account Status
python -c "
from backend.app.database import get_db_connection, init_db
init_db()
conn = get_db_connection()
admin = conn.execute(\"SELECT id, username FROM users WHERE role = 'Admin' AND is_active = 1 LIMIT 1\").fetchone()
if not admin:
    print('[Auth Setup] No administrator account found. First-run setup required.')
    print('[Auth Setup] Open http://127.0.0.1:8000 or run: python scripts/create_admin.py')
else:
    print(f'[Auth Status] Master Administrator verified: {admin[\"username\"]}')
conn.close()
"


# 3. Start LM Studio Local AI Server & Load Model
echo "[AI Setup] Initializing Local AI engine..."

# Add standard LM Studio binary paths to PATH if present
if [ -d "$HOME/.lmstudio/bin" ]; then
    export PATH="$HOME/.lmstudio/bin:$PATH"
fi

LMS_BIN=""
if command -v lms >/dev/null 2>&1; then
    LMS_BIN="$(command -v lms)"
elif [ -x "$HOME/.lmstudio/bin/lms" ]; then
    LMS_BIN="$HOME/.lmstudio/bin/lms"
elif [ -x "/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms" ]; then
    LMS_BIN="/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms"
fi

SELECTED_MODEL=""

if [ -n "$LMS_BIN" ]; then
    echo "[AI Setup] Found LM Studio CLI at: $LMS_BIN"

    # 3a. Start server if not running
    if ! curl -s --connect-timeout 2 http://localhost:1234/v1/models >/dev/null 2>&1; then
        echo "[AI Setup] Starting LM Studio local server..."
        "$LMS_BIN" server start || true
        # Wait up to 10 seconds for server to respond
        for i in {1..10}; do
            if curl -s --connect-timeout 1 http://localhost:1234/v1/models >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
    fi

    # 3b. Verify server connectivity
    if curl -s --connect-timeout 2 http://localhost:1234/v1/models >/dev/null 2>&1; then
        echo "[AI Status] LM Studio server is running at http://localhost:1234"

        # 3c. Check if a model is already loaded in memory
        LOADED_MODEL=$("$LMS_BIN" ps 2>/dev/null | grep -E "(IDLE|LOADING|LOADED|RUNNING)" | head -n 1 | awk '{print $1}')
        
        if [ -n "$LOADED_MODEL" ]; then
            echo "[AI Model] Active model currently loaded: $LOADED_MODEL"
            SELECTED_MODEL="$LOADED_MODEL"
        else
            # Select target model to load
            TARGET_MODEL="qwen2.5-coder-14b-instruct-mlx"
            if ! "$LMS_BIN" ls 2>/dev/null | grep -q "$TARGET_MODEL"; then
                # Fallback to first available downloaded LLM
                FALLBACK_MODEL=$("$LMS_BIN" ls 2>/dev/null | awk '/Local/ && !/EMBEDDING/ && !/nomic/ {print $1}' | head -n 1)
                if [ -n "$FALLBACK_MODEL" ]; then
                    TARGET_MODEL="$FALLBACK_MODEL"
                fi
            fi

            echo "[AI Model] Loading model '$TARGET_MODEL' into local GPU/RAM..."
            "$LMS_BIN" load "$TARGET_MODEL" -y || true
            SELECTED_MODEL="$TARGET_MODEL"
        fi

        # 3d. Update backend database with selected model
        if [ -n "$SELECTED_MODEL" ]; then
            python -c "
try:
    from backend.app.services.local_ai_provider import LocalAIModelManager
    LocalAIModelManager.save_config({
        'engine': 'LMStudio',
        'model_name': '${SELECTED_MODEL}',
        'model_location': 'http://localhost:1234',
        'is_enabled': True
    })
    print('[AI Config] FinAuditPro backend registered model: ${SELECTED_MODEL}')
except Exception as e:
    print(f'[AI Config] Note: {e}')
" || true
        fi
    else
        echo "[AI Warning] Could not connect to LM Studio server on port 1234."
        echo "[AI Status] Core auditing will run in offline deterministic mode."
    fi
else
    # Fallback if lms CLI is not installed
    if curl -s --connect-timeout 2 http://localhost:1234/v1/models >/dev/null 2>&1; then
        echo "[AI Status] LM Studio Connected (http://localhost:1234)"
    else
        echo "[AI Status] LM Studio CLI not detected and server not running."
        echo "[AI Status] Core auditing will run in offline deterministic mode."
    fi
fi

# 4. Launch Application
echo ""
echo "=============================================================================="
echo "  FinAuditPro Desktop Platform Ready"
echo "  Access URL: http://127.0.0.1:8000"
echo "  Initial Setup: First-run setup via web UI or run: python scripts/create_admin.py"
echo "=============================================================================="
echo ""
echo "Launching standalone server and opening default browser..."
python run.py

