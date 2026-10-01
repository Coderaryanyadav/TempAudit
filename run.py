import uvicorn
import webbrowser
import os
import sys
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
