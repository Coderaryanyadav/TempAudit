"""
Test Data Generator Script
FinAuditPro - Test Data Architecture

Generates comprehensive, deterministic, mathematically coherent test datasets for:
1. Aryan Fintech Pvt. Ltd. (ARYAN)
2. Hitansh Fintech Pvt. Ltd. (HITANSH)
"""

import os
import json
import csv
from datetime import datetime, timedelta
import random

from test_data.companies import ARYAN_COMPANY, HITANSH_COMPANY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_directories():
    os.makedirs(os.path.join(BASE_DIR, "aryan_fintech"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "hitansh_fintech"), exist_ok=True)

def generate_datasets_for_company(company: dict):
    short_code = company["short_code"]
    c_dir = os.path.join(BASE_DIR, f"{short_code.lower()}_fintech")
    os.makedirs(c_dir, exist_ok=True)
    
    # Deterministic random seed per company
    rnd = random.Random(42 if short_code == "ARYAN" else 84)

    # 1. Company JSON
    with open(os.path.join(c_dir, "company.json"), "w", encoding="utf-8") as f:
        json.dump(company, f, indent=2)

    # 2. Clients CSV
    client_row = {
        "name": company["name"],
        "company_type": company["company_type"],
        "pan": company["pan"],
        "gstin": company["gstin"],
        "industry": company["industry"],
        "contact_person": company["primary_contact"],
        "email": company["email"],
        "phone": company["phone"],
        "address": company["address"]
    }
    with open(os.path.join(c_dir, "clients.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(client_row.keys()))
        writer.writeheader()
        writer.writerow(client_row)

    # Setup Vendors and Customers
    prefix = "AF" if short_code == "ARYAN" else "HF"
    customers = [
        {"name": f"{prefix} Enterprise Client {i}", "gstin": f"27AAAC{short_code[:2]}{1000+i}A1Z{i%9+1}", "state": "27"} for i in range(1, 15)
    ] + [
        {"name": f"{prefix} Inter-State Client {i}", "gstin": f"29BBBC{short_code[:2]}{2000+i}B1Z{i%9+1}", "state": "29"} for i in range(1, 10)
    ]
    
    suppliers = [
        {"name": f"{prefix} Cloud Infrastructure Provider {i}", "gstin": f"27AAAC{short_code[:2]}{3000+i}C1Z{i%9+1}", "state": "27"} for i in range(1, 12)
    ] + [
        {"name": f"{prefix} SaaS Tool Vendor {i}", "gstin": f"07DDDC{short_code[:2]}{4000+i}D1Z{i%9+1}", "state": "07"} for i in range(1, 10)
    ]

    # 3. Generate Transactions (1,050 Transactions per company)
    transactions = []
    base_date = datetime(2025, 4, 1)
    tx_id_counter = 1

    # (A) Capital Infusion (10 transactions)
    for i in range(1, 11):
        d_str = (base_date + timedelta(days=i*2)).strftime("%Y-%m-%d")
        amt = 2500000.0 if i <= 2 else 500000.0
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"BNK-CAP-{i:03d}",
            "invoice_no": f"CAP-{i:03d}",
            "ledger": company["bank_name"],
            "account_group": "Asset",
            "description": f"Share capital equity subscription tranche {i}",
            "debit": amt,
            "credit": 0.0,
            "amount": amt,
            "party_name": f"{company['primary_contact']} & Co-Founders",
            "party_gstin": "",
            "taxable_amount": 0.0,
            "tax_amount": 0.0,
            "gst_rate": 0.0,
            "cost_center": "Corporate",
            "reference": f"EQUITY-TR-{i}"
        })
        tx_id_counter += 1
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"JV-CAP-{i:03d}",
            "invoice_no": f"CAP-{i:03d}",
            "ledger": "Share Capital",
            "account_group": "Equity",
            "description": f"Allotment of equity shares tranche {i}",
            "debit": 0.0,
            "credit": amt,
            "amount": amt,
            "party_name": f"{company['primary_contact']} & Co-Founders",
            "party_gstin": "",
            "taxable_amount": 0.0,
            "tax_amount": 0.0,
            "gst_rate": 0.0,
            "cost_center": "Corporate",
            "reference": f"EQUITY-TR-{i}"
        })
        tx_id_counter += 1

    # (B) Term Loan Transactions (15 transactions)
    for i in range(1, 16):
        d_str = (base_date + timedelta(days=10 + i*15)).strftime("%Y-%m-%d")
        loan_amt = 1000000.0 if i == 1 else 200000.0
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"BNK-LN-{i:03d}",
            "invoice_no": f"LN-{i:03d}",
            "ledger": company["bank_name"],
            "account_group": "Asset",
            "description": f"Bank term loan drawdown / facility utilization {i}",
            "debit": loan_amt,
            "credit": 0.0,
            "amount": loan_amt,
            "party_name": company["bank_name"],
            "party_gstin": "",
            "taxable_amount": 0.0,
            "tax_amount": 0.0,
            "gst_rate": 0.0,
            "cost_center": "Treasury",
            "reference": f"LOAN-FAC-{i}"
        })
        tx_id_counter += 1
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"JV-LN-{i:03d}",
            "invoice_no": f"LN-{i:03d}",
            "ledger": "Long-Term Borrowings",
            "account_group": "Liability",
            "description": f"Secured term loan liability acknowledgment {i}",
            "debit": 0.0,
            "credit": loan_amt,
            "amount": loan_amt,
            "party_name": company["bank_name"],
            "party_gstin": "",
            "taxable_amount": 0.0,
            "tax_amount": 0.0,
            "gst_rate": 0.0,
            "cost_center": "Treasury",
            "reference": f"LOAN-FAC-{i}"
        })
        tx_id_counter += 1

    # (C) Fixed Assets (25 transactions)
    for i in range(1, 26):
        d_str = (base_date + timedelta(days=5 + i*12)).strftime("%Y-%m-%d")
        fa_amt = 75000.0 + (i * 12500.0)
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"FA-VCH-{i:03d}",
            "invoice_no": f"FA-INV-{i:03d}",
            "ledger": "Property, Plant & Equipment",
            "account_group": "Asset",
            "description": f"Procurement of high-performance developer workstations & servers {i}",
            "debit": fa_amt,
            "credit": 0.0,
            "amount": fa_amt,
            "party_name": f"{prefix} Hardware Systems Ltd",
            "party_gstin": f"27AAACH{7000+i}H1Z9",
            "taxable_amount": round(fa_amt / 1.18, 2),
            "tax_amount": round(fa_amt - (fa_amt / 1.18), 2),
            "gst_rate": 18.0,
            "cost_center": "Engineering",
            "reference": f"FA-PO-{i}"
        })
        tx_id_counter += 1

    # (D) Sales & Revenue Transactions (250 transactions)
    sales_invoices_data = []
    for i in range(1, 251):
        day_offset = int((i / 250.0) * 360)
        d = base_date + timedelta(days=day_offset)
        d_str = d.strftime("%Y-%m-%d")
        cust = customers[(i - 1) % len(customers)]
        taxable = 40000.0 + ((i * 1370.0) % 250000.0)
        taxable = round(taxable, 2)
        gst_rate = 18.0
        tax = round(taxable * 0.18, 2)
        total = round(taxable + tax, 2)
        
        is_intra = (cust["state"] == company["state_code"])
        cgst = round(tax / 2.0, 2) if is_intra else 0.0
        sgst = round(tax / 2.0, 2) if is_intra else 0.0
        igst = tax if not is_intra else 0.0

        inv_no = f"INV-{short_code}-{2025000 + i}"
        vch_no = f"SAL-{i:04d}"

        sales_invoices_data.append({
            "invoice_number": inv_no,
            "invoice_date": d_str,
            "customer": cust["name"],
            "customer_gstin": cust["gstin"],
            "place_of_supply": f"{cust['state']}-Maharashtra" if is_intra else f"{cust['state']}-Interstate",
            "taxable_value": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "total": total
        })

        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": vch_no,
            "invoice_no": inv_no,
            "ledger": "Sales Revenue",
            "account_group": "Revenue",
            "description": f"Fintech platform SaaS licensing & API processing service fees {i}",
            "debit": 0.0,
            "credit": total,
            "amount": total,
            "party_name": cust["name"],
            "party_gstin": cust["gstin"],
            "taxable_amount": taxable,
            "tax_amount": tax,
            "gst_rate": gst_rate,
            "cost_center": "Platform Revenue",
            "reference": f"ORD-{short_code}-{i}"
        })
        tx_id_counter += 1

    # (E) Purchase & Vendor Transactions (250 transactions)
    purchase_invoices_data = []
    for i in range(1, 251):
        day_offset = int((i / 250.0) * 360)
        d = base_date + timedelta(days=day_offset)
        d_str = d.strftime("%Y-%m-%d")
        supp = suppliers[(i - 1) % len(suppliers)]
        taxable = 25000.0 + ((i * 980.0) % 180000.0)
        taxable = round(taxable, 2)
        gst_rate = 18.0
        tax = round(taxable * 0.18, 2)
        total = round(taxable + tax, 2)

        is_intra = (supp["state"] == company["state_code"])
        cgst = round(tax / 2.0, 2) if is_intra else 0.0
        sgst = round(tax / 2.0, 2) if is_intra else 0.0
        igst = tax if not is_intra else 0.0

        inv_no = f"PUR-{short_code}-{50000 + i}"
        vch_no = f"PUR-{i:04d}"

        purchase_invoices_data.append({
            "supplier": supp["name"],
            "supplier_gstin": supp["gstin"],
            "invoice_number": inv_no,
            "invoice_date": d_str,
            "taxable_value": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "total": total
        })

        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": vch_no,
            "invoice_no": inv_no,
            "ledger": "Cloud & Infrastructure Cost",
            "account_group": "Expense",
            "description": f"Cloud compute bandwidth & database hosting tier {i}",
            "debit": total,
            "credit": 0.0,
            "amount": total,
            "party_name": supp["name"],
            "party_gstin": supp["gstin"],
            "taxable_amount": taxable,
            "tax_amount": tax,
            "gst_rate": gst_rate,
            "cost_center": "Infrastructure",
            "reference": f"BILL-{short_code}-{i}"
        })
        tx_id_counter += 1

    # (F) Payroll Transactions (60 transactions - 12 months x 5 departments)
    depts = ["Engineering", "Product", "Quality Assurance", "Finance & Legal", "Executive Management"]
    for m in range(1, 13):
        m_date = (datetime(2025, 4, 1) + timedelta(days=m*30 - 2)).strftime("%Y-%m-%d")
        for d_idx, dept in enumerate(depts):
            sal_amt = 350000.0 + (d_idx * 120000.0)
            transactions.append({
                "id": tx_id_counter,
                "date": m_date,
                "voucher_no": f"PAY-{m:02d}-{d_idx+1}",
                "invoice_no": f"SAL-M{m:02d}-{dept[:3].upper()}",
                "ledger": "Salaries & Wages",
                "account_group": "Expense",
                "description": f"Monthly salary disbursement for {dept} - Month {m}",
                "debit": sal_amt,
                "credit": 0.0,
                "amount": sal_amt,
                "party_name": f"{company['bank_name']} Corporate Salary A/c",
                "party_gstin": "",
                "taxable_amount": 0.0,
                "tax_amount": 0.0,
                "gst_rate": 0.0,
                "cost_center": dept,
                "reference": f"PAYROLL-M{m}"
            })
            tx_id_counter += 1

    # (G) Rent & Utilities (36 transactions - 12 months x 3 heads)
    for m in range(1, 13):
        m_date = (datetime(2025, 4, 1) + timedelta(days=m*30 - 25)).strftime("%Y-%m-%d")
        # Rent
        transactions.append({
            "id": tx_id_counter,
            "date": m_date,
            "voucher_no": f"RNT-M{m:02d}",
            "invoice_no": f"RENT-{m:02d}",
            "ledger": "Office Rent",
            "account_group": "Expense",
            "description": f"Corporate office lease rent for Month {m}",
            "debit": 175000.0,
            "credit": 0.0,
            "amount": 175000.0,
            "party_name": f"{prefix} Real Estate Properties LLP",
            "party_gstin": f"27AAAFR{5500+m}A1ZY",
            "taxable_amount": 148305.08,
            "tax_amount": 26694.92,
            "gst_rate": 18.0,
            "cost_center": "Administration",
            "reference": f"LEASE-M{m}"
        })
        tx_id_counter += 1
        # Utilities
        transactions.append({
            "id": tx_id_counter,
            "date": m_date,
            "voucher_no": f"UTL-M{m:02d}",
            "invoice_no": f"ELEC-{m:02d}",
            "ledger": "Electricity & Power",
            "account_group": "Expense",
            "description": f"Commercial electricity bill Month {m}",
            "debit": 32500.0,
            "credit": 0.0,
            "amount": 32500.0,
            "party_name": "Tata Power Mumbai",
            "party_gstin": "27AAACT2727Q1ZX",
            "taxable_amount": 32500.0,
            "tax_amount": 0.0,
            "gst_rate": 0.0,
            "cost_center": "Administration",
            "reference": f"ELEC-BILL-M{m}"
        })
        tx_id_counter += 1
        # Internet
        transactions.append({
            "id": tx_id_counter,
            "date": m_date,
            "voucher_no": f"INT-M{m:02d}",
            "invoice_no": f"NET-{m:02d}",
            "ledger": "Telephone & Internet",
            "account_group": "Expense",
            "description": f"High-speed dedicated leased line Month {m}",
            "debit": 18500.0,
            "credit": 0.0,
            "amount": 18500.0,
            "party_name": "Airtel Business Leased Lines",
            "party_gstin": "27AAACB2233Q1Z6",
            "taxable_amount": 15677.97,
            "tax_amount": 2822.03,
            "gst_rate": 18.0,
            "cost_center": "Administration",
            "reference": f"NET-M{m}"
        })
        tx_id_counter += 1

    # (H) Professional & Legal Fees (40 transactions)
    for i in range(1, 41):
        d_str = (base_date + timedelta(days=i*8)).strftime("%Y-%m-%d")
        prof_amt = 45000.0 + (i * 2500.0)
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"PRF-VCH-{i:03d}",
            "invoice_no": f"PRF-{i:03d}",
            "ledger": "Professional & Legal Fees",
            "account_group": "Expense",
            "description": f"Statutory compliance, legal advisory & secretarial fees {i}",
            "debit": prof_amt,
            "credit": 0.0,
            "amount": prof_amt,
            "party_name": f"{prefix} Legal & Compliance Advisors",
            "party_gstin": f"27AAACL{8100+i}F1Z3",
            "taxable_amount": round(prof_amt / 1.18, 2),
            "tax_amount": round(prof_amt - (prof_amt / 1.18), 2),
            "gst_rate": 18.0,
            "cost_center": "Legal",
            "reference": f"LEGAL-VCH-{i}"
        })
        tx_id_counter += 1

    # (I) Bank Charges & Interest (50 transactions)
    for i in range(1, 51):
        d_str = (base_date + timedelta(days=i*7)).strftime("%Y-%m-%d")
        b_amt = 1250.0 + (i * 350.0)
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"BNK-CHG-{i:03d}",
            "invoice_no": f"CHG-{i:03d}",
            "ledger": "Bank Interest & Finance Charges",
            "account_group": "Expense",
            "description": f"Payment gateway processing charge & NEFT/RTGS transaction fees {i}",
            "debit": b_amt,
            "credit": 0.0,
            "amount": b_amt,
            "party_name": company["bank_name"],
            "party_gstin": "",
            "taxable_amount": b_amt,
            "tax_amount": 0.0,
            "gst_rate": 0.0,
            "cost_center": "Treasury",
            "reference": f"CHG-REF-{i}"
        })
        tx_id_counter += 1

    # (J) Journal Adjustments & Depreciation (30 transactions)
    for i in range(1, 31):
        d_str = (base_date + timedelta(days=i*11)).strftime("%Y-%m-%d")
        dep_amt = 35000.0 + (i * 1000.0)
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"JV-DEP-{i:03d}",
            "invoice_no": f"DEP-{i:03d}",
            "ledger": "Depreciation Expense",
            "account_group": "Expense",
            "description": f"Systematic monthly depreciation amortization on IT hardware & servers {i}",
            "debit": dep_amt,
            "credit": 0.0,
            "amount": dep_amt,
            "party_name": "Accumulated Depreciation",
            "party_gstin": "",
            "taxable_amount": 0.0,
            "tax_amount": 0.0,
            "gst_rate": 0.0,
            "cost_center": "Engineering",
            "reference": f"DEP-SCH-{i}"
        })
        tx_id_counter += 1

    # (K) General & Miscellaneous Operations (300 transactions to reach 1,000+ total)
    for i in range(1, 301):
        day_offset = int((i / 300.0) * 360)
        d_str = (base_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        gen_amt = 5000.0 + ((i * 450.0) % 45000.0)
        is_travel = (i % 3 == 0)
        ledger_name = "Travel & Conveyance" if is_travel else "Office & Administrative Expenses"
        transactions.append({
            "id": tx_id_counter,
            "date": d_str,
            "voucher_no": f"GEN-VCH-{i:04d}",
            "invoice_no": f"GEN-{i:04d}",
            "ledger": ledger_name,
            "account_group": "Expense",
            "description": f"Client site visits, engineer logistics, and operational supplies {i}",
            "debit": gen_amt,
            "credit": 0.0,
            "amount": gen_amt,
            "party_name": f"{prefix} Business Services Vendor {i%15+1}",
            "party_gstin": f"27AAACB{9000+i%20}A1Z1",
            "taxable_amount": round(gen_amt / 1.18, 2),
            "tax_amount": round(gen_amt - (gen_amt / 1.18), 2),
            "gst_rate": 18.0,
            "cost_center": "Administration",
            "reference": f"OPS-REF-{i}"
        })
        tx_id_counter += 1

    # (L) Intentional Controlled Anomaly Injections (Phase 9)
    # 1. Cash Payment > 10,000 (Sec 40A(3))
    transactions.append({
        "id": tx_id_counter,
        "date": "2025-06-15",
        "voucher_no": f"CPV-{short_code}-01",
        "invoice_no": f"CASH-EXP-01",
        "ledger": "Freight & Cartage (Cash)",
        "account_group": "Expense",
        "description": "Urgent cash payment for inter-state consignment server delivery",
        "debit": 55000.0,
        "credit": 0.0,
        "amount": 55000.0,
        "party_name": "Express Logistics Cash Desk",
        "party_gstin": "",
        "taxable_amount": 55000.0,
        "tax_amount": 0.0,
        "gst_rate": 0.0,
        "cost_center": "Operations",
        "reference": "SEC-40A-FLAG"
    })
    tx_id_counter += 1

    # 2. Cash Receipt >= 2,00,000 (Sec 269ST)
    transactions.append({
        "id": tx_id_counter,
        "date": "2025-07-20",
        "voucher_no": f"CRV-{short_code}-01",
        "invoice_no": f"SCRAP-CASH-01",
        "ledger": "Scrap & Disposal Sales (Cash)",
        "account_group": "Revenue",
        "description": "Direct cash receipt for decommissioned server racks liquidation",
        "debit": 0.0,
        "credit": 275000.0,
        "amount": 275000.0,
        "party_name": "Metal Scrap Traders",
        "party_gstin": "",
        "taxable_amount": 275000.0,
        "tax_amount": 0.0,
        "gst_rate": 0.0,
        "cost_center": "Operations",
        "reference": "SEC-269ST-FLAG"
    })
    tx_id_counter += 1

    # 3. Duplicate Invoice Entry
    transactions.append({
        "id": tx_id_counter,
        "date": "2025-08-10",
        "voucher_no": f"DUP-VCH-{short_code}-1",
        "invoice_no": f"INV-DUP-{short_code}-99",
        "ledger": "IT Software & Cloud Services",
        "account_group": "Expense",
        "description": "Annual security penetration testing & threat monitoring retainership",
        "debit": 125000.0,
        "credit": 0.0,
        "amount": 125000.0,
        "party_name": f"{prefix} CyberSecurity Labs Ltd",
        "party_gstin": f"27AAACC{9988}A1Z5",
        "taxable_amount": 105932.20,
        "tax_amount": 19067.80,
        "gst_rate": 18.0,
        "cost_center": "Security",
        "reference": "DUP-REF-1"
    })
    tx_id_counter += 1
    transactions.append({
        "id": tx_id_counter,
        "date": "2025-08-10",
        "voucher_no": f"DUP-VCH-{short_code}-2",
        "invoice_no": f"INV-DUP-{short_code}-99",
        "ledger": "IT Software & Cloud Services",
        "account_group": "Expense",
        "description": "Annual security penetration testing & threat monitoring retainership (Duplicate)",
        "debit": 125000.0,
        "credit": 0.0,
        "amount": 125000.0,
        "party_name": f"{prefix} CyberSecurity Labs Ltd",
        "party_gstin": f"27AAACC{9988}A1Z5",
        "taxable_amount": 105932.20,
        "tax_amount": 19067.80,
        "gst_rate": 18.0,
        "cost_center": "Security",
        "reference": "DUP-REF-2"
    })
    tx_id_counter += 1

    # 4. Round Number Large Transaction
    transactions.append({
        "id": tx_id_counter,
        "date": "2025-09-14",
        "voucher_no": f"RND-VCH-{short_code}",
        "invoice_no": f"RND-{short_code}-01",
        "ledger": "Consultancy & Professional Fees",
        "account_group": "Expense",
        "description": "Lumpsum management consultancy fee",
        "debit": 500000.0,
        "credit": 0.0,
        "amount": 500000.0,
        "party_name": f"{prefix} Strategic Consulting Group",
        "party_gstin": f"27AAACP{5544}K1Z1",
        "taxable_amount": 423728.81,
        "tax_amount": 76271.19,
        "gst_rate": 18.0,
        "cost_center": "Executive",
        "reference": "ROUND-NUM-FLAG"
    })
    tx_id_counter += 1

    # 5. Weekend High-Value Posting (2025-10-19 was Sunday)
    transactions.append({
        "id": tx_id_counter,
        "date": "2025-10-19",
        "voucher_no": f"SUN-VCH-{short_code}",
        "invoice_no": f"ADV-SUN-{short_code}",
        "ledger": "Advertisement & Marketing",
        "account_group": "Expense",
        "description": "Sunday marketing media buy and billboard sponsorship",
        "debit": 210000.0,
        "credit": 0.0,
        "amount": 210000.0,
        "party_name": f"{prefix} Media Promotions LLP",
        "party_gstin": f"27AABCM{6622}J1ZK",
        "taxable_amount": 177966.10,
        "tax_amount": 32033.90,
        "gst_rate": 18.0,
        "cost_center": "Marketing",
        "reference": "WEEKEND-POSTING"
    })
    tx_id_counter += 1

    # Write Transactions CSV
    tx_headers = list(transactions[0].keys())
    with open(os.path.join(c_dir, "transactions.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=tx_headers)
        writer.writeheader()
        writer.writerows(transactions)

    # 4. Write Sales Register CSV (250 invoices)
    sales_headers = list(sales_invoices_data[0].keys())
    with open(os.path.join(c_dir, "sales_register.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sales_headers)
        writer.writeheader()
        writer.writerows(sales_invoices_data)

    # 5. Write Purchase Register CSV (250 invoices)
    purchase_headers = list(purchase_invoices_data[0].keys())
    with open(os.path.join(c_dir, "purchase_register.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=purchase_headers)
        writer.writeheader()
        writer.writerows(purchase_invoices_data)

    # 6. Generate Synthetic GST Portal Dataset (SOURCE = TEST_GST_PORTAL) (Phase 12)
    gst_portal_data = []
    for i, p_inv in enumerate(purchase_invoices_data[:200]):
        # Match types:
        # 1-150: Exact Match
        # 151-170: Slight tax difference (₹2 difference)
        # 171-180: Date disparity (shifted by 10 days)
        # 181-190: Missing in books / only in portal
        # 191-200: GSTIN mismatch
        tax_val = p_inv["cgst"] + p_inv["sgst"] + p_inv["igst"]
        if i < 150:
            # Exact
            gst_portal_data.append({
                "source": "TEST_GST_PORTAL",
                "supplier": p_inv["supplier"],
                "supplier_gstin": p_inv["supplier_gstin"],
                "invoice_number": p_inv["invoice_number"],
                "invoice_date": p_inv["invoice_date"],
                "taxable_value": p_inv["taxable_value"],
                "cgst": p_inv["cgst"],
                "sgst": p_inv["sgst"],
                "igst": p_inv["igst"],
                "total": p_inv["total"],
                "status": "Active"
            })
        elif i < 170:
            # Tax disparity
            gst_portal_data.append({
                "source": "TEST_GST_PORTAL",
                "supplier": p_inv["supplier"],
                "supplier_gstin": p_inv["supplier_gstin"],
                "invoice_number": p_inv["invoice_number"],
                "invoice_date": p_inv["invoice_date"],
                "taxable_value": p_inv["taxable_value"],
                "cgst": round(p_inv["cgst"] + 5.0, 2),
                "sgst": round(p_inv["sgst"] + 5.0, 2),
                "igst": p_inv["igst"],
                "total": round(p_inv["total"] + 10.0, 2),
                "status": "Active"
            })
        elif i < 180:
            # Date disparity
            d_obj = datetime.strptime(p_inv["invoice_date"], "%Y-%m-%d") + timedelta(days=12)
            gst_portal_data.append({
                "source": "TEST_GST_PORTAL",
                "supplier": p_inv["supplier"],
                "supplier_gstin": p_inv["supplier_gstin"],
                "invoice_number": p_inv["invoice_number"],
                "invoice_date": d_obj.strftime("%Y-%m-%d"),
                "taxable_value": p_inv["taxable_value"],
                "cgst": p_inv["cgst"],
                "sgst": p_inv["sgst"],
                "igst": p_inv["igst"],
                "total": p_inv["total"],
                "status": "Active"
            })
        elif i < 190:
            # Extra portal invoice
            gst_portal_data.append({
                "source": "TEST_GST_PORTAL",
                "supplier": f"{prefix} Unrecorded Cloud Vendor",
                "supplier_gstin": f"27AAACU{8800+i}P1Z2",
                "invoice_number": f"UNREC-GSTR2B-{i}",
                "invoice_date": p_inv["invoice_date"],
                "taxable_value": 75000.0,
                "cgst": 6750.0,
                "sgst": 6750.0,
                "igst": 0.0,
                "total": 88500.0,
                "status": "Active"
            })
        else:
            # GSTIN mismatch
            gst_portal_data.append({
                "source": "TEST_GST_PORTAL",
                "supplier": p_inv["supplier"],
                "supplier_gstin": f"27ZZZZZ{1111+i}Z1ZZ",
                "invoice_number": p_inv["invoice_number"],
                "invoice_date": p_inv["invoice_date"],
                "taxable_value": p_inv["taxable_value"],
                "cgst": p_inv["cgst"],
                "sgst": p_inv["sgst"],
                "igst": p_inv["igst"],
                "total": p_inv["total"],
                "status": "Active"
            })

    gst_headers = list(gst_portal_data[0].keys())
    with open(os.path.join(c_dir, "gst_portal.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=gst_headers)
        writer.writeheader()
        writer.writerows(gst_portal_data)

    # 7. Generate Bank Statement Transactions (200 records) (Phase 13)
    bank_statement_data = []
    # 100 Exact matches from sales/purchases
    for i, s_tx in enumerate(transactions[:100]):
        amt = s_tx["amount"]
        is_dep = (s_tx["debit"] > 0)
        bank_statement_data.append({
            "date": s_tx["date"],
            "voucher_no": s_tx["voucher_no"],
            "reference_no": s_tx["reference"],
            "description": f"NEFT / RTGS settlement - {s_tx['description']}",
            "party_name": s_tx["party_name"],
            "debit": 0.0 if is_dep else amt,
            "credit": amt if is_dep else 0.0,
            "amount": amt,
            "balance": 25000000.0 + (i * 10000.0)
        })
    # 25 Reference matches
    for i, s_tx in enumerate(transactions[100:125]):
        amt = s_tx["amount"]
        is_dep = (s_tx["debit"] > 0)
        bank_statement_data.append({
            "date": s_tx["date"],
            "voucher_no": f"REF-MATCH-{i}",
            "reference_no": s_tx["reference"],
            "description": f"Online payment ref {s_tx['reference']}",
            "party_name": s_tx["party_name"],
            "debit": 0.0 if is_dep else amt,
            "credit": amt if is_dep else 0.0,
            "amount": amt,
            "balance": 26000000.0
        })
    # 20 Date/Amount matches (shifted ref)
    for i, s_tx in enumerate(transactions[125:145]):
        amt = s_tx["amount"]
        is_dep = (s_tx["debit"] > 0)
        bank_statement_data.append({
            "date": s_tx["date"],
            "voucher_no": f"BNK-TXN-{i+500}",
            "reference_no": f"BNK-REF-{i+500}",
            "description": f"Direct clearing transaction {s_tx['party_name']}",
            "party_name": s_tx["party_name"],
            "debit": 0.0 if is_dep else amt,
            "credit": amt if is_dep else 0.0,
            "amount": amt,
            "balance": 26500000.0
        })
    # 10 Bank charges
    for i in range(1, 11):
        bank_statement_data.append({
            "date": f"2025-{i+3:02d}-28",
            "voucher_no": f"CHG-BNK-{i}",
            "reference_no": f"SYS-CHG-{i}",
            "description": "Monthly consolidated current account ledger maintenance fee",
            "party_name": company["bank_name"],
            "debit": 1500.0,
            "credit": 0.0,
            "amount": 1500.0,
            "balance": 26400000.0
        })
    # 10 Interest credits
    for i in range(1, 11):
        bank_statement_data.append({
            "date": f"2025-{i+3:02d}-30",
            "voucher_no": f"INT-BNK-{i}",
            "reference_no": f"AUTO-INT-{i}",
            "description": "Quarterly flexi-deposit auto sweep interest credit",
            "party_name": company["bank_name"],
            "debit": 0.0,
            "credit": 12500.0,
            "amount": 12500.0,
            "balance": 26450000.0
        })
    # 35 Additional items (outstanding cheques, deposits in transit, etc.)
    for i in range(1, 36):
        bank_statement_data.append({
            "date": f"2025-11-{i%28+1:02d}",
            "voucher_no": f"EXTRA-BNK-{i}",
            "reference_no": f"EXT-REF-{i}",
            "description": f"Direct bank credit entry {i}",
            "party_name": f"{prefix} Bank Partner {i%5+1}",
            "debit": 0.0,
            "credit": 25000.0,
            "amount": 25000.0,
            "balance": 27000000.0
        })

    bank_headers = list(bank_statement_data[0].keys())
    with open(os.path.join(c_dir, "bank_statement.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=bank_headers)
        writer.writeheader()
        writer.writerows(bank_statement_data)

    # 8. Generate Prior Year Baseline (FY 2024-25) Transactions (Phase 16)
    py_transactions = []
    py_base_date = datetime(2024, 4, 1)
    py_tx_counter = 1
    for i in range(1, 401):
        d_str = (py_base_date + timedelta(days=int((i/400.0)*360))).strftime("%Y-%m-%d")
        if i <= 200:
            # Sales
            amt = 35000.0 + ((i * 1100.0) % 180000.0)
            py_transactions.append({
                "id": py_tx_counter,
                "date": d_str,
                "voucher_no": f"PY-SAL-{i:04d}",
                "invoice_no": f"PY-INV-{i:04d}",
                "ledger": "Sales Revenue",
                "account_group": "Revenue",
                "description": f"FY 2024-25 SaaS platform revenue {i}",
                "debit": 0.0,
                "credit": amt,
                "amount": amt,
                "party_name": customers[i % len(customers)]["name"],
                "party_gstin": customers[i % len(customers)]["gstin"],
                "taxable_amount": round(amt / 1.18, 2),
                "tax_amount": round(amt - (amt / 1.18), 2),
                "gst_rate": 18.0,
                "cost_center": "Platform Revenue",
                "reference": f"PY-ORD-{i}"
            })
            py_tx_counter += 1
        else:
            # Purchases / Expenses
            amt = 20000.0 + ((i * 800.0) % 120000.0)
            py_transactions.append({
                "id": py_tx_counter,
                "date": d_str,
                "voucher_no": f"PY-PUR-{i:04d}",
                "invoice_no": f"PY-PUR-{i:04d}",
                "ledger": "Cloud & Infrastructure Cost",
                "account_group": "Expense",
                "description": f"FY 2024-25 Cloud server hosting fees {i}",
                "debit": amt,
                "credit": 0.0,
                "amount": amt,
                "party_name": suppliers[i % len(suppliers)]["name"],
                "party_gstin": suppliers[i % len(suppliers)]["gstin"],
                "taxable_amount": round(amt / 1.18, 2),
                "tax_amount": round(amt - (amt / 1.18), 2),
                "gst_rate": 18.0,
                "cost_center": "Infrastructure",
                "reference": f"PY-BILL-{i}"
            })
            py_tx_counter += 1

    py_headers = list(py_transactions[0].keys())
    with open(os.path.join(c_dir, "prior_year_transactions.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=py_headers)
        writer.writeheader()
        writer.writerows(py_transactions)

    # Validation: Assert Accounting Equations & Invariants
    tot_dr = sum(float(t.get("debit") or 0.0) for t in transactions)
    tot_cr = sum(float(t.get("credit") or 0.0) for t in transactions)
    assert abs(tot_dr - tot_cr) < 1.0, f"Accounting equation failed for {short_code} GL: Total Dr ({tot_dr}) != Total Cr ({tot_cr})"

    for s_inv in sales_invoices_data:
        t_amt = float(s_inv.get("taxable_amount") or 0.0)
        c_gst = float(s_inv.get("cgst") or 0.0)
        s_gst = float(s_inv.get("sgst") or 0.0)
        i_gst = float(s_inv.get("igst") or 0.0)
        inv_tot = float(s_inv.get("invoice_total") or 0.0)
        assert abs(inv_tot - (t_amt + c_gst + s_gst + i_gst)) < 0.05, f"Sales invoice {s_inv.get('invoice_no')} total mismatch: {inv_tot} vs {t_amt + c_gst + s_gst + i_gst}"

    for p_inv in purchase_invoices_data:
        t_amt = float(p_inv.get("taxable_amount") or 0.0)
        c_gst = float(p_inv.get("cgst") or 0.0)
        s_gst = float(p_inv.get("sgst") or 0.0)
        i_gst = float(p_inv.get("igst") or 0.0)
        inv_tot = float(p_inv.get("invoice_total") or 0.0)
        assert abs(inv_tot - (t_amt + c_gst + s_gst + i_gst)) < 0.05, f"Purchase invoice {p_inv.get('invoice_no')} total mismatch: {inv_tot} vs {t_amt + c_gst + s_gst + i_gst}"

    # 9. Expected Results JSON
    expected_results = {
        "company_code": short_code,
        "company_name": company["name"],
        "financial_year": company["financial_year"],
        "prior_financial_year": company["prior_financial_year"],
        "total_current_year_transactions": len(transactions),
        "total_prior_year_transactions": len(py_transactions),
        "total_sales_invoices": len(sales_invoices_data),
        "total_purchase_invoices": len(purchase_invoices_data),
        "total_gst_portal_invoices": len(gst_portal_data),
        "total_bank_statement_records": len(bank_statement_data),
        "expected_anomalies": {
            "sec_40a_cash_violations_count": 1,
            "sec_269st_cash_receipts_count": 1,
            "duplicate_invoices_count": 2,
            "round_number_transactions_count": 1,
            "weekend_transactions_count": 1
        },
        "expected_reconciliation": {
            "gst_matched_minimum": 140,
            "gst_discrepancies_minimum": 20,
            "brs_matched_minimum": 100
        }
    }
    with open(os.path.join(c_dir, "expected_results.json"), "w", encoding="utf-8") as f:
        json.dump(expected_results, f, indent=2)

    print(f"Generated and validated complete test dataset for {company['name']} in {c_dir}")

def run():
    create_directories()
    generate_datasets_for_company(ARYAN_COMPANY)
    generate_datasets_for_company(HITANSH_COMPANY)

if __name__ == "__main__":
    run()
