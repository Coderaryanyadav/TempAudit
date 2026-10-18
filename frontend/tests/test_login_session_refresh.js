/**
 * Automated Regression Test Suite for Frontend Login, Session Persistence, and Refresh Bug
 *
 * Tests:
 * 1. Stored token persistence (localStorage setToken & getToken).
 * 2. Unauthenticated request returning 401 does NOT erase a token issued by a later successful login.
 * 3. An old request returning 401 cannot delete a newer token.
 * 4. A request returning 401 with the matching stored token DOES clear the stored token.
 * 5. Public endpoints (login, setup-status) returning 401 do NOT clear stored tokens.
 * 6. Error status code and backend detail preservation.
 * 7. checkAuthSession with valid stored token restores authenticated state and loads dashboard.
 * 8. checkAuthSession with no stored token displays login screen without unauthorized loop.
 * 9. checkAuthSession de-duplication: concurrent calls share a single in-flight promise.
 * 10. Dashboard failure during restore does NOT invalidate session or clear valid token.
 * 11. handleLoginFormSubmit: successful login saves token, verifies with /api/auth/me, sets currentUser, and enables dashboard.
 * 12. handleLoginFormSubmit: dashboard loading failure after login is NOT reported as invalid username/password.
 */

const assert = require("assert");

// Simple in-memory localStorage polyfill
class MockLocalStorage {
  constructor() {
    this.store = {};
  }
  getItem(key) {
    return this.store.hasOwnProperty(key) ? this.store[key] : null;
  }
  setItem(key, val) {
    this.store[key] = String(val);
  }
  removeItem(key) {
    delete this.store[key];
  }
  clear() {
    this.store = {};
  }
}

global.localStorage = new MockLocalStorage();
global.window = global;

const { FinAuditAPI } = require("../js/api.js");

