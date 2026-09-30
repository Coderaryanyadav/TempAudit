import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
DATE_REGEX = r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?$"
PAN_REGEX = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    full_name: str = Field(..., min_length=2, max_length=100)
    role: Literal["Admin", "Auditor", "Audit Staff"] = "Auditor"
    password: str = Field(..., min_length=8)
    phone: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = (v or "").strip()
        if not re.match(EMAIL_REGEX, v):
            raise ValueError("Invalid email format.")
        return v

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[Literal["Admin", "Auditor", "Audit Staff"]] = None
    phone: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not re.match(EMAIL_REGEX, v):
                raise ValueError("Invalid email format.")
        return v

class UserStatusUpdate(BaseModel):
    is_active: bool

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: int
    created_at: str
    last_login: Optional[str] = None
    phone: Optional[str] = None

# --- CLIENT SCHEMAS ---
class ClientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    entity_type: str = "Private Limited Company" # Proprietorship, Partnership, LLP, Private Limited Company, Public Limited Company, Trust, Society, NGO, Other
    pan: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = "Manufacturing"
    financial_year: Optional[str] = "2024-25"
    notes: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            if not re.match(EMAIL_REGEX, v):
                raise ValueError("Invalid email format.")
        return v

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    entity_type: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    financial_year: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            if not re.match(EMAIL_REGEX, v):
                raise ValueError("Invalid email format.")
        return v

# --- ENGAGEMENT SCHEMAS ---
class EngagementCreate(BaseModel):
    client_id: int
    title: str = Field(..., min_length=3, max_length=200)
    audit_type: str = "Statutory Audit" # Statutory Audit, Internal Audit, Tax Audit, Review, Special Audit, Other
    financial_year: str = "2024-25"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    lead_auditor_id: Optional[int] = None
    assigned_staff_id: Optional[int] = None
    status: Optional[str] = "In Progress"
    notes: Optional[str] = None

    @field_validator("period_start", "period_end")
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            if not re.match(DATE_REGEX, v):
                raise ValueError("Date must be in YYYY-MM-DD format.")
        return v

class EngagementUpdate(BaseModel):
    title: Optional[str] = None
    audit_type: Optional[str] = None
    financial_year: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    lead_auditor_id: Optional[int] = None
    assigned_staff_id: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("period_start", "period_end")
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            if not re.match(DATE_REGEX, v):
                raise ValueError("Date must be in YYYY-MM-DD format.")
        return v

class DuplicateEngagementRequest(BaseModel):
    source_engagement_id: int
    target_financial_year: str # e.g. "2025-26"
    title: Optional[str] = None
    copy_checklists: bool = True
    copy_working_paper_templates: bool = True

class ColumnMappingRequest(BaseModel):
    file_id: int
    column_mapping: Dict[str, str]
    data_category: Optional[str] = "General Ledger"

class ValidateMappingRequest(BaseModel):
    file_id: int
    column_mapping: Dict[str, str]
    data_category: Optional[str] = "General Ledger"

