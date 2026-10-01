const API_BASE = "";

class FinAuditAPI {
  static getToken() {
    return localStorage.getItem("finaudit_token") || "";
  }

  static setToken(token) {
    if (token) {
      localStorage.setItem("finaudit_token", token);
    } else {
      localStorage.removeItem("finaudit_token");
    }
  }

  static async request(endpoint, options = {}) {
    const token = this.getToken();
    const defaultHeaders = {
      "Accept": "application/json"
    };

    if (token) {
      defaultHeaders["Authorization"] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
      defaultHeaders["Content-Type"] = "application/json";
    }

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers
      }
    };

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, config);
      if (!response.ok) {
        let errorMsg = `HTTP Error ${response.status}`;
        try {
          const errData = await response.json();
          errorMsg = errData.detail || errorMsg;
        } catch (e) {}
        
        if (response.status === 401 && !endpoint.includes("/api/auth/login")) {
          // Token expired or invalid
          this.setToken(null);
          if (typeof window.showLoginScreen === "function") {
            window.showLoginScreen("Session expired. Please log in again.");
          }
        }
        throw new Error(errorMsg);
      }
      return await response.json();
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }

  // --- Authentication & User Management ---
  static async login(username, password) {
    const res = await this.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  static async logout() {
    try {
      await this.request("/api/auth/logout", { method: "POST" });
    } catch (e) {}
    this.setToken(null);
  }

  static getSetupStatus() {
    return this.request("/api/auth/setup-status");
  }

  static initialSetup(userData) {
    return this.request("/api/auth/initial-setup", {
      method: "POST",
      body: JSON.stringify(userData)
    });
  }

  static getMe() {
    return this.request("/api/auth/me");
  }

  static changePassword(oldPassword, newPassword) {
    return this.request("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
    });
  }

  static getUsers() {
    return this.request("/api/auth/users");
  }

  static createUser(userData) {
    return this.request("/api/auth/users", {
      method: "POST",
      body: JSON.stringify(userData)
    });
  }

  static updateUser(userId, userData) {
    return this.request(`/api/auth/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(userData)
    });
  }

  static toggleUserStatus(userId, isActive) {
    return this.request(`/api/auth/users/${userId}/status`, {
      method: "PUT",
      body: JSON.stringify({ is_active: isActive })
    });
  }

  static adminResetPassword(userId, newPassword) {
    return this.request(`/api/auth/users/${userId}/reset-password`, {
      method: "POST",
      body: JSON.stringify({ new_password: newPassword })
    });
  }

  // --- Clients ---
  static getClients(params = {}) {
    let query = "";
    if (typeof params === "string") {
      query = params ? `?search=${encodeURIComponent(params)}` : "";
    } else {
      const q = new URLSearchParams(params).toString();
      query = q ? `?${q}` : "";
    }
    return this.request(`/api/clients${query}`);
  }

  static getClient(id) {
    return this.request(`/api/clients/${id}`);
  }

  static getClientHistory(id) {
    return this.request(`/api/clients/${id}/history`);
  }

  static createClient(data) {
    return this.request("/api/clients", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static updateClient(id, data) {
    return this.request(`/api/clients/${id}`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  // --- Engagements ---
  static getEngagements(filters = {}) {
    let query = "";
    if (typeof filters === "number") {
      query = `?client_id=${filters}`;
    } else {
      const q = new URLSearchParams(filters).toString();
      query = q ? `?${q}` : "";
    }
    return this.request(`/api/engagements${query}`);
  }

  static getEngagementDetails(id) {
    return this.request(`/api/engagements/${id}`);
  }

  static getDashboardSummaryStats(engagementId = null) {
    const q = engagementId ? `?engagement_id=${engagementId}` : "";
    return this.request(`/api/engagements/dashboard/summary-stats${q}`);
  }

  static getComprehensiveDashboard(engagementId = null) {
    const q = engagementId ? `?engagement_id=${engagementId}` : "";
    return this.request(`/api/engagements/dashboard/comprehensive${q}`);
  }

  static createEngagement(data) {
    return this.request("/api/engagements", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static updateEngagement(id, data) {
    return this.request(`/api/engagements/${id}`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static updateEngagementStatus(id, status) {
    return this.request(`/api/engagements/${id}/status?status=${encodeURIComponent(status)}`, {
      method: "PUT"
    });
  }

  static duplicateEngagement(data) {
    return this.request("/api/engagements/duplicate", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  // --- Data Import ---
  static uploadFile(engagementId, file, dataCategory = "General Ledger") {
    const formData = new FormData();
    formData.append("engagement_id", engagementId);
    formData.append("data_category", dataCategory);
    formData.append("file", file);
    return this.request("/api/import/upload", {
      method: "POST",
      body: formData
    });
  }

  static validateMapping(fileId, mapping, dataCategory = "General Ledger") {
    return this.request("/api/import/validate", {
      method: "POST",
      body: JSON.stringify({ file_id: fileId, column_mapping: mapping, data_category: dataCategory })
    });
  }

  static applyMapping(fileId, mapping, dataCategory = "General Ledger") {
    return this.request("/api/import/apply-mapping", {
      method: "POST",
      body: JSON.stringify({ file_id: fileId, column_mapping: mapping, data_category: dataCategory })
    });
  }

  static getUploadedFiles(engagementId) {
    return this.request(`/api/import/files/${engagementId}`);
  }

  static deleteUploadedFile(fileId) {
    return this.request(`/api/import/files/${fileId}`, {
      method: "DELETE"
    });
  }

  static getErrorReportDownloadUrl(fileId) {
    return `/api/import/errors/${fileId}/download`;
  }

  // --- Data Cleaning & Normalization ---
  static getCleaningSummary(engagementId) {
    return this.request(`/api/cleaning/summary/${engagementId}`);
  }

  static getCleaningLogs(engagementId, filters = {}) {
    const query = new URLSearchParams({ ...filters }).toString();
    return this.request(`/api/cleaning/logs/${engagementId}${query ? `?${query}` : ""}`);
  }

  static reviewCleaningLog(logId, data) {
    return this.request(`/api/cleaning/logs/${logId}/review`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static previewNormalization(fieldName, rawValue) {
    return this.request("/api/cleaning/normalize-preview", {
      method: "POST",
      body: JSON.stringify({ field_name: fieldName, raw_value: rawValue })
    });
  }

  // --- Transactions & General Ledger ---
  static getTransactions(engagementId, params = {}) {
    const query = new URLSearchParams({ engagement_id: engagementId, ...params }).toString();
    return this.request(`/api/transactions?${query}`);
  }

  static getGLAnalysis(engagementId, params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "All") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return this.request(`/api/transactions/analysis/${engagementId}${query ? `?${query}` : ""}`);
  }

  static getGLLedgersList(engagementId) {
    return this.request(`/api/transactions/ledgers-list/${engagementId}`);
  }

  static getGLPartiesList(engagementId) {
    return this.request(`/api/transactions/parties-list/${engagementId}`);
  }

  static getGLReportDownloadUrl(engagementId, params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "All") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return `/api/transactions/report/${engagementId}/download${query ? `?${query}` : ""}`;
  }

  // --- Trial Balance ---
  static getTrialBalance(engagementId) {
    return this.request(`/api/trial-balance/${engagementId}`);
  }

  static getTrialBalanceAnalysis(engagementId) {
    return this.request(`/api/trial-balance/${engagementId}/analysis`);
  }

  static getLedgerDrilldown(engagementId, ledgerName) {
    return this.request(`/api/trial-balance/${engagementId}/ledger-drilldown?ledger_name=${encodeURIComponent(ledgerName)}`);
  }

  static explainTrialBalanceException(engagementId, data) {
    return this.request(`/api/trial-balance/${engagementId}/ai-explain`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static getTrialBalanceReportDownloadUrl(engagementId) {
    return `/api/trial-balance/${engagementId}/report/download`;
  }

  // --- Financial Statements ---
  static getFinancialStatements(engagementId) {
    return this.request(`/api/financial-statements/${engagementId}`);
  }

  static saveFSExplanation(engagementId, data) {
    return this.request(`/api/financial-statements/${engagementId}/explanation`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static getFSReportDownloadUrl(engagementId) {
    return `/api/financial-statements/${engagementId}/report/download`;
  }

  // --- Year-on-Year Financial Comparison ---
  static getYoYComparison(engagementId, params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "ALL") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return this.request(`/api/yoy-comparison/${engagementId}${query ? `?${query}` : ""}`);
  }

  static saveYoYComment(engagementId, data) {
    return this.request(`/api/yoy-comparison/${engagementId}/comment`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static explainYoYMovement(engagementId, data) {
    return this.request(`/api/yoy-comparison/${engagementId}/ai-explain`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static getYoYReportDownloadUrl(engagementId, params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "ALL") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return `/api/yoy-comparison/${engagementId}/report/download${query ? `?${query}` : ""}`;
  }

  // --- Duplicate & Missing Transaction Detection ---
  static getDuplicatesAndGaps(engagementId) {
    return this.request(`/api/duplicates-and-gaps/${engagementId}`);
  }

  static reviewDuplicateGroup(engagementId, data) {
    return this.request(`/api/duplicates-and-gaps/${engagementId}/duplicate-review`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static reviewSequenceGap(engagementId, data) {
    return this.request(`/api/duplicates-and-gaps/${engagementId}/gap-review`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static getDuplicatesAndGapsReportDownloadUrl(engagementId) {
    return `/api/duplicates-and-gaps/${engagementId}/report/download`;
  }

  // --- Reconciliation & Bank BRS ---
  static getReconciliations(engagementId) {
    return this.request(`/api/reconciliation/${engagementId}`);
  }

  static getBankLedgers(engagementId) {
    return this.request(`/api/reconciliation/bank-ledgers/${engagementId}`);
  }

  static getReconciliationDetails(reconId, params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "ALL") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return this.request(`/api/reconciliation/details/${reconId}${query ? `?${query}` : ""}`);
  }

  static executeReconciliation(data) {
    return this.request("/api/reconciliation/execute", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static confirmReconMatch(reconId, itemId) {
    return this.request(`/api/reconciliation/${reconId}/items/${itemId}/confirm`, {
      method: "PUT"
    });
  }

  static rejectReconMatch(reconId, itemId) {
    return this.request(`/api/reconciliation/${reconId}/items/${itemId}/reject`, {
      method: "PUT"
    });
  }

  static manualMatchReconItems(reconId, data) {
    return this.request(`/api/reconciliation/${reconId}/manual-match`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static getBRSReportDownloadUrl(reconId) {
    return `/api/reconciliation/${reconId}/report/download`;
  }

  // --- Sales & Purchase Reconciliation ---
  static executeSalesPurchaseRecon(data) {
    return this.request("/api/reconciliation/sales-purchase/execute", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static getSalesPurchaseReconDetails(reconId, params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "ALL") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return this.request(`/api/reconciliation/sales-purchase/${reconId}${query ? `?${query}` : ""}`);
  }

  static updateSalesPurchaseItemAction(reconId, itemId, data) {
    return this.request(`/api/reconciliation/sales-purchase/${reconId}/items/${itemId}/action`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static getSalesPurchaseReportDownloadUrl(reconId) {
    return `/api/reconciliation/sales-purchase/${reconId}/report/download`;
  }

  // --- GST Reconciliation & Configurable Rule Framework ---
  static getGSTRules() {
    return this.request("/api/gst-reconciliation/rules");
  }

  static updateGSTRule(ruleKey, config) {
    return this.request(`/api/gst-reconciliation/rules/${ruleKey}`, {
      method: "PUT",
      body: JSON.stringify({ config })
    });
  }

  static resetGSTRules() {
    return this.request("/api/gst-reconciliation/rules/reset", {
      method: "POST"
    });
  }

  static executeGSTReconciliation(data) {
    return this.request("/api/gst-reconciliation/execute", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static getGSTReconciliationDetails(reconId, params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "ALL") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return this.request(`/api/gst-reconciliation/${reconId}${query ? `?${query}` : ""}`);
  }

  static updateGSTItemAction(reconId, itemId, data) {
    return this.request(`/api/gst-reconciliation/${reconId}/items/${itemId}/action`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static getGSTReportDownloadUrl(reconId) {
    return `/api/gst-reconciliation/${reconId}/report/download`;
  }

  // --- AI-Assisted Anomaly Detection Engine ---
  static getAnomalies(engagementId, params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "ALL") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return this.request(`/api/anomalies/${engagementId}${query ? `?${query}` : ""}`);
  }

  static triggerAnomalyDetection(engagementId) {
    return this.request(`/api/anomalies/${engagementId}/detect`, {
      method: "POST"
    });
  }

  static reviewAnomaly(engagementId, anomalyId, data) {
    return this.request(`/api/anomalies/${engagementId}/review/${anomalyId}`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static getAIAnomalyExplanation(engagementId, anomalyId) {
    return this.request(`/api/anomalies/${engagementId}/ai-explain/${anomalyId}`, {
      method: "POST"
    });
  }

  static getAnomalyReportDownloadUrl(engagementId) {
    return `/api/anomalies/${engagementId}/report/download`;
  }

  // --- Findings & Anomaly Engine ---
  static runHybridEngine(engagementId) {
    return this.request(`/api/findings/run-engine/${engagementId}`, {
      method: "POST"
    });
  }

  static getFindings(engagementId, filters = {}) {
    const query = new URLSearchParams({ ...filters }).toString();
    return this.request(`/api/findings/${engagementId}${query ? `?${query}` : ""}`);
  }

  static getFindingDetail(findingId) {
    return this.request(`/api/findings/detail/${findingId}`);
  }

  static updateFinding(findingId, data) {
    return this.request(`/api/findings/detail/${findingId}`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  // --- AI Assistant ---
  static queryAssistant(data) {
    return this.request("/api/assistant/query", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  // --- Local AI Assistant ---
  static queryAssistant(engagementId, query, findingId = null, transactionId = null, voucherNo = null) {
    return this.request("/api/assistant/query", {
      method: "POST",
      body: JSON.stringify({
        engagement_id: engagementId,
        query: query,
        finding_id: findingId,
        transaction_id: transactionId,
        voucher_no: voucherNo
      })
    });
  }

  static getAISummary(engagementId) {
    return this.request(`/api/assistant/summary/${engagementId}`);
  }

  static getSuggestedPrompts(engagementId) {
    return this.request(`/api/assistant/suggested-prompts/${engagementId}`);
  }

  // --- Audit Findings & Risk Management ---
  static getFindings(engagementId, filters = {}) {
    const params = new URLSearchParams();
    if (filters.severity) params.append("severity", filters.severity);
    if (filters.module) params.append("module", filters.module);
    if (filters.category) params.append("category", filters.category);
    if (filters.status) params.append("status", filters.status);
    if (filters.engine_type) params.append("engine_type", filters.engine_type);
    if (filters.search) params.append("search", filters.search);
    if (filters.min_risk_score !== undefined && filters.min_risk_score !== null) params.append("min_risk_score", filters.min_risk_score);
    if (filters.max_risk_score !== undefined && filters.max_risk_score !== null) params.append("max_risk_score", filters.max_risk_score);
    if (filters.sort_by) params.append("sort_by", filters.sort_by);

    const qs = params.toString();
    return this.request(`/api/findings/${engagementId}${qs ? `?${qs}` : ''}`);
  }

  static getFindingsDashboardSummary(engagementId) {
    return this.request(`/api/findings/${engagementId}/dashboard-summary`);
  }

  static syncAllFindings(engagementId) {
    return this.request(`/api/findings/${engagementId}/sync`, { method: "POST" });
  }

  static getFindingDetail(findingId) {
    return this.request(`/api/findings/detail/${findingId}`);
  }

  static updateFinding(findingId, data) {
    return this.request(`/api/findings/item/${findingId}`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static getFindingAIExplanation(findingId) {
    return this.request(`/api/findings/item/${findingId}/ai-explain`, { method: "POST" });
  }

  static createCustomFinding(data) {
    return this.request("/api/findings/custom", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static getExportFindingsCsvUrl(engagementId) {
    return `/api/findings/${engagementId}/export/csv`;
  }

  // --- Checklist ---
  static getChecklist(engagementId, filters = {}) {
    const params = new URLSearchParams();
    if (filters.category && filters.category !== "All") params.append("category", filters.category);
    if (filters.status && filters.status !== "All") params.append("status", filters.status);
    if (filters.assigned_staff) params.append("assigned_staff", filters.assigned_staff);
    if (filters.search) params.append("search", filters.search);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return this.request(`/api/checklist/${engagementId}${qs}`);
  }

  static getChecklistSummary(engagementId) {
    return this.request(`/api/checklist/${engagementId}/summary`);
  }

  static generateChecklist(engagementId, options = {}) {
    return this.request(`/api/checklist/${engagementId}/generate`, {
      method: "POST",
      body: JSON.stringify(options)
    });
  }

  static createCustomChecklistItem(engagementId, data) {
    return this.request(`/api/checklist/${engagementId}/custom`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static updateChecklistItem(itemId, data) {
    return this.request(`/api/checklist/item/${itemId}`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static deleteChecklistItem(itemId) {
    return this.request(`/api/checklist/item/${itemId}`, {
      method: "DELETE"
    });
  }

  static getExportChecklistCsvUrl(engagementId) {
    return `/api/checklist/${engagementId}/export/csv`;
  }

  // --- Working Papers (SA 230 Audit Documentation) ---
  static getWorkingPapers(engagementId, filters = {}) {
    let url = `/api/working-papers/${engagementId}?`;
    const params = [];
    if (filters.area && filters.area !== "All") params.push(`area=${encodeURIComponent(filters.area)}`);
    if (filters.status && filters.status !== "All") params.push(`status=${encodeURIComponent(filters.status)}`);
    if (filters.search) params.push(`search=${encodeURIComponent(filters.search)}`);
    if (filters.prepared_by) params.push(`prepared_by=${encodeURIComponent(filters.prepared_by)}`);
    if (filters.reviewed_by) params.push(`reviewed_by=${encodeURIComponent(filters.reviewed_by)}`);
    url += params.join("&");
    return this.request(url);
  }

  static getWorkingPaperDetail(wpId) {
    return this.request(`/api/working-papers/detail/${wpId}`);
  }

  static createWorkingPaper(engagementId, data) {
    return this.request(`/api/working-papers?engagement_id=${engagementId}`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static updateWorkingPaper(wpId, data) {
    return this.request(`/api/working-papers/${wpId}`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  }

  static async uploadWorkingPaperDocument(wpId, formData) {
    const token = localStorage.getItem("finaudit_token");
    const headers = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const response = await fetch(`/api/working-papers/${wpId}/upload-document`, {
      method: "POST",
      headers: headers,
      body: formData
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to upload supporting document.");
    }
    return response.json();
  }

  static deleteWorkingPaperDocument(wpId, docId) {
    return this.request(`/api/working-papers/${wpId}/document/${docId}`, {
      method: "DELETE"
    });
  }

  static getWorkingPaperDocumentDownloadUrl(wpId, docId) {
    return `/api/working-papers/download-file/${wpId}/${docId}`;
  }

  static addWorkingPaperComment(wpId, data) {
    return this.request(`/api/working-papers/${wpId}/comments`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static updateWorkingPaperNotes(wpId, data) {
    return this.request(`/api/working-papers/${wpId}/notes`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static updateWorkingPaperStatus(wpId, data) {
    return this.request(`/api/working-papers/${wpId}/status`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static updateWorkingPaperLink(wpId, data) {
    return this.request(`/api/working-papers/${wpId}/links`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static deleteWorkingPaper(wpId, reason = "") {
    return this.request(`/api/working-papers/${wpId}`, {
      method: "DELETE",
      body: JSON.stringify({ reason: reason })
    });
  }

  static getWorkingPaperLinkableItems(engagementId) {
    return this.request(`/api/working-papers/${engagementId}/linkable-items`);
  }

  static getExportWorkingPapersCsvUrl(engagementId) {
    return `/api/working-papers/${engagementId}/export/csv`;
  }

  // --- Reports ---
  static getReportTypes() {
    return this.request("/api/reports/types");
  }

  static getReports(engagementId) {
    return this.request(`/api/reports/${engagementId}`);
  }

  static generatePDFReport(engagementId, reportType = "complete_audit_analysis") {
    return this.request(`/api/reports/generate-pdf/${engagementId}?report_type=${encodeURIComponent(reportType)}`, {
      method: "POST",
      body: JSON.stringify({ report_type: reportType })
    });
  }

  static getReportDownloadUrl(reportId) {
    return `/api/reports/download/${reportId}`;
  }


  // --- Audit Trail & Local Logs ---
  static getAuditTrail(params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "All") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return this.request(`/api/audit-trail${query ? `?${query}` : ""}`);
  }

  static getAuditTrailMetadata() {
    return this.request("/api/audit-trail/metadata");
  }

  static getAuditTrailStatistics() {
    return this.request("/api/audit-trail/statistics");
  }

  static getAuditTrailExportCsvUrl(params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "All") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return `/api/audit-trail/export/csv${query ? `?${query}` : ""}`;
  }

  static getAuditTrailExportJsonUrl(params = {}) {
    const cleanParams = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "" && v !== "All") {
        cleanParams[k] = v;
      }
    }
    const query = new URLSearchParams(cleanParams).toString();
    return `/api/audit-trail/export/json${query ? `?${query}` : ""}`;
  }

  // --- Database Backups & Restore ---
  static getBackupsList() {
    return this.request("/api/audit-trail/backups");
  }

  static createDatabaseBackup() {
    return this.request("/api/audit-trail/backup/create", { method: "POST" });
  }

  static getBackupDownloadUrl(filename) {
    return `/api/audit-trail/backup/download/${encodeURIComponent(filename)}`;
  }

  static restoreDatabaseBackup(filename) {
    return this.request(`/api/audit-trail/backup/restore/${encodeURIComponent(filename)}`, { method: "POST" });
  }

  static async restoreDatabaseUpload(file) {
    const formData = new FormData();
    formData.append("file", file);

    const token = this.getToken();
    const headers = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${this.BASE_URL}/api/audit-trail/backup/restore-upload`, {
      method: "POST",
      headers: headers,
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Database restore failed" }));
      throw new Error(err.detail || "Database restore failed");
    }
    return res.json();
  }

  // --- Settings & Configuration ---
  static getSystemInfo() {
    return this.request("/api/settings/system-info");
  }

  static getAppSettings() {
    return this.request("/api/settings");
  }

  static updateAppSettings(settingsDict) {
    return this.request("/api/settings", {
      method: "POST",
      body: JSON.stringify({ settings: settingsDict })
    });
  }

  static createBackup() {
    return this.request("/api/audit-trail/backup/create", { method: "POST" });
  }

  // --- Offline Local AI Model Manager ---
  static getAIStatus() {
    return this.request("/api/ai-manager/status");
  }

  static updateAISettings(data) {
    return this.request("/api/ai-manager/settings", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  static getAvailableModels() {
    return this.request("/api/ai-manager/models");
  }

  static testAIGeneration(prompt = "Confirm LM Studio connectivity with a concise verification statement.") {
    return this.request("/api/ai-manager/test-ai", {
      method: "POST",
      body: JSON.stringify({ prompt })
    });
  }

  static generateAI(prompt, systemPrompt = null, clientName = null) {
    return this.request("/api/ai-manager/generate", {
      method: "POST",
      body: JSON.stringify({
        prompt: prompt,
        system_prompt: systemPrompt,
        client_name: clientName
      })
    });
  }

  static previewSanitization(text, clientName = null) {
    return this.request("/api/ai-manager/sanitize-preview", {
      method: "POST",
      body: JSON.stringify({
        text: text,
        client_name: clientName
      })
    });
  }
}

window.FinAuditAPI = FinAuditAPI;

