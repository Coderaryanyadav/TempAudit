import re
from datetime import datetime
from typing import List, Dict, Any, Tuple

GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
PAN_REGEX = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"

class DeterministicAuditEngine:
    def __init__(self, transactions: List[Dict[str, Any]], financial_year: str = "2024-25"):
        self.transactions = transactions
        self.financial_year = financial_year
        self.findings = []

    def run_all_checks(self) -> List[Dict[str, Any]]:
        self.findings = []
        self.check_debit_credit_balance()
        self.check_duplicates()
        self.check_section_40a3_cash_payments()
        self.check_section_269st_cash_receipts()
        self.check_gstin_validity()
        self.check_date_inconsistencies()
        self.check_round_number_spikes()
        self.check_missing_essential_metadata()
        self.check_negative_balances()
        self.check_high_value_unusual_narrations()
        return self.findings

    def check_debit_credit_balance(self):
        """Rule: Trial Balance and Transaction Debit must equal Credit."""
        total_debit = sum(float(t.get('debit') or 0.0) for t in self.transactions)
        total_credit = sum(float(t.get('credit') or 0.0) for t in self.transactions)
        diff = round(abs(total_debit - total_credit), 2)

        if diff > 0.01:
            self.findings.append({
                "finding_code": "DET-001",
                "category": "Accounting Standard",
                "severity": "CRITICAL",
                "risk_score": 9.5,
                "title": "Trial Balance Mismatch: Total Debits != Total Credits",
                "description": f"The aggregate debits (₹{total_debit:,.2f}) and aggregate credits (₹{total_credit:,.2f}) do not balance, resulting in an unreconciled difference of ₹{diff:,.2f}.",
                "affected_records": [t.get('id') for t in self.transactions[:10]],
                "expected_value": f"Debits equal to Credits (Diff: ₹0.00)",
                "actual_value": f"Debits: ₹{total_debit:,.2f}, Credits: ₹{total_credit:,.2f}",
                "difference": f"₹{diff:,.2f}",
                "reason": "Double-entry accounting equation violation. Unposted journal entries, missing one-sided entries, or manual ledger tampering.",
                "evidence": {
                    "total_debit": total_debit,
                    "total_credit": total_credit,
                    "difference": diff,
                    "sample_records_count": len(self.transactions)
                },
                "rule_used": "Ind AS 1 / AS 1: Principle of Double-Entry Bookkeeping & Trial Balance Equality",
                "engine_type": "DETERMINISTIC",
                "ai_explanation": "In double-entry bookkeeping, every debit must have a corresponding credit. An imbalance of ₹" + f"{diff:,.2f}" + " indicates an incomplete ledger export, improper suspense account adjustment, or one-sided system corruption.",
                "recommended_action": "Verify suspense accounts, extract full trial balance with opening adjustments, and re-check manual Journal Vouchers."
            })

    def check_duplicates(self):
        """Rule: Exact and near-duplicate transactions."""
        seen_exact = {}
        for t in self.transactions:
            t_id = t.get('id')
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            date = str(t.get('date') or '').strip()
            party = str(t.get('party_name') or t.get('ledger') or '').strip().lower()
            inv = str(t.get('invoice_no') or t.get('voucher_no') or '').strip().lower()

            if amt > 0 and date and party:
                key = (date, amt, party, inv)
                if key in seen_exact:
                    prev_t = seen_exact[key]
                    self.findings.append({
                        "finding_code": "DET-DUP-01",
                        "category": "Exception",
                        "severity": "HIGH",
                        "risk_score": 8.0,
                        "title": f"Potential Duplicate Entry: ₹{amt:,.2f} for {party.title()}",
                        "description": f"Two or more transactions share identical Date ({date}), Party ({party.title()}), Amount (₹{amt:,.2f}), and Reference ({inv}).",
                        "affected_records": [prev_t.get('id'), t_id],
                        "expected_value": "Unique transaction per distinct economic event",
                        "actual_value": f"Duplicate entries found on {date}",
                        "difference": f"Duplicate amount: ₹{amt:,.2f}",
                        "reason": "Double booking of supplier invoice, repeated bank charge posting, or batch processing error.",
                        "evidence": {
                            "original_transaction_id": prev_t.get('id'),
                            "duplicate_transaction_id": t_id,
                            "voucher_original": prev_t.get('voucher_no'),
                            "voucher_duplicate": t.get('voucher_no'),
                            "amount": amt
                        },
                        "rule_used": "Deterministic Duplicate Key Hash Check (Date + Amount + Party + Invoice)",
                        "engine_type": "DETERMINISTIC",
                        "ai_explanation": "Identical entries recorded under the same voucher/invoice number create inflated expense or liability balances, leading to double payments or incorrect input tax credit claims.",
                        "recommended_action": "Inspect the original supporting invoice and bank statement to confirm whether this represents two genuine purchases or an unintentional double posting."
                    })
                else:
                    seen_exact[key] = t

    def check_section_40a3_cash_payments(self):
        """
        Rule: Income Tax Act Section 40A(3) - Cash payments exceeding ₹10,000 per person per day.
        Accounting Semantics:
        - When the pure cash asset ledger ('Cash in hand', 'Petty Cash', 'Cash Account') is debited,
          it represents cash being received (Receipt).
        - When an expense or vendor ledger is debited (or transaction is a Payment), it represents an expenditure/payment.
        """
        cash_keywords = ['cash', 'petty cash', 'cash in hand', 'bearer cheque']
        cash_by_party_day = {}

        for t in self.transactions:
            ledger = str(t.get('ledger') or '').strip().lower()
            desc = str(t.get('description') or '').strip().lower()
            tx_type = str(t.get('transaction_type') or '').strip().lower()
            voucher_type = str(t.get('voucher_type') or '').strip().lower()

            is_pure_cash_asset = ledger in ['cash', 'petty cash', 'cash in hand', 'cash account'] or ledger.startswith('cash in hand') or ledger.startswith('petty cash')
            is_cash_tx = is_pure_cash_asset or any(k in desc or k in tx_type or k in voucher_type or k in ledger for k in cash_keywords)

            debit = float(t.get('debit') or 0.0)
            credit = float(t.get('credit') or 0.0)
            raw_amt = float(t.get('amount') or 0.0)

            # Determine if this transaction is a payment / expenditure:
            # Case 1: Pure cash asset ledger credited -> cash outflow / payment
            # Case 2: Non-cash expense/vendor ledger debited with cash keyword in ledger/desc/type
            is_payment = False
            amount = 0.0

            if is_pure_cash_asset:
                if credit > 0:
                    is_payment = True
                    amount = credit
                elif 'payment' in tx_type or 'payment' in voucher_type or 'paid' in desc or 'expense' in desc or 'purchase' in desc:
                    is_payment = True
                    amount = raw_amt if raw_amt > 0 else (debit if debit > 0 else 0.0)
            else:
                # Ledger is expense, vendor, or nominal account (e.g. 'Freight (Cash)', 'Office Rent')
                if debit > 0 and ('receipt' not in tx_type and 'receipt' not in voucher_type and 'received' not in desc):
                    is_payment = True
                    amount = debit
                elif 'payment' in tx_type or 'payment' in voucher_type or 'paid' in desc or 'expense' in desc:
                    is_payment = True
                    amount = debit if debit > 0 else raw_amt

            # Pure receipts must never be classified as 40A(3) payments
            if 'receipt' in tx_type or 'receipt' in voucher_type or 'received' in desc:
                is_payment = False

            if is_cash_tx and is_payment and amount > 0:
                date = str(t.get('date') or '').split('T')[0]
                party = str(t.get('party_name') or '').strip()
                if not party or party.lower() in ['cash', 'cash account', 'cash in hand', 'petty cash']:
                    party = str(t.get('ledger') or 'Unknown Party').strip()
                    party = re.sub(r'\s*\(\s*cash\s*\)', '', party, flags=re.IGNORECASE).strip()

                key = (date, party)
                if key not in cash_by_party_day:
                    cash_by_party_day[key] = {"total": 0.0, "records": [], "vouchers": []}
                cash_by_party_day[key]["total"] += amount
                cash_by_party_day[key]["records"].append(t.get('id'))
                cash_by_party_day[key]["vouchers"].append(t.get('voucher_no'))

        for (date, party), data in cash_by_party_day.items():
            if data["total"] > 10000.0 and party.lower() not in ['cash', 'petty cash', 'bank', 'cash account', 'cash in hand']:
                self.findings.append({
                    "finding_code": "DET-TAX-40A3",
                    "category": "Statutory Compliance",
                    "severity": "CRITICAL" if data["total"] > 50000 else "HIGH",
                    "risk_score": 8.8,
                    "title": f"Section 40A(3) Breach: Aggregate Cash Payment of ₹{data['total']:,.2f} to {party}",
                    "description": f"Aggregate cash payments to '{party}' on {date} totaled ₹{data['total']:,.2f}, exceeding the statutory limit of ₹10,000 prescribed under Section 40A(3) of the Income Tax Act, 1961.",
                    "affected_records": data["records"],
                    "expected_value": "Payment via Account Payee Cheque / DD / ECS / prescribed electronic mode <= ₹10,000",
                    "actual_value": f"Total Cash Paid: ₹{data['total']:,.2f}",
                    "difference": f"Excess over limit: ₹{data['total'] - 10000:,.2f}",
                    "reason": "Direct cash disallowance under Section 40A(3) will result in 100% add-back of this expenditure to taxable business income in Form 3CD (Clause 21(d)).",
                    "evidence": {
                        "date": date,
                        "party": party,
                        "vouchers": data["vouchers"],
                        "total_cash": data["total"],
                        "records_count": len(data["records"])
                    },
                    "rule_used": "Income Tax Act, 1961 - Section 40A(3) read with Rule 6DD",
                    "engine_type": "DETERMINISTIC",
                    "ai_explanation": "Under Section 40A(3), where an assessee incurs any expenditure in respect of which a payment or aggregate of payments made to a person in a day exceeds ₹10,000 otherwise than by an account payee cheque or electronic clearing system, no deduction shall be allowed. This must be reported under Clause 21(d) of Tax Audit Report Form 3CD.",
                    "recommended_action": "Check whether the payment falls under any exemption listed under Rule 6DD (e.g. payments to cultivators, cottage industry, banking holidays). If not exempt, classify for 3CD tax audit disallowance."
                })

    def check_section_269st_cash_receipts(self):
        """
        Rule: Income Tax Act Section 269ST - Cash receipts of ₹2,00,000 or more:
        (a) In aggregate from a person in a day; or
        (b) In respect of a single transaction; or
        (c) In respect of transactions relating to one event or occasion from a person.
        Penalty under Section 271DA equals 100% of sum received.
        """
        # -------------------------------------------------------------------------
        # Section 269ST Aggregation Categories:
        # (a) in aggregate from a person in a day;
        # (b) in respect of a single transaction (e.g. against the same invoice/voucher reference);
        # (c) in respect of transactions relating to one event or occasion from a person (e.g. project, contract, event).
        # -------------------------------------------------------------------------
        receipts_by_person_day: Dict[Tuple[str, str], Dict[str, Any]] = {}
        receipts_by_ref_trans: Dict[Tuple[str, str], Dict[str, Any]] = {}
        cash_keywords = ['cash', 'petty cash', 'cash in hand']

        for t in self.transactions:
            credit = float(t.get('credit') or 0.0)
            debit = float(t.get('debit') or 0.0)
            raw_amt = float(t.get('amount') or 0.0)
            ledger = str(t.get('ledger') or '').strip().lower()
            desc = str(t.get('description') or '').strip().lower()
            tx_type = str(t.get('transaction_type') or '').strip().lower()
            voucher_type = str(t.get('voucher_type') or '').strip().lower()

            is_pure_cash_asset = ledger in ['cash', 'petty cash', 'cash in hand', 'cash account'] or ledger.startswith('cash in hand') or ledger.startswith('petty cash')
            is_cash_tx = is_pure_cash_asset or any(k in desc or k in tx_type or k in voucher_type or k in ledger for k in cash_keywords)

            # Determine whether this is a cash receipt:
            is_receipt = False
            amount = 0.0

            if is_pure_cash_asset:
                if debit > 0:
                    is_receipt = True
                    amount = debit
                elif 'receipt' in tx_type or 'receipt' in voucher_type or 'received' in desc:
                    is_receipt = True
                    amount = raw_amt if raw_amt > 0 else (credit if credit > 0 else 0.0)
            else:
                if credit > 0 and ('payment' not in tx_type and 'payment' not in voucher_type and 'expense' not in desc and 'purchase' not in desc):
                    is_receipt = True
                    amount = credit
                elif 'receipt' in tx_type or 'receipt' in voucher_type or 'received' in desc:
                    is_receipt = True
                    amount = credit if credit > 0 else raw_amt

            # Pure payments must never be classified as receipts
            if 'payment' in tx_type or 'payment' in voucher_type or 'paid' in desc:
                is_receipt = False

            if not is_cash_tx or not is_receipt or amount <= 0:
                continue

            date = str(t.get('date') or '').split('T')[0]
            party = str(t.get('party_name') or '').strip()
            if not party or party.lower() in ['cash', 'cash account', 'cash in hand', 'petty cash']:
                party = str(t.get('ledger') or 'Unknown Counterparty').strip()
                party = re.sub(r'\s*\(\s*cash\s*\)', '', party, flags=re.IGNORECASE).strip()

            vch = str(t.get('voucher_no') or t.get('id') or '—')
            rec_id = t.get('id')

            # Reference identification for single transaction / event across dates
            inv_ref = str(t.get('invoice_no') or t.get('reference_no') or '').strip()
            if not inv_ref:
                # Check description for invoice / contract / bill / receipt / order / event reference pattern
                match_ref = re.search(r'\b(?:INV|BILL|CONTR|EVENT|ORD|REF|ADV|REC|BOOKING)[-:\s#]*([A-Za-z0-9_-]+)\b', desc, re.IGNORECASE)
                if match_ref:
                    inv_ref = match_ref.group(0).upper().replace(" ", "")
                elif any(k in desc.lower() for k in ['booking', 'flat', 'plot', 'wedding', 'event', 'catering', 'annual function', 'conference', 'advance']):
                    # Event/occasion or ongoing transaction cluster detected in narration
                    for keyword in ['wedding', 'catering', 'conference', 'annual function', 'flat', 'plot', 'booking', 'advance']:
                        if keyword in desc.lower():
                            inv_ref = f"EVENT-{keyword.upper().replace(' ', '_')}"
                            break

            # 1. Aggregate by person and day (Section 269ST(a))
            day_key = (party, date)
            if day_key not in receipts_by_person_day:
                receipts_by_person_day[day_key] = {
                    "party": party,
                    "date": date,
                    "total_amount": 0.0,
                    "records": [],
                    "vouchers": []
                }
            receipts_by_person_day[day_key]["total_amount"] += amount
            receipts_by_person_day[day_key]["records"].append(rec_id)
            receipts_by_person_day[day_key]["vouchers"].append(vch)

            # 2. Aggregate by person and transaction/event across different dates (Section 269ST(b) & (c))
            if inv_ref:
                ref_key = (party, inv_ref)
                if ref_key not in receipts_by_ref_trans:
                    receipts_by_ref_trans[ref_key] = {
                        "party": party,
                        "ref": inv_ref,
                        "dates": set(),
                        "total_amount": 0.0,
                        "records": [],
                        "vouchers": []
                    }
                receipts_by_ref_trans[ref_key]["total_amount"] += amount
                receipts_by_ref_trans[ref_key]["records"].append(rec_id)
                receipts_by_ref_trans[ref_key]["vouchers"].append(vch)
                receipts_by_ref_trans[ref_key]["dates"].add(date)

        emitted_record_sets: List[set] = []

        # Evaluate condition (a): Person and Day
        for (party, date), data in receipts_by_person_day.items():
            tot = data["total_amount"]
            if tot >= 200000.0 and party.lower() not in ['cash', 'cash account', 'cash in hand', 'bank']:
                vch_list = data["vouchers"]
                rec_list = data["records"]
                rec_set = set(rec_list)
                emitted_record_sets.append(rec_set)
                is_split = len(rec_list) > 1
                split_note = f" (aggregated across {len(rec_list)} split receipts on {date})" if is_split else ""

                self.findings.append({
                    "finding_code": "DET-TAX-269ST",
                    "category": "Statutory Compliance",
                    "severity": "CRITICAL",
                    "risk_score": 9.5 if is_split else 9.2,
                    "title": f"Section 269ST Breach: Aggregate Cash Receipt of ₹{tot:,.2f} from {party}{split_note}",
                    "description": f"Aggregate cash receipts from '{party}' on {date} totaled ₹{tot:,.2f}{split_note}, violating Section 269ST(a) of the Income Tax Act, 1961 (threshold ₹2,00,000 per person per day).",
                    "affected_records": rec_list,
                    "expected_value": "Receipts >= ₹2,00,000 through banking channels / account payee modes",
                    "actual_value": f"Total Cash Received: ₹{tot:,.2f}",
                    "difference": f"₹{tot:,.2f}",
                    "reason": "Section 271DA levies an unavoidable penalty equal to 100% of the amount received in contravention of Section 269ST.",
                    "evidence": {
                        "date": date,
                        "party": party,
                        "vouchers": vch_list,
                        "amount": tot,
                        "split_receipts_count": len(rec_list),
                        "is_aggregated": is_split
                    },
                    "rule_used": "Income Tax Act, 1961 - Section 269ST & Penalty Section 271DA",
                    "engine_type": "DETERMINISTIC",
                    "ai_explanation": "Section 269ST prohibits receiving ₹2,00,000 or more in cash in aggregate from a person in a day, in respect of a single transaction, or relating to one event. A penalty equal to 100% of the sum received is leviable under Section 271DA.",
                    "recommended_action": "Seek immediate management explanation, inspect bank deposit slips, and document in working papers for reporting under Clause 31 of Tax Audit Report 3CD."
                })
        # Evaluate condition (b) & (c): Single Transaction or Event/Occasion across different dates
        for (party, ref), data in receipts_by_ref_trans.items():
            tot = data["total_amount"]
            rec_list = data["records"]
            rec_set = set(rec_list)
            
            # Avoid duplicate reporting if already completely covered by a single-day breach
            if any(rec_set.issubset(s) for s in emitted_record_sets):
                continue

            if tot >= 200000.0 and party.lower() not in ['cash', 'cash account', 'cash in hand', 'bank']:
                emitted_record_sets.append(rec_set)
                dates_str = ", ".join(sorted(data["dates"]))
                vch_list = data["vouchers"]

                self.findings.append({
                    "finding_code": "DET-TAX-269ST",
                    "category": "Statutory Compliance",
                    "severity": "CRITICAL",
                    "risk_score": 9.6,
                    "title": f"Section 269ST Breach: Aggregate Cash Receipt of ₹{tot:,.2f} for Transaction/Event '{ref}' across dates",
                    "description": f"Aggregate cash receipts from '{party}' relating to single transaction/event reference '{ref}' across dates ({dates_str}) totaled ₹{tot:,.2f}, violating Section 269ST(b)/(c) of the Income Tax Act, 1961 (threshold ₹2,00,000).",
                    "affected_records": rec_list,
                    "expected_value": "Receipts >= ₹2,00,000 through banking channels / account payee modes",
                    "actual_value": f"Total Cash Received: ₹{tot:,.2f}",
                    "difference": f"₹{tot:,.2f}",
                    "reason": "Section 271DA levies an unavoidable penalty equal to 100% of the amount received in contravention of Section 269ST (applies to receipts relating to a single transaction or event across multiple dates).",
                    "evidence": {
                        "party": party,
                        "reference": ref,
                        "dates": list(data["dates"]),
                        "vouchers": vch_list,
                        "amount": tot,
                        "split_receipts_count": len(rec_list),
                        "is_aggregated_across_dates": True
                    },
                    "rule_used": "Income Tax Act, 1961 - Section 269ST(b)/(c) & Penalty Section 271DA",
                    "engine_type": "DETERMINISTIC",
                    "ai_explanation": "Section 269ST(b) and (c) prohibit receiving ₹2,00,000 or more in cash in respect of a single transaction or relating to one event/occasion from a person, even if split across different dates. A penalty equal to 100% of the sum received is leviable under Section 271DA.",
                    "recommended_action": "Seek immediate management explanation, inspect related contract/invoice, and report under Clause 31 of Tax Audit Form 3CD."
                })

    def check_gstin_validity(self):
        """Rule: Validate 15-character GSTIN format on B2B invoices and taxable transactions."""
        for t in self.transactions:
            gstin = str(t.get('gstin') or '').strip()
            amount = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)

            if gstin:
                if not re.match(GSTIN_REGEX, gstin):
                    self.findings.append({
                        "finding_code": "DET-GST-001",
                        "category": "Statutory Compliance",
                        "severity": "HIGH",
                        "risk_score": 7.5,
                        "title": f"Invalid GSTIN Format: '{gstin}' on Transaction ₹{amount:,.2f}",
                        "description": f"The GSTIN '{gstin}' recorded for party '{t.get('party_name')}' does not comply with the standard 15-digit GST structure (2 State + 10 PAN + 1 Entity + 1 Z + 1 Check Digit).",
                        "affected_records": [t.get('id')],
                        "expected_value": "Valid 15-character alphanumeric GSTIN format",
                        "actual_value": gstin,
                        "difference": "Format Syntax Error",
                        "reason": "Invalid GSTIN will cause ITC disallowance during GSTR-2B/3B matching and portal validation failures.",
                        "evidence": {
                            "voucher": t.get('voucher_no'),
                            "party_name": t.get('party_name'),
                            "gstin_entered": gstin,
                            "amount": amount
                        },
                        "rule_used": "CGST Act 2017 - Section 22/25 & GSTIN Structuring Specification",
                        "engine_type": "DETERMINISTIC",
                        "ai_explanation": "Every valid Indian GSTIN consists of 15 alphanumeric characters. An invalid GSTIN implies either a clerical data entry error or an unregistered entity masquerading as a registered supplier, risking loss of Input Tax Credit.",
                        "recommended_action": "Obtain copy of supplier's GST Registration Certificate or verify active status on the GST Portal search tool."
                    })

    def check_date_inconsistencies(self):
        """Rule: Payment date before invoice date or future dates."""
        for t in self.transactions:
            inv_date_str = t.get('invoice_date')
            pay_date_str = t.get('payment_date') or t.get('date')

            if inv_date_str and pay_date_str:
                try:
                    inv_d = datetime.strptime(str(inv_date_str).split('T')[0], "%Y-%m-%d")
                    pay_d = datetime.strptime(str(pay_date_str).split('T')[0], "%Y-%m-%d")
                    if pay_d < inv_d:
                        self.findings.append({
                            "finding_code": "DET-DATE-001",
                            "category": "Exception",
                            "severity": "MEDIUM",
                            "risk_score": 6.5,
                            "title": f"Date Anomaly: Payment Date ({pay_date_str}) precedes Invoice Date ({inv_date_str})",
                            "description": f"Payment recorded on {pay_date_str} is chronologically earlier than the invoice creation date {inv_date_str} for party '{t.get('party_name')}'.",
                            "affected_records": [t.get('id')],
                            "expected_value": "Payment Date >= Invoice Date (or recorded as Advance)",
                            "actual_value": f"Invoice: {inv_date_str}, Payment: {pay_date_str}",
                            "difference": f"{(inv_d - pay_d).days} days prior",
                            "reason": "Incorrect backdating of payment voucher or lack of advance payment classification.",
                            "evidence": {
                                "voucher": t.get('voucher_no'),
                                "invoice_no": t.get('invoice_no'),
                                "invoice_date": inv_date_str,
                                "payment_date": pay_date_str
                            },
                            "rule_used": "Chronological Integrity & Accrual Principle Verification",
                            "engine_type": "DETERMINISTIC",
                            "ai_explanation": "A payment cannot extinguish an invoice liability before the invoice exists unless it is categorized as an 'Advance to Supplier' with appropriate GST reverse charge / tax deduction treatment.",
                            "recommended_action": "Verify if this was an advance payment or a typo in the voucher date."
                        })
                except Exception:
                    pass

    def check_round_number_spikes(self):
        """Rule: High-value round numbers (e.g. exactly ₹5,00,000, ₹10,00,000) on discretionary expense ledgers."""
        suspicious_groups = ['consultancy', 'legal', 'advertisement', 'miscellaneous', 'repairs', 'commission', 'donations']
        for t in self.transactions:
            ledger = str(t.get('ledger') or '').lower()
            amt = float(t.get('amount') or t.get('debit') or 0.0)

            if any(k in ledger for k in suspicious_groups) and amt >= 100000.0:
                if amt % 50000 == 0: # Exactly divisible by 50,000
                    self.findings.append({
                        "finding_code": "DET-ROUND-001",
                        "category": "Outlier / ML",
                        "severity": "MEDIUM",
                        "risk_score": 6.0,
                        "title": f"Unusual Round-Sum Expense: ₹{amt:,.2f} in '{t.get('ledger')}'",
                        "description": f"A perfectly round amount of ₹{amt:,.2f} posted to discretionary account '{t.get('ledger')}'.",
                        "affected_records": [t.get('id')],
                        "expected_value": "Itemized commercial invoice with exact tax / TDS deductions",
                        "actual_value": f"Exact round figure: ₹{amt:,.2f}",
                        "difference": "Round sum estimate indicator",
                        "reason": "Round-sum transactions in professional or miscellaneous fees often represent lump-sum provisions, unverified estimates, or non-arms-length payments.",
                        "evidence": {
                            "voucher": t.get('voucher_no'),
                            "party": t.get('party_name'),
                            "amount": amt,
                            "narration": t.get('description')
                        },
                        "rule_used": "Round Number Heuristic & Discretionary Expense Filter",
                        "engine_type": "DETERMINISTIC",
                        "ai_explanation": "Professional services, consultancy, and repairs typically carry GST (18%) and TDS (10% or 2% u/s 194J/194C), resulting in non-round net settlement amounts. A round figure warrants inspection of the underlying contract and tax deduction.",
                        "recommended_action": "Review contract/agreement, verify TDS deduction under Section 194J/194C, and check proof of service delivery."
                    })

    def check_missing_essential_metadata(self):
        """Rule: Missing voucher number or description on high value items."""
        for t in self.transactions:
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            voucher = str(t.get('voucher_no') or '').strip()
            desc = str(t.get('description') or '').strip()

            if amt > 50000.0 and (not voucher or not desc):
                self.findings.append({
                    "finding_code": "DET-META-001",
                    "category": "Missing Data",
                    "severity": "LOW",
                    "risk_score": 4.5,
                    "title": f"Missing Voucher/Narration on High-Value Entry (₹{amt:,.2f})",
                    "description": f"Transaction of ₹{amt:,.2f} in ledger '{t.get('ledger')}' lacks {'a Voucher Number' if not voucher else 'an audit Narration/Description'}.",
                    "affected_records": [t.get('id')],
                    "expected_value": "Mandatory Voucher Number and explanatory Narration",
                    "actual_value": f"Voucher: '{voucher or 'MISSING'}', Narration: '{desc or 'MISSING'}'",
                    "difference": "Missing mandatory audit trail field",
                    "reason": "Lack of adequate documentation and audit trail compliance under Companies (Accounts) Rules.",
                    "evidence": {
                        "date": t.get('date'),
                        "ledger": t.get('ledger'),
                        "amount": amt
                    },
                    "rule_used": "Companies Act 2013 - Section 128 (Books of Account & Audit Trail)",
                    "engine_type": "DETERMINISTIC",
                    "ai_explanation": "The Ministry of Corporate Affairs mandates that accounting software maintain an edit log and complete audit trail. Journal entries without proper voucher numbering or explanatory narration impair audit verification.",
                    "recommended_action": "Require client accounting team to update supporting voucher references and narrations."
                })

    def check_negative_balances(self):
        """Rule: Check for negative closing balance in Cash or Asset ledgers."""
        for t in self.transactions:
            cb = t.get('closing_balance')
            ledger = str(t.get('ledger') or '').lower()
            if cb is not None:
                cb_val = float(cb)
                if cb_val < -0.01 and ('cash' in ledger or 'bank' in ledger):
                    self.findings.append({
                        "finding_code": "DET-BAL-001",
                        "category": "Accounting Standard",
                        "severity": "HIGH",
                        "risk_score": 7.8,
                        "title": f"Negative Balance Detected in '{t.get('ledger')}': ₹{cb_val:,.2f}",
                        "description": f"Cash/Bank account cannot mathematically carry a negative balance without an approved bank overdraft / CC facility.",
                        "affected_records": [t.get('id')],
                        "expected_value": "Cash Balance >= ₹0.00",
                        "actual_value": f"Closing Balance: ₹{cb_val:,.2f}",
                        "difference": f"Negative ₹{abs(cb_val):,.2f}",
                        "reason": "Unrecorded cash receipts, backdated disbursements, or delayed deposit entry.",
                        "evidence": {
                            "date": t.get('date'),
                            "ledger": t.get('ledger'),
                            "closing_balance": cb_val
                        },
                        "rule_used": "Fundamental Accounting Principle - Asset Ledger Non-Negativity",
                        "engine_type": "DETERMINISTIC",
                        "ai_explanation": "Physical cash in hand cannot be negative. If this is a bank account, it must be reclassified under 'Current Liabilities - Bank Overdraft' on the Balance Sheet.",
                        "recommended_action": "Reconcile daily cash register and verify whether bank overdraft limit has been configured in the balance sheet grouping."
                    })

    def check_high_value_unusual_narrations(self):
        """Rule: Identify suspicious or vague keywords in high-value transactions."""
        vague_terms = ['adjustment', 'rectification', 'transfer', 'dummy', 'temp', 'misc', 'suspense', 'clearing', 'unknown']
        for t in self.transactions:
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            desc = str(t.get('description') or '').lower()
            if amt >= 100000.0:
                for term in vague_terms:
                    if term in desc:
                        self.findings.append({
                            "finding_code": "DET-NARR-001",
                            "category": "Exception",
                            "severity": "MEDIUM",
                            "risk_score": 6.8,
                            "title": f"High-Value Transaction with Vague Narration: '{term.upper()}' (₹{amt:,.2f})",
                            "description": f"Journal entry of ₹{amt:,.2f} contains non-descriptive term '{term}' in narration.",
                            "affected_records": [t.get('id')],
                            "expected_value": "Specific economic rationale and reference to underlying transaction document",
                            "actual_value": f"Narration: {t.get('description')}",
                            "difference": "Vague Narration",
                            "reason": "Vague narrations on large transfers often mask unapproved year-end adjustments or window dressing.",
                            "evidence": {
                                "date": t.get('date'),
                                "voucher": t.get('voucher_no'),
                                "ledger": t.get('ledger'),
                                "narration": t.get('description'),
                                "amount": amt
                            },
                            "rule_used": "Auditing Standard SA 240 - Auditor's Responsibilities Relating to Fraud in an Audit of Financial Statements",
                            "engine_type": "DETERMINISTIC",
                            "ai_explanation": "SA 240 requires auditors to test journal entries made at the end of a reporting period and entries with unusual descriptions or vague adjustments for management override of controls.",
                            "recommended_action": "Inspect approval authority and underlying documentary justification for this manual entry."
                        })
                        break
