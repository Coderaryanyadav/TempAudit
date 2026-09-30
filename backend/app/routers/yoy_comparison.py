from fastapi import APIRouter, HTTPException, Depends, Query, Response
from typing import Optional, Dict, Any
from backend.app.auth import get_current_user, require_engagement_access
from backend.app.schemas import YoYCommentRequest, YoYExplainRequest
from backend.app.services.yoy_comparison_engine import (
    run_yoy_comparison,
    explain_yoy_movement_factually,
    save_yoy_auditor_comment,
    generate_yoy_csv_report
)

router = APIRouter(prefix="/api/yoy-comparison", tags=["Year-on-Year Financial Comparison"])

@router.get("/{engagement_id}")
def get_yoy_comparison(
    engagement_id: int,
    py_engagement_id: Optional[int] = Query(None, description="Optional previous financial year engagement ID to compare against"),
    threshold_pct: float = Query(10.0, description="Configurable variance percentage threshold (e.g. 5, 10, 15, 20)"),
    materiality_threshold: float = Query(50000.0, description="Minimum materiality threshold in INR"),
    category: Optional[str] = Query(None, description="Filter by category: Executive Total, Major Ledger, Party Balance, Operational Metric"),
    only_significant: bool = Query(False, description="Filter to show only items exceeding threshold"),
    search: Optional[str] = Query(None, description="Search keyword across account names"),
    current_user: dict = Depends(get_current_user)
):
    """
    Executes and returns Year-on-Year Financial Comparison with configurable thresholds,
    comparing Revenue, Expenses, Profit, Assets, Liabilities, Receivables, Payables,
    Inventory, Cash, Bank, Major Ledgers, Party Balances, and Transaction Volumes.
    """
    require_engagement_access(engagement_id, current_user)
    if py_engagement_id is not None:
        require_engagement_access(py_engagement_id, current_user)
    try:
        data = run_yoy_comparison(
            engagement_id=engagement_id,
            py_engagement_id=py_engagement_id,
            threshold_pct=threshold_pct,
            materiality_threshold=materiality_threshold
        )

        def filter_items(items):
            res = items
            if only_significant:
                res = [i for i in res if i["is_significant"]]
            if search:
                q = search.lower()
                res = [i for i in res if q in i["account_name"].lower() or q in i["item_key"].lower() or q in i.get("group", "").lower()]
            return res

        data["executive_comparison"] = filter_items(data["executive_comparison"])
        data["major_ledgers_comparison"] = filter_items(data["major_ledgers_comparison"])
        data["party_comparison"] = filter_items(data["party_comparison"])
        data["volume_comparison"] = filter_items(data["volume_comparison"])

        if category:
            cat_map = {
                "Executive Total": ["executive_comparison"],
                "Major Ledger": ["major_ledgers_comparison"],
                "Party Balance": ["party_comparison"],
                "Operational Metric": ["volume_comparison"]
            }
            allowed = cat_map.get(category, [])
            for k in ["executive_comparison", "major_ledgers_comparison", "party_comparison", "volume_comparison"]:
                if k not in allowed:
                    data[k] = []

        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YoY Comparison failed: {str(e)}")

@router.put("/{engagement_id}/comment")
def add_yoy_comment(
    engagement_id: int,
    payload: YoYCommentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Saves auditor working paper comment and review status for a comparative line item."""
    require_engagement_access(engagement_id, current_user)
    try:
        user_name = current_user.get("username", "admin")
        return save_yoy_auditor_comment(
            engagement_id=engagement_id,
            item_key=payload.item_key,
            category=payload.category,
            account_name=payload.account_name,
            status=payload.status or "Reviewed",
            comment=payload.auditor_comment or "",
            user_name=user_name
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save comment: {str(e)}")

@router.post("/{engagement_id}/ai-explain")
def explain_movement(
    engagement_id: int,
    payload: YoYExplainRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generates a factual, evidence-based AI explanation for a YoY movement based strictly
    on recorded ledger data. Returns 'Insufficient data to determine the reason.' if evidence is lacking.
    """
    require_engagement_access(engagement_id, current_user)
    try:
        return explain_yoy_movement_factually(
            engagement_id=engagement_id,
            item_key=payload.item_key,
            threshold_pct=payload.threshold_pct or 10.0
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to explain movement: {str(e)}")

@router.get("/{engagement_id}/report/download")
def download_yoy_report(
    engagement_id: int,
    py_engagement_id: Optional[int] = Query(None),
    threshold_pct: float = Query(10.0),
    materiality_threshold: float = Query(50000.0),
    current_user: dict = Depends(get_current_user)
):
    """Downloads full Year-on-Year Financial Comparison Audit Report in CSV format."""
    require_engagement_access(engagement_id, current_user)
    if py_engagement_id is not None:
        require_engagement_access(py_engagement_id, current_user)
    try:
        csv_content = generate_yoy_csv_report(
            engagement_id=engagement_id,
            py_engagement_id=py_engagement_id,
            threshold_pct=threshold_pct,
            materiality_threshold=materiality_threshold
        )
        filename = f"YoY_Financial_Comparison_Engagement_{engagement_id}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export CSV report: {str(e)}")
