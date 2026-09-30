# FinAuditPro - REST API Specification

All endpoints are hosted at `http://127.0.0.1:8000/api`. Interactive OpenAPI / Swagger UI documentation is available at `http://127.0.0.1:8000/docs`.

---

## 1. Authentication (`/api/auth`)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Authenticate user, return JWT bearer token & role | No |
| `GET` | `/api/auth/me` | Fetch authenticated user profile and permissions | Yes |

---

## 2. Client & Engagement Management (`/api/clients`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/clients` | List all client profiles |
| `POST` | `/api/clients` | Create a new client entity |
| `GET` | `/api/clients/{id}` | Get client details |
| `PUT` | `/api/clients/{id}` | Update client information |
| `GET` | `/api/clients/{id}/engagements` | List engagements under a client |
| `POST` | `/api/clients/{id}/engagements` | Create a new audit engagement |
| `GET` | `/api/clients/engagements/{eng_id}` | Get engagement metadata |

---

## 3. Data Ingestion & Pre-Validation (`/api/import-export`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/import-export/upload-preview` | Upload `.xlsx`/`.csv`/`.json`/`.pdf` and inspect pre-validation anomalies |
| `POST` | `/api/import-export/apply-mapping` | Commit mapped transactions into engagement database |
| `GET` | `/api/import-export/download-error-report`| Download CSV validation error report for corrupted rows |
| `DELETE`| `/api/import-export/files/{file_id}` | Delete uploaded staging file |

---

## 4. Trial Balance & General Ledger (`/api/trial-balance`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/trial-balance/{engagement_id}` | Calculate debit/credit balance, suspense & abnormal balances |
| `GET` | `/api/trial-balance/{engagement_id}/gl-drilldown` | Filter ledger transactions by account name |
| `GET` | `/api/trial-balance/{engagement_id}/export-csv` | Download complete Trial Balance schedule |

---

## 5. Multi-Way Reconciliation (`/api/reconciliation`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/reconciliation/bank/reconcile` | Run Bank BRS matching algorithm (Exact & Fuzzy) |
| `GET` | `/api/reconciliation/bank/{engagement_id}` | Retrieve Bank BRS summary and unmatched items |
| `POST` | `/api/reconciliation/gst/reconcile` | Cross-match GSTR-2B ITC against Purchase Register |
| `GET` | `/api/reconciliation/gst/{engagement_id}` | Retrieve GST reconciliation summary |

---

## 6. Deterministic & Statistical Audit Rules (`/api/audit`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/audit/run-all/{engagement_id}` | Execute all statutory rules, Sec 40A(3), Sec 269ST & Benford's Law |
| `GET` | `/api/audit/rules/{engagement_id}` | List all flagged deterministic rule exceptions |
| `GET` | `/api/audit/benford/{engagement_id}` | Retrieve first-digit Benford's Law distribution analysis |
| `GET` | `/api/audit/isolation-forest/{engagement_id}`| Retrieve Isolation Forest ML outlier detections |

---

## 7. Findings & Risk Register (`/api/findings`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/findings/{engagement_id}` | Retrieve all findings filtered by severity, status, or module |
| `POST` | `/api/findings/{engagement_id}/sync` | Consolidate and sync exceptions across all modules |
| `PUT` | `/api/findings/{finding_id}/status` | Update finding status (`Open`, `In Progress`, `Resolved`, `Accepted Risk`) |
| `POST` | `/api/findings/{finding_id}/comment` | Add CA auditor comment or management representation |

---

## 8. Working Papers Module (`/api/working-papers`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/working-papers/{engagement_id}` | List all SA 230 audit working papers |
| `POST` | `/api/working-papers/{engagement_id}` | Create new working paper with reference code |
| `PUT` | `/api/working-papers/{wp_id}` | Update WP content, linked findings, txns, or checklists |
| `POST` | `/api/working-papers/{wp_id}/review` | Submit reviewer comment and transition review status |
| `POST` | `/api/working-papers/{wp_id}/upload` | Attach supporting document evidence |

---

## 9. Report Generation (`/api/reports`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/reports/types` | List 10 available PDF report templates |
| `POST` | `/api/reports/generate/{engagement_id}` | Generate deterministic PDF report |
| `GET` | `/api/reports/download/{filename}` | Download generated PDF report binary |

---

## 10. Audit Trail & Backups (`/api/audit-trail`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/audit-trail/logs` | Query tamper-resistant audit logs with search, user, and module filter |
| `GET` | `/api/audit-trail/backup/list` | List timestamped local database backups |
| `POST` | `/api/audit-trail/backup/create` | Create a new timestamped local backup snapshot |
| `POST` | `/api/audit-trail/backup/restore/{name}`| Restore database snapshot (Admin only) |

---

## 11. Local AI Model Manager (`/api/ai-manager`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/ai-manager/status` | Get LM Studio status, model name, RAM requirement, and latency |
| `GET` | `/api/ai-manager/models` | List loaded / available models in local LM Studio instance |
| `POST` | `/api/ai-manager/settings` | Update LM Studio endpoint, model name, temperature, context size |
| `POST` | `/api/ai-manager/test-connection`| Test connectivity with local LM Studio server at `http://localhost:1234` |
| `POST` | `/api/ai-manager/test-ai` | Send test verification prompt to LM Studio |
| `POST` | `/api/ai-manager/generate` | Generate privacy-sanitized local AI inference response |
| `POST` | `/api/ai-manager/sanitize-preview`| Preview PII redactor (PAN, GSTIN, Bank A/C redaction) |
