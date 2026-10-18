#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "🚀 Pushing TempAudit Changes to GitHub"
echo "=========================================================="

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "[+] Active Branch: $CURRENT_BRANCH"

# Ensure all untracked or modified files are staged
if [[ -n $(git status --porcelain) ]]; then
  echo "[+] Staging remaining changes..."
  git add .
  git commit -m "feat: complete forensic repair and production readiness for presentation" || true
fi

echo "[+] Pushing active repair branch to origin..."
git push origin "$CURRENT_BRANCH"

echo ""
echo "=========================================================="
echo "✅ Successfully pushed $CURRENT_BRANCH to GitHub!"
echo "=========================================================="
