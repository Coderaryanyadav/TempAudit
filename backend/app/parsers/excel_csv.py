import os
import re
import json
import csv
import io
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from pypdf import PdfReader
from backend.app.database import get_db_connection

GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

# Safety limits for enterprise document parsing & memory protection
MAX_PDF_PAGES = 500
MAX_PDF_EXTRACTED_CHARS = 15_000_000
MAX_EXCEL_ROWS = 500_000
MAX_EXCEL_COLS = 250
MAX_EXCEL_SHEETS = 30

STANDARD_COLUMNS = {
    "date": ["date", "voucher date", "vch date", "txn date", "posting date", "bill date", "invoice date", "trans date", "txndate", "value date", "entry date"],
    "voucher_no": ["voucher no", "voucher", "vch no", "vch", "voucher_no", "entry no", "trans no", "vch_no", "journal no", "doc no", "document number"],
    "invoice_no": ["invoice no", "inv no", "invoice", "bill no", "document no", "ref no", "invoice_no", "inv_num", "bill number", "tax invoice no"],
    "ledger": ["ledger", "account", "ledger name", "account name", "head", "head of account", "gl account", "particulars", "account head", "ledger title"],
    "account_group": ["group", "account group", "head group", "type", "category", "class", "gl group"],
    "party_name": ["party name", "party", "vendor", "customer", "party_name", "supplier", "payee", "beneficiary", "client name", "account holder"],
    "gstin": ["gstin", "gst", "tin", "party gstin", "supplier gstin", "customer gstin", "gstin/uin", "gst number"],
    "debit": ["debit", "dr", "dr amount", "dr.", "debit amount", "withdrawal", "withdrawals", "dr_amount", "paid out"],
    "credit": ["credit", "cr", "cr amount", "cr.", "credit amount", "deposit", "deposits", "cr_amount", "paid in"],
    "amount": ["amount", "net amount", "total", "value", "txn amount", "transaction amount", "gross amount", "invoice value", "taxable value"],
    "tax_amount": ["tax", "tax amount", "gst amount", "igst", "cgst", "sgst", "vat", "tax value", "total tax"],
    "description": ["description", "narration", "remarks", "details", "narrative", "notes", "transaction details", "particulars"],
    "reference_no": ["reference", "reference no", "ref no", "cheque no", "utr", "chq no", "instrument no", "trans ref", "bank ref"],
    "opening_balance": ["opening balance", "opening", "op bal", "open balance", "initial balance"],
    "closing_balance": ["closing balance", "closing", "cl bal", "close balance", "balance", "running balance"],
    "payment_date": ["payment date", "pay date", "clearance date", "realisation date"]
}

SUPPORTED_DATA_CATEGORIES = [
    "Trial Balance",
    "General Ledger",
    "Sales Register",
    "Purchase Register",
    "Bank Statement",
    "Expense Register",
    "Customer Ledger",
    "Vendor Ledger",
    "Journal Entries",
    "GST-related data",
    "Other transaction data"
]

def auto_detect_mapping(columns: List[str]) -> Dict[str, str]:
    """Auto-detects mapping from source column names to standard fields with strict disambiguation."""
    mapping = {}
    used_targets = set()
    used_columns = set()
    
    clean_cols = [re.sub(r'[^a-z0-9_]', '', str(c).strip().lower().replace(' ', '_')) for c in columns]
    raw_lower_cols = [str(c).strip().lower() for c in columns]
    
    # Priority order: specific multi-word fields first, general fields later
    target_priority = [
        "tax_amount", "opening_balance", "closing_balance", "payment_date",
        "voucher_no", "invoice_no", "account_group", "party_name", "gstin",
        "reference_no", "debit", "credit", "amount", "ledger", "date", "description"
    ]
    
    # Pass 1: Exact matches
    for target in target_priority:
        aliases = STANDARD_COLUMNS.get(target, [])
        for i, col in enumerate(columns):
            if col in used_columns or target in used_targets:
                continue
            cleaned = clean_cols[i]
            raw_low = raw_lower_cols[i]
            if raw_low in aliases or cleaned in aliases or cleaned == target:
                mapping[col] = target
                used_targets.add(target)
                used_columns.add(col)
                break

    # Pass 2: Word-boundary & regex matching
    for target in target_priority:
        if target in used_targets:
            continue
        aliases = STANDARD_COLUMNS.get(target, [])
        for i, col in enumerate(columns):
            if col in used_columns:
                continue
            raw_low = raw_lower_cols[i]
            for alias in aliases:
                # Require word boundary
                pattern = rf"(^|[\s_\-\./]){re.escape(alias)}($|[\s_\-\./])"
                if re.search(pattern, raw_low):
                    # Disambiguation safeguard: avoid matching 'amount' if 'tax' is in the column name
                    if target == "amount" and any(t in raw_low for t in ["tax", "gst", "vat", "igst", "cgst", "sgst"]):
                        continue
                    mapping[col] = target
                    used_targets.add(target)
                    used_columns.add(col)
                    break
            if target in used_targets:
                break

    return mapping

