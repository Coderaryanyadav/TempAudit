# Developer Environment Setup & Installation Guide

This guide details the procedure for setting up an isolated local development environment for **FinAuditPro**.

---

## 1. Prerequisites

- **Operating System:** macOS (Apple Silicon / Intel), Linux (Ubuntu 22.04+), or Windows 10/11.
- **Python Runtime:** Python **3.10** through **3.12** (Python 3.12 recommended).
- **Node.js (Optional, for frontend tests):** Node.js 18+ LTS.
- **Local AI Engine (Optional):** [LM Studio](https://lmstudio.ai/) with `lms` CLI configured (recommended model: `qwen2.5-coder-14b-instruct-mlx` or `meta-llama-3-8b-instruct`).

---

## 2. Quickstart Installation (Automated)

### macOS / Linux
Run the automated initialization script from the repository root:
```bash
./scripts/setup_mac.sh
```

### Windows
Run the setup batch script from the repository root:
```cmd
scripts\setup_windows.bat
```

The script will automatically:
1. Verify Python 3.10+ installation.
2. Create an isolated virtual environment (`./venv`).
3. Install dependencies from `requirements.txt`.
4. Create necessary local directories (`backend/backups`, `backend/uploaded_files`, `backend/reports_generated`, `backend/logs`).
5. Initialize the SQLite database schema at `backend/finauditpro.db`.
6. Prompt to configure an initial Administrator account.

---

## 3. Manual Installation (Step-by-Step)

If you prefer setting up the environment manually:

```bash
# 1. Clone repository & change directory
cd TempAudit-main

# 2. Create isolated virtual environment
python3 -m venv venv

# 3. Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# 4. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 5. Create runtime data folders
mkdir -p backend/backups backend/uploaded_files backend/reports_generated backend/logs

# 6. Initialize SQLite database schema
python -m backend.app.database

# 7. Create initial administrator account
python scripts/create_admin.py
```

---

## 4. Starting the Application

To launch the local web server and open the browser interface:

```bash
# On macOS:
./scripts/start_mac.sh

# Or directly with Python:
python run.py
```

Navigate to: `http://127.0.0.1:8000`
