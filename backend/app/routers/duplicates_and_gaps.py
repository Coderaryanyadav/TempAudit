import io
import csv
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from backend.app.routers.auth import get_current_user, require_role
from backend.app.services.duplicate_missing_detector import (
    detect_duplicates_and_gaps,
    update_duplicate_group_review,
    update_sequence_gap_review
)

router = APIRouter(
    prefix="/api/duplicates-and-gaps",
    tags=["Duplicates & Sequence Gaps"]
)

class DuplicateGroupReviewRequest(BaseModel):
    group_code: str
    status: str # Confirmed Duplicate, Marked Valid, Ignored, Unreviewed
    auditor_comment: Optional[str] = ""

class SequenceGapReviewRequest(BaseModel):
    sequence_type: str # INVOICE_GAP, VOUCHER_GAP, CHEQUE_GAP
    series_prefix: Optional[str] = ""
    expected_from: str
    expected_to: str
    status: str # Documented / Valid Gap, In Review, Resolved, Open
    auditor_comment: Optional[str] = ""

@router.get("/{engagement_id}")
def get_duplicates_and_gaps_endpoint(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Executes duplicate detection and missing sequence gap detection for an engagement."""
    try:
        return detect_duplicates_and_gaps(engagement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing duplicates and gaps: {str(e)}")

@router.put("/{engagement_id}/duplicate-review")
def review_duplicate_group_endpoint(
    engagement_id: int,
    req: DuplicateGroupReviewRequest,
    current_user: dict = Depends(require_role(["Admin", "Auditor"]))
):
    """Allows auditor to action a duplicate group (Confirm Duplicate, Mark as Valid, Ignore, Add Comment)."""
    valid_statuses = {"Confirmed Duplicate", "Marked Valid", "Ignored", "Unreviewed"}
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    try:
        res = update_duplicate_group_review(
            engagement_id=engagement_id,
            group_code=req.group_code,
            status=req.status,
            comment=req.auditor_comment or "",
            user_name=current_user.get("username", "auditor")
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update duplicate review: {str(e)}")

@router.put("/{engagement_id}/gap-review")
def review_sequence_gap_endpoint(
    engagement_id: int,
    req: SequenceGapReviewRequest,
    current_user: dict = Depends(require_role(["Admin", "Auditor"]))
):
    """Allows auditor to document sequence gap findings (Cancelled invoice, Spoiled cheque, Multi-branch)."""
    valid_statuses = {"Open", "In Review", "Documented / Valid Gap", "Resolved"}
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    try:
        res = update_sequence_gap_review(
            engagement_id=engagement_id,
            sequence_type=req.sequence_type,
            series_prefix=req.series_prefix,
            expected_from=req.expected_from,
            expected_to=req.expected_to,
            status=req.status,
            comment=req.auditor_comment or "",
            user_name=current_user.get("username", "auditor")
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update sequence gap review: {str(e)}")

@router.get("/{engagement_id}/report/download")
def download_duplicates_and_gaps_csv_report(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Generates a downloadable CSV report of duplicate groups and missing sequence gaps."""
    try:
        data = detect_duplicates_and_gaps(engagement_id)
        summary = data["summary"]
        dup_groups = data["duplicate_groups"]
        seq_gaps = data["sequence_gaps"]

        output = io.StringIO()
        writer = csv.writer(output)

        # Header section
        writer.writerow(["FinAuditPro - Duplicate and Sequence Gap Audit Report"])
        writer.writerow(["Engagement ID", engagement_id])
        writer.writerow(["Date Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["Total Transactions Analyzed", data["total_transactions_analyzed"]])
        writer.writerow(["Total Duplicate Groups", summary["total_duplicate_groups"]])
        writer.writerow(["Potential Financial Exposure (₹)", summary["potential_financial_exposure"]])
        writer.writerow(["Total Missing Sequence Gaps", summary["total_sequence_gaps"]])
        writer.writerow([])

        # Section 1: Duplicate Groups
        writer.writerow(["--- SECTION 1: DUPLICATE GROUPS WORKBENCH ---"])
        writer.writerow([
            "Group Code", "Group Type", "Similarity Score", "Detection Reason",
            "Financial Exposure (₹)", "Auditor Status", "Auditor Comment", "Reviewed By", "Reviewed At",
            "Tx A ID", "Tx A Date", "Tx A Party", "Tx A Amount", "Tx A Voucher", "Tx A Invoice", "Tx A Description",
            "Tx B ID", "Tx B Date", "Tx B Party", "Tx B Amount", "Tx B Voucher", "Tx B Invoice", "Tx B Description"
        ])

        for g in dup_groups:
            tx_a = g["transactions"][0]
            tx_b = g["transactions"][1]
            writer.writerow([
                f"#{g['group_code']}",
                g["group_type"],
                f"{g['similarity_pct']}%",
                g["detection_reason"],
                g["financial_exposure"],
                g["status"],
                g["auditor_comment"] or "None",
                g["reviewed_by"] or "—",
                g["reviewed_at"] or "—",
                tx_a["id"], tx_a["date"], tx_a["party_name"], tx_a["amount"], tx_a["voucher_no"], tx_a["invoice_no"], tx_a["description"],
                tx_b["id"], tx_b["date"], tx_b["party_name"], tx_b["amount"], tx_b["voucher_no"], tx_b["invoice_no"], tx_b["description"]
            ])

        writer.writerow([])

        # Section 2: Sequence Gaps
        writer.writerow(["--- SECTION 2: MISSING SEQUENCE GAPS ---"])
        writer.writerow([
            "Sequence Type", "Item Series", "Prefix", "Missing From", "Missing To",
            "Missing Count", "Severity", "Audit Status", "Auditor Explanation / Remarks", "Reviewed By", "Exception Reason"
        ])

        for gap in seq_gaps:
            writer.writerow([
                gap["sequence_type"],
                gap["item_label"],
                gap["series_prefix"],
                gap["expected_from"],
                gap["expected_to"],
                gap["missing_count"],
                gap["severity"],
                gap["status"],
                gap["auditor_comment"] or "Pending auditor review",
                gap["reviewed_by"] or "—",
                gap["exception_reason"]
            ])

        csv_content = output.getvalue()
        output.close()

        filename = f"Duplicate_and_Sequence_Gaps_Engagement_{engagement_id}_{datetime.now().strftime('%Y%m%d')}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV report: {str(e)}")
