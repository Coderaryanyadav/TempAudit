#!/usr/bin/env bash
# FinAuditPro - Test Runner Helper
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ -f "$REPO_DIR/venv/bin/pytest" ]; then
    exec "$REPO_DIR/venv/bin/pytest" "$@"
else
    exec pytest "$@"
fi
