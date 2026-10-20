/**
 * Frontend API Client & Download Token Regression Suite
 * Verifies Bearer header authentication, safe URL generation without token leakage,
 * authenticated blob download dispatch, and session storage integrity.
 */
const assert = require("assert");

// Mock browser environment
const storage = {};
global.localStorage = {
  getItem: (key) => storage[key] || null,
  setItem: (key, val) => { storage[key] = String(val); },
  removeItem: (key) => { delete storage[key]; },
  clear: () => { Object.keys(storage).forEach((k) => delete storage[k]); }
};
global.window = {
  localStorage: global.localStorage,
  URL: {
    createObjectURL: (blob) => "blob:http://127.0.0.1:8000/mock-uuid",
    revokeObjectURL: (url) => {}
  }
};
global.document = {
  createElement: (tag) => ({
    tagName: tag,
    href: "",
    download: "",
    click: function() {}
  }),
  body: {
    appendChild: () => {},
    removeChild: () => {}
  }
};

const { FinAuditAPI } = require("../js/api.js");

async function runFrontendClientTests() {
  console.log("Starting Frontend API Client & Download Security Tests...\n");
  let passed = 0;

  // Test 1: attachAuthToken returns clean URL without query tokens
  FinAuditAPI.setToken("");
  const url1 = FinAuditAPI.attachAuthToken("/api/reports/download/1");
  assert.strictEqual(url1, "/api/reports/download/1");
  console.log("[PASS] 1. attachAuthToken returns clean URL when unauthenticated");
  passed++;

  // Test 2: attachAuthToken never leaks tokens in query strings even when token is set
  const sampleToken = "jwt.sample.token_abc123";
  FinAuditAPI.setToken(sampleToken);
  const url2 = FinAuditAPI.attachAuthToken("/api/reports/download/1");
  assert.strictEqual(url2, "/api/reports/download/1");
  assert(!url2.includes("token="), "Token must NOT be leaked in URL query parameters");
  console.log("[PASS] 2. attachAuthToken prevents token leakage in URL query parameters");
  passed++;

  // Test 3: Download URL generators generate clean endpoint paths
  const dlMethods = [
    { name: "getErrorReportDownloadUrl", url: FinAuditAPI.getErrorReportDownloadUrl(5) },
    { name: "getGLReportDownloadUrl", url: FinAuditAPI.getGLReportDownloadUrl(4, { ledger: "Cash" }) },
    { name: "getTrialBalanceReportDownloadUrl", url: FinAuditAPI.getTrialBalanceReportDownloadUrl(4) },
    { name: "getFSReportDownloadUrl", url: FinAuditAPI.getFSReportDownloadUrl(4) },
    { name: "getYoYReportDownloadUrl", url: FinAuditAPI.getYoYReportDownloadUrl(4) },
    { name: "getDuplicatesAndGapsReportDownloadUrl", url: FinAuditAPI.getDuplicatesAndGapsReportDownloadUrl(4) },
    { name: "getBRSReportDownloadUrl", url: FinAuditAPI.getBRSReportDownloadUrl(1) },
    { name: "getSalesPurchaseReportDownloadUrl", url: FinAuditAPI.getSalesPurchaseReportDownloadUrl(1) },
    { name: "getGSTReportDownloadUrl", url: FinAuditAPI.getGSTReportDownloadUrl(1) },
    { name: "getAnomalyReportDownloadUrl", url: FinAuditAPI.getAnomalyReportDownloadUrl(4) },
    { name: "getWorkingPaperDocumentDownloadUrl", url: FinAuditAPI.getWorkingPaperDocumentDownloadUrl(2, 3) },
    { name: "getReportDownloadUrl", url: FinAuditAPI.getReportDownloadUrl(1) },
    { name: "getBackupDownloadUrl", url: FinAuditAPI.getBackupDownloadUrl("backup.db") }
  ];

  dlMethods.forEach((m) => {
    assert(!m.url.includes("token="), `${m.name} must never expose JWT in URL`);
  });
  console.log(`[PASS] 3. All 13 download URL generators generate clean URLs free of token exposure`);
  passed++;

  // Test 4: downloadFile sends Bearer authorization header
  let fetchHeaders = null;
  let fetchEndpoint = null;
  global.fetch = async (endpoint, opts) => {
    fetchEndpoint = endpoint;
    fetchHeaders = opts.headers;
    return {
      ok: true,
      status: 200,
      blob: async () => ({ size: 1024, type: "application/pdf" })
    };
  };

  await FinAuditAPI.downloadFile("/api/reports/download/1", "audit_report.pdf");
  assert.strictEqual(fetchEndpoint, "/api/reports/download/1");
  assert.strictEqual(fetchHeaders["Authorization"], `Bearer ${sampleToken}`);
  console.log("[PASS] 4. downloadFile sends Authorization Bearer header correctly");
  passed++;

  // Test 5: Logout clears token
  FinAuditAPI.setToken(null);
  assert.strictEqual(FinAuditAPI.getToken(), "");
  console.log("[PASS] 5. Logout clears active token from storage");
  passed++;

  console.log(`\n========================================\nResults: ${passed} passed, 0 failed.\n========================================\n`);
}

runFrontendClientTests();
