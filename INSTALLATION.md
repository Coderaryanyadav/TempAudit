# FinAuditPro — Installation & Setup Guide

## 1. System Requirements

### Hardware Requirements
- **Operating System:** Windows 10/11 (64-bit), macOS Monterey+, or Ubuntu 20.04+ Linux
- **Processor:** 64-bit Intel / AMD x86_64 or Apple Silicon ARM
- **Memory (RAM):**
  - Minimum 4 GB RAM for FinAuditPro Core (Deterministic Rules, BRS/GST Reconciliations, Isolation Forest ML, Trial Balance, PDF Reports)
  - Recommended 8 GB – 16 GB RAM if hosting a local language model in LM Studio
- **Storage:** 500 MB for FinAuditPro runtime; 4–8 GB additional if running quantized local models in LM Studio.

### Software Prerequisites
- **Python 3.10, 3.11, or 3.12 (64-bit)**
- **Modern Web Browser:** Google Chrome, Microsoft Edge, Mozilla Firefox, Brave, or Safari.
- **LM Studio (Optional for Local AI):** Available from [https://lmstudio.ai](https://lmstudio.ai).

---

## 2. Windows Quick Setup (One-Click)

1. Double-click **`setup.bat`** (or run `.\setup.bat` in Command Prompt / PowerShell).
2. The setup script will automatically:
   - Verify your Windows environment and Python runtime.
   - Create a Python virtual environment in `.\venv`.
   - Install all required dependencies from `requirements.txt`.
   - Create runtime storage folders (`backups/`, `uploaded_files/`, `reports_generated/`, `logs/`).
   - Initialize a clean SQLite database at `backend\finauditpro.db` (0 demo data records, 0 pre-populated users).
   - Check local LM Studio server status at `http://localhost:1234`.
3. To start the application, double-click **`start.bat`** or run:
   ```cmd
   start.bat
   ```

---

## 3. Manual Installation Steps

### Step 1: Clone or Extract Repository
```bash
cd TempAudit-main
```

### Step 2: Create & Activate Python Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Initialize Production Database
```bash
python -m backend.app.database
```
*Note: This creates all database tables, triggers, and cryptographic schemas. The database starts with zero users for strict security.*

### Step 5: Start FinAuditPro Desktop Server
```bash
python run.py
```
Open your browser and navigate to: `http://127.0.0.1:8000`

---

## 4. First-Run Administrator Setup Wizard

Upon opening `http://127.0.0.1:8000` for the first time, FinAuditPro automatically detects that no administrative account exists and launches the **First-Run Administrator Setup Wizard**:

1. Enter your Full Name (e.g. *Partner / FCA*).
2. Set your master Administrator Username.
3. Enter your contact email.
4. Choose a strong master password (minimum 8 characters with letters and numbers).
5. Complete setup and log in securely.

---

## 5. Offline Operation Certification
FinAuditPro is engineered to run in 100% air-gapped environments with zero external network connectivity. Disconnect your workstation from the internet; all rule evaluations, mathematical reconciliations, anomaly detections, working papers, and reporting features will operate without interruption.
