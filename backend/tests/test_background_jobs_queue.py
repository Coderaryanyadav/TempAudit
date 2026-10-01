import time
import pytest
from backend.app.jobs.job_manager import JobManager, JobStatus
from backend.app.database import init_db

def test_job_lifecycle_queued_to_completion():
    """Verify background job creation, execution, and state transitions."""
    init_db()

    def dummy_task(job_id: str, payload: dict):
        JobManager.update_progress(job_id, 50)
        time.sleep(0.05)
        return {"records_processed": 150, "status": "ALL_MATCHED"}

    job_id = JobManager.create_job(
        job_type="RECONCILIATION_BATCH",
        engagement_id=1,
        payload={"batch_size": 150},
        created_by="AuditorTest"
    )

    initial_job = JobManager.get_job(job_id)
    assert initial_job["status"] in (JobStatus.QUEUED, JobStatus.RUNNING)

    # Submit task
    JobManager.submit_task(job_id, dummy_task, {"batch_size": 150})

    # Poll for completion
    for _ in range(20):
        time.sleep(0.05)
        job = JobManager.get_job(job_id)
        if job["status"] == JobStatus.COMPLETED:
            break

    final_job = JobManager.get_job(job_id)
    assert final_job["status"] == JobStatus.COMPLETED
    assert final_job["progress"] == 100
    assert final_job["result"].get("records_processed") == 150

def test_job_cancellation():
    """Verify job cancellation updates status safely."""
    init_db()
    job_id = JobManager.create_job(
        job_type="EXCEL_IMPORT",
        engagement_id=1,
        payload={"file": "test.xlsx"}
    )

    assert JobManager.cancel_job(job_id) is True
    job = JobManager.get_job(job_id)
    assert job["status"] == JobStatus.CANCELLED
    assert JobManager.is_cancelled(job_id) is True
