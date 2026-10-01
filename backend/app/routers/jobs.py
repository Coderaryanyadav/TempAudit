from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from backend.app.auth import get_current_user, require_engagement_access
from backend.app.jobs.job_manager import JobManager, JobStatus

router = APIRouter(prefix="/api/jobs", tags=["Background Jobs"])

class JobCreateRequest(BaseModel):
    job_type: str
    engagement_id: Optional[int] = None
    payload: Optional[dict] = None

@router.get("/")
def list_jobs(
    engagement_id: Optional[int] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Lists background jobs with optional engagement scoping."""
    if engagement_id:
        require_engagement_access(engagement_id, current_user)
    return JobManager.list_jobs(engagement_id=engagement_id, limit=limit)

@router.get("/{job_id}")
def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Fetches real-time status and progress of a background job."""
    job = JobManager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("engagement_id"):
        require_engagement_access(job["engagement_id"], current_user)
    return job

@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancels a queued or running background job."""
    job = JobManager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("engagement_id"):
        require_engagement_access(job["engagement_id"], current_user)
    JobManager.cancel_job(job_id)
    return {"status": "success", "message": "Job cancellation requested.", "job_id": job_id}
