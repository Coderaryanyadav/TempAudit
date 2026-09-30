from fastapi import APIRouter, HTTPException, Depends, Query, Response
from typing import Optional, Dict, Any
from backend.app.auth import get_current_user, require_engagement_access
from backend.app.schemas import AnomalyReviewRequest
from backend.app.services.anomaly_detection_engine import (
    detect_all_anomalies,
    update_anomaly_review,
    generate_ai_anomaly_explanation,
    generate_anomaly_csv_report
)

router = APIRouter(prefix="/api/anomalies", tags=["AI Anomaly Detection Engine"])

@router.get("/{engagement_id}")
def get_engagement_anomalies(
    engagement_id: int,
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"),
    level: Optional[str] = Query(None, description="Filter by level: LEVEL 1, LEVEL 2, LEVEL 3"),
    pattern: Optional[str] = Query(None, description="Filter by detected pattern name"),
    status: Optional[str] = Query(None, description="Filter by review status: Open, Confirmed Anomaly, Marked Normal, Ignored"),
    search: Optional[str] = Query(None, description="Search keyword in voucher, party, ledger, description"),
    current_user: dict = Depends(get_current_user)
):
    """
    Executes and returns the 3-Tier Hybrid Anomaly Detection Engine results
    with deterministic rules, statistical z-scores/IQR/Benford, and ML models.
    """
    require_engagement_access(engagement_id, current_user)
    try:
        data = detect_all_anomalies(engagement_id)
        anomalies = data["anomalies"]

        if severity:
            anomalies = [a for a in anomalies if a["severity"].upper() == severity.upper()]
        if level:
            anomalies = [a for a in anomalies if level.upper() in a["level"].upper()]
        if pattern:
            anomalies = [a for a in anomalies if pattern.lower() in a["pattern_type"].lower()]
        if status:
            anomalies = [a for a in anomalies if a["status"].lower() == status.lower()]
        if search:
            q = search.lower()
            anomalies = [
                a for a in anomalies
                if q in a["anomaly_id"].lower()
                or q in a["pattern_type"].lower()
                or q in a["transaction"]["ledger"].lower()
                or q in a["transaction"]["party_name"].lower()
                or q in a["transaction"]["voucher_no"].lower()
                or q in a["transaction"]["description"].lower()
            ]

        data["anomalies"] = anomalies
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute anomaly detection: {str(e)}")

@router.post("/{engagement_id}/detect")
def trigger_anomaly_detection(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """Triggers fresh execution of the 3-Tier Hybrid Anomaly Detection Engine."""
    require_engagement_access(engagement_id, current_user)
    try:
        return detect_all_anomalies(engagement_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")

@router.put("/{engagement_id}/review/{anomaly_id}")
def review_anomaly(
    engagement_id: int,
    anomaly_id: str,
    payload: AnomalyReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """Updates auditor review status (Confirmed Anomaly, Marked Normal, Ignored) and comments."""
    require_engagement_access(engagement_id, current_user)
    try:
        user_name = current_user.get("username", "admin")
        return update_anomaly_review(
            engagement_id=engagement_id,
            anomaly_id=anomaly_id,
            status=payload.status,
            comment=payload.auditor_comment or "",
            user_name=user_name
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update review: {str(e)}")

@router.post("/{engagement_id}/ai-explain/{anomaly_id}")
def get_ai_anomaly_explanation(
    engagement_id: int,
    anomaly_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Generates an in-depth CA-oriented AI Working Paper Memorandum explaining the anomaly."""
    require_engagement_access(engagement_id, current_user)
    try:
        return generate_ai_anomaly_explanation(engagement_id, anomaly_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate AI memo: {str(e)}")

@router.get("/{engagement_id}/report/download")
def download_anomaly_report(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Downloads full Anomaly Detection Audit Report in CSV format."""
    require_engagement_access(engagement_id, current_user)
    try:
        csv_content = generate_anomaly_csv_report(engagement_id)
        filename = f"AI_Anomaly_Detection_Report_Engagement_{engagement_id}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV report: {str(e)}")
