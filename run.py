import os
import sys

# Auto-detect and seamlessly switch to project virtual environment if available
in_venv = getattr(sys, "base_prefix", sys.prefix) != sys.prefix or "VIRTUAL_ENV" in os.environ
if not in_venv:
    project_root = os.path.dirname(os.path.abspath(__file__))
    venv_python_unix = os.path.join(project_root, "venv", "bin", "python")
    venv_python_win = os.path.join(project_root, "venv", "Scripts", "python.exe")
    target_python = None
    if os.path.exists(venv_python_unix):
        target_python = venv_python_unix
    elif os.path.exists(venv_python_win):
        target_python = venv_python_win

    if target_python and os.path.abspath(sys.executable) != os.path.abspath(target_python):
        os.execv(target_python, [target_python] + sys.argv)

try:
    import uvicorn
except ImportError:
    print("\n" + "=" * 70)
    print("❌ ERROR: Missing required dependencies (e.g. uvicorn, fastapi).")
    print("Please activate your virtual environment or install dependencies:")
    print("  source venv/bin/activate       # macOS / Linux")
    print("  .\\venv\\Scripts\\activate        # Windows")
    print("  pip install -r requirements.txt")
    print("=" * 70 + "\n")
    sys.exit(1)

import webbrowser
import threading
import time

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("==================================================================")
    print("  FinAuditPro - AI-Assisted Auditing Software (Offline Edition)  ")
    print("  Standalone Desktop Server starting on http://127.0.0.1:8000     ")
    print("==================================================================")

    # Initialize database schema
    from backend.app.database import init_db
    init_db()

    # Launch browser in separate thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run FastAPI server
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
