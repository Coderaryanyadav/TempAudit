#!/usr/bin/env bash
# ==============================================================================
# FinAuditPro Safe Repository Cleanup Script
# ==============================================================================
# Safely discovers and removes disposable build artifacts, Python bytecode,
# and test caches.
#
# Safety Principles:
# 1. Defaults to DRY-RUN mode.
# 2. Excludes databases (*.db, *.sqlite3), backups, reports, uploaded files,
#    virtual environments (venv, .venv), and test fixtures.
# 3. Refuses to run if executed outside the TempAudit repository.
# 4. Requires explicit --apply or -f flag to perform actual deletions.
#
# Usage:
#   ./scripts/cleanup_generated.sh         # Dry-run (lists disposable paths)
#   ./scripts/cleanup_generated.sh --apply # Performs safe cleanup
# ==============================================================================

set -euo pipefail

# Ensure script is run from project root
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

# Verify repository identity to prevent executing in arbitrary directories
if [ ! -f "run.py" ] || [ ! -d "backend/app" ] || [ ! -f "pyproject.toml" ]; then
    echo "❌ ERROR: Safety check failed. This script must only be run inside the TempAudit repository root." >&2
    exit 1
fi

APPLY_CHANGES=false
if [ "${1:-}" = "--apply" ] || [ "${1:-}" = "-f" ] || [ "${1:-}" = "--force" ]; then
    APPLY_CHANGES=true
fi

echo "================================================================================"
if [ "$APPLY_CHANGES" = true ]; then
    echo "🧹 FinAuditPro Cleanup Mode: ACTIVE (Applying deletions)"
else
    echo "🔍 FinAuditPro Cleanup Mode: DRY-RUN (No files will be deleted)"
    echo "   Pass '--apply' to execute deletions."
fi
echo "================================================================================"
echo ""

CANDIDATES=()

# 1. Python bytecode (__pycache__ and *.pyc)
while IFS= read -r -d '' item; do
    CANDIDATES+=("$item")
done < <(find . -type d -name "__pycache__" -not -path "./venv*" -not -path "./.venv*" -print0 2>/dev/null)

while IFS= read -r -d '' item; do
    CANDIDATES+=("$item")
done < <(find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -not -path "./venv*" -not -path "./.venv*" -print0 2>/dev/null)

# 2. Test and coverage caches
if [ -d ".pytest_cache" ]; then
    CANDIDATES+=(".pytest_cache")
fi
if [ -f ".coverage" ]; then
    CANDIDATES+=(".coverage")
fi
while IFS= read -r -d '' item; do
    CANDIDATES+=("$item")
done < <(find . -maxdepth 2 -type d -name ".mypy_cache" -print0 2>/dev/null)

# 3. Build artifacts
while IFS= read -r -d '' item; do
    CANDIDATES+=("$item")
done < <(find . -maxdepth 2 -type d -name "*.egg-info" -not -path "./venv*" -print0 2>/dev/null)

# 4. OS metadata (.DS_Store)
while IFS= read -r -d '' item; do
    CANDIDATES+=("$item")
done < <(find . -name ".DS_Store" -not -path "./venv*" -print0 2>/dev/null)

COUNT=${#CANDIDATES[@]}

if [ "$COUNT" -eq 0 ]; then
    echo "✅ Repository is already clean! No disposable caches or temporary files found."
    exit 0
fi

echo "Discovered $COUNT disposable artifact(s):"
echo "--------------------------------------------------------------------------------"
for item in "${CANDIDATES[@]}"; do
    echo "  - $item"
done
echo "--------------------------------------------------------------------------------"

if [ "$APPLY_CHANGES" = true ]; then
    echo ""
    echo "Applying safe deletions..."
    for item in "${CANDIDATES[@]}"; do
        if [ -e "$item" ]; then
            rm -rf "$item"
            echo "  ✔ Removed: $item"
        fi
    done
    echo ""
    echo "🎉 Safe cleanup completed successfully!"
else
    echo ""
    echo "Dry-run complete. $COUNT item(s) would be removed."
    echo "To delete these items, re-run with: ./scripts/cleanup_generated.sh --apply"
fi
