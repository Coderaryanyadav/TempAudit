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
    print("  pip install -r requirements.lock")
    print("=" * 70 + "\n")
    sys.exit(1)

import webbrowser
import threading
import time
import urllib.request

def open_browser():
    """Open the UI only after FastAPI has completed startup and its health check responds."""
    deadline = time.monotonic() + 30
    health_url = "http://127.0.0.1:8000/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    webbrowser.open("http://127.0.0.1:8000")
                    return
        except Exception:
            time.sleep(0.5)
    print("[WARN] Server health check did not succeed; open http://127.0.0.1:8000 after startup if the server is running.")


if __name__ == "__main__":
    print("==================================================================")
    print("  FinAuditPro - AI-Assisted Auditing Software (Offline Edition)  ")
    print("  Standalone Desktop Server starting on http://127.0.0.1:8000     ")
    print("==================================================================")

    # Launch browser in separate thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run FastAPI server
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
