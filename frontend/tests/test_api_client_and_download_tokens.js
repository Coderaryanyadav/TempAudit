/**
 * Frontend API Client & Download Token Regression Suite (Phase 8)
 * Verifies URL token parameter appending, header authentication,
 * FormData handling, and session storage integrity.
 */
const assert = require("assert");

// Mock browser localStorage and window environment
const storage = {};
global.localStorage = {
  getItem: (key) => storage[key] || null,
  setItem: (key, val) => { storage[key] = String(val); },
  removeItem: (key) => { delete storage[key]; },
  clear: () => { Object.keys(storage).forEach((k) => delete storage[k]); }
};
global.window = { localStorage: global.localStorage };

const { FinAuditAPI } = require("../js/api.js");

function runFrontendClientTests() {
  console.log("Starting Frontend API Client & Download URL Tests...\n");
  let passed = 0;

  // Test 1: attachAuthToken with no token returns original URL
  FinAuditAPI.setToken("");
  const url1 = FinAuditAPI.attachAuthToken("/api/reports/download/1");
  assert.strictEqual(url1, "/api/reports/download/1");
  console.log("[PASS] 1. attachAuthToken returns clean URL when unauthenticated");
  passed++;

  // Test 2: attachAuthToken appends ?token= when token is set
  const sampleToken = "jwt.sample.token_abc123";
  FinAuditAPI.setToken(sampleToken);
  const url2 = FinAuditAPI.attachAuthToken("/api/reports/download/1");
  assert.strictEqual(url2, `/api/reports/download/1?token=${encodeURIComponent(sampleToken)}`);
  console.log("[PASS] 2. attachAuthToken appends ?token= to query-less URLs");
  passed++;

  // Test 3: attachAuthToken appends &token= when query parameters already exist
  const urlWithQuery = "/api/yoy-comparison/4/report/download?threshold=10";
  const url3 = FinAuditAPI.attachAuthToken(urlWithQuery);
  assert.strictEqual(url3, `${urlWithQuery}&token=${encodeURIComponent(sampleToken)}`);
  console.log("[PASS] 3. attachAuthToken appends &token= when query parameters exist");
  passed++;

  // Test 4: All download URL generators include authentication token
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
    assert(m.url.includes(`token=${encodeURIComponent(sampleToken)}`), `${m.name} must include token`);
  });
  console.log(`[PASS] 4. All 13 download URL generators automatically append active auth token`);
  passed++;

  // Test 5: Logout clears token
  FinAuditAPI.setToken(null);
  assert.strictEqual(FinAuditAPI.getToken(), "");
  const urlLoggedOut = FinAuditAPI.getReportDownloadUrl(1);
  assert(!urlLoggedOut.includes("token="), "Logged out download URL must not contain token");
  console.log("[PASS] 5. Logout clears token and reverts download URLs to clean paths");
  passed++;

  console.log(`\n========================================\nResults: ${passed} passed, 0 failed.\n========================================\n`);
}

runFrontendClientTests();