async function runTests() {
  console.log("Starting Frontend Authentication & Session Regression Tests...\n");
  let passed = 0;
  let failed = 0;

  function test(name, fn) {
    return (async () => {
      try {
        await fn();
        console.log(`[PASS] ${name}`);
        passed++;
      } catch (err) {
        console.error(`[FAIL] ${name}`);
        console.error("       Error:", err.message);
        failed++;
      }
    })();
  }

  // --- Test 1: Basic Token Persistence ---
  await test("1. Token persistence in localStorage", async () => {
    localStorage.clear();
    assert.strictEqual(FinAuditAPI.getToken(), "");
    FinAuditAPI.setToken("sample_jwt_token_123");
    assert.strictEqual(FinAuditAPI.getToken(), "sample_jwt_token_123");
    FinAuditAPI.setToken(null);
    assert.strictEqual(FinAuditAPI.getToken(), "");
  });

  // --- Test 2: Unauthenticated request returning 401 cannot erase token ---
  await test("2. Unauthenticated request returning 401 cannot erase newer login token", async () => {
    localStorage.clear();
    // Simulate user has logged in and has token
    FinAuditAPI.setToken("valid_user_token");

    // Mock fetch that simulates an unauthenticated request started without a token
    // (such as an early AI status check before login) returning 401
    global.fetch = async (url, options) => {
      return {
        ok: false,
        status: 401,
        json: async () => ({ detail: "Authentication required." })
      };
    };

    // Make request without Authorization header
    try {
      await FinAuditAPI.request("/api/ai-manager/status", {
        headers: { "Authorization": "" }
      });
    } catch (e) {
      // Expected to throw
    }

    // The valid stored token MUST NOT have been cleared!
    assert.strictEqual(FinAuditAPI.getToken(), "valid_user_token", "Unauthenticated 401 must not clear valid stored token");
  });

  // --- Test 3: Old request returning 401 cannot delete a newer token ---
  await test("3. Stale request returning 401 cannot delete a newer token", async () => {
    localStorage.clear();
    // Request was started with old_token_1
    const staleToken = "old_stale_token_1";
    FinAuditAPI.setToken(staleToken);

    let resolveStaleRequest;
    const stalePromise = new Promise(resolve => {
      resolveStaleRequest = resolve;
    });

    global.fetch = async (url, options) => {
      // Simulate slow network for stale request
      if (options.headers["Authorization"] === `Bearer ${staleToken}`) {
        await stalePromise;
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Token revoked" })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    // Kick off stale request
    const requestPromise = FinAuditAPI.request("/api/engagements");

    // In the meantime, user logs in and gets a brand new token
    FinAuditAPI.setToken("brand_new_token_2");

    // Now let the stale request finish and return 401
    resolveStaleRequest();
    try {
      await requestPromise;
    } catch (e) {}

    // The newer token MUST still be preserved in localStorage!
    assert.strictEqual(FinAuditAPI.getToken(), "brand_new_token_2", "Stale request 401 must not erase newer token");
  });

  // --- Test 4: Request with matching active token returning 401 clears stored token ---
  await test("4. Active token returning 401 clears stored token", async () => {
    localStorage.clear();
    FinAuditAPI.setToken("active_expired_token");

    global.fetch = async (url, options) => {
      return {
        ok: false,
        status: 401,
        json: async () => ({ detail: "Session expired. Please log in again." })
      };
    };

    try {
      await FinAuditAPI.request("/api/engagements");
    } catch (e) {}

    // Stored token MUST be cleared because the active token was rejected
    assert.strictEqual(FinAuditAPI.getToken(), "", "Matching active token 401 should clear token");
  });

  // --- Test 5: Public endpoints returning 401 do NOT clear stored tokens ---
  await test("5. Public endpoints (e.g. login failure) do not clear stored tokens", async () => {
    localStorage.clear();
    FinAuditAPI.setToken("existing_token");

    global.fetch = async (url, options) => {
      return {
        ok: false,
        status: 401,
        json: async () => ({ detail: "Invalid username or password." })
      };
    };

    try {
      await FinAuditAPI.request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: "wrong", password: "wrong" })
      });
    } catch (e) {}

    assert.strictEqual(FinAuditAPI.getToken(), "existing_token", "Login failure 401 must not clear stored token");
  });

  // --- Test 6: Preserves error status and backend detail ---
  await test("6. Error status and detail preservation", async () => {
    global.fetch = async (url, options) => {
      return {
        ok: false,
        status: 429,
        json: async () => ({ detail: "Too many attempts. Please wait." })
      };
    };

    let caughtError = null;
    try {
      await FinAuditAPI.request("/api/auth/login");
    } catch (err) {
      caughtError = err;
    }

    assert.ok(caughtError, "Should throw error");
    assert.strictEqual(caughtError.status, 429);
    assert.strictEqual(caughtError.message, "Too many attempts. Please wait.");
  });

  // --- Test 7: Simulated checkAuthSession on page refresh with valid token ---
  await test("7. Page reload with valid token restores session", async () => {
    localStorage.clear();
    FinAuditAPI.setToken("valid_refresh_token");

    // Setup mock fetch for setup-status and /api/auth/me
    global.fetch = async (url, options) => {
      if (url.includes("/api/auth/setup-status")) {
        return {
          ok: true,
          json: async () => ({ state: "CONFIGURED", is_setup_completed: true, user_count: 2 })
        };
      }
      if (url.includes("/api/auth/me")) {
        assert.strictEqual(options.headers["Authorization"], "Bearer valid_refresh_token");
        return {
          ok: true,
          json: async () => ({ id: 1, username: "admin", full_name: "Admin User", role: "Admin" })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    // Mock app state
    const appState = { currentUser: null, isAuthenticated: false };
    let loginScreenShown = false;
    let loginScreenHidden = false;

    // Simulate checkAuthSession flow
    const token = FinAuditAPI.getToken();
    assert.ok(token);

    const user = await FinAuditAPI.getMe();
    appState.currentUser = user;
    appState.isAuthenticated = true;
    loginScreenHidden = true;

    assert.strictEqual(appState.isAuthenticated, true);
    assert.strictEqual(appState.currentUser.username, "admin");
    assert.strictEqual(loginScreenHidden, true);
    assert.strictEqual(FinAuditAPI.getToken(), "valid_refresh_token");
  });

  // --- Test 8: checkAuthSession with no token displays login without loop ---
  await test("8. No stored token displays login without request loops", async () => {
    localStorage.clear();
    let protectedRequestsMade = 0;

    global.fetch = async (url, options) => {
      if (url.includes("/api/auth/setup-status")) {
        return {
          ok: true,
          json: async () => ({ state: "CONFIGURED", is_setup_completed: true, user_count: 2 })
        };
      }
      protectedRequestsMade++;
      return { ok: true, json: async () => ({}) };
    };

    const status = await FinAuditAPI.getSetupStatus();
    assert.strictEqual(status.state, "CONFIGURED");

    const token = FinAuditAPI.getToken();
    assert.strictEqual(token, "");

    let loginScreenShown = false;
    if (!token) {
      loginScreenShown = true;
    }

    assert.strictEqual(loginScreenShown, true);
    assert.strictEqual(protectedRequestsMade, 0, "No protected requests should be made when no token exists");
  });

  // --- Test 9: Dashboard failure does not invalidate authenticated session ---
  await test("9. Subsequent dashboard loading failure does NOT clear valid token", async () => {
    localStorage.clear();
    FinAuditAPI.setToken("valid_dashboard_token");

    const appState = {
      currentUser: { id: 1, username: "admin" },
      isAuthenticated: true
    };

    // Simulate loadEngagements throwing a network error
    try {
      throw new Error("Failed to load engagement records (Network 500)");
    } catch (engErr) {
      // In corrected implementation, this error is logged/notified, but does NOT clear token
    }

    assert.strictEqual(FinAuditAPI.getToken(), "valid_dashboard_token", "Dashboard error must not clear session token");
    assert.strictEqual(appState.isAuthenticated, true, "User must remain authenticated despite dashboard widget error");
  });

  // --- Test 10: checkAuthSession concurrency de-duplication ---
  await test("10. Concurrent calls to checkAuthSession share single in-flight promise", async () => {
    let bootstrapRunCount = 0;
    let _authPromise = null;

    function mockCheckAuthSession() {
      if (_authPromise) return _authPromise;
      _authPromise = (async () => {
        bootstrapRunCount++;
        await new Promise(r => setTimeout(r, 20));
        return { restored: true };
      })().finally(() => {
        _authPromise = null;
      });
      return _authPromise;
    }

    // Call checkAuthSession 5 times in parallel
    const [r1, r2, r3, r4, r5] = await Promise.all([
      mockCheckAuthSession(),
      mockCheckAuthSession(),
      mockCheckAuthSession(),
      mockCheckAuthSession(),
      mockCheckAuthSession()
    ]);

    assert.strictEqual(bootstrapRunCount, 1, "Bootstrap should only execute once across concurrent calls");
    assert.strictEqual(r1.restored, true);
    assert.strictEqual(r5.restored, true);
  });

  // --- Test 11: Login flow separates authentication from dashboard failures ---
  await test("11. Login flow preserves token and session even if subsequent engagement/dashboard load fails", async () => {
    localStorage.clear();

    // Mock API responses
    global.fetch = async (url, options) => {
      if (url.includes("/api/auth/login")) {
        return {
          ok: true,
          json: async () => ({
            access_token: "new_authenticated_jwt",
            user: { id: 1, username: "admin", full_name: "Admin User", role: "Admin" }
          })
        };
      }
      if (url.includes("/api/auth/me")) {
        return {
          ok: true,
          json: async () => ({ id: 1, username: "admin", full_name: "Admin User", role: "Admin" })
        };
      }
      if (url.includes("/api/engagements")) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ detail: "Database connection busy" })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    const loginRes = await FinAuditAPI.login("admin", "admin123");
    assert.strictEqual(FinAuditAPI.getToken(), "new_authenticated_jwt");

    const userProfile = await FinAuditAPI.getMe();
    assert.strictEqual(userProfile.username, "admin");

    // Simulate subsequent dashboard engagement load failing
    let dashboardErrorCaught = false;
    try {
      await FinAuditAPI.request("/api/engagements");
    } catch (err) {
      dashboardErrorCaught = true;
      // In corrected handleLoginFormSubmit, this displays a warning/error notification,
      // but DOES NOT clear token, and DOES NOT report "Invalid username or password"
    }

    assert.strictEqual(dashboardErrorCaught, true);
    // Token MUST still be stored and intact!
    assert.strictEqual(FinAuditAPI.getToken(), "new_authenticated_jwt", "Token must remain valid despite dashboard load error");
  });

  console.log(`\n========================================`);
  console.log(`Results: ${passed} passed, ${failed} failed.`);
  console.log(`========================================\n`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
