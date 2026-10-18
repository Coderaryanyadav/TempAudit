# FinAuditPro — Initialization & Setup Suite

This folder provides unified setup and launch scripts for both **Windows** and **macOS / Linux**.

---

## 🪟 Windows Setup & Launch

1. **First-Time Setup & Installation:**
   - Double-click `setup_windows.bat` or run:
     ```cmd
     initialize\setup_windows.bat
     ```
   - Checks Python, builds the virtual environment (`venv`), installs dependencies, creates folders, initializes the database, and prompts you to configure an Administrator account.

2. **Daily Startup:**
   - Double-click `start_windows.bat` or run:
     ```cmd
     initialize\start_windows.bat
     ```
   - Activates `venv`, tests the local AI server, starts the desktop server, and opens your browser to `http://127.0.0.1:8000`.

---

## 🍎 macOS / Linux Setup & Launch

1. **First-Time Setup & Installation:**
   - Open Terminal and run:
     ```bash
     ./initialize/setup_mac.sh
     ```
   - Prepares Python 3 virtual environment, installs dependencies, sets up SQLite database, and prompts you to create an Administrator.

2. **Daily Startup:**
   - Open Terminal and run:
     ```bash
     ./initialize/start_mac.sh
     ```
   - Launches the FastAPI backend and opens `http://127.0.0.1:8000`.

---

## 👤 Creating or Resetting an Administrator Anytime

You can create or update an administrator account at any time using the command line:

```bash
# Interactive mode (prompts for username and password securely):
python scripts/create_admin.py

# Direct non-interactive mode:
python scripts/create_admin.py --username admin --password "StrongPass123!" --email admin@firm.com --name "CA Rajeshwar Sharma"
```

Alternatively, when opening `http://127.0.0.1:8000` for the first time, the **First-Run Web Setup Wizard** guides you through creating the master FCA Partner account directly in your browser.
