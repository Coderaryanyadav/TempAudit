# LM Studio Local AI Integration Guide

FinAuditPro utilizes **LM Studio** as its local, offline AI inference engine. All communication is routed through LM Studio's local OpenAI-compatible API endpoint (`http://localhost:1234`). No cloud APIs (OpenAI, Gemini, Anthropic, Azure) are ever contacted.

---

## 1. Why LM Studio?

1. **100% Offline & Private:** Models run completely on your local CPU / GPU.
2. **Zero Cloud Leakage:** Financial data, PAN, GSTIN, bank accounts, and client details never leave your physical workstation.
3. **Pluggable & Model Agnostic:** Works with any open-source instruction-tuned model (e.g., Llama-3, Mistral, Qwen, Phi-3).

---

## 2. Step-by-Step Setup Instructions

### Step 1: Download & Install LM Studio
1. Visit [https://lmstudio.ai](https://lmstudio.ai).
2. Download the installer for Windows (or macOS / Linux).
3. Follow the setup wizard to complete installation.

### Step 2: Download a Compatible Local Model
Inside LM Studio:
1. Click the **Search (Magnifying Glass)** icon in the left sidebar.
2. Search for any recommended audit assistant model:
   - **Recommended (8 GB RAM):** `Meta-Llama-3-8B-Instruct-GGUF` (Q4_K_M)
   - **Alternative (8 GB RAM):** `Mistral-7B-Instruct-v0.3-GGUF` (Q4_K_M)
   - **Compact (4 GB RAM):** `Phi-3.5-mini-instruct-GGUF` (Q4_K_M)
   - **Advanced (16 GB RAM / GPU):** `Qwen2.5-14B-Instruct-GGUF`
3. Click **Download** on the `Q4_K_M` quantization.

### Step 3: Start the Local Server in LM Studio
1. In LM Studio, click the **Local Server (↔️)** tab on the left sidebar.
2. At the top, select your downloaded model from the dropdown to load it into memory.
3. Ensure the port is set to **`1234`** (Default).
4. Toggle **Start Server**.
5. You should see: `Server running at http://localhost:1234`.

---

## 3. Configuring FinAuditPro to Connect to LM Studio

1. Open **FinAuditPro** in your browser (`http://127.0.0.1:8000`).
2. Navigate to **Offline AI Manager** from the left navigation sidebar (or click the top bar AI status pill).
3. Verify the settings:
   - **AI Provider:** `LM Studio (Local Server)`
   - **Server URL:** `http://localhost:1234`
4. Click **🔄 Refresh Models** — FinAuditPro will automatically query LM Studio and load your active model identifier.
5. Click **Test Connection** — You will receive a success alert showing connection status and response latency.
6. Click **Test AI Generation** — Verifies end-to-end prompt inference with your local model.
7. Click **Save Settings**.

---

## 4. Disconnected / Fallback Behavior

If LM Studio is closed or the local server is stopped:
- FinAuditPro does **NOT** crash or stop working.
- The UI gracefully displays:
  > *"LM Studio is not connected. AI assistance is unavailable, but audit calculations and analysis remain available."*
- All core audit features remain **100% operational**:
  - Trial Balance & General Ledger analysis
  - Bank BRS & GST 2B reconciliations
  - Statutory Section 40A(3) & 269ST rule evaluations
  - Scikit-Learn Isolation Forest & Benford's Law anomaly detection
  - Working Papers & ICAI checklists
  - PDF Master Audit Reports & exports
