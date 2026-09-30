import numpy as np
import math
from datetime import datetime
from typing import List, Dict, Any
from sklearn.ensemble import IsolationForest

class StatisticalAuditEngine:
    def __init__(self, transactions: List[Dict[str, Any]]):
        self.transactions = transactions
        self.findings = []

    def run_all_checks(self) -> Dict[str, Any]:
        self.findings = []
        benford_res = self.analyze_benfords_law()
        ml_res = self.detect_isolation_forest_outliers()
        zscore_res = self.detect_ledger_zscore_anomalies()
        weekend_res = self.detect_weekend_spikes()

        return {
            "findings": self.findings,
            "benford_analysis": benford_res,
            "ml_summary": ml_res,
            "zscore_summary": zscore_res,
            "weekend_summary": weekend_res
        }

    def analyze_benfords_law(self) -> Dict[str, Any]:
        """Benford's Law Analysis on leading digits (1-9) of transaction amounts."""
        first_digits = []
        for t in self.transactions:
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            if amt >= 10.0:
                s = f"{amt:.2f}".lstrip('0.')
                if s and s[0].isdigit() and s[0] != '0':
                    first_digits.append(int(s[0]))

        total_count = len(first_digits)
        if total_count < 30: # Statistical sample requirement
            return {
                "conformity": "INSUFFICIENT_DATA",
                "sample_size": total_count,
                "mad": 0.0,
                "digit_distribution": {}
            }

        counts = {d: first_digits.count(d) for d in range(1, 10)}
        actual_dist = {d: counts[d] / total_count for d in range(1, 10)}
        expected_dist = {d: math.log10(1 + 1 / d) for d in range(1, 10)}

        mad = sum(abs(actual_dist[d] - expected_dist[d]) for d in range(1, 10)) / 9.0

        conformity = "Close Conformity"
        if mad > 0.015:
            conformity = "Non-Conformity (Suspicious Distribution)"
        elif mad > 0.012:
            conformity = "Marginally Acceptable"
        elif mad > 0.006:
            conformity = "Acceptable Conformity"

        digit_data = []
        for d in range(1, 10):
            digit_data.append({
                "digit": d,
                "count": counts[d],
                "actual_percent": round(actual_dist[d] * 100, 2),
                "expected_percent": round(expected_dist[d] * 100, 2),
                "difference_percent": round((actual_dist[d] - expected_dist[d]) * 100, 2)
            })

        if mad > 0.015:
            # Find the most anomalous digit
            max_dev_digit = max(range(1, 10), key=lambda d: abs(actual_dist[d] - expected_dist[d]))
            self.findings.append({
                "finding_code": "STAT-BENFORD-01",
                "category": "Outlier / ML",
                "severity": "HIGH",
                "risk_score": 7.6,
                "title": f"Benford's Law Non-Conformity (MAD: {mad:.4f}, Peak at Digit {max_dev_digit})",
                "description": f"The empirical leading digit distribution of {total_count} transactions deviates significantly from Benford's Law (Mean Absolute Deviation = {mad:.4f}). Digit {max_dev_digit} occurs at {actual_dist[max_dev_digit]*100:.1f}% vs theoretical {expected_dist[max_dev_digit]*100:.1f}%.",
                "affected_records": [t.get('id') for t in self.transactions if str(t.get('amount') or '').startswith(str(max_dev_digit))][:15],
                "expected_value": f"Theoretical Benford Digit 1-9 curve (MAD < 0.012)",
                "actual_value": f"Observed MAD: {mad:.4f} ({conformity})",
                "difference": f"MAD deviation +{(mad - 0.012):.4f}",
                "reason": "Anomalous concentration of transactions starting with specific digits often points to authorization limit thresholds (e.g. ₹4,999 or ₹9,990 to avoid manager sign-off) or synthetic number generation.",
                "evidence": {
                    "total_samples": total_count,
                    "mad_score": mad,
                    "anomalous_digit": max_dev_digit,
                    "distribution": digit_data
                },
                "rule_used": "Benford's Law First-Digit Analysis (Nigrini Forensic Accounting Standard)",
                "engine_type": "STATISTICAL_ML",
                "ai_explanation": "Naturally occurring accounting data follows a logarithmic first-digit frequency where digit 1 occurs ~30.1% of the time and digit 9 occurs ~4.6%. A significant deviation indicates either repetitive round figures, artificial invoice splitting to circumvent statutory limits, or human fabrication.",
                "recommended_action": "Filter transactions starting with the anomalous digit and examine if they represent invoice splitting below approval or TDS thresholds."
            })

        return {
            "conformity": conformity,
            "sample_size": total_count,
            "mad": round(mad, 4),
            "digit_distribution": digit_data
        }

    def detect_isolation_forest_outliers(self) -> Dict[str, Any]:
        """Multi-dimensional Isolation Forest machine learning anomaly detection."""
        if len(self.transactions) < 10:
            return {"status": "insufficient_data", "outliers_count": 0}

        features = []
        valid_indices = []

        for idx, t in enumerate(self.transactions):
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            debit = float(t.get('debit') or 0.0)
            credit = float(t.get('credit') or 0.0)

            day_of_week = 0
            day_of_month = 15
            date_str = str(t.get('date') or '').split('T')[0]
            if date_str:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    day_of_week = dt.weekday()
                    day_of_month = dt.day
                except Exception:
                    pass

            if amt > 0:
                features.append([np.log1p(amt), np.log1p(debit), np.log1p(credit), day_of_week, day_of_month])
                valid_indices.append(idx)

        if len(features) < 10:
            return {"status": "insufficient_data", "outliers_count": 0}

        X = np.array(features)
        # 5% expected contamination
        clf = IsolationForest(contamination=0.05, random_state=42)
        preds = clf.fit_predict(X)
        scores = clf.decision_function(X)

        outlier_records = []
        for i, pred in enumerate(preds):
            if pred == -1:
                orig_idx = valid_indices[i]
                t = self.transactions[orig_idx]
                anomaly_score = round(float(-scores[i]), 3)
                outlier_records.append({
                    "transaction": t,
                    "anomaly_score": anomaly_score
                })

        # Generate audit findings for top outliers
        outlier_records.sort(key=lambda x: x["anomaly_score"], reverse=True)
        for out in outlier_records[:5]:
            t = out["transaction"]
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            self.findings.append({
                "finding_code": "ML-ISO-01",
                "category": "Outlier / ML",
                "severity": "HIGH" if out["anomaly_score"] > 0.15 else "MEDIUM",
                "risk_score": min(9.0, round(5.0 + out["anomaly_score"] * 10, 1)),
                "title": f"Statistical Outlier (Isolation Forest): ₹{amt:,.2f} in '{t.get('ledger')}'",
                "description": f"Transaction of ₹{amt:,.2f} on {t.get('date')} exhibits unusual multi-variate characteristics (Amount, Timing, Ledger distribution) compared to the engagement baseline.",
                "affected_records": [t.get('id')],
                "expected_value": "Normal transaction clustering within 95% confidence region",
                "actual_value": f"Anomaly Score: {out['anomaly_score']}",
                "difference": f"Outlier Deviation Score: {out['anomaly_score']}",
                "reason": "Multivariate isolation tree isolated this observation with very few random partitions, signifying unusual amount/timing combinations.",
                "evidence": {
                    "voucher": t.get('voucher_no'),
                    "party": t.get('party_name'),
                    "ledger": t.get('ledger'),
                    "date": t.get('date'),
                    "amount": amt,
                    "anomaly_score": out["anomaly_score"]
                },
                "rule_used": "Unsupervised Machine Learning - Isolation Forest (Scikit-Learn)",
                "engine_type": "STATISTICAL_ML",
                "ai_explanation": "Isolation Forest constructs random decision trees. Anomalous transactions require significantly fewer splits to isolate from the general population, highlighting atypical operational spending.",
                "recommended_action": "Perform substantive audit testing on this voucher, verifying purchase order, delivery challan, and director/management authorization."
            })

        return {
            "status": "completed",
            "total_analyzed": len(features),
            "outliers_count": len(outlier_records),
            "top_outliers": outlier_records[:10]
        }

    def detect_ledger_zscore_anomalies(self) -> Dict[str, Any]:
        """Z-Score outlier detection grouped by Ledger account."""
        ledger_map = {}
        for t in self.transactions:
            ledger = t.get('ledger') or 'General'
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            if amt > 0:
                if ledger not in ledger_map:
                    ledger_map[ledger] = []
                ledger_map[ledger].append((amt, t))

        ledger_anomalies = []
        for ledger, items in ledger_map.items():
            if len(items) >= 6:
                amounts = [x[0] for x in items]
                mean = np.mean(amounts)
                std = np.std(amounts)

                if std > 0:
                    for amt, t in items:
                        z_score = (amt - mean) / std
                        if z_score > 3.0: # 3 standard deviations
                            ledger_anomalies.append({
                                "ledger": ledger,
                                "amount": amt,
                                "mean": round(mean, 2),
                                "std": round(std, 2),
                                "z_score": round(z_score, 2),
                                "transaction": t
                            })

        for anom in ledger_anomalies[:5]:
            t = anom["transaction"]
            self.findings.append({
                "finding_code": "STAT-ZSCORE-01",
                "category": "Outlier / ML",
                "severity": "MEDIUM",
                "risk_score": 6.8,
                "title": f"Z-Score Statistical Spike (Z={anom['z_score']}): ₹{anom['amount']:,.2f} in '{anom['ledger']}'",
                "description": f"Transaction amount ₹{anom['amount']:,.2f} is {anom['z_score']} standard deviations above the ledger mean (₹{anom['mean']:,.2f} ± ₹{anom['std']:,.2f}).",
                "affected_records": [t.get('id')],
                "expected_value": f"Ledger normal range (Mean: ₹{anom['mean']:,.2f})",
                "actual_value": f"Actual: ₹{anom['amount']:,.2f} (Z-Score: {anom['z_score']})",
                "difference": f"₹{anom['amount'] - anom['mean']:,.2f} above average",
                "reason": "Extreme variance from historical baseline indicates either an extraordinary one-off expense, capital expenditure misclassified as revenue, or recording error.",
                "evidence": {
                    "ledger": anom["ledger"],
                    "amount": anom["amount"],
                    "ledger_mean": anom["mean"],
                    "ledger_std": anom["std"],
                    "z_score": anom["z_score"],
                    "voucher": t.get("voucher_no")
                },
                "rule_used": "Statistical Z-Score Univariate Outlier Model (3-Sigma Rule)",
                "engine_type": "STATISTICAL_ML",
                "ai_explanation": "Under the 3-Sigma statistical rule, in a normal distribution fewer than 0.3% of observations fall beyond 3 standard deviations. Such large values warrant scrutiny to ensure capital items are not charged to revenue.",
                "recommended_action": "Check if this transaction represents capital expenditure (e.g., fixed asset addition) erroneously booked under operational expenses."
            })

        return {
            "total_ledger_groups": len(ledger_map),
            "anomalies_found": len(ledger_anomalies),
            "items": ledger_anomalies[:10]
        }

    def detect_weekend_spikes(self) -> Dict[str, Any]:
        """Detect unusually high volume or cash disbursements on Sundays."""
        sunday_transactions = []
        for t in self.transactions:
            date_str = str(t.get('date') or '').split('T')[0]
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            if date_str and amt > 25000.0:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if dt.weekday() == 6: # Sunday
                        sunday_transactions.append(t)
                except Exception:
                    pass

        if len(sunday_transactions) >= 2:
            self.findings.append({
                "finding_code": "STAT-WEEKEND-01",
                "category": "Outlier / ML",
                "severity": "LOW",
                "risk_score": 5.0,
                "title": f"High-Value Non-Business Day Transactions ({len(sunday_transactions)} Sunday entries)",
                "description": f"{len(sunday_transactions)} high-value transactions (> ₹25,000) were recorded on Sundays when commercial offices/banks are typically closed.",
                "affected_records": [t.get('id') for t in sunday_transactions],
                "expected_value": "Standard business day postings or scheduled electronic payroll/rent",
                "actual_value": f"{len(sunday_transactions)} transactions on non-working days",
                "difference": "Timing anomaly",
                "reason": "Posting entries on non-business days can indicate emergency adjustments or back-dated manual entries.",
                "evidence": {
                    "count": len(sunday_transactions),
                    "sample_vouchers": [t.get('voucher_no') for t in sunday_transactions[:5]]
                },
                "rule_used": "Calendar & Business-Hours Timing Anomaly Filter",
                "engine_type": "STATISTICAL_ML",
                "ai_explanation": "Auditing Standard SA 240 highlights transactions entered at unusual times or dates as potential indicators of management override of controls.",
                "recommended_action": "Verify electronic banking timestamp against voucher date to confirm actual transaction execution date."
            })

        return {
            "sunday_transactions_count": len(sunday_transactions)
        }
