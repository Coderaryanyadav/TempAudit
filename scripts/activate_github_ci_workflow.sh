#!/bin/bash
set -e

echo "================================================================================"
echo "🚀 FINAUITPRO GITHUB ACTIONS CI ACTIVATION SCRIPT"
echo "================================================================================"
echo ""
echo "Step 1: Expanding GitHub CLI OAuth scope to include 'workflow'..."
gh auth refresh -s workflow

echo ""
echo "Step 2: Installing workflow to .github/workflows/ci.yml..."
mkdir -p .github/workflows
cp DevOps/ci/ci.yml .github/workflows/ci.yml

echo ""
echo "Step 3: Staging, committing, and pushing workflow to GitHub..."
git add .github/workflows/ci.yml
git commit -m "ci: activate GitHub Actions automated workflow (.github/workflows/ci.yml)"
git push origin main

echo ""
echo "Step 4: Monitoring GitHub Actions execution..."
sleep 3
gh run list --limit 1
echo ""
echo "✅ Workflow deployed successfully! Check run in GitHub Actions tab:"
echo "👉 https://github.com/Coderaryanyadav/TempAudit/actions"
