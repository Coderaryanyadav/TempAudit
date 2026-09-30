# FinAuditPro - Comprehensive Installation & Setup Guide

## 1. System Requirements

### Hardware Requirements
- **Processor:** 64-bit Intel / AMD x86_64 or Apple Silicon (ARM64)
- **RAM:** 
  - Minimum 4 GB RAM (Rule engine, reconciliation, data processing, statistical ML, reports)
  - Recommended 8 GB - 16 GB RAM if running local LLMs via LM Studio
- **Disk Space:** 500 MB for core application & dependencies; 4–8 GB additional if hosting local LM Studio model weights.
- **Operating System:** Windows 10/11, macOS Monterey+, or Ubuntu 20.04+ Linux.

### Software Prerequisites
- **Python 3.10+** (Tested on Python 3.11 & 3.12 64-bit)
- **Modern Web Browser:** Chrome, Edge, Firefox, Brave, or Safari.
- **Local AI Provider:** [LM Studio](https://lmstudio.ai) (Local OpenAI-compatible API on `http://localhost:1234`).

---

## 2. Installation Steps

### Step 1: Clone or Extract Repository
```bash
git clone https://github.com/your-org/FinAuditPro.git
cd FinAuditPro
```

### Step 2: Run Automated Windows Setup
```cmd
setup.bat
```
This automatically verifies Python, creates a virtual environment, installs `requirements.txt`, creates data directories, initializes a clean SQLite database, and detects LM Studio.

---

## 3. Manual Installation Steps

### Step 1: Set Up Python Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install Required Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Initialize Clean Production Database
```bash
python -m backend.app.database
```

---

## 4. Launching the Application

### Windows (One-Click)
```cmd
start.bat
```

### Manual Launch
```bash
python run.py
```
Navigate to: `http://127.0.0.1:8000`

---

## 5. Default Credentials

| Username | Password | Full Name & Role |
| :--- | :--- | :--- |
| `admin` | `admin123` | **System Administrator (Partner, FCA)** |

---

## 6. Offline Verification
- Disconnect your workstation from the internet (Wi-Fi/Ethernet).
- All ingestion, validation, ledger processing, GST/Bank reconciliation, findings generation, working papers, PDF reporting, and Local AI assistant will function seamlessly without dropping a single capability.