class TransactionCreate(BaseModel):
    date: Optional[str] = None
    voucher_no: Optional[str] = None
    invoice_no: Optional[str] = None
    ledger: str
    account_group: Optional[str] = "Expense"
    description: Optional[str] = None
    debit: float = Field(default=0.0, ge=0.0)
    credit: float = Field(default=0.0, ge=0.0)
    party_name: Optional[str] = None
    gstin: Optional[str] = None
    payment_date: Optional[str] = None

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip().upper()
            if not re.match(GSTIN_REGEX, v):
                raise ValueError("Invalid Indian GSTIN format (Expected 15 characters).")
        return v

    @field_validator("date", "payment_date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            if not re.match(DATE_REGEX, v):
                raise ValueError("Date must be in YYYY-MM-DD format.")
        return v

    @field_validator("debit", "credit")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Transaction amounts cannot be negative.")
        return round(float(v), 2)

    @model_validator(mode="after")
    def validate_accounting_entry(self):
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debit and credit amounts cannot be negative.")
        return self

class FindingUpdate(BaseModel):
    status: Optional[str] = None # Open, Under Review, Resolved, Waived
    auditor_comment: Optional[str] = None
    reviewed_by: Optional[str] = None

class FindingCreateCustom(BaseModel):
    engagement_id: int
    finding_code: Optional[str] = None
    module: Optional[str] = "Manual Audit"
    category: str = "General Audit"
    severity: str = "MEDIUM" # LOW, MEDIUM, HIGH, CRITICAL
    title: str
    description: str
    affected_records: Optional[List[int]] = []
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    difference: Optional[str] = None
    rule_used: Optional[str] = "Manual Audit Observation"
    recommended_action: Optional[str] = None
    auditor_comment: Optional[str] = None

class ChecklistItemUpdate(BaseModel):
    status: Optional[str] = None # Not Started, In Progress, Completed, Not Applicable, Requires Review
    assigned_staff: Optional[str] = None
    evidence: Optional[str] = None
    comment: Optional[str] = None
    auditor_remarks: Optional[str] = None
    reference_wp: Optional[str] = None
    due_date: Optional[str] = None
    completed_date: Optional[str] = None

class ChecklistItemCreate(BaseModel):
    category: str
    question: str
    item_code: Optional[str] = None
    guidance: Optional[str] = None
    status: Optional[str] = "Not Started"
    assigned_staff: Optional[str] = None
    due_date: Optional[str] = None
    evidence: Optional[str] = None
    comment: Optional[str] = None

class ChecklistGenerateRequest(BaseModel):
    client_type: Optional[str] = None
    audit_type: Optional[str] = None
    financial_year: Optional[str] = None
    selected_modules: Optional[List[str]] = []
    regenerate: Optional[bool] = False

class WorkingPaperCreate(BaseModel):
    wp_reference: str
    title: str
    area: Optional[str] = "General"
    category: Optional[str] = None # Backwards compatibility
    description: Optional[str] = None
    evidence: Optional[str] = None
    prepared_by: Optional[str] = None
    prepared_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = "Prepared" # Prepared, Under Review, Reviewed, Needs Correction
    linked_findings: Optional[List[int]] = []
    linked_transactions: Optional[List[int]] = []
    linked_checklists: Optional[List[int]] = []

class WorkingPaperUpdate(BaseModel):
    wp_reference: Optional[str] = None
    title: Optional[str] = None
    area: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    evidence: Optional[str] = None
    prepared_by: Optional[str] = None
    prepared_date: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    linked_findings: Optional[List[int]] = None
    linked_transactions: Optional[List[int]] = None
    linked_checklists: Optional[List[int]] = None

class WorkingPaperStatusUpdate(BaseModel):
    status: str # Prepared, Under Review, Reviewed, Needs Correction
    reviewed_by: Optional[str] = None
    review_date: Optional[str] = None
    comment: Optional[str] = None

class WorkingPaperCommentCreate(BaseModel):
    comment: str
    author: Optional[str] = None

class WorkingPaperNotesUpdate(BaseModel):
    notes: str

class WorkingPaperLinkUpdate(BaseModel):
    link_type: str # "finding", "transaction", "checklist"
    action: str # "link", "unlink"
    item_id: int

class WorkingPaperDeleteRequest(BaseModel):
    reason: Optional[str] = None

class GenerateReportRequest(BaseModel):
    report_type: Optional[str] = "complete_audit_analysis"



class AssistantQuery(BaseModel):
    engagement_id: int
    query: str
    finding_id: Optional[int] = None
    transaction_id: Optional[int] = None
    voucher_no: Optional[str] = None
    context_type: Optional[str] = "general"

class ReconciliationRequest(BaseModel):
    engagement_id: int
    recon_type: str
    title: str
    file_a_id: int
    file_b_id: int

class CleaningLogReviewRequest(BaseModel):
    action: str # Accepted, Overridden, Reverted
    custom_normalized_value: Optional[str] = None
    auditor_comment: Optional[str] = None

class NormalizationPreviewRequest(BaseModel):
    field_name: str # date, amount, debit, credit, party_name, ledger, gstin, invoice_no
    raw_value: str

class AnomalyReviewRequest(BaseModel):
    status: str # Open, Confirmed Anomaly, Marked Normal, Ignored
    auditor_comment: Optional[str] = ""

class YoYCommentRequest(BaseModel):
    item_key: str
    category: str
    account_name: str
    status: Optional[str] = "Reviewed"
    auditor_comment: str

class YoYExplainRequest(BaseModel):
    item_key: str
    threshold_pct: Optional[float] = 10.0


