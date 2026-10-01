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

## 5. First-Run Setup, Onboarding & User Activation

Upon navigating to `http://127.0.0.1:8000` on a fresh installation, the system automatically detects an uninitialized workspace and presents the **Welcome & Practice Setup Wizard**:

### Step 1: Master Administrator Creation
- **Full Name:** Lead Partner / Practitioner Name (e.g., *CA Rajeshwar Sharma, FCA*).
- **Username & Email:** Master credentials.
- **Professional Designation:** e.g., *Senior Partner, FCA*.
- **Password:** Strong password (minimum 8 characters with letters, numbers, and special symbols).

### Step 2: Firm / Practice Profile Setup
- **Firm Name:** Registered CA Firm or Professional Practice Name.
- **ICAI Registration / FRN:** (e.g., *123456N*).
- **Practice Address, City, State, PIN:** Official practice location for report generation.
- **Contact Details:** Email, Phone, Website.

### Step 3: Session Security & Local AI Shield
- **Session Timeout:** Select idle logout threshold (15, 30, 60, or 120 minutes).
- **AI Privacy Mode:** 
  - *Local AI Only (Maximum Privacy):* Air-gapped compliance; audit data never leaves your computer.
  - *Allow Configured Providers:* Allows connections to local or custom LLM endpoints.

### Step 4: Backup Storage Location
- **Backup Directory:** Specify path on local or external drive for automated snapshots.
- **Snapshot Frequency:** Daily on exit, manual, or custom intervals.

### Step 5: Setup Completion & Workspace Launch
- Verify summary checklist and click **Open FinAuditPro Workspace** to enter the main dashboard.

---

### 👥 Adding Team Members (Offline Activation)
1. Navigate to **Administration → Users** and click **Add User**.
2. Enter staff details (Name, Username, Role: *Partner*, *Auditor*, or *Audit Staff*).
3. The system generates a single-use 32-character activation code valid for 48 hours.
4. Share the activation code with the staff member.
5. On their browser/desktop, the staff member clicks **"Have an activation code?"**, enters the code, sets their private permanent password, and immediately accesses their assigned audit engagements.

---

## 6. Offline Verification
- Disconnect your workstation from the internet (Wi-Fi/Ethernet).
- All ingestion, validation, ledger processing, GST/Bank reconciliation, findings generation, working papers, PDF reporting, and Local AI assistant will function seamlessly without dropping a single capability.
