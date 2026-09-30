"""
Test GST Portal Data Loader (SOURCE = TEST_GST_PORTAL)
FinAuditPro - Test Data Architecture
"""

import os
import csv
from typing import List, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_gst_portal_data_for_company(company_code: str) -> List[Dict[str, Any]]:
    code = company_code.lower()
    csv_path = os.path.join(BASE_DIR, f"{code}_fintech", "gst_portal.csv")
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)