def parse_raw_dataframe(file_path: str, file_type: str, limit: Optional[int] = None) -> pd.DataFrame:
    """Reads various file formats (CSV, XLSX, XLS, JSON, PDF) into a pandas DataFrame with strict bounds checking."""
    ext = file_type.lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"

    if ext == ".csv":
        bad_lines_encountered = []
        def track_bad_line(bad_line):
            bad_lines_encountered.append(bad_line)
            return None

        # Try clean encodings in priority order
        for encoding in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252', 'utf-16']:
            try:
                with open(file_path, 'r', encoding=encoding, errors='strict') as f:
                    sample = f.read(4096)
                    try:
                        dialect = csv.Sniffer().sniff(sample)
                        delimiter = dialect.delimiter
                    except Exception:
                        delimiter = ',' if ',' in sample else ('\t' if '\t' in sample else ';')

                df = pd.read_csv(
                    file_path,
                    delimiter=delimiter,
                    encoding=encoding,
                    nrows=limit,
                    on_bad_lines=track_bad_line,
                    engine='python' if bad_lines_encountered is not None else 'c'
                )
                if bad_lines_encountered:
                    df.attrs["bad_lines_count"] = len(bad_lines_encountered)
                    df.attrs["bad_lines_sample"] = bad_lines_encountered[:5]
                return df
            except UnicodeDecodeError:
                continue
            except Exception:
                continue

        # Fallback with error tracking
        df = pd.read_csv(file_path, nrows=limit, on_bad_lines=track_bad_line, engine='python')
        if bad_lines_encountered:
            df.attrs["bad_lines_count"] = len(bad_lines_encountered)
            df.attrs["bad_lines_sample"] = bad_lines_encountered[:5]
        return df

    elif ext in [".xlsx", ".xls"]:
        xl = pd.ExcelFile(file_path)
        if len(xl.sheet_names) > MAX_EXCEL_SHEETS:
            raise ValueError(f"Excel file exceeds maximum allowable sheets ({len(xl.sheet_names)} > {MAX_EXCEL_SHEETS}). Please upload a workbook with fewer sheets.")

        df = pd.read_excel(file_path, nrows=limit or MAX_EXCEL_ROWS)
        if len(df.columns) > MAX_EXCEL_COLS:
            raise ValueError(f"Excel table exceeds maximum column limit ({len(df.columns)} > {MAX_EXCEL_COLS}).")
        return df

    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                for key in ["transactions", "rows", "data", "records", "items", "entries"]:
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
                if isinstance(data, dict):
                    data = [data]
            df = pd.DataFrame(data)
            if limit:
                df = df.head(limit)
            return df

    elif ext == ".pdf":
        return parse_pdf_to_dataframe(file_path, limit)

    else:
        raise ValueError(f"Unsupported file format: '{ext}'. Supported formats: CSV, Excel (.xlsx, .xls), PDF (.pdf), JSON (.json).")

