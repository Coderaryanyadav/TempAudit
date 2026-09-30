# FinAuditPro — Troubleshooting & Operational FAQ

## 1. Installation & Startup Issues

### Problem: `setup.bat` fails with "Python is not recognized"
- **Cause:** Python is not added to the Windows system `PATH`.
- **Solution:** 
  1. Re-run the Python 3.10/3.11/3.12 installer.
  2. Check the box **"Add Python to PATH"** on the first screen.
  3. Re-run `setup.bat`.

### Problem: Port 8000 already in use
- **Cause:** Another process or previous instance of FinAuditPro is occupying port 8000.
- **Solution:** 
  - Stop the running process using Task Manager or run in PowerShell:
    ```powershell
    Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
    ```
  - Or specify a custom port:
    ```bash
    uvicorn backend.app.main:app --host 127.0.0.1 --port 8080
    ```

---

## 2. LM Studio & AI Connectivity

### Problem: AI Settings shows "LM Studio is not connected"
- **Checklist:**
  1. Is LM Studio open?
  2. Is a model loaded into memory at the top of the **Local Server (↔️)** tab?
  3. Did you click **Start Server** inside LM Studio?
  4. Is the port configured as `1234`?
  5. Try opening `http://localhost:1234/v1/models` in your browser. It should return a JSON response with the loaded models.

### Problem: AI Assistant gives a generic response
- **Cause:** LM Studio local server is offline; FinAuditPro has fallen back to the built-in deterministic rule reasoner.
- **Solution:** Start the LM Studio server on port 1234, go to **Offline AI Manager** in FinAuditPro, click **Refresh Models**, and **Test Connection**.

---

## 3. Financial Data & Reconciliation

### Problem: Trial Balance shows a difference
- **Cause:** Imported ledger records have an imbalance between Total Debits and Total Credits ($Dr \neq Cr$).
- **Explanation:** This is a core audit feature! FinAuditPro calculates $Difference = Total\,Dr - Total\,Cr$ and generates a High-Severity Mathematical Imbalance Finding for auditor investigation.

### Problem: Uploaded Excel file fails validation
- **Cause:** Header row missing or unrecognized column names.
- **Solution:**
  - FinAuditPro includes an interactive column mapper on the **Data Import** screen.
  - Map your columns to `Date`, `Voucher No`, `Ledger`, `Account Group`, `Debit`, `Credit`, and `Party Name`.
  - Alternatively, refer to the sample template format in `backend/sample_files/apex_general_ledger_fy2425.xlsx`.

---

## 4. Resetting Database to Clean State

If you ever wish to purge all operational data and reset FinAuditPro to a fresh production state:
```bash
# Delete the local SQLite database
del backend\finauditpro.db

# Re-initialize clean database with initial admin user
python -m backend.app.database
```
*Your database is now fresh and ready for production client setup.*
