"""
Test Checklists Definitions
FinAuditPro - Test Data Architecture
"""

from typing import List, Dict, Any
from backend.app.services.checklist_templates import STANDARD_CHECKLIST_ITEMS

def get_test_checklist_items(engagement_id: int) -> List[Dict[str, Any]]:
    items = []
    for item in STANDARD_CHECKLIST_ITEMS:
        items.append({
            "engagement_id": engagement_id,
            "category": item["category"],
            "item_code": item["item_code"],
            "question": item["question"],
            "guidance": item["guidance"],
            "status": "In Progress" if "CARO" in item["item_code"] else "Pending"
        })
    return items