def parse_pdf_to_dataframe(file_path: str, limit: Optional[int] = None) -> pd.DataFrame:
    """Extracts text tables or line records from PDF bank statements or audit reports with resource protection."""
    try:
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)
        if total_pages > MAX_PDF_PAGES:
            raise ValueError(f"PDF document exceeds the maximum limit of {MAX_PDF_PAGES} pages (uploaded file has {total_pages} pages). Please split the document.")

        all_lines = []
        total_extracted_chars = 0

        for page in reader.pages:
            text = page.extract_text()
            if text:
                total_extracted_chars += len(text)
                if total_extracted_chars > MAX_PDF_EXTRACTED_CHARS:
                    raise ValueError(f"PDF text extraction exceeded safety limit of {MAX_PDF_EXTRACTED_CHARS:,} characters.")
                all_lines.extend([line.strip() for line in text.splitlines() if line.strip()])
        
        if not all_lines:
            raise ValueError("The uploaded PDF file contains no readable text or structured table data.")

        rows = []
        header = None
        for line in all_lines:
            parts = re.split(r'\s{2,}|\t|\|', line)
            if len(parts) >= 3:
                if not header and any(w in line.lower() for w in ["date", "particulars", "description", "debit", "credit", "amount"]):
                    header = [p.strip() for p in parts]
                    continue
                rows.append(parts)

        if not rows:
            date_pattern = r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}-[A-Za-z]{3}-\d{2,4})'
            for line in all_lines:
                if re.match(date_pattern, line):
                    tokens = line.split()
                    if len(tokens) >= 3:
                        rows.append(tokens)

        if header and rows:
            max_len = max(len(r) for r in rows)
            if len(header) < max_len:
                header += [f"Column_{i+1}" for i in range(len(header), max_len)]
            normalized_rows = [r + [None]*(len(header)-len(r)) if len(r) < len(header) else r[:len(header)] for r in rows]
            df = pd.DataFrame(normalized_rows, columns=header)
        elif rows:
            max_len = max(len(r) for r in rows)
            cols = ["Date", "Description", "Ref_No", "Debit", "Credit", "Balance"][:max_len]
            if len(cols) < max_len:
                cols += [f"Column_{i+1}" for i in range(len(cols), max_len)]
            normalized_rows = [r + [None]*(len(cols)-len(r)) if len(r) < len(cols) else r[:len(cols)] for r in rows]
            df = pd.DataFrame(normalized_rows, columns=cols)
        else:
            df = pd.DataFrame([{"raw_content": line} for line in all_lines])

        if limit:
            df = df.head(limit)
        return df

    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"Could not extract tabular financial data from PDF: {str(e)}")

def read_file_preview(file_path: str, file_type: str, data_category: Optional[str] = None) -> Dict[str, Any]:
    """Reads top rows of the uploaded file, suggests column mappings, and detects structure."""
    df = parse_raw_dataframe(file_path, file_type, limit=50)
    
    # Strip whitespace from column names
    df.columns = [str(c).strip() for c in df.columns]
    columns = list(df.columns)
    suggested_mapping = auto_detect_mapping(columns)

    # Convert preview data to clean JSON-serializable records
    preview_data = df.head(15).replace({np.nan: None}).to_dict(orient="records")

    # Efficient total rows estimation
    ext = file_type.lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"

    estimated_total = len(df)
    try:
        if ext == ".csv":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                estimated_total = max(0, sum(1 for _ in f) - 1)
        elif ext in [".xlsx", ".xls"]:
            xl = pd.ExcelFile(file_path)
            if xl.sheet_names:
                df_sheet = pd.read_excel(file_path, sheet_name=0)
                estimated_total = len(df_sheet)
        elif ext == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    estimated_total = len(data)
                elif isinstance(data, dict):
                    for k in ["transactions", "rows", "data", "records", "items", "entries"]:
                        if k in data and isinstance(data[k], list):
                            estimated_total = len(data[k])
                            break
    except Exception:
        estimated_total = len(df)

    # Column mapping status summary
    mapped_targets = set(suggested_mapping.values())
    status_summary = {}
    for target in STANDARD_COLUMNS.keys():
        if target in mapped_targets:
            src = [k for k, v in suggested_mapping.items() if v == target][0]
            status_summary[target] = {"status": "Detected", "source_column": src}
        elif target in ["date", "ledger", "amount", "debit", "credit"]:
            status_summary[target] = {"status": "Needs mapping", "source_column": None}
        else:
            status_summary[target] = {"status": "Not detected", "source_column": None}

    return {
        "columns": columns,
        "suggested_mapping": suggested_mapping,
        "mapping_status": status_summary,
        "preview_rows": preview_data,
        "estimated_total_rows": estimated_total,
        "data_category": data_category or "General Ledger",
        "supported_categories": SUPPORTED_DATA_CATEGORIES
    }

