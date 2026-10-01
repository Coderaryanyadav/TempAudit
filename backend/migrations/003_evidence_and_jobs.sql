-- 003_evidence_and_jobs.sql
-- Evidence Immutability & Versioning Store + SQLite Background Jobs Architecture

CREATE TABLE IF NOT EXISTS evidence_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    working_paper_id INTEGER,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    sha256_hash TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    parent_evidence_id INTEGER,
    replacement_reason TEXT,
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, SUPERSEDED, ARCHIVED, INTEGRITY_FAILED
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE,
    FOREIGN KEY (working_paper_id) REFERENCES working_papers (id) ON DELETE SET NULL,
    FOREIGN KEY (parent_evidence_id) REFERENCES evidence_items (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_engagement ON evidence_items(engagement_id);
CREATE INDEX IF NOT EXISTS idx_evidence_wp ON evidence_items(working_paper_id);
CREATE INDEX IF NOT EXISTS idx_evidence_hash ON evidence_items(sha256_hash);
CREATE INDEX IF NOT EXISTS idx_evidence_status ON evidence_items(engagement_id, status);

CREATE TABLE IF NOT EXISTS background_jobs (
    id TEXT PRIMARY KEY, -- UUID string
    engagement_id INTEGER,
    job_type TEXT NOT NULL, -- EXCEL_IMPORT, CSV_IMPORT, RECONCILIATION, ANOMALY_DETECTION, REPORT_GENERATION, AI_ANALYSIS
    status TEXT NOT NULL DEFAULT 'QUEUED', -- QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    progress INTEGER NOT NULL DEFAULT 0, -- 0 to 100 percentage
    payload_json TEXT,
    result_json TEXT,
    error_message TEXT,
    result_location TEXT,
    created_by TEXT DEFAULT 'system',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON background_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_engagement ON background_jobs(engagement_id);
