# FinAuditPro — Offline AI Setup (LM Studio)

FinAuditPro is engineered to run in **air-gapped, offline environments**. No financial data, client names, PANs, GSTINs, or transaction amounts are ever transmitted to external cloud APIs.

---

## 1. Local AI Architecture

```
FinAuditPro Web UI / Backend
           │
           ▼
[Privacy Shield & Data Sanitizer]
(Automatic redaction of PAN, GSTIN, Bank A/C, Client Name, PII)
           │
           ▼
[Local AI Model Manager (LM Studio OpenAI-Compatible API)]
   ├── 1. LM Studio Local Server (http://localhost:1234)
   └── 2. Built-in Deterministic NLP Engine (Offline Fallback)
```

---

## 2. LM Studio Local Inference Setup

### Step 1: Install LM Studio
Download and install LM Studio from [https://lmstudio.ai](https://lmstudio.ai) (Windows / macOS / Linux).

### Step 2: Download a Compatible Local Model
Inside LM Studio:
- Search for and download **`Meta-Llama-3-8B-Instruct-GGUF`** (Q4_K_M) or **`Mistral-7B-Instruct-v0.3-GGUF`**.
- For low-spec hardware (4 GB RAM), download **`Phi-3.5-mini-instruct-GGUF`**.

### Step 3: Start the Local Server in LM Studio
1. Open the **Local Server (↔️)** tab in LM Studio.
2. Select your downloaded model from the top dropdown to load it into memory.
3. Ensure port is set to `1234`.
4. Click **Start Server**.

### Step 4: Configure FinAuditPro
1. In FinAuditPro, open the **Offline AI Manager** screen.
2. Verify Server URL: `http://localhost:1234`.
3. Click **🔄 Refresh Models** to automatically detect the loaded model.
4. Click **Test Connection** & **Test AI Generation**.
5. Click **Save Settings**.

---

## 3. Privacy & Security Safeguards

1. **Strict Localhost Binding:** AI requests are restricted strictly to `http://localhost:1234` or `http://127.0.0.1:1234`.
2. **PII Sanitization:** The built-in regex scrubber masks sensitive entity tokens before passing text to the context window:
   - PAN: `[PAN_REDACTED]`
   - GSTIN: `[GSTIN_REDACTED]`
   - Bank Account: `[BANK_ACCT_REDACTED]`
   - Client Names: `[ENTITY_UNDER_AUDIT]`
3. **Graceful Fallback:** If LM Studio is not running, the application displays a clear notice while **100% of core auditing calculations, reconciliation, anomaly detection, working papers, and report generation continue without interruption**.