def try_parse_date(date_str: Any) -> Tuple[Optional[str], bool]:
    """Attempts to parse varied date representations without modifying genuine dates."""
    if date_str is None or pd.isna(date_str) or str(date_str).strip() == "":
        return None, False

    s = str(date_str).strip()
    # Common standard ISO format
    if re.match(r'^\d{4}-\d{2}-\d{2}', s):
        return s.split(" ")[0].split("T")[0], True

    # Common Indian / British formats: DD/MM/YYYY, DD-MM-YYYY
    for fmt in [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%d/%m/%y", "%d-%m-%y",
        "%Y/%m/%d", "%Y-%m-%d",
        "%d-%b-%Y", "%d-%b-%y", "%d %b %Y",
        "%d-%B-%Y", "%B %d, %Y"
    ]:
        try:
            dt = datetime.strptime(s.split(" ")[0], fmt)
            return dt.strftime("%Y-%m-%d"), True
        except Exception:
            continue

    # Fallback to pandas to_datetime
    try:
        dt = pd.to_datetime(s, errors='raise', dayfirst=True)
        return dt.strftime("%Y-%m-%d"), True
    except Exception:
        return s, False

def validate_imported_dataframe(df: pd.DataFrame, mapping: Dict[str, str], data_category: str = "General Ledger") -> Dict[str, Any]:
    """
    Executes comprehensive pre-import accounting and statutory data integrity checks:
    - Invalid dates
    - Empty required fields
    - Duplicate rows
    - Invalid amounts / non-numeric values
    - Debit/credit conflicts
    - Invalid GSTIN format (when applicable)
    - Missing invoice numbers
    - Duplicate invoice numbers (for Sales registers)
    """
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    
    seen_rows = set()
    seen_invoices = set()
    valid_rows_count = 0
    failed_rows_count = 0

    has_date_col = any(v == "date" for v in mapping.values())
    has_ledger_col = any(v == "ledger" for v in mapping.values())
    has_party_col = any(v == "party_name" for v in mapping.values())
    has_debit_col = any(v == "debit" for v in mapping.values())
    has_credit_col = any(v == "credit" for v in mapping.values())
    has_amount_col = any(v == "amount" for v in mapping.values())
    has_invoice_col = any(v == "invoice_no" for v in mapping.values())
    has_gstin_col = any(v == "gstin" for v in mapping.values())

    for idx, row in df.iterrows():
        row_num = idx + 1 # 1-indexed
        row_errors = []
        row_warnings = []
        
        mapped_data = {}
        for src_col, target in mapping.items():
            if src_col in row and target:
                val = row[src_col]
                mapped_data[target] = None if pd.isna(val) else val

        # 1. Check Date
        raw_date = mapped_data.get("date")
        if raw_date is not None and str(raw_date).strip() != "":
            parsed_date, is_valid_date = try_parse_date(raw_date)
            if not is_valid_date:
                row_errors.append({
                    "row": row_num,
                    "field": "date",
                    "error_type": "INVALID_DATE",
                    "message": f"Unparseable date value: '{raw_date}'",
                    "value": str(raw_date)
                })
        else:
            if has_date_col:
                row_warnings.append({
                    "row": row_num,
                    "field": "date",
                    "error_type": "EMPTY_DATE",
                    "message": "Date is empty for this row.",
                    "value": ""
                })

        # 2. Check Empty Required Head (Ledger or Party)
        ledger_val = str(mapped_data.get("ledger") or "").strip()
        party_val = str(mapped_data.get("party_name") or "").strip()
        if not ledger_val and not party_val and (has_ledger_col or has_party_col):
            row_warnings.append({
                "row": row_num,
                "field": "ledger",
                "error_type": "EMPTY_REQUIRED_HEAD",
                "message": "Both Ledger Account and Party Name are missing.",
                "value": ""
            })

        # 3. Numeric & Amount Validations
        raw_debit = mapped_data.get("debit")
        raw_credit = mapped_data.get("credit")
        raw_amount = mapped_data.get("amount")

        debit_val = 0.0
        credit_val = 0.0
        amount_val = 0.0

        if raw_debit is not None and str(raw_debit).strip() != "":
            try:
                debit_val = float(str(raw_debit).replace(",", "").strip())
                if debit_val < 0:
                    row_warnings.append({
                        "row": row_num,
                        "field": "debit",
                        "error_type": "NEGATIVE_AMOUNT",
                        "message": f"Negative debit value detected: {debit_val}",
                        "value": str(raw_debit)
                    })
            except ValueError:
                row_errors.append({
                    "row": row_num,
                    "field": "debit",
                    "error_type": "INVALID_NUMERIC",
                    "message": f"Non-numeric debit amount: '{raw_debit}'",
                    "value": str(raw_debit)
                })

        if raw_credit is not None and str(raw_credit).strip() != "":
            try:
                credit_val = float(str(raw_credit).replace(",", "").strip())
                if credit_val < 0:
                    row_warnings.append({
                        "row": row_num,
                        "field": "credit",
                        "error_type": "NEGATIVE_AMOUNT",
                        "message": f"Negative credit value detected: {credit_val}",
                        "value": str(raw_credit)
                    })
            except ValueError:
                row_errors.append({
                    "row": row_num,
                    "field": "credit",
                    "error_type": "INVALID_NUMERIC",
                    "message": f"Non-numeric credit amount: '{raw_credit}'",
                    "value": str(raw_credit)
                })

        if raw_amount is not None and str(raw_amount).strip() != "":
            try:
                amount_val = float(str(raw_amount).replace(",", "").strip())
            except ValueError:
                row_errors.append({
                    "row": row_num,
                    "field": "amount",
                    "error_type": "INVALID_NUMERIC",
                    "message": f"Non-numeric total amount: '{raw_amount}'",
                    "value": str(raw_amount)
                })

        # 4. Debit/Credit Conflict
        if debit_val > 0 and credit_val > 0:
            row_warnings.append({
                "row": row_num,
                "field": "debit/credit",
                "error_type": "DEBIT_CREDIT_CONFLICT",
                "message": f"Both Debit (₹{debit_val:,.2f}) and Credit (₹{credit_val:,.2f}) are populated on a single transaction line.",
                "value": f"Dr:{debit_val}, Cr:{credit_val}"
            })

        # 5. GSTIN Format Validation
        raw_gstin = mapped_data.get("gstin")
        if raw_gstin is not None and str(raw_gstin).strip() != "":
            clean_gstin = str(raw_gstin).strip().upper()
            if not re.match(GSTIN_REGEX, clean_gstin):
                row_warnings.append({
                    "row": row_num,
                    "field": "gstin",
                    "error_type": "INVALID_GSTIN_FORMAT",
                    "message": f"Invalid statutory GSTIN format: '{raw_gstin}'",
                    "value": str(raw_gstin)
                })

        # 6. Invoice Number Validation
        raw_inv = mapped_data.get("invoice_no")
        inv_str = str(raw_inv).strip() if raw_inv is not None else ""
        if data_category in ["Sales Register", "Purchase Register", "GST-related data"]:
            if not inv_str:
                row_warnings.append({
                    "row": row_num,
                    "field": "invoice_no",
                    "error_type": "MISSING_INVOICE_NO",
                    "message": f"Invoice number is missing for {data_category} entry.",
                    "value": ""
                })
            elif data_category == "Sales Register":
                if inv_str in seen_invoices:
                    row_warnings.append({
                        "row": row_num,
                        "field": "invoice_no",
                        "error_type": "DUPLICATE_INVOICE_NO",
                        "message": f"Duplicate invoice number '{inv_str}' identified in Sales Register.",
                        "value": inv_str
                    })
                else:
                    seen_invoices.add(inv_str)

        # 7. Duplicate Row Detection
        row_signature = (
            str(raw_date or "").strip(),
            str(mapped_data.get("voucher_no") or "").strip(),
            inv_str,
            str(mapped_data.get("ledger") or "").strip(),
            debit_val,
            credit_val,
            amount_val
        )
        if row_signature in seen_rows and any(x != "" and x != 0.0 for x in row_signature):
            row_warnings.append({
                "row": row_num,
                "field": "row",
                "error_type": "DUPLICATE_ROW",
                "message": "Duplicate row matching identical date, voucher/invoice, ledger, and monetary amounts.",
                "value": str(row_signature)
            })
        else:
            seen_rows.add(row_signature)

        # Record findings for this row
        if row_errors:
            failed_rows_count += 1
            errors.extend(row_errors)
        else:
            valid_rows_count += 1

        if row_warnings:
            warnings.extend(row_warnings)

    return {
        "total_rows": len(df),
        "valid_rows": valid_rows_count,
        "failed_rows": failed_rows_count,
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "error_summary": {
            "invalid_dates": sum(1 for e in errors if e["error_type"] == "INVALID_DATE"),
            "invalid_numeric": sum(1 for e in errors if e["error_type"] == "INVALID_NUMERIC"),
            "empty_heads": sum(1 for w in warnings if w["error_type"] == "EMPTY_REQUIRED_HEAD"),
            "debit_credit_conflicts": sum(1 for w in warnings if w["error_type"] == "DEBIT_CREDIT_CONFLICT"),
            "invalid_gstin": sum(1 for w in warnings if w["error_type"] == "INVALID_GSTIN_FORMAT"),
            "missing_invoices": sum(1 for w in warnings if w["error_type"] == "MISSING_INVOICE_NO"),
            "duplicate_invoices": sum(1 for w in warnings if w["error_type"] == "DUPLICATE_INVOICE_NO"),
            "duplicate_rows": sum(1 for w in warnings if w["error_type"] == "DUPLICATE_ROW")
        }
    }

