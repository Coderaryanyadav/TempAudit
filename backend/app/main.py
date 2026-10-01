import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.database import init_db
from backend.app.routers import (
    auth, clients, engagements, import_data, data_cleaning, transactions,
    trial_balance, financial_statements, yoy_comparison, reconciliation, gst_reconciliation,
    duplicates_and_gaps, anomalies, audit_findings, assistant, checklist, working_papers,
    reports, audit_trail, settings, ai_manager, evidence, jobs, system
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initializes database tables, indexes, and immutable triggers
    init_db()
    yield

app = FastAPI(
    title="FinAuditPro",
    description="Standalone Offline-First AI-Assisted Auditing Application for Indian Chartered Accountants",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local client connections with explicit safe origins
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Include all API Routers
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(engagements.router)
app.include_router(import_data.router)
app.include_router(data_cleaning.router)
app.include_router(transactions.router)
app.include_router(trial_balance.router)
app.include_router(financial_statements.router)
app.include_router(yoy_comparison.router)
app.include_router(reconciliation.router)
app.include_router(gst_reconciliation.router)
app.include_router(duplicates_and_gaps.router)
app.include_router(anomalies.router)
app.include_router(audit_findings.router)
app.include_router(assistant.router)
app.include_router(checklist.router)
app.include_router(working_papers.router)
app.include_router(reports.router)
app.include_router(audit_trail.router)
app.include_router(settings.router)
app.include_router(ai_manager.router)
app.include_router(evidence.router)
app.include_router(jobs.router)
app.include_router(system.router)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "FinAuditPro Backend API is running locally.", "docs": "/docs"}

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy"
    }