def import_and_save_transactions(
    engagement_id: int,
    file_id: int,
    file_path: str,
    file_type: str,
    mapping: Dict[str, str],
    data_category: str = "General Ledger"
) -> Dict[str, Any]:
    """
    Imports full data file, applies mapped columns, validates, persists original values into
    transactions, updates ledger balances, and creates an audit import log.
    """
    df = parse_raw_dataframe(file_path, file_type)
    df.columns = [str(c).strip() for c in df.columns]

    # Run full pre-import validation
    val_report = validate_imported_dataframe(df, mapping, data_category)

    conn = get_db_connection()
    cursor = conn.cursor()

    imported_count = 0
    failed_count = 0
    ledger_totals = {}

    from backend.app.services.data_normalizer import normalize_row_data

    now_ts = datetime.now().isoformat()

    for idx, row in df.iterrows():
        row_num = idx + 1
        original_dict = {}

        # Preserve complete untouched raw input values for this row
        for col_name in df.columns:
            v = row[col_name]
            original_dict[col_name] = None if pd.isna(v) else v

        # Execute deterministic normalization engine
        norm_tx, row_logs = normalize_row_data(original_dict, mapping, row_num=row_num)

        ledger_name = norm_tx.get("ledger") or norm_tx.get("party_name") or "General Ledger"
        debit = norm_tx.get("debit", 0.0)
        credit = norm_tx.get("credit", 0.0)
        amount = norm_tx.get("amount", max(debit, credit))
        tax_amount = norm_tx.get("tax_amount", 0.0)
        account_group = norm_tx.get("account_group") or ("Expense" if debit > 0 else "Revenue")
        standard_date = norm_tx.get("date") or datetime.now().strftime("%Y-%m-%d")

        cursor.execute("""
        INSERT INTO transactions (
            engagement_id, file_id, date, voucher_no, invoice_no, ledger,
            account_group, description, debit, credit, amount, tax_amount, party_name,
            gstin, invoice_date, payment_date, reference_no, bank_ref,
            opening_balance, closing_balance, transaction_type, original_row_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            engagement_id,
            file_id,
            standard_date,
            str(norm_tx.get("voucher_no") or ""),
            str(norm_tx.get("invoice_no") or ""),
            ledger_name,
            account_group,
            str(norm_tx.get("description") or ""),
            debit,
            credit,
            amount,
            tax_amount,
            str(norm_tx.get("party_name") or ""),
            str(norm_tx.get("gstin") or ""),
            str(norm_tx.get("invoice_date") or standard_date),
            str(norm_tx.get("payment_date") or standard_date),
            str(norm_tx.get("reference_no") or ""),
            str(norm_tx.get("bank_ref") or ""),
            float(norm_tx.get("opening_balance") or 0.0),
            float(norm_tx.get("closing_balance") or 0.0),
            str(norm_tx.get("transaction_type") or data_category),
            json.dumps(original_dict, default=str)
        ))
        new_tx_id = cursor.lastrowid
        imported_count += 1

        # Insert transformation logs into data_cleaning_logs
        for log in row_logs:
            cursor.execute("""
            INSERT INTO data_cleaning_logs (
                engagement_id, file_id, transaction_id, row_number, field_name,
                original_value, normalized_value, transformation_rule,
                is_questionable, confidence_score, review_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Auto-Applied', ?)
            """, (
                engagement_id,
                file_id,
                new_tx_id,
                log["row_number"],
                log["field_name"],
                log["original_value"],
                log["normalized_value"],
                log["transformation_rule"],
                log["is_questionable"],
                log["confidence_score"],
                now_ts
            ))

        # Track ledger aggregates
        if ledger_name not in ledger_totals:
            ledger_totals[ledger_name] = {
                "group": account_group,
                "debit": 0.0,
                "credit": 0.0,
                "op": float(norm_tx.get("opening_balance") or 0.0),
                "cl": float(norm_tx.get("closing_balance") or 0.0)
            }
        ledger_totals[ledger_name]["debit"] += debit
        ledger_totals[ledger_name]["credit"] += credit

    # Update or insert into ledgers summary table
    for l_name, l_data in ledger_totals.items():
        closing = l_data["op"] + l_data["debit"] - l_data["credit"]
        cursor.execute("""
        INSERT INTO ledgers (
            engagement_id, ledger_name, account_group, opening_balance,
            total_debit, total_credit, closing_balance
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(engagement_id, ledger_name) DO UPDATE SET
            total_debit = total_debit + excluded.total_debit,
            total_credit = total_credit + excluded.total_credit,
            closing_balance = closing_balance + excluded.total_debit - excluded.total_credit
        """, (
            engagement_id,
            l_name,
            l_data["group"],
            l_data["op"],
            round(l_data["debit"], 2),
            round(l_data["credit"], 2),
            round(closing, 2)
        ))

    # Update uploaded_files record with complete audit import metadata
    all_err_json = json.dumps({
        "errors": val_report["errors"],
        "warnings": val_report["warnings"],
        "error_summary": val_report["error_summary"]
    }, default=str)

    cursor.execute("""
    UPDATE uploaded_files SET
        row_count = ?,
        successful_rows = ?,
        failed_rows = ?,
        warning_count = ?,
        data_category = ?,
        mapping_json = ?,
        errors_json = ?
    WHERE id = ?
    """, (
        len(df),
        imported_count,
        val_report["failed_rows"],
        val_report["warning_count"],
        data_category,
        json.dumps(mapping),
        all_err_json,
        file_id
    ))

    conn.commit()
    conn.close()

    rows_rejected = val_report["failed_rows"]
    data_quality_warning = (rows_rejected > 0) or (val_report["warning_count"] > 0)

    return {
        "rows_received": len(df),
        "rows_imported": imported_count,
        "rows_rejected": rows_rejected,
        "data_quality_warning": data_quality_warning,
        "imported_rows": imported_count,
        "total_rows": len(df),
        "failed_rows": rows_rejected,
        "warning_count": val_report["warning_count"],
        "validation_report": val_report
    }

def generate_error_report_csv(errors_data: List[Dict[str, Any]]) -> str:
    """Formats validation errors into a clean, downloadable CSV report for auditors."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Row Number", "Field", "Issue Type", "Error Description", "Supplied Value"])
    for item in errors_data:
        writer.writerow([
            item.get("row", ""),
            item.get("field", ""),
            item.get("error_type", ""),
            item.get("message", ""),
            item.get("value", "")
        ])
    return output.getvalue()
