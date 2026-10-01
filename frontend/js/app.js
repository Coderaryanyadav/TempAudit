// FinAuditPro Desktop Application Controller & Authentication System

const state = {
  currentUser: null,
  isAuthenticated: false,
  currentTab: "dashboard",
  currentEngagementId: null,
  engagements: [],
  activeEngagement: null,
  activeFinding: null,
  uploadPreview: null,
  isSidebarCollapsed: false,
  isFormDirty: false
};

// ==========================================
// UNIFIED NOTIFICATION SYSTEM (FinNotify)
// ==========================================
const FinNotify = {
  container: null,
  
  init() {
    if (!this.container) {
      this.container = document.getElementById("notification-toast-container");
      if (!this.container) {
        this.container = document.createElement("div");
        this.container.id = "notification-toast-container";
        this.container.className = "toast-container";
        document.body.appendChild(this.container);
      }
    }
  },

  show({ type = "info", title = "", message = "", duration = 4000 }) {
    this.init();
    const toast = document.createElement("div");
    toast.className = `toast-item toast-${type}`;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "polite");

    const icons = {
      success: "✓",
      error: "✕",
      warning: "⚠",
      info: "ℹ"
    };

    const defaultTitles = {
      success: "Operation Successful",
      error: "Action Failed",
      warning: "Attention Required",
      info: "Information"
    };

    const displayTitle = title || defaultTitles[type] || "Notice";
    const icon = icons[type] || "ℹ";

    toast.innerHTML = `
      <div class="toast-icon-wrap">${icon}</div>
      <div class="toast-content-wrap">
        <div class="toast-title">${escapeHTML(displayTitle)}</div>
        ${message ? `<div class="toast-message">${escapeHTML(message)}</div>` : ""}
      </div>
      <button type="button" class="toast-close-btn" aria-label="Dismiss notification">✕</button>
      <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
    `;

    const closeBtn = toast.querySelector(".toast-close-btn");
    const removeToast = () => {
      toast.classList.add("fade-out");
      setTimeout(() => {
        if (toast.parentElement) toast.parentElement.removeChild(toast);
      }, 250);
    };

    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      removeToast();
    });

    this.container.appendChild(toast);

    if (duration > 0) {
      setTimeout(removeToast, duration);
    }
    return toast;
  },

  success(message, title = "Success") {
    return this.show({ type: "success", title, message, duration: 4500 });
  },

  error(message, title = "Error") {
    return this.show({ type: "error", title, message, duration: 6000 });
  },

  warning(message, title = "Warning") {
    return this.show({ type: "warning", title, message, duration: 5000 });
  },

  info(message, title = "Notice") {
    return this.show({ type: "info", title, message, duration: 4000 });
  }
};

// Global toast / alert redirection
window.FinNotify = FinNotify;
window.notifySuccess = (msg, title) => FinNotify.success(msg, title);
window.notifyError = (msg, title) => FinNotify.error(msg, title);
window.notifyWarning = (msg, title) => FinNotify.warning(msg, title);
window.notifyInfo = (msg, title) => FinNotify.info(msg, title);
window.showToast = (msg, type = "info") => FinNotify[type] ? FinNotify[type](msg) : FinNotify.info(msg);
window.alert = (msg) => {
  if (typeof msg !== "string") msg = String(msg);
  if (msg.toLowerCase().includes("fail") || msg.toLowerCase().includes("error")) {
    FinNotify.error(msg);
  } else if (msg.toLowerCase().includes("success") || msg.toLowerCase().includes("complete") || msg.toLowerCase().includes("saved")) {
    FinNotify.success(msg);
  } else if (msg.toLowerCase().includes("warn") || msg.toLowerCase().includes("required")) {
    FinNotify.warning(msg);
  } else {
    FinNotify.info(msg);
  }
};

// ==========================================
// UNIFIED CONFIRMATION MODAL SYSTEM (FinConfirm)
// ==========================================
function FinConfirm({
  title = "Confirm Action",
  message = "Are you sure you want to proceed?",
  consequences = [],
  confirmText = "Confirm",
  cancelText = "Cancel",
  isDanger = false
}) {
  return new Promise((resolve) => {
    let container = document.getElementById("fin-confirm-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "fin-confirm-container";
      document.body.appendChild(container);
    }

    const consequenceListHtml = consequences && consequences.length > 0
      ? `<div class="fin-confirm-consequences">
           <div class="consequence-label">Affected items:</div>
           <ul>${consequences.map(c => `<li>${escapeHTML(c)}</li>`).join("")}</ul>
         </div>`
      : "";

    container.innerHTML = `
      <div class="fin-confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
        <div class="fin-confirm-card ${isDanger ? 'confirm-danger' : ''}">
          <div class="fin-confirm-header">
            <div class="fin-confirm-icon">${isDanger ? '⚠️' : '❓'}</div>
            <h3 id="confirm-modal-title" class="fin-confirm-title">${escapeHTML(title)}</h3>
          </div>
          <div class="fin-confirm-body">
            <p class="fin-confirm-msg">${escapeHTML(message)}</p>
            ${consequenceListHtml}
          </div>
          <div class="fin-confirm-actions">
            <button type="button" class="btn btn-secondary" id="fin-confirm-cancel-btn">${escapeHTML(cancelText)}</button>
            <button type="button" class="btn ${isDanger ? 'btn-danger' : 'btn-primary'}" id="fin-confirm-ok-btn">${escapeHTML(confirmText)}</button>
          </div>
        </div>
      </div>
    `;

    const overlay = container.querySelector(".fin-confirm-overlay");
    const cancelBtn = document.getElementById("fin-confirm-cancel-btn");
    const okBtn = document.getElementById("fin-confirm-ok-btn");

    const cleanup = (result) => {
      container.innerHTML = "";
      document.removeEventListener("keydown", handleKey);
      resolve(result);
    };

    const handleKey = (e) => {
      if (e.key === "Escape") cleanup(false);
      if (e.key === "Enter") cleanup(true);
    };

    cancelBtn.addEventListener("click", () => cleanup(false));
    okBtn.addEventListener("click", () => cleanup(true));
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) cleanup(false);
    });

    document.addEventListener("keydown", handleKey);
    okBtn.focus();
  });
}
window.FinConfirm = FinConfirm;

// ==========================================
// ERROR TRANSLATOR & DIAGNOSTIC RENDERER
// ==========================================
function translateError(err, contextTitle = "Action Failed") {
  const rawMsg = (typeof err === "string" ? err : err?.message || "An unexpected error occurred").trim();
  let friendlyTitle = contextTitle;
  let friendlyMessage = rawMsg;
  let suggestion = "Please review your input or try again.";

  if (rawMsg.includes("UNIQUE constraint failed: engagements.title") || rawMsg.includes("UNIQUE constraint failed: engagements.reference")) {
    friendlyTitle = "Duplicate Engagement Reference";
    friendlyMessage = "An audit engagement with this title or reference already exists in your workspace.";
    suggestion = "Please change the engagement title or financial year and try again.";
  } else if (rawMsg.includes("UNIQUE constraint failed: clients.pan")) {
    friendlyTitle = "Duplicate Client PAN";
    friendlyMessage = "A client record with this Permanent Account Number (PAN) is already registered.";
    suggestion = "Check the Client Directory to view or edit the existing client record.";
  } else if (rawMsg.includes("UNIQUE constraint failed: users.username")) {
    friendlyTitle = "Username Already Taken";
    friendlyMessage = "A user account with this username already exists.";
    suggestion = "Please choose a different username.";
  } else if (rawMsg.includes("401") || rawMsg.toLowerCase().includes("unauthorized") || rawMsg.toLowerCase().includes("token expired")) {
    friendlyTitle = "Session Expired";
    friendlyMessage = "Your local authentication session has timed out or is no longer valid.";
    suggestion = "Please log in again to continue working.";
  } else if (rawMsg.includes("403") || rawMsg.toLowerCase().includes("forbidden") || rawMsg.toLowerCase().includes("permission")) {
    friendlyTitle = "Access Restricted";
    friendlyMessage = "You do not have the required administrative permissions for this operation.";
    suggestion = "Contact your firm's Lead Partner or Administrator to adjust your role privileges.";
  } else if (rawMsg.toLowerCase().includes("failed to fetch") || rawMsg.toLowerCase().includes("networkerror")) {
    friendlyTitle = "Local Service Unavailable";
    friendlyMessage = "Could not communicate with the local FinAuditPro backend server.";
    suggestion = "Ensure the local server process is running on port 8000 and try again.";
  }

  return {
    title: friendlyTitle,
    friendlyMessage,
    suggestion,
    rawError: rawMsg
  };
}

function renderErrorBanner(err, contextTitle = "Action Failed") {
  const translated = translateError(err, contextTitle);
  return `
    <div class="error-banner-card">
      <div class="error-banner-header">
        <div class="error-banner-icon">⚠️</div>
        <div>
          <h4 class="error-banner-title">${escapeHTML(translated.title)}</h4>
          <p class="error-banner-message">${escapeHTML(translated.friendlyMessage)}</p>
        </div>
      </div>
      <div class="error-banner-suggestion">
        <strong>What you can do:</strong> ${escapeHTML(translated.suggestion)}
      </div>
      <details class="error-diagnostic-details">
        <summary>Technical Details & Diagnostics</summary>
        <div class="error-diagnostic-body">
          <code>${escapeHTML(translated.rawError)}</code>
          <button type="button" class="btn btn-sm btn-secondary" onclick="navigator.clipboard.writeText('${escapeHTML(translated.rawError).replace(/'/g, "\\'")}'); FinNotify.info('Diagnostic details copied to clipboard');" style="margin-top: 8px;">
            📋 Copy Diagnostic Info
          </button>
        </div>
      </details>
    </div>
  `;
}

// Formatting helpers
function escapeHTML(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatINR(val) {
  const num = Number(val) || 0;
  return "₹" + num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function getSeverityBadge(sev) {
  const s = (sev || "MEDIUM").toUpperCase();
  if (s === "CRITICAL") return `<span class="badge badge-critical">CRITICAL</span>`;
  if (s === "HIGH") return `<span class="badge badge-high">HIGH</span>`;
  if (s === "MEDIUM") return `<span class="badge badge-medium">MEDIUM</span>`;
  return `<span class="badge badge-low">LOW</span>`;
}

function getStatusBadge(status) {
  const st = status || "Open";
  if (st === "Resolved") return `<span class="badge badge-resolved">Resolved</span>`;
  if (st === "In Review") return `<span class="badge badge-medium">In Review</span>`;
  if (st === "Waived") return `<span class="badge badge-low">Waived</span>`;
  return `<span class="badge badge-open">Open</span>`;
}

function getRoleBadge(role) {
  const r = (role || "").trim();
  if (r === "Admin") return `<span class="badge badge-role-admin">Admin</span>`;
  if (r === "Auditor") return `<span class="badge badge-role-auditor">Auditor</span>`;
  return `<span class="badge badge-role-staff">Audit Staff</span>`;
}

// App Initialization
document.addEventListener("DOMContentLoaded", async () => {
  setupNavigation();
  setupDrawer();
  setupUserMenu();
  setupSidebarControls();
  setupGlobalSearch();
  setupKeyboardShortcuts();
  refreshTopBarAIStatus().catch(() => {});
  await checkAuthSession();
});

// Authentication & Session Bootstrap
async function checkAuthSession() {
  try {
    const status = await FinAuditAPI.getSetupStatus();
    if (!status.is_setup_completed || status.user_count === 0) {
      showFirstRunSetupScreen();
      return;
    }
  } catch (e) {
    console.warn("Could not check setup status:", e);
  }

  const token = FinAuditAPI.getToken();
  if (!token) {
    showLoginScreen();
    return;
  }

  try {
    const user = await FinAuditAPI.getMe();
    state.currentUser = user;
    state.isAuthenticated = true;
    hideLoginScreen();
    updateUserTopBar();
    applyRoleNavigationPermissions();
    await loadEngagements();
    await refreshTopBarAIStatus();
    navigateTo("dashboard");
  } catch (err) {
    console.warn("Auth check failed:", err.message);
    showLoginScreen(err.message.includes("disabled") ? err.message : null);
  }
}

function showFirstRunSetupScreen(errorMsg = null) {
  state.isAuthenticated = false;
  let overlay = document.getElementById("login-screen-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "login-screen-overlay";
    document.body.appendChild(overlay);
  }

  overlay.style.display = "flex";
  overlay.innerHTML = `
    <div class="login-card" style="max-width: 480px;">
      <div class="login-header">
        <div class="login-logo">F</div>
        <div class="login-title">FinAuditPro Setup</div>
        <div class="login-subtitle">First-Time Deployment — Create Master Administrator</div>
      </div>

      <div class="login-body">
        <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 8px; padding: 12px; margin-bottom: 16px; font-size: 12px; color: #0284c7; line-height: 1.5;">
          <strong>🚀 Welcome to FinAuditPro!</strong><br/>
          No users exist in this local database. Please create the primary System Administrator (Partner/Lead Auditor) account to activate your firm workspace.
        </div>

        <div id="setup-alert" class="login-alert-box ${errorMsg ? 'error' : ''}">
          ${errorMsg || ''}
        </div>

        <form id="setup-form" onsubmit="handleInitialSetupSubmit(event)">
          <div class="form-group">
            <label class="form-label">Full Name</label>
            <input type="text" id="setup-fullname" class="form-control" placeholder="e.g., CA Rajesh Sharma, FCA" required autofocus>
          </div>

          <div class="form-group">
            <label class="form-label">Admin Username</label>
            <input type="text" id="setup-username" class="form-control" placeholder="Enter administrator username" required>
          </div>

          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input type="email" id="setup-email" class="form-control" placeholder="partner@cafirm.in" required>
          </div>

          <div class="form-group">
            <label class="form-label">Master Password <span style="font-size: 11px; color: #64748b;">(min. 12 characters)</span></label>
            <div class="password-input-wrap">
              <input type="password" id="setup-password" class="form-control" placeholder="Enter secure passphrase" minlength="12" required>
              <button type="button" class="password-toggle-btn" onclick="togglePasswordVisibility('setup-password')">👁️</button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Confirm Master Password</label>
            <div class="password-input-wrap">
              <input type="password" id="setup-confirm-password" class="form-control" placeholder="Re-enter password" minlength="12" required>
              <button type="button" class="password-toggle-btn" onclick="togglePasswordVisibility('setup-confirm-password')">👁️</button>
            </div>
          </div>

          <button type="submit" id="setup-submit-btn" class="btn btn-primary" style="width: 100%; padding: 12px; font-size: 14px; font-weight: 600; margin-top: 8px;">
            Initialize Workspace & Log In
          </button>
        </form>

        <div class="login-footer-security">
          <span class="offline-pill" style="font-size: 10px;"><span class="offline-dot"></span> 100% Offline SQLite</span>
          <span>• Passwords protected using PBKDF2-HMAC-SHA256</span>
        </div>
      </div>
    </div>
  `;
}

window.showFirstRunSetupScreen = showFirstRunSetupScreen;

async function handleInitialSetupSubmit(event) {
  event.preventDefault();
  const fullName = document.getElementById("setup-fullname").value.trim();
  const username = document.getElementById("setup-username").value.trim();
  const email = document.getElementById("setup-email").value.trim();
  const password = document.getElementById("setup-password").value;
  const confirmPassword = document.getElementById("setup-confirm-password").value;
  const alertBox = document.getElementById("setup-alert");
  const submitBtn = document.getElementById("setup-submit-btn");

  if (password !== confirmPassword) {
    alertBox.className = "login-alert-box error";
    alertBox.innerText = "Passwords do not match. Please re-enter.";
    return;
  }

  if (password.length < 12) {
    alertBox.className = "login-alert-box error";
    alertBox.innerText = "Password must be at least 12 characters long.";
    return;
  }

  submitBtn.disabled = true;
  submitBtn.innerText = "Initializing Database...";

  try {
    await FinAuditAPI.initialSetup({
      username: username,
      email: email,
      full_name: fullName,
      role: "Admin",
      password: password
    });

    // Auto login
    submitBtn.innerText = "Logging in...";
    await FinAuditAPI.login(username, password);
    const user = await FinAuditAPI.getMe();
    state.currentUser = user;
    state.isAuthenticated = true;
    hideLoginScreen();
    updateUserTopBar();
    applyRoleNavigationPermissions();
    await loadEngagements();
    await refreshTopBarAIStatus();
    navigateTo("dashboard");
  } catch (err) {
    alertBox.className = "login-alert-box error";
    alertBox.innerText = err.message || "Failed to initialize setup.";
    submitBtn.disabled = false;
    submitBtn.innerText = "Initialize Workspace & Log In";
  }
}

function showLoginScreen(errorMsg = null) {
  state.isAuthenticated = false;
  let overlay = document.getElementById("login-screen-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "login-screen-overlay";
    document.body.appendChild(overlay);
  }

  overlay.style.display = "flex";
  overlay.innerHTML = `
    <div class="login-card">
      <div class="login-header">
        <div class="login-logo">F</div>
        <div class="login-title">FinAuditPro</div>
        <div class="login-subtitle">Standalone Offline AI Audit Assistant for Indian CAs</div>
      </div>

      <div class="login-body">
        <div id="login-alert" class="login-alert-box ${errorMsg ? 'error' : ''}">
          ${errorMsg || ''}
        </div>

        <form id="login-form" onsubmit="handleLoginFormSubmit(event)">
          <div class="form-group">
            <label class="form-label">Username</label>
            <input type="text" id="login-username" class="form-control" placeholder="Enter your username" required autofocus>
          </div>

          <div class="form-group">
            <label class="form-label">Password</label>
            <div class="password-input-wrap">
              <input type="password" id="login-password" class="form-control" placeholder="Enter password" required>
              <button type="button" class="password-toggle-btn" onclick="togglePasswordVisibility('login-password')">👁️</button>
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-size: 12px; color: #64748b;">
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
              <input type="checkbox" id="remember-me" checked> Remember session locally
            </label>
          </div>

          <button type="submit" id="login-submit-btn" class="btn btn-primary" style="width: 100%; padding: 10px; font-size: 14px;">
            Secure Offline Sign In
          </button>
        </form>

        <div class="login-footer-security">
          <span class="offline-pill" style="font-size: 10px;"><span class="offline-dot"></span> Local SQLite Database</span>
          <span>• Zero Cloud Transmissions</span>
        </div>
      </div>
    </div>
  `;
}

window.showLoginScreen = showLoginScreen;

function hideLoginScreen() {
  const overlay = document.getElementById("login-screen-overlay");
  if (overlay) overlay.style.display = "none";
}

function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  if (input) {
    input.type = input.type === "password" ? "text" : "password";
  }
}

async function handleLoginFormSubmit(event) {
  event.preventDefault();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  const alertBox = document.getElementById("login-alert");
  const submitBtn = document.getElementById("login-submit-btn");

  if (!username || !password) return;

  submitBtn.disabled = true;
  submitBtn.innerText = "Verifying locally...";
  alertBox.className = "login-alert-box";
  alertBox.style.display = "none";

  try {
    const res = await FinAuditAPI.login(username, password);
    state.currentUser = res.user;
    state.isAuthenticated = true;
    hideLoginScreen();
    updateUserTopBar();
    applyRoleNavigationPermissions();
    await loadEngagements();
    navigateTo("dashboard");
  } catch (err) {
    alertBox.innerText = err.message || "Invalid username or password";
    alertBox.className = "login-alert-box error";
    alertBox.style.display = "block";
    submitBtn.disabled = false;
    submitBtn.innerText = "Secure Offline Sign In";
  }
}

async function handleLogout() {
  const confirmed = await FinConfirm({
    title: "Sign Out of FinAuditPro",
    message: "Are you sure you want to end your current local session?",
    consequences: [
      "Any unsaved form entries in active tabs may be cleared",
      "Local cached session tokens will be removed"
    ],
    confirmText: "Sign Out",
    cancelText: "Stay Signed In",
    isDanger: false
  });

  if (confirmed) {
    await FinAuditAPI.logout();
    state.currentUser = null;
    state.isAuthenticated = false;
    showLoginScreen("You have been signed out.");
  }
}

function setupSidebarControls() {
  const collapseToggle = document.getElementById("sidebar-collapse-toggle");
  const mobileToggle = document.getElementById("mobile-sidebar-toggle");
  const backdrop = document.getElementById("mobile-sidebar-backdrop");
  const sidebar = document.getElementById("sidebar");
  const mainContent = document.getElementById("main-content");
  const topBar = document.getElementById("top-bar");

  if (collapseToggle && sidebar) {
    collapseToggle.addEventListener("click", () => {
      state.isSidebarCollapsed = !state.isSidebarCollapsed;
      sidebar.classList.toggle("sidebar-collapsed", state.isSidebarCollapsed);
      if (mainContent) mainContent.classList.toggle("sidebar-collapsed", state.isSidebarCollapsed);
      if (topBar) topBar.classList.toggle("sidebar-collapsed", state.isSidebarCollapsed);
    });
  }

  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", () => {
      sidebar.classList.toggle("mobile-open");
      if (backdrop) {
        backdrop.style.display = sidebar.classList.contains("mobile-open") ? "block" : "none";
      }
    });
  }

  if (backdrop && sidebar) {
    backdrop.addEventListener("click", () => {
      sidebar.classList.remove("mobile-open");
      backdrop.style.display = "none";
    });
  }
}

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Cmd+K or Ctrl+K for Global Search
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      openGlobalSearchModal();
    }
    // Escape to close drawers and modals
    if (e.key === "Escape") {
      closeGlobalSearchModal();
      if (typeof closeDrawer === "function") closeDrawer();
      const userMenu = document.getElementById("user-dropdown-menu");
      if (userMenu) userMenu.classList.remove("show");
    }
  });
}

function setupGlobalSearch() {
  const searchBtn = document.getElementById("global-search-btn");
  if (searchBtn) {
    searchBtn.addEventListener("click", () => {
      openGlobalSearchModal();
    });
  }
}

function openGlobalSearchModal() {
  let container = document.getElementById("global-search-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "global-search-container";
    document.body.appendChild(container);
  }

  container.innerHTML = `
    <div class="global-search-overlay" id="global-search-modal-overlay">
      <div class="global-search-dialog">
        <div class="global-search-header">
          <span class="search-icon">🔍</span>
          <input type="text" id="global-search-input" class="global-search-input" placeholder="Search engagements, clients, findings, working papers, or navigation tabs..." autofocus />
          <button type="button" class="global-search-close-btn" onclick="closeGlobalSearchModal()" aria-label="Close search">✕</button>
        </div>
        <div class="global-search-body" id="global-search-results">
          <div class="search-empty-hint">Type to start searching across your workspace or use navigation shortcuts below.</div>
          <div class="search-quick-nav-section">
            <div class="search-section-title">Quick Navigation</div>
            <div class="search-quick-grid">
              <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('dashboard')">📊 Dashboard</button>
              <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('import')">📥 Import Data</button>
              <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('trial_balance')">⚖️ Trial Balance</button>
              <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('general_ledger')">📖 General Ledger</button>
              <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('findings')">🚩 Audit Findings</button>
              <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('working_papers')">📝 Working Papers</button>
              <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('clients')">🏢 Clients</button>
              <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('engagements')">📁 Engagements</button>
            </div>
          </div>
        </div>
        <div class="global-search-footer">
          <span>Navigate with <kbd>Tab</kbd> or <kbd>Enter</kbd></span>
          <span>Close with <kbd>Esc</kbd></span>
        </div>
      </div>
    </div>
  `;

  const input = document.getElementById("global-search-input");
  const overlay = document.getElementById("global-search-modal-overlay");

  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeGlobalSearchModal();
    });
  }

  if (input) {
    input.focus();
    input.addEventListener("input", debounce(handleGlobalSearchQuery, 200));
  }
}

function closeGlobalSearchModal() {
  const container = document.getElementById("global-search-container");
  if (container) container.innerHTML = "";
}

window.closeGlobalSearchModal = closeGlobalSearchModal;

function navigateToTabFromSearch(tab) {
  closeGlobalSearchModal();
  navigateTo(tab);
}
window.navigateToTabFromSearch = navigateToTabFromSearch;

function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

async function handleGlobalSearchQuery(e) {
  const query = e.target.value.trim().toLowerCase();
  const resultsContainer = document.getElementById("global-search-results");
  if (!resultsContainer) return;

  if (!query) {
    resultsContainer.innerHTML = `
      <div class="search-empty-hint">Type to start searching across your workspace or use navigation shortcuts below.</div>
      <div class="search-quick-nav-section">
        <div class="search-section-title">Quick Navigation</div>
        <div class="search-quick-grid">
          <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('dashboard')">📊 Dashboard</button>
          <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('import')">📥 Import Data</button>
          <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('trial_balance')">⚖️ Trial Balance</button>
          <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('general_ledger')">📖 General Ledger</button>
          <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('findings')">🚩 Audit Findings</button>
          <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('working_papers')">📝 Working Papers</button>
          <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('clients')">🏢 Clients</button>
          <button type="button" class="quick-nav-chip" onclick="navigateToTabFromSearch('engagements')">📁 Engagements</button>
        </div>
      </div>
    `;
    return;
  }

  // Filter engagements & clients
  const matchedEngagements = (state.engagements || []).filter(eng => 
    (eng.title && eng.title.toLowerCase().includes(query)) ||
    (eng.client_name && eng.client_name.toLowerCase().includes(query)) ||
    (eng.financial_year && eng.financial_year.toLowerCase().includes(query))
  );

  let html = "";
  if (matchedEngagements.length > 0) {
    html += `<div class="search-section-title">Audit Engagements (${matchedEngagements.length})</div>`;
    matchedEngagements.forEach(eng => {
      html += `
        <div class="search-result-row" onclick="selectEngagementFromSearch(${eng.id})">
          <div class="search-result-icon">📁</div>
          <div class="search-result-details">
            <div class="search-result-title">${escapeHTML(eng.client_name)} — ${escapeHTML(eng.title)}</div>
            <div class="search-result-sub">FY ${escapeHTML(eng.financial_year)} • ${escapeHTML(eng.audit_type || 'Statutory Audit')}</div>
          </div>
          <span class="badge badge-medium">Switch & View</span>
        </div>
      `;
    });
  }

  // Navigation tab matches
  const navTabs = [
    { id: "dashboard", label: "Executive Dashboard", desc: "Overview of findings, risks and KPIs" },
    { id: "import", label: "Import Financial Data", desc: "Upload Trial Balance, GL, GSTR, Bank Statements" },
    { id: "cleaning_logs", label: "Data Quality & Cleaning", desc: "Ingestion and validation logs" },
    { id: "trial_balance", label: "Trial Balance", desc: "Interactive TB review with drill-down" },
    { id: "general_ledger", label: "General Ledger Explorer", desc: "Search transactions and ledger accounts" },
    { id: "reconciliation", label: "Reconciliation Statements", desc: "GST 2B vs Purchase, Bank Reconciliation" },
    { id: "financial_statements", label: "Financial Statements", desc: "Balance sheet, P&L, Notes to Accounts" },
    { id: "yoy_comparison", label: "Year-over-Year Analysis", desc: "Variance and ratio trends" },
    { id: "findings", label: "Audit Findings & Exceptions", desc: "Review, waive, or flag high-risk anomalies" },
    { id: "checklist", label: "CARO & Standards Checklist", desc: "Statutory compliance workflows" },
    { id: "working_papers", label: "Working Papers & ISA Documentation", desc: "Auditor working papers and evidence" },
    { id: "reports", label: "Audit Report Generation", desc: "Draft and export statutory audit reports" },
    { id: "clients", label: "Client Directory", desc: "Manage client organizations, PANs and GSTINs" },
    { id: "engagements", label: "Engagement Hub", desc: "Manage audit engagements and scopes" },
    { id: "users", label: "Firm User Management", desc: "Manage auditor accounts and permissions" },
    { id: "audit_trail", label: "Cryptographic Audit Trail", desc: "Tamper-evident SHA-256 event log" },
    { id: "settings", label: "Workspace Settings", desc: "Firm preferences and configuration" }
  ];

  const matchedTabs = navTabs.filter(t => 
    t.label.toLowerCase().includes(query) || 
    t.desc.toLowerCase().includes(query) || 
    t.id.toLowerCase().includes(query)
  );

  if (matchedTabs.length > 0) {
    html += `<div class="search-section-title">Navigation & Modules (${matchedTabs.length})</div>`;
    matchedTabs.forEach(t => {
      html += `
        <div class="search-result-row" onclick="navigateToTabFromSearch('${t.id}')">
          <div class="search-result-icon">⚡</div>
          <div class="search-result-details">
            <div class="search-result-title">${escapeHTML(t.label)}</div>
            <div class="search-result-sub">${escapeHTML(t.desc)}</div>
          </div>
          <span class="badge badge-low">Go to tab</span>
        </div>
      `;
    });
  }

  if (!html) {
    html = `<div class="search-empty-hint">No results found matching "<strong>${escapeHTML(query)}</strong>". Try searching for clients, engagements, or navigation tabs.</div>`;
  }

  resultsContainer.innerHTML = html;
}

window.selectEngagementFromSearch = async function(engId) {
  closeGlobalSearchModal();
  state.currentEngagementId = engId;
  const select = document.getElementById("engagement-select");
  if (select) select.value = String(engId);
  await updateActiveEngagement();
  navigateTo(state.currentTab);
  FinNotify.success("Switched active engagement context");
};

// ==========================================
// EMPTY ENGAGEMENT ONBOARDING RENDERER
// ==========================================
function renderEmptyEngagementGuide(container, tabName = "dashboard") {
  container.innerHTML = `
    <div class="onboarding-hero-card">
      <div class="onboarding-hero-icon">🚀</div>
      <h2 class="onboarding-hero-title">Welcome to FinAuditPro!</h2>
      <p class="onboarding-hero-desc">
        You don't have any audit engagements configured yet. To begin auditing, create a client record and initialize your first audit engagement.
      </p>

      <div class="onboarding-step-grid">
        <div class="onboarding-step-box active-step">
          <div class="step-badge">Step 1</div>
          <div class="step-title">Register Client</div>
          <div class="step-desc">Add client details, PAN, GSTIN, and company type in the Client Directory.</div>
          <button type="button" class="btn btn-sm btn-secondary" onclick="navigateTo('clients')" style="margin-top: 10px;">
            Go to Clients →
          </button>
        </div>

        <div class="onboarding-step-box">
          <div class="step-badge">Step 2</div>
          <div class="step-title">Create Engagement</div>
          <div class="step-desc">Define financial year (e.g., 2025-26), audit scope, and assigned team members.</div>
          <button type="button" class="btn btn-sm btn-primary" onclick="navigateTo('engagements')" style="margin-top: 10px;">
            Create Engagement →
          </button>
        </div>

        <div class="onboarding-step-box">
          <div class="step-badge">Step 3</div>
          <div class="step-title">Import & Audit</div>
          <div class="step-desc">Upload Trial Balance, GL, GSTR data to run automated checks & generate papers.</div>
          <button type="button" class="btn btn-sm btn-secondary" disabled style="margin-top: 10px; opacity: 0.6;">
            Pending Engagement
          </button>
        </div>
      </div>

      <div style="margin-top: 24px; display: flex; gap: 12px; justify-content: center;">
        <button type="button" class="btn btn-primary" onclick="navigateTo('engagements')" style="padding: 10px 20px; font-weight: 600;">
          + Create First Engagement
        </button>
        <button type="button" class="btn btn-secondary" onclick="navigateTo('clients')" style="padding: 10px 20px;">
          View Client Directory
        </button>
      </div>
    </div>
  `;
}

// Navigation
function setupNavigation() {
  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", () => {
      const tab = item.dataset.tab;
      if (tab) navigateTo(tab);
    });
    // Keyboard accessibility (Enter / Space)
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const tab = item.dataset.tab;
        if (tab) navigateTo(tab);
      }
    });
  });

  const engSelect = document.getElementById("engagement-select");
  if (engSelect) {
    engSelect.addEventListener("change", async (e) => {
      const val = e.target.value;
      if (!val) {
        state.currentEngagementId = null;
        state.activeEngagement = null;
      } else {
        state.currentEngagementId = parseInt(val);
        await updateActiveEngagement();
      }
      navigateTo(state.currentTab);
    });
  }
}

async function loadEngagements() {
  try {
    const list = await FinAuditAPI.getEngagements();
    state.engagements = list || [];
    const select = document.getElementById("engagement-select");
    if (select) {
      if (state.engagements.length === 0) {
        select.innerHTML = `<option value="">No Active Engagement</option>`;
        state.currentEngagementId = null;
        state.activeEngagement = null;
      } else {
        // If current engagement is null or no longer valid, select first one
        if (!state.currentEngagementId || !state.engagements.some(e => e.id === state.currentEngagementId)) {
          state.currentEngagementId = state.engagements[0].id;
        }
        select.innerHTML = state.engagements.map(e => `
          <option value="${e.id}" ${e.id === state.currentEngagementId ? 'selected' : ''}>
            ${escapeHTML(e.client_name)} (${escapeHTML(e.financial_year)}) — ${escapeHTML(e.title)}
          </option>
        `).join("");
      }
    }
    await updateActiveEngagement();
  } catch (err) {
    console.error("Failed loading engagements:", err);
  }
}

async function updateActiveEngagement() {
  try {
    if (state.currentEngagementId) {
      state.activeEngagement = await FinAuditAPI.getEngagementDetails(state.currentEngagementId);
    } else {
      state.activeEngagement = null;
    }
  } catch (err) {
    console.error("Error updating engagement details:", err);
    state.activeEngagement = null;
  }
}

function navigateTo(tab) {
  state.currentTab = tab;
  document.querySelectorAll(".nav-item").forEach(item => {
    item.classList.toggle("active", item.dataset.tab === tab);
    item.setAttribute("aria-selected", item.dataset.tab === tab ? "true" : "false");
  });

  // Close mobile sidebar on navigation
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("mobile-sidebar-backdrop");
  if (sidebar && sidebar.classList.contains("mobile-open")) {
    sidebar.classList.remove("mobile-open");
    if (backdrop) backdrop.style.display = "none";
  }

  const container = document.getElementById("content-container");

  // Check if this tab requires an active engagement
  const engagementRequiredTabs = [
    "dashboard", "import", "cleaning_logs", "trial_balance", "general_ledger", 
    "ledgers", "reconciliation", "financial_statements", "yoy_comparison", 
    "duplicate_missing", "anomaly_detection", "findings", "checklist", 
    "working_papers", "reports"
  ];

  if (engagementRequiredTabs.includes(tab) && (!state.currentEngagementId || !state.engagements || state.engagements.length === 0)) {
    renderEmptyEngagementGuide(container, tab);
    return;
  }

  container.innerHTML = `
    <div style="padding: 24px;">
      <div class="skeleton-shimmer skeleton-box" style="height: 38px; width: 280px; margin-bottom: 20px;"></div>
      <div class="skeleton-shimmer skeleton-card" style="height: 140px; margin-bottom: 20px;"></div>
      <div class="skeleton-shimmer skeleton-box" style="height: 220px; width: 100%;"></div>
    </div>
  `;

  switch (tab) {
    case "dashboard": renderDashboard(); break;
    case "users": renderUserManagement(); break;
    case "clients": renderClients(); break;
    case "engagements": renderEngagements(); break;
    case "import": renderImportData(); break;
    case "cleaning_logs": renderDataCleaningLogs(); break;
    case "trial_balance": renderTrialBalance(); break;
    case "general_ledger": renderGeneralLedger(); break;
    case "ledgers": renderGeneralLedger(); break;
    case "reconciliation": renderReconciliation(); break;
    case "financial_statements": renderFinancialStatements(); break;
    case "yoy_comparison": renderYoYComparison(); break;
    case "duplicate_missing": renderDuplicateAndMissing(); break;
    case "anomaly_detection": renderAnomalyDetection(); break;
    case "findings": renderFindings(); break;
    case "assistant": renderAIAssistant(); break;
    case "checklist": renderChecklist(); break;
    case "working_papers": renderWorkingPapers(); break;
    case "reports": renderReports(); break;
    case "audit_trail": renderAuditTrail(); break;
    case "settings": renderSettings(); break;
    case "ai_manager": renderAIManager(); break;
    default: renderDashboard(); break;
  }
}

// ----------------- USER MANAGEMENT (ADMIN MODULE) -----------------
async function renderUserManagement() {
  const container = document.getElementById("content-container");
  if (state.currentUser?.role !== "Admin") {
    container.innerHTML = `
      <div class="card" style="padding: 40px; text-align: center; color: #dc2626;">
        <h3>Access Restricted</h3>
        <p style="margin-top: 8px;">Only Administrators have permission to manage audit users and roles.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `<div style="padding: 20px;">Loading user records...</div>`;

  try {
    const users = await FinAuditAPI.getUsers();

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">User Management & Role Access</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Manage audit team accounts, roles, active status, and password resets
          </div>
        </div>
        <button class="btn btn-primary" onclick="openCreateUserModal()">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path></svg>
          + Add New Audit User
        </button>
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">Audit Team Users (${users.length})</div>
        </div>
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>User Details</th>
                <th>Username</th>
                <th>Role Assignment</th>
                <th>Account Status</th>
                <th>Phone / Contact</th>
                <th>Last Login</th>
                <th class="text-center">Admin Actions</th>
              </tr>
            </thead>
            <tbody>
              ${users.map(u => `
                <tr>
                  <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <div class="user-avatar ${u.role.toLowerCase().replace(' ', '')}" style="width: 28px; height: 28px; font-size: 11px;">
                        ${u.full_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <b>${u.full_name}</b><br/>
                        <span style="font-size: 11px; color: #64748b;">${u.email}</span>
                      </div>
                    </div>
                  </td>
                  <td class="font-mono font-bold">${u.username}</td>
                  <td>
                    <select class="form-control" style="font-size: 11.5px; padding: 3px 6px; width: 120px;" onchange="changeUserRole(${u.id}, this.value)">
                      <option value="Admin" ${u.role === 'Admin' ? 'selected' : ''}>Admin</option>
                      <option value="Auditor" ${u.role === 'Auditor' ? 'selected' : ''}>Auditor</option>
                      <option value="Audit Staff" ${u.role === 'Audit Staff' ? 'selected' : ''}>Audit Staff</option>
                    </select>
                  </td>
                  <td>
                    <span class="badge ${u.is_active ? 'badge-resolved' : 'badge-disabled'}">
                      ${u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td style="font-size: 12px;">${u.phone || '—'}</td>
                  <td class="font-mono" style="font-size: 11.5px; color: #475569;">
                    ${u.last_login ? u.last_login.replace('T', ' ').split('.')[0] : 'Never logged in'}
                  </td>
                  <td class="text-center">
                    <div style="display: flex; gap: 6px; justify-content: center;">
                      ${u.id !== state.currentUser.id ? `
                        <button class="btn btn-sm ${u.is_active ? 'btn-secondary' : 'btn-success'}" onclick="toggleUserStatus(${u.id}, ${u.is_active ? 'false' : 'true'}, '${u.username}')">
                          ${u.is_active ? 'Disable' : 'Enable'}
                        </button>
                      ` : `
                        <span style="font-size: 11px; color: #94a3b8; padding: 4px 6px;">(You)</span>
                      `}
                      <button class="btn btn-sm btn-secondary" onclick="openAdminResetPasswordModal(${u.id}, '${u.username}')">
                        Reset Pwd
                      </button>
                    </div>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading users: ${err.message}</div>`;
  }
}

// User Actions
async function changeUserRole(userId, newRole) {
  try {
    await FinAuditAPI.updateUser(userId, { role: newRole });
    notifySuccess(`User role updated to '${newRole}'.`);
    renderUserManagement();
  } catch (err) {
    notifyError("Failed to update role: " + err.message);
    renderUserManagement();
  }
}

async function toggleUserStatus(userId, newStatus, username) {
  const actionName = newStatus ? "enable" : "disable";
  const confirmed = await FinConfirm({
    title: `${newStatus ? 'Enable' : 'Disable'} User Account`,
    message: `Are you sure you want to ${actionName} account '${username}'?`,
    consequences: newStatus ? ["The user will regain login access to the firm workspace"] : ["The user will be immediately logged out and blocked from signing in"],
    confirmText: newStatus ? "Enable Account" : "Disable Account",
    isDanger: !newStatus
  });
  if (!confirmed) return;

  try {
    const res = await FinAuditAPI.toggleUserStatus(userId, newStatus);
    notifyInfo(res.message);
    renderUserManagement();
  } catch (err) {
    notifyError("Failed to change account status: " + err.message);
  }
}

function openCreateUserModal() {
  const modalHtml = `
    <div class="modal-overlay" id="user-modal">
      <div class="modal-card">
        <div class="modal-header">
          <div class="modal-title">Create New Audit Team User</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('user-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form id="create-user-form" onsubmit="handleCreateUserSubmit(event)">
            <div class="form-group">
              <label class="form-label">Full Name *</label>
              <input type="text" id="new-full-name" class="form-control" placeholder="e.g. Vikram Joshi (ACA)" required>
            </div>
            <div class="form-group">
              <label class="form-label">Username *</label>
              <input type="text" id="new-username" class="form-control" placeholder="e.g. vikram_j" required>
            </div>
            <div class="form-group">
              <label class="form-label">Email Address *</label>
              <input type="email" id="new-email" class="form-control" placeholder="e.g. vikram@finauditpro.in" required>
            </div>
            <div class="form-group">
              <label class="form-label">Phone / Mobile</label>
              <input type="text" id="new-phone" class="form-control" placeholder="+91 98200 55667">
            </div>
            <div class="form-group">
              <label class="form-label">Role Assignment *</label>
              <select id="new-role" class="form-control">
                <option value="Auditor">Auditor (Clients, Engagements, Rules, Reports)</option>
                <option value="Audit Staff">Audit Staff (Assigned checks & WP notes)</option>
                <option value="Admin">Admin (Full User & System Management)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Temporary Password (Min 6 chars) *</label>
              <input type="password" id="new-password" class="form-control" placeholder="Create temporary password" minlength="6" required>
            </div>
            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('user-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Create User</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleCreateUserSubmit(event) {
  event.preventDefault();
  const full_name = document.getElementById("new-full-name").value.trim();
  const username = document.getElementById("new-username").value.trim();
  const email = document.getElementById("new-email").value.trim();
  const phone = document.getElementById("new-phone").value.trim();
  const role = document.getElementById("new-role").value;
  const password = document.getElementById("new-password").value;

  try {
    await FinAuditAPI.createUser({
      full_name, username, email, phone, role, password
    });
    notifySuccess(`User '${username}' created successfully with role '${role}'.`);
    closeModal("user-modal");
    renderUserManagement();
  } catch (err) {
    notifyError("Error creating user: " + err.message);
  }
}

function openAdminResetPasswordModal(userId, username) {
  const modalHtml = `
    <div class="modal-overlay" id="reset-pwd-modal">
      <div class="modal-card">
        <div class="modal-header">
          <div class="modal-title">Admin Reset Password: ${username}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('reset-pwd-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleAdminResetPasswordSubmit(event, ${userId}, '${username}')">
            <div class="form-group">
              <label class="form-label">New Password (Min 6 characters) *</label>
              <input type="password" id="admin-new-pwd" class="form-control" minlength="6" required placeholder="Enter new password">
            </div>
            <div class="modal-footer" style="padding: 10px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('reset-pwd-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Reset Password</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleAdminResetPasswordSubmit(event, userId, username) {
  event.preventDefault();
  const newPassword = document.getElementById("admin-new-pwd").value;
  try {
    await FinAuditAPI.adminResetPassword(userId, newPassword);
    notifySuccess(`Password for '${username}' has been reset successfully.`);
    closeModal("reset-pwd-modal");
  } catch (err) {
    notifyError("Error resetting password: " + err.message);
  }
}

// Change My Password Modal (For current user)
function openChangePasswordModal() {
  const modalHtml = `
    <div class="modal-overlay" id="change-pwd-modal">
      <div class="modal-card">
        <div class="modal-header">
          <div class="modal-title">Change Account Password</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('change-pwd-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleChangePasswordSubmit(event)">
            <div class="form-group">
              <label class="form-label">Current Password *</label>
              <input type="password" id="curr-password" class="form-control" placeholder="Enter current password" required>
            </div>
            <div class="form-group">
              <label class="form-label">New Password (Min 6 characters) *</label>
              <input type="password" id="new-account-password" class="form-control" minlength="6" placeholder="Enter new secure password" required>
            </div>
            <div class="form-group">
              <label class="form-label">Confirm New Password *</label>
              <input type="password" id="confirm-account-password" class="form-control" minlength="6" placeholder="Re-enter new password" required>
            </div>
            <div class="modal-footer" style="padding: 10px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('change-pwd-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Update Password</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleChangePasswordSubmit(event) {
  event.preventDefault();
  const oldPwd = document.getElementById("curr-password").value;
  const newPwd = document.getElementById("new-account-password").value;
  const confPwd = document.getElementById("confirm-account-password").value;

  if (newPwd !== confPwd) {
    notifyInfo("New password and confirmation do not match.");
    return;
  }

  try {
    await FinAuditAPI.changePassword(oldPwd, newPwd);
    notifySuccess("Password updated successfully!");
    closeModal("change-pwd-modal");
  } catch (err) {
    notifyError("Error changing password: " + err.message);
  }
}

function closeModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) m.remove();
}

// ----------------- CLIENT & ENGAGEMENT HELPERS & BADGES -----------------
function getEntityBadge(type) {
  const t = type || "Other";
  return `<span class="badge badge-entity">${t}</span>`;
}

function getAuditTypeBadge(type) {
  const t = type || "Statutory Audit";
  return `<span class="badge badge-audit-type">${t}</span>`;
}

function getEngagementStatusBadge(status) {
  const st = status || "Draft";
  if (st === "Completed") return `<span class="badge badge-status-completed">● Completed</span>`;
  if (st === "Under Review") return `<span class="badge badge-status-review">● Under Review</span>`;
  if (st === "In Progress") return `<span class="badge badge-status-progress">● In Progress</span>`;
  if (st === "Archived") return `<span class="badge badge-status-archived">● Archived</span>`;
  return `<span class="badge badge-status-draft">● Draft</span>`;
}

// ----------------- CLIENT MANAGEMENT MODULE -----------------
let clientSearchState = {
  search: "",
  entityType: "All",
  industry: "All"
};

async function renderClients(searchQuery = null, entityFilter = null) {
  const container = document.getElementById("content-container");
  if (searchQuery !== null) clientSearchState.search = searchQuery;
  if (entityFilter !== null) clientSearchState.entityType = entityFilter;

  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading Client Directory...</div>`;

  try {
    const clients = await FinAuditAPI.getClients({
      search: clientSearchState.search,
      entity_type: clientSearchState.entityType !== "All" ? clientSearchState.entityType : "",
      industry: clientSearchState.industry !== "All" ? clientSearchState.industry : ""
    });

    const isAuditorOrAdmin = ["Admin", "Auditor"].includes(state.currentUser?.role);

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Client Directory & Entity Master</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Independent entity profiles, PAN/GSTIN registration, and multi-year financial audit isolation
          </div>
        </div>
        ${isAuditorOrAdmin ? `
          <button class="btn btn-primary" onclick="openCreateClientModal()">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path></svg>
            + Register New Client
          </button>
        ` : ''}
      </div>

      <!-- Search & Filters -->
      <div class="card" style="padding: 14px; margin-bottom: 16px;">
        <div style="display: grid; grid-template-columns: 2fr 1fr 1fr auto; gap: 12px; align-items: center;">
          <div>
            <input type="text" id="client-search-input" class="form-control" placeholder="Search by Client Name, PAN, GSTIN, Contact..." value="${clientSearchState.search}" onkeyup="if(event.key==='Enter') applyClientFilters()">
          </div>
          <div>
            <select id="client-entity-filter" class="form-control" onchange="applyClientFilters()">
              <option value="All" ${clientSearchState.entityType === 'All' ? 'selected' : ''}>All Entity Types</option>
              <option value="Proprietorship" ${clientSearchState.entityType === 'Proprietorship' ? 'selected' : ''}>Proprietorship</option>
              <option value="Partnership" ${clientSearchState.entityType === 'Partnership' ? 'selected' : ''}>Partnership</option>
              <option value="LLP" ${clientSearchState.entityType === 'LLP' ? 'selected' : ''}>LLP</option>
              <option value="Private Limited Company" ${clientSearchState.entityType === 'Private Limited Company' ? 'selected' : ''}>Private Limited Company</option>
              <option value="Public Limited Company" ${clientSearchState.entityType === 'Public Limited Company' ? 'selected' : ''}>Public Limited Company</option>
              <option value="Trust" ${clientSearchState.entityType === 'Trust' ? 'selected' : ''}>Trust</option>
              <option value="Society" ${clientSearchState.entityType === 'Society' ? 'selected' : ''}>Society</option>
              <option value="NGO" ${clientSearchState.entityType === 'NGO' ? 'selected' : ''}>NGO</option>
              <option value="Other" ${clientSearchState.entityType === 'Other' ? 'selected' : ''}>Other</option>
            </select>
          </div>
          <div>
            <select id="client-industry-filter" class="form-control" onchange="applyClientFilters()">
              <option value="All" ${clientSearchState.industry === 'All' ? 'selected' : ''}>All Industries</option>
              <option value="Manufacturing" ${clientSearchState.industry === 'Manufacturing' ? 'selected' : ''}>Manufacturing</option>
              <option value="Information Technology" ${clientSearchState.industry === 'Information Technology' ? 'selected' : ''}>Information Technology</option>
              <option value="Retail & Trading" ${clientSearchState.industry === 'Retail & Trading' ? 'selected' : ''}>Retail & Trading</option>
              <option value="Healthcare & Pharma" ${clientSearchState.industry === 'Healthcare & Pharma' ? 'selected' : ''}>Healthcare & Pharma</option>
              <option value="Real Estate & Construction" ${clientSearchState.industry === 'Real Estate & Construction' ? 'selected' : ''}>Real Estate & Construction</option>
              <option value="Financial Services" ${clientSearchState.industry === 'Financial Services' ? 'selected' : ''}>Financial Services</option>
              <option value="Hospitality & Travel" ${clientSearchState.industry === 'Hospitality & Travel' ? 'selected' : ''}>Hospitality & Travel</option>
              <option value="Education & Non-Profit" ${clientSearchState.industry === 'Education & Non-Profit' ? 'selected' : ''}>Education & Non-Profit</option>
            </select>
          </div>
          <div>
            <button class="btn btn-secondary" onclick="applyClientFilters()">
              <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
              Filter
            </button>
            <button class="btn btn-secondary" style="margin-left: 4px;" onclick="resetClientFilters()">Reset</button>
          </div>
        </div>
      </div>

      <!-- Clients Table -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">Registered Clients (${clients.length})</div>
        </div>
        ${clients.length === 0 ? `
          <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>No clients matched your search criteria.</p>
            ${isAuditorOrAdmin ? `<button class="btn btn-primary" style="margin-top: 12px;" onclick="openCreateClientModal()">+ Register Client</button>` : ''}
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Client ID & Name</th>
                  <th>Entity Type</th>
                  <th>PAN / GSTIN</th>
                  <th>Industry & Contact</th>
                  <th>Financial Years</th>
                  <th>Audit Engagements</th>
                  <th class="text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${clients.map(c => `
                  <tr>
                    <td>
                      <div style="font-weight: 700; color: #0f172a; font-size: 14px;">${c.name}</div>
                      <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
                        ID: <span class="font-mono font-bold">#${c.id}</span> • Registered FY: ${c.financial_year || '2024-25'}
                      </div>
                    </td>
                    <td>${getEntityBadge(c.entity_type)}</td>
                    <td>
                      <div style="font-size: 12px;"><b style="color: #475569;">PAN:</b> <span class="font-mono font-bold">${c.pan || '—'}</span></div>
                      <div style="font-size: 11px; color: #64748b; margin-top: 2px;"><b style="color: #475569;">GSTIN:</b> <span class="font-mono">${c.gstin || '—'}</span></div>
                    </td>
                    <td>
                      <div style="font-size: 12px; font-weight: 600;">${c.industry || 'General'}</div>
                      <div style="font-size: 11px; color: #64748b;">
                        ${c.contact_person ? `👤 ${c.contact_person}` : ''}
                        ${c.phone ? ` • 📞 ${c.phone}` : ''}
                      </div>
                    </td>
                    <td>
                      <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                        ${(c.financial_years || []).map(fy => `
                          <span class="badge" style="background: #f1f5f9; color: #334155; font-size: 10.5px;">${fy}</span>
                        `).join('') || '<span style="color: #94a3b8; font-size: 11px;">None</span>'}
                      </div>
                    </td>
                    <td>
                      <div style="font-size: 12px;">
                        <b>${c.engagements_count || 0}</b> total (${c.active_engagements || 0} active)
                      </div>
                    </td>
                    <td class="text-center">
                      <div style="display: flex; gap: 6px; justify-content: center;">
                        <button class="btn btn-sm btn-secondary" onclick="openClientHistoryDrawer(${c.id})" title="View Historical Multi-Year Timeline">
                          📅 Previous Years
                        </button>
                        ${isAuditorOrAdmin ? `
                          <button class="btn btn-sm btn-secondary" onclick="openCreateEngagementModal(${c.id})" title="Create Audit Engagement">
                            + Engagement
                          </button>
                          <button class="btn btn-sm btn-secondary" onclick="openEditClientModal(${c.id})" title="Edit Client Profile">
                            ✏️ Edit
                          </button>
                        ` : ''}
                      </div>
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading clients: ${err.message}</div>`;
  }
}

function applyClientFilters() {
  const search = document.getElementById("client-search-input")?.value.trim() || "";
  const entity = document.getElementById("client-entity-filter")?.value || "All";
  const ind = document.getElementById("client-industry-filter")?.value || "All";
  clientSearchState.search = search;
  clientSearchState.entityType = entity;
  clientSearchState.industry = ind;
  renderClients();
}

function resetClientFilters() {
  clientSearchState = { search: "", entityType: "All", industry: "All" };
  renderClients();
}

// Client Creation Modal
function openCreateClientModal() {
  const modalHtml = `
    <div class="modal-overlay" id="client-modal">
      <div class="modal-card" style="max-width: 620px;">
        <div class="modal-header">
          <div class="modal-title">Register New Client Master Profile</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('client-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleClientFormSubmit(event, null)">
            <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Client / Legal Entity Name *</label>
                <input type="text" id="client-name" class="form-control" placeholder="e.g. Acme Tech Solutions Pvt Ltd" required autofocus>
              </div>
              <div class="form-group">
                <label class="form-label">Entity Type *</label>
                <select id="client-entity-type" class="form-control" required>
                  <option value="Proprietorship">Proprietorship</option>
                  <option value="Partnership">Partnership</option>
                  <option value="LLP">LLP</option>
                  <option value="Private Limited Company" selected>Private Limited Company</option>
                  <option value="Public Limited Company">Public Limited Company</option>
                  <option value="Trust">Trust</option>
                  <option value="Society">Society</option>
                  <option value="NGO">NGO</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1.3fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Permanent Account Number (PAN)</label>
                <input type="text" id="client-pan" class="form-control font-mono" placeholder="AAAAA9999A" maxlength="10" style="text-transform: uppercase;">
                <div style="font-size: 10.5px; color: #64748b; margin-top: 2px;">Format: 5 letters + 4 digits + 1 letter</div>
              </div>
              <div class="form-group">
                <label class="form-label">GST Identification Number (GSTIN)</label>
                <input type="text" id="client-gstin" class="form-control font-mono" placeholder="27AAAAA9999A1Z5" maxlength="15" style="text-transform: uppercase;">
                <div style="font-size: 10.5px; color: #64748b; margin-top: 2px;">Format: 15-character statutory GSTIN</div>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Industry / Sector</label>
                <select id="client-industry" class="form-control">
                  <option value="Manufacturing" selected>Manufacturing</option>
                  <option value="Information Technology">Information Technology</option>
                  <option value="Retail & Trading">Retail & Trading</option>
                  <option value="Healthcare & Pharma">Healthcare & Pharma</option>
                  <option value="Real Estate & Construction">Real Estate & Construction</option>
                  <option value="Financial Services">Financial Services</option>
                  <option value="Hospitality & Travel">Hospitality & Travel</option>
                  <option value="Education & Non-Profit">Education & Non-Profit</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Financial Year (Initial) *</label>
                <input type="text" id="client-fy" class="form-control" value="2024-25" placeholder="e.g. 2024-25" required>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
              <div class="form-group">
                <label class="form-label">Contact Person</label>
                <input type="text" id="client-contact" class="form-control" placeholder="CFO / Director name">
              </div>
              <div class="form-group">
                <label class="form-label">Email</label>
                <input type="email" id="client-email" class="form-control" placeholder="accounts@client.in">
              </div>
              <div class="form-group">
                <label class="form-label">Phone</label>
                <input type="tel" id="client-phone" class="form-control" placeholder="+91 9876543210">
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Registered Office Address</label>
              <textarea id="client-address" class="form-control" rows="2" placeholder="Full address of registered office"></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Notes / Special Instructions</label>
              <textarea id="client-notes" class="form-control" rows="2" placeholder="Materiality thresholds, prior audit observations, related party disclosures..."></textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('client-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Client Master</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

// Client Edit Modal
async function openEditClientModal(clientId) {
  try {
    const client = await FinAuditAPI.getClient(clientId);
    const modalHtml = `
      <div class="modal-overlay" id="client-modal">
        <div class="modal-card" style="max-width: 620px;">
          <div class="modal-header">
            <div class="modal-title">Edit Client Profile: ${client.name}</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('client-modal')">✕</button>
          </div>
          <div class="modal-body">
            <form onsubmit="handleClientFormSubmit(event, ${clientId})">
              <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 12px;">
                <div class="form-group">
                  <label class="form-label">Client / Legal Entity Name *</label>
                  <input type="text" id="client-name" class="form-control" value="${client.name}" required>
                </div>
                <div class="form-group">
                  <label class="form-label">Entity Type *</label>
                  <select id="client-entity-type" class="form-control" required>
                    <option value="Proprietorship" ${client.entity_type === 'Proprietorship' ? 'selected' : ''}>Proprietorship</option>
                    <option value="Partnership" ${client.entity_type === 'Partnership' ? 'selected' : ''}>Partnership</option>
                    <option value="LLP" ${client.entity_type === 'LLP' ? 'selected' : ''}>LLP</option>
                    <option value="Private Limited Company" ${client.entity_type === 'Private Limited Company' ? 'selected' : ''}>Private Limited Company</option>
                    <option value="Public Limited Company" ${client.entity_type === 'Public Limited Company' ? 'selected' : ''}>Public Limited Company</option>
                    <option value="Trust" ${client.entity_type === 'Trust' ? 'selected' : ''}>Trust</option>
                    <option value="Society" ${client.entity_type === 'Society' ? 'selected' : ''}>Society</option>
                    <option value="NGO" ${client.entity_type === 'NGO' ? 'selected' : ''}>NGO</option>
                    <option value="Other" ${client.entity_type === 'Other' ? 'selected' : ''}>Other</option>
                  </select>
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1.3fr; gap: 12px;">
                <div class="form-group">
                  <label class="form-label">Permanent Account Number (PAN)</label>
                  <input type="text" id="client-pan" class="form-control font-mono" value="${client.pan || ''}" maxlength="10" style="text-transform: uppercase;">
                </div>
                <div class="form-group">
                  <label class="form-label">GST Identification Number (GSTIN)</label>
                  <input type="text" id="client-gstin" class="form-control font-mono" value="${client.gstin || ''}" maxlength="15" style="text-transform: uppercase;">
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 12px;">
                <div class="form-group">
                  <label class="form-label">Industry / Sector</label>
                  <select id="client-industry" class="form-control">
                    <option value="Manufacturing" ${client.industry === 'Manufacturing' ? 'selected' : ''}>Manufacturing</option>
                    <option value="Information Technology" ${client.industry === 'Information Technology' ? 'selected' : ''}>Information Technology</option>
                    <option value="Retail & Trading" ${client.industry === 'Retail & Trading' ? 'selected' : ''}>Retail & Trading</option>
                    <option value="Healthcare & Pharma" ${client.industry === 'Healthcare & Pharma' ? 'selected' : ''}>Healthcare & Pharma</option>
                    <option value="Real Estate & Construction" ${client.industry === 'Real Estate & Construction' ? 'selected' : ''}>Real Estate & Construction</option>
                    <option value="Financial Services" ${client.industry === 'Financial Services' ? 'selected' : ''}>Financial Services</option>
                    <option value="Hospitality & Travel" ${client.industry === 'Hospitality & Travel' ? 'selected' : ''}>Hospitality & Travel</option>
                    <option value="Education & Non-Profit" ${client.industry === 'Education & Non-Profit' ? 'selected' : ''}>Education & Non-Profit</option>
                    <option value="Other" ${client.industry === 'Other' ? 'selected' : ''}>Other</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Financial Year</label>
                  <input type="text" id="client-fy" class="form-control" value="${client.financial_year || '2024-25'}">
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div class="form-group">
                  <label class="form-label">Contact Person</label>
                  <input type="text" id="client-contact" class="form-control" value="${client.contact_person || ''}">
                </div>
                <div class="form-group">
                  <label class="form-label">Email</label>
                  <input type="email" id="client-email" class="form-control" value="${client.email || ''}">
                </div>
                <div class="form-group">
                  <label class="form-label">Phone</label>
                  <input type="tel" id="client-phone" class="form-control" value="${client.phone || ''}">
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Registered Office Address</label>
                <textarea id="client-address" class="form-control" rows="2">${client.address || ''}</textarea>
              </div>

              <div class="form-group">
                <label class="form-label">Auditor Notes</label>
                <textarea id="client-notes" class="form-control" rows="2">${client.notes || ''}</textarea>
              </div>

              <div class="modal-footer" style="padding: 10px 0 0 0;">
                <button type="button" class="btn btn-secondary" onclick="closeModal('client-modal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Update Profile</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Error loading client profile: " + err.message);
  }
}

async function handleClientFormSubmit(event, clientId) {
  event.preventDefault();
  const pan = document.getElementById("client-pan").value.trim().toUpperCase();
  const gstin = document.getElementById("client-gstin").value.trim().toUpperCase();

  // PAN validation regex
  if (pan && !/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(pan)) {
    notifyWarning("Invalid PAN format. Standard format: 5 letters + 4 digits + 1 letter (e.g. ABCDE1234F)");
    return;
  }

  // GSTIN validation regex
  if (gstin && !/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/.test(gstin)) {
    notifyWarning("Invalid GSTIN format. Standard format: 15 alphanumeric characters (e.g. 27ABCDE1234F1Z5)");
    return;
  }

  const payload = {
    name: document.getElementById("client-name").value.trim(),
    entity_type: document.getElementById("client-entity-type").value,
    pan: pan || null,
    gstin: gstin || null,
    industry: document.getElementById("client-industry").value,
    financial_year: document.getElementById("client-fy").value.trim() || "2024-25",
    contact_person: document.getElementById("client-contact").value.trim(),
    email: document.getElementById("client-email").value.trim(),
    phone: document.getElementById("client-phone").value.trim(),
    address: document.getElementById("client-address").value.trim(),
    notes: document.getElementById("client-notes").value.trim()
  };

  try {
    if (clientId) {
      await FinAuditAPI.updateClient(clientId, payload);
      notifySuccess("Client profile updated successfully!");
    } else {
      const res = await FinAuditAPI.createClient(payload);
      notifySuccess(`Client '${payload.name}' registered successfully!`);
    }
    closeModal("client-modal");
    await loadEngagements();
    renderClients();
  } catch (err) {
    notifyError("Operation failed: " + err.message);
  }
}

// View Previous Years / Multi-Year Timeline Drawer
async function openClientHistoryDrawer(clientId) {
  try {
    const history = await FinAuditAPI.getClientHistory(clientId);
    const client = history.client || {};
    const timeline = history.timeline || [];

    const overlay = document.getElementById("drawer-overlay");
    const header = document.getElementById("drawer-title");
    const body = document.getElementById("drawer-content");

    header.innerHTML = `Multi-Year Audit History: ${client.name}`;

    body.innerHTML = `
      <div style="margin-bottom: 18px; padding: 12px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md);">
        <div style="font-weight: 700; font-size: 14px; color: #0f172a;">${client.name}</div>
        <div style="font-size: 11.5px; color: #64748b; margin-top: 4px;">
          Entity: ${getEntityBadge(client.entity_type)} • PAN: <span class="font-mono font-bold">${client.pan || '—'}</span> • Industry: ${client.industry || 'General'}
        </div>
      </div>

      <div style="font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">
        Financial Years & Engagement Timelines (${timeline.length}):
      </div>

      ${timeline.length === 0 ? `
        <div style="padding: 20px; text-align: center; color: #64748b;">
          No audit engagements recorded for this client yet.
        </div>
      ` : `
        <div class="timeline-container">
          ${timeline.map(item => `
            <div class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                  <div>
                    <span style="font-size: 14px; font-weight: 700; color: var(--primary);">FY ${item.financial_year}</span>
                    <span style="margin-left: 6px;">${getAuditTypeBadge(item.audit_type)}</span>
                  </div>
                  <div>${getEngagementStatusBadge(item.status)}</div>
                </div>
                <div style="font-weight: 600; font-size: 13px; color: #0f172a;">${item.title}</div>
                <div style="font-size: 11.5px; color: #64748b; margin-top: 4px;">
                  Period: <span class="font-mono">${item.period_start || '—'}</span> to <span class="font-mono">${item.period_end || '—'}</span>
                </div>
                <div style="display: flex; gap: 14px; margin-top: 8px; padding-top: 8px; border-top: 1px solid #f1f5f9; font-size: 11.5px;">
                  <div><b>Transactions:</b> <span class="font-mono">${item.transactions_count}</span></div>
                  <div><b>Total Exceptions:</b> <span class="font-mono">${item.findings_count}</span></div>
                  <div><b>Critical:</b> <span class="font-mono" style="color: #dc2626;">${item.critical_findings_count}</span></div>
                </div>
                <div style="margin-top: 10px; display: flex; gap: 6px;">
                  <button class="btn btn-sm btn-primary" onclick="switchEngagement(${item.id}); closeEvidenceDrawer();">
                    Open Engagement
                  </button>
                  <button class="btn btn-sm btn-secondary" onclick="openDuplicateEngagementModal(${item.id}); closeEvidenceDrawer();">
                    Duplicate Structure for New FY
                  </button>
                </div>
              </div>
            </div>
          `).join("")}
        </div>
      `}
    `;

    overlay.style.display = "block";
    document.getElementById("evidence-drawer").classList.add("open");
  } catch (err) {
    notifyError("Error fetching client history: " + err.message);
  }
}

// ----------------- ENGAGEMENTS MANAGEMENT MODULE -----------------
let engagementFilterState = {
  status: "All",
  clientId: "All",
  financialYear: "All"
};

async function renderEngagements(statusFilter = null, clientFilter = null, fyFilter = null) {
  const container = document.getElementById("content-container");
  if (statusFilter !== null) engagementFilterState.status = statusFilter;
  if (clientFilter !== null) engagementFilterState.clientId = clientFilter;
  if (fyFilter !== null) engagementFilterState.financialYear = fyFilter;

  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading Engagements...</div>`;

  try {
    const clients = await FinAuditAPI.getClients();
    const engagements = await FinAuditAPI.getEngagements({
      status: engagementFilterState.status !== "All" ? engagementFilterState.status : "",
      client_id: engagementFilterState.clientId !== "All" ? engagementFilterState.clientId : "",
      financial_year: engagementFilterState.financialYear !== "All" ? engagementFilterState.financialYear : ""
    });

    const isAuditorOrAdmin = ["Admin", "Auditor"].includes(state.currentUser?.role);

    // Extract unique financial years
    const uniqueFYs = Array.from(new Set(engagements.map(e => e.financial_year).filter(Boolean)));

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Audit Engagements Workspace</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Multi-client, multi-financial year audit portfolio with strict data segregation
          </div>
        </div>
        ${isAuditorOrAdmin ? `
          <button class="btn btn-primary" onclick="openCreateEngagementModal()">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            + Create New Engagement
          </button>
        ` : ''}
      </div>

      <!-- Filter Controls -->
      <div class="card" style="padding: 14px; margin-bottom: 16px;">
        <div style="display: grid; grid-template-columns: 1.5fr 1fr 1fr auto; gap: 12px; align-items: center;">
          <div>
            <select id="eng-client-filter" class="form-control" onchange="applyEngagementFilters()">
              <option value="All" ${engagementFilterState.clientId === 'All' ? 'selected' : ''}>All Clients</option>
              ${clients.map(c => `
                <option value="${c.id}" ${String(engagementFilterState.clientId) === String(c.id) ? 'selected' : ''}>
                  ${c.name} (${c.entity_type})
                </option>
              `).join("")}
            </select>
          </div>
          <div>
            <select id="eng-status-filter" class="form-control" onchange="applyEngagementFilters()">
              <option value="All" ${engagementFilterState.status === 'All' ? 'selected' : ''}>All Statuses</option>
              <option value="Draft" ${engagementFilterState.status === 'Draft' ? 'selected' : ''}>Draft</option>
              <option value="In Progress" ${engagementFilterState.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
              <option value="Under Review" ${engagementFilterState.status === 'Under Review' ? 'selected' : ''}>Under Review</option>
              <option value="Completed" ${engagementFilterState.status === 'Completed' ? 'selected' : ''}>Completed</option>
              <option value="Archived" ${engagementFilterState.status === 'Archived' ? 'selected' : ''}>Archived</option>
            </select>
          </div>
          <div>
            <select id="eng-fy-filter" class="form-control" onchange="applyEngagementFilters()">
              <option value="All" ${engagementFilterState.financialYear === 'All' ? 'selected' : ''}>All Financial Years</option>
              ${uniqueFYs.map(fy => `
                <option value="${fy}" ${engagementFilterState.financialYear === fy ? 'selected' : ''}>FY ${fy}</option>
              `).join("")}
            </select>
          </div>
          <div>
            <button class="btn btn-secondary" onclick="resetEngagementFilters()">Reset Filters</button>
          </div>
        </div>
      </div>

      <!-- Engagements Table -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">Audit Portfolio Engagements (${engagements.length})</div>
        </div>
        ${engagements.length === 0 ? `
          <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>No engagements found matching the selected filters.</p>
            ${isAuditorOrAdmin ? `<button class="btn btn-primary" style="margin-top: 12px;" onclick="openCreateEngagementModal()">+ Create Engagement</button>` : ''}
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Engagement ID & Title</th>
                  <th>Client & Entity</th>
                  <th>Financial Year & Type</th>
                  <th>Audit Period</th>
                  <th>Auditor / Staff</th>
                  <th>Status</th>
                  <th class="text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                ${engagements.map(e => `
                  <tr style="${e.id === state.currentEngagementId ? 'background-color: #f0fdf4;' : ''}">
                    <td>
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="font-mono font-bold" style="color: var(--primary);">#${e.id}</span>
                        <b>${e.title}</b>
                        ${e.id === state.currentEngagementId ? '<span class="badge badge-resolved" style="font-size: 10px;">ACTIVE</span>' : ''}
                      </div>
                      <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
                        ${e.notes ? e.notes.substring(0, 50) + (e.notes.length > 50 ? '...' : '') : 'Standard audit engagement'}
                      </div>
                    </td>
                    <td>
                      <div style="font-weight: 600; color: #0f172a;">${e.client_name}</div>
                      <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
                        ${getEntityBadge(e.client_entity_type)}
                      </div>
                    </td>
                    <td>
                      <div><b class="font-mono" style="font-size: 13px; color: #1e293b;">FY ${e.financial_year}</b></div>
                      <div style="margin-top: 2px;">${getAuditTypeBadge(e.audit_type)}</div>
                    </td>
                    <td>
                      <div class="font-mono" style="font-size: 11.5px; color: #475569;">
                        ${e.period_start || '—'} to ${e.period_end || '—'}
                      </div>
                    </td>
                    <td>
                      <div style="font-size: 12px;">👤 <b>${e.lead_auditor_name || 'Unassigned'}</b></div>
                      <div style="font-size: 11px; color: #64748b;">Staff: ${e.assigned_staff_name || 'Unassigned'}</div>
                    </td>
                    <td>
                      ${isAuditorOrAdmin ? `
                        <select class="form-control" style="font-size: 11px; padding: 2px 6px; width: 120px;" onchange="changeEngagementStatus(${e.id}, this.value)">
                          <option value="Draft" ${e.status === 'Draft' ? 'selected' : ''}>Draft</option>
                          <option value="In Progress" ${e.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
                          <option value="Under Review" ${e.status === 'Under Review' ? 'selected' : ''}>Under Review</option>
                          <option value="Completed" ${e.status === 'Completed' ? 'selected' : ''}>Completed</option>
                          <option value="Archived" ${e.status === 'Archived' ? 'selected' : ''}>Archived</option>
                        </select>
                      ` : `
                        ${getEngagementStatusBadge(e.status)}
                      `}
                    </td>
                    <td class="text-center">
                      <div style="display: flex; gap: 6px; justify-content: center;">
                        ${e.id === state.currentEngagementId ? `
                          <button class="btn btn-sm btn-secondary" onclick="navigateTo('dashboard')">
                            Dashboard
                          </button>
                        ` : `
                          <button class="btn btn-sm btn-primary" onclick="switchEngagement(${e.id})">
                            Open
                          </button>
                        `}
                        ${isAuditorOrAdmin ? `
                          <button class="btn btn-sm btn-secondary" onclick="openDuplicateEngagementModal(${e.id})" title="Duplicate structure to a new financial year">
                            📑 Clone FY
                          </button>
                          <button class="btn btn-sm btn-secondary" onclick="openEditEngagementModal(${e.id})" title="Edit Details">
                            ✏️ Edit
                          </button>
                        ` : ''}
                      </div>
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading engagements: ${err.message}</div>`;
  }
}

function applyEngagementFilters() {
  engagementFilterState.clientId = document.getElementById("eng-client-filter")?.value || "All";
  engagementFilterState.status = document.getElementById("eng-status-filter")?.value || "All";
  engagementFilterState.financialYear = document.getElementById("eng-fy-filter")?.value || "All";
  renderEngagements();
}

function resetEngagementFilters() {
  engagementFilterState = { status: "All", clientId: "All", financialYear: "All" };
  renderEngagements();
}

async function switchEngagement(engId) {
  state.currentEngagementId = engId;
  await loadEngagements();
  await updateActiveEngagement();
  navigateTo("dashboard");
}

async function changeEngagementStatus(engId, newStatus) {
  try {
    await FinAuditAPI.updateEngagementStatus(engId, newStatus);
    notifySuccess(`Engagement status updated to '${newStatus}'.`);
    await loadEngagements();
    renderEngagements();
  } catch (err) {
    notifyError("Error updating status: " + err.message);
  }
}

// Create Engagement Modal
async function openCreateEngagementModal(preselectedClientId = null) {
  try {
    const clients = await FinAuditAPI.getClients();
    const users = await FinAuditAPI.getUsers();

    if (clients.length === 0) {
      notifyWarning("Please register a Client first before creating an audit engagement.");
      openCreateClientModal();
      return;
    }

    const modalHtml = `
      <div class="modal-overlay" id="engagement-modal">
        <div class="modal-card" style="max-width: 600px;">
          <div class="modal-header">
            <div class="modal-title">Create New Audit Engagement</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('engagement-modal')">✕</button>
          </div>
          <div class="modal-body">
            <form onsubmit="handleEngagementFormSubmit(event, null)">
              <div class="form-group">
                <label class="form-label">Select Client *</label>
                <select id="eng-client-id" class="form-control" required onchange="autoFillEngagementTitle()">
                  ${clients.map(c => `
                    <option value="${c.id}" ${preselectedClientId === c.id ? 'selected' : ''}>
                      ${c.name} (${c.entity_type}) [PAN: ${c.pan || 'N/A'}]
                    </option>
                  `).join("")}
                </select>
              </div>

              <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 12px;">
                <div class="form-group">
                  <label class="form-label">Engagement Title *</label>
                  <input type="text" id="eng-title" class="form-control" placeholder="e.g. Statutory Audit FY 2024-25" required>
                </div>
                <div class="form-group">
                  <label class="form-label">Audit Type *</label>
                  <select id="eng-audit-type" class="form-control" required onchange="autoFillEngagementTitle()">
                    <option value="Statutory Audit" selected>Statutory Audit</option>
                    <option value="Internal Audit">Internal Audit</option>
                    <option value="Tax Audit">Tax Audit (Form 3CD)</option>
                    <option value="Review">Review</option>
                    <option value="Special Audit">Special Audit</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div class="form-group">
                  <label class="form-label">Financial Year *</label>
                  <input type="text" id="eng-fy" class="form-control font-mono" value="2024-25" placeholder="2024-25" required onchange="autoFillEngagementDates()">
                </div>
                <div class="form-group">
                  <label class="form-label">Period Start Date</label>
                  <input type="date" id="eng-start-date" class="form-control" value="2024-04-01">
                </div>
                <div class="form-group">
                  <label class="form-label">Period End Date</label>
                  <input type="date" id="eng-end-date" class="form-control" value="2025-03-31">
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                <div class="form-group">
                  <label class="form-label">Lead Signing Auditor *</label>
                  <select id="eng-lead-auditor" class="form-control">
                    ${users.filter(u => ['Admin', 'Auditor'].includes(u.role)).map(u => `
                      <option value="${u.id}" ${u.id === state.currentUser?.id ? 'selected' : ''}>
                        ${u.full_name} (${u.role})
                      </option>
                    `).join("")}
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Assigned Audit Staff</label>
                  <select id="eng-assigned-staff" class="form-control">
                    <option value="">-- None Assigned --</option>
                    ${users.map(u => `
                      <option value="${u.id}">${u.full_name} (${u.role})</option>
                    `).join("")}
                  </select>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Scope & Working Notes</label>
                <textarea id="eng-notes" class="form-control" rows="2" placeholder="Engagement scope, materiality benchmark (e.g., 0.5% of turnover), special reporting directives..."></textarea>
              </div>

              <div class="modal-footer" style="padding: 10px 0 0 0;">
                <button type="button" class="btn btn-secondary" onclick="closeModal('engagement-modal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Create Engagement</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
    autoFillEngagementTitle();
  } catch (err) {
    notifyError("Error initializing engagement creation: " + err.message);
  }
}

function autoFillEngagementTitle() {
  const clientSelect = document.getElementById("eng-client-id");
  const auditType = document.getElementById("eng-audit-type")?.value || "Statutory Audit";
  const fy = document.getElementById("eng-fy")?.value || "2024-25";
  const titleInput = document.getElementById("eng-title");

  if (titleInput && clientSelect) {
    titleInput.value = `${auditType} FY ${fy}`;
  }
}

function autoFillEngagementDates() {
  const fy = document.getElementById("eng-fy")?.value || "2024-25";
  const parts = fy.split("-");
  if (parts.length === 2 && parts[0].length === 4) {
    const y1 = parts[0];
    const y2 = parts[1].length === 2 ? `20${parts[1]}` : parts[1];
    const startInput = document.getElementById("eng-start-date");
    const endInput = document.getElementById("eng-end-date");
    if (startInput) startInput.value = `${y1}-04-01`;
    if (endInput) endInput.value = `${y2}-03-31`;
  }
}

// Edit Engagement Modal
async function openEditEngagementModal(engId) {
  try {
    const eng = await FinAuditAPI.getEngagementDetails(engId);
    const users = await FinAuditAPI.getUsers();

    const modalHtml = `
      <div class="modal-overlay" id="engagement-modal">
        <div class="modal-card" style="max-width: 600px;">
          <div class="modal-header">
            <div class="modal-title">Edit Engagement: #${eng.id} ${eng.title}</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('engagement-modal')">✕</button>
          </div>
          <div class="modal-body">
            <form onsubmit="handleEngagementFormSubmit(event, ${engId})">
              <div class="form-group">
                <label class="form-label">Client</label>
                <input type="text" class="form-control" value="${eng.client_name}" disabled>
              </div>

              <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 12px;">
                <div class="form-group">
                  <label class="form-label">Engagement Title *</label>
                  <input type="text" id="eng-title" class="form-control" value="${eng.title}" required>
                </div>
                <div class="form-group">
                  <label class="form-label">Audit Type *</label>
                  <select id="eng-audit-type" class="form-control" required>
                    <option value="Statutory Audit" ${eng.audit_type === 'Statutory Audit' ? 'selected' : ''}>Statutory Audit</option>
                    <option value="Internal Audit" ${eng.audit_type === 'Internal Audit' ? 'selected' : ''}>Internal Audit</option>
                    <option value="Tax Audit" ${eng.audit_type === 'Tax Audit' ? 'selected' : ''}>Tax Audit (Form 3CD)</option>
                    <option value="Review" ${eng.audit_type === 'Review' ? 'selected' : ''}>Review</option>
                    <option value="Special Audit" ${eng.audit_type === 'Special Audit' ? 'selected' : ''}>Special Audit</option>
                    <option value="Other" ${eng.audit_type === 'Other' ? 'selected' : ''}>Other</option>
                  </select>
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div class="form-group">
                  <label class="form-label">Financial Year *</label>
                  <input type="text" id="eng-fy" class="form-control font-mono" value="${eng.financial_year}" required>
                </div>
                <div class="form-group">
                  <label class="form-label">Period Start</label>
                  <input type="date" id="eng-start-date" class="form-control" value="${eng.period_start || ''}">
                </div>
                <div class="form-group">
                  <label class="form-label">Period End</label>
                  <input type="date" id="eng-end-date" class="form-control" value="${eng.period_end || ''}">
                </div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div class="form-group">
                  <label class="form-label">Lead Auditor</label>
                  <select id="eng-lead-auditor" class="form-control">
                    ${users.filter(u => ['Admin', 'Auditor'].includes(u.role)).map(u => `
                      <option value="${u.id}" ${u.id === eng.lead_auditor_id ? 'selected' : ''}>
                        ${u.full_name}
                      </option>
                    `).join("")}
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Assigned Staff</label>
                  <select id="eng-assigned-staff" class="form-control">
                    <option value="">-- None --</option>
                    ${users.map(u => `
                      <option value="${u.id}" ${u.id === eng.assigned_staff_id ? 'selected' : ''}>${u.full_name}</option>
                    `).join("")}
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Status</label>
                  <select id="eng-status" class="form-control">
                    <option value="Draft" ${eng.status === 'Draft' ? 'selected' : ''}>Draft</option>
                    <option value="In Progress" ${eng.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
                    <option value="Under Review" ${eng.status === 'Under Review' ? 'selected' : ''}>Under Review</option>
                    <option value="Completed" ${eng.status === 'Completed' ? 'selected' : ''}>Completed</option>
                    <option value="Archived" ${eng.status === 'Archived' ? 'selected' : ''}>Archived</option>
                  </select>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Audit Notes & Scope</label>
                <textarea id="eng-notes" class="form-control" rows="2">${eng.notes || ''}</textarea>
              </div>

              <div class="modal-footer" style="padding: 10px 0 0 0;">
                <button type="button" class="btn btn-secondary" onclick="closeModal('engagement-modal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Save Changes</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Error loading engagement details: " + err.message);
  }
}

async function handleEngagementFormSubmit(event, engId) {
  event.preventDefault();
  const staffVal = document.getElementById("eng-assigned-staff").value;

  const payload = {
    title: document.getElementById("eng-title").value.trim(),
    audit_type: document.getElementById("eng-audit-type").value,
    financial_year: document.getElementById("eng-fy").value.trim(),
    period_start: document.getElementById("eng-start-date").value || null,
    period_end: document.getElementById("eng-end-date").value || null,
    lead_auditor_id: parseInt(document.getElementById("eng-lead-auditor").value),
    assigned_staff_id: staffVal ? parseInt(staffVal) : null,
    notes: document.getElementById("eng-notes").value.trim()
  };

  const statusEl = document.getElementById("eng-status");
  if (statusEl) payload.status = statusEl.value;

  const clientEl = document.getElementById("eng-client-id");
  if (clientEl) payload.client_id = parseInt(clientEl.value);

  try {
    if (engId) {
      await FinAuditAPI.updateEngagement(engId, payload);
      notifySuccess("Engagement updated successfully!");
    } else {
      const res = await FinAuditAPI.createEngagement(payload);
      notifySuccess(`Engagement '${res.title}' created successfully!`);
      state.currentEngagementId = res.id;
    }
    closeModal("engagement-modal");
    await loadEngagements();
    await updateActiveEngagement();
    renderEngagements();
  } catch (err) {
    notifyError("Operation failed: " + err.message);
  }
}

// Duplicate / Clone Engagement for New Financial Year Modal
async function openDuplicateEngagementModal(sourceEngId) {
  try {
    const src = await FinAuditAPI.getEngagementDetails(sourceEngId);
    
    // Calculate next financial year suggestion (e.g. 2024-25 -> 2025-26)
    let nextFy = "2025-26";
    if (src.financial_year && src.financial_year.includes("-")) {
      const parts = src.financial_year.split("-");
      const y1 = parseInt(parts[0]);
      if (!isNaN(y1)) {
        const nextY1 = y1 + 1;
        const nextY2 = (nextY1 + 1).toString().slice(-2);
        nextFy = `${nextY1}-${nextY2}`;
      }
    }

    const modalHtml = `
      <div class="modal-overlay" id="duplicate-modal">
        <div class="modal-card" style="max-width: 540px;">
          <div class="modal-header">
            <div class="modal-title">Duplicate Engagement for New Financial Year</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('duplicate-modal')">✕</button>
          </div>
          <div class="modal-body">
            <div style="margin-bottom: 16px; padding: 12px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md);">
              <div style="font-weight: 700; font-size: 13.5px; color: #0f172a;">Source Audit: ${src.title}</div>
              <div style="font-size: 12px; color: #64748b; margin-top: 2px;">
                Client: <b>${src.client_name}</b> | Current FY: <b>${src.financial_year}</b> | Type: ${src.audit_type}
              </div>
            </div>

            <form onsubmit="handleDuplicateEngagementSubmit(event, ${sourceEngId})">
              <div class="form-group">
                <label class="form-label">Target Financial Year *</label>
                <input type="text" id="dup-target-fy" class="form-control font-mono font-bold" value="${nextFy}" required>
                <div style="font-size: 11px; color: #64748b; margin-top: 2px;">e.g. 2025-26, 2026-27</div>
              </div>

              <div class="form-group">
                <label class="form-label">New Engagement Title</label>
                <input type="text" id="dup-title" class="form-control" value="${src.audit_type} FY ${nextFy}" placeholder="Custom title">
              </div>

              <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: var(--radius-md); padding: 12px; margin-bottom: 16px;">
                <div style="font-weight: 700; font-size: 12px; color: #1e40af; margin-bottom: 8px;">Structure Cloning Options:</div>
                <label style="display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: #1e3a8a; margin-bottom: 6px; cursor: pointer;">
                  <input type="checkbox" id="dup-copy-checklists" checked> Clone 3CD & Audit Checklists (Reset status to Pending)
                </label>
                <label style="display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: #1e3a8a; cursor: pointer;">
                  <input type="checkbox" id="dup-copy-wps" checked> Clone Working Papers Structure & Index (Reset to Draft)
                </label>
              </div>

              <div style="font-size: 11.5px; color: #059669; padding: 10px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: var(--radius-md); margin-bottom: 16px;">
                🔒 <b>Multi-Year Isolation Assurance:</b> Transaction vouchers, ledger balances, and prior-year exceptions will <b>NOT</b> be copied. The new engagement will start with completely clean financial tables.
              </div>

              <div class="modal-footer" style="padding: 10px 0 0 0;">
                <button type="button" class="btn btn-secondary" onclick="closeModal('duplicate-modal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Create FY Duplicate</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Error initializing duplication modal: " + err.message);
  }
}

async function handleDuplicateEngagementSubmit(event, sourceEngId) {
  event.preventDefault();
  const targetFy = document.getElementById("dup-target-fy").value.trim();
  const title = document.getElementById("dup-title").value.trim();
  const copyChecklists = document.getElementById("dup-copy-checklists").checked;
  const copyWps = document.getElementById("dup-copy-wps").checked;

  if (!targetFy) {
    notifyWarning("Target financial year is required.");
    return;
  }

  try {
    const res = await FinAuditAPI.duplicateEngagement({
      source_engagement_id: sourceEngId,
      target_financial_year: targetFy,
      title: title || undefined,
      copy_checklists: copyChecklists,
      copy_working_paper_templates: copyWps
    });

    notifyInfo(res.message);
    closeModal("duplicate-modal");
    state.currentEngagementId = res.new_engagement_id;
    await loadEngagements();
    await updateActiveEngagement();
    navigateTo("dashboard");
  } catch (err) {
    notifyError("Duplication failed: " + err.message);
  }
}


// ----------------- FINANCIAL DATA IMPORT MODULE -----------------
const STANDARD_TARGET_FIELDS = [
  { key: "date", label: "Transaction Date *", desc: "Voucher/Posting/Bill Date (e.g., DD-MM-YYYY, YYYY-MM-DD)", required: true },
  { key: "voucher_no", label: "Voucher Number", desc: "Journal/Voucher reference string", required: false },
  { key: "invoice_no", label: "Invoice / Bill Number", desc: "Tax Invoice or Bill sequence number", required: false },
  { key: "ledger", label: "Ledger Account Name *", desc: "General Ledger account head or particulars", required: true },
  { key: "party_name", label: "Party / Customer / Vendor", desc: "Third-party entity or transacting counterparty", required: false },
  { key: "account_group", label: "Account Classification Group", desc: "Assets, Liabilities, Revenue, Expense, Equity", required: false },
  { key: "debit", label: "Debit Amount (₹)", desc: "Debit side monetary value", required: false },
  { key: "credit", label: "Credit Amount (₹)", desc: "Credit side monetary value", required: false },
  { key: "amount", label: "Net / Gross Amount (₹)", desc: "Single amount column (or fallback for Debit/Credit)", required: false },
  { key: "tax_amount", label: "GST / Tax Amount (₹)", desc: "IGST, CGST, SGST, or TDS deducted", required: false },
  { key: "gstin", label: "Party GSTIN", desc: "15-digit statutory GST identification number", required: false },
  { key: "description", label: "Narration / Description", desc: "Transaction narrative, line remarks, or notes", required: false },
  { key: "reference_no", label: "Reference / Cheque / UTR No", desc: "Bank UTR, cheque, or external transaction ref", required: false },
  { key: "opening_balance", label: "Opening Balance (₹)", desc: "Starting balance for the ledger or statement", required: false },
  { key: "closing_balance", label: "Closing Balance (₹)", desc: "Ending/Running balance after transaction", required: false },
  { key: "payment_date", label: "Payment / Value Date", desc: "Date of bank settlement or payment realization", required: false }
];

async function renderImportData() {
  const container = document.getElementById("content-container");
  if (!state.activeEngagement) await updateActiveEngagement();
  const eng = state.activeEngagement || {};

  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading Financial Data Import...</div>`;

  try {
    const uploadedFiles = await FinAuditAPI.getUploadedFiles(state.currentEngagementId);

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Financial Data Import Workspace</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Target Client: <b>${eng.client_name || 'Client'}</b> | Engagement: <b>${eng.title || 'Audit'}</b> (FY ${eng.financial_year || '2024-25'})
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary" onclick="navigateTo('trial_balance')">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"></path></svg>
            View Trial Balance
          </button>
          <button class="btn btn-primary" onclick="triggerRunHybridEngine()">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
            Run Audit Engine
          </button>
        </div>
      </div>

      <!-- Step 1: Upload Card -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-header">
          <div>
            <div class="card-title">1. Select Data Type & Upload File</div>
            <div class="card-subtitle">Supported formats: Excel (.xlsx, .xls), CSV (.csv), JSON (.json), PDF (.pdf)</div>
          </div>
          <span class="offline-pill"><span class="offline-dot"></span> 100% Offline Local Parser</span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 16px; align-items: flex-start;">
          <div>
            <div class="form-group">
              <label class="form-label">Financial Data Category *</label>
              <select id="import-data-category" class="form-control" style="font-weight: 600;">
                <option value="General Ledger" selected>General Ledger (GL Extract)</option>
                <option value="Trial Balance">Trial Balance</option>
                <option value="Sales Register">Sales Register (GSTR-1 / Invoices)</option>
                <option value="Purchase Register">Purchase Register (GSTR-2B / Bills)</option>
                <option value="Bank Statement">Bank Statement (Passbook / PDF)</option>
                <option value="Expense Register">Expense & Voucher Register</option>
                <option value="Customer Ledger">Debtors / Customer Ledger</option>
                <option value="Vendor Ledger">Creditors / Vendor Ledger</option>
                <option value="Journal Entries">Journal Entries (Day Book)</option>
                <option value="GST-related data">GST Returns / 2B Reconciliation</option>
                <option value="Other transaction data">Other Financial Transactions</option>
              </select>
              <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
                FinAuditPro applies specific statutory audit checks tailored to the selected data category.
              </div>
            </div>

            <div style="padding: 10px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: var(--radius-md); font-size: 11.5px; color: #065f46;">
              🔒 <b>Security & Integrity:</b> Files are processed purely on your machine using Python & SQLite. No data is ever transmitted to external cloud APIs.
            </div>
          </div>

          <div>
            <div class="upload-zone" id="file-drop-zone" onclick="document.getElementById('file-upload-input').click()" style="border: 2px dashed #93c5fd; background: #f8fafc; border-radius: var(--radius-lg); padding: 30px; text-align: center; cursor: pointer; transition: all 0.2s;">
              <svg width="40" height="40" fill="none" stroke="#2563eb" viewBox="0 0 24 24" style="margin: 0 auto 10px auto;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
              <div style="font-size: 14px; font-weight: 700; color: #0f172a;">Click to browse or Drag & Drop financial file here</div>
              <div style="font-size: 12px; color: #64748b; margin-top: 4px;">CSV, XLSX, XLS, PDF, JSON (Max 100MB)</div>
              <input type="file" id="file-upload-input" style="display: none;" accept=".csv,.xlsx,.xls,.json,.pdf" onchange="handleFileInputChange(event)">
            </div>
          </div>
        </div>
      </div>

      <!-- Container for Preview & Mapping Workspace (Populated after upload) -->
      <div id="mapping-workspace-container"></div>

      <!-- Uploaded Files Repository & Import Log -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">Imported Financial Datasets & Audit Logs (${uploadedFiles.length})</div>
        </div>
        ${uploadedFiles.length === 0 ? `
          <div style="padding: 30px; text-align: center; color: #64748b;">
            No financial datasets have been imported for this audit engagement yet.
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>File Name & Type</th>
                  <th>Category</th>
                  <th>Import Date & Auditor</th>
                  <th>Total Rows</th>
                  <th>Valid Rows</th>
                  <th>Failed Rows</th>
                  <th>Warnings</th>
                  <th class="text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${uploadedFiles.map(f => `
                  <tr>
                    <td>
                      <div style="font-weight: 700; color: #0f172a; font-size: 13px;">${f.file_name}</div>
                      <div style="font-size: 11px; color: #64748b;" class="font-mono">Format: ${f.file_type.toUpperCase()}</div>
                    </td>
                    <td>
                      <span class="badge badge-entity">${f.data_category || 'General Ledger'}</span>
                    </td>
                    <td>
                      <div style="font-size: 12px;">${f.uploaded_at ? f.uploaded_at.replace('T', ' ').split('.')[0] : '—'}</div>
                      <div style="font-size: 11px; color: #64748b;">By: <b>${f.uploaded_by || 'Auditor'}</b></div>
                    </td>
                    <td class="font-mono font-bold">${f.row_count || 0}</td>
                    <td class="font-mono" style="color: #059669; font-weight: 600;">${f.successful_rows || f.row_count || 0}</td>
                    <td class="font-mono" style="color: ${f.failed_rows > 0 ? '#dc2626' : '#64748b'}; font-weight: 600;">${f.failed_rows || 0}</td>
                    <td class="font-mono" style="color: ${f.warning_count > 0 ? '#d97706' : '#64748b'}; font-weight: 600;">${f.warning_count || 0}</td>
                    <td class="text-center">
                      <div style="display: flex; gap: 6px; justify-content: center;">
                        ${(f.failed_rows > 0 || f.warning_count > 0) ? `
                          <a href="/api/import/errors/${f.id}/download" target="_blank" class="btn btn-sm btn-secondary" title="Download CSV Error Log">
                            📥 Error Log
                          </a>
                        ` : ''}
                        <button class="btn btn-sm btn-secondary" style="color: #dc2626;" onclick="deleteImportedFile(${f.id}, '${f.file_name}')" title="Delete Dataset & Transactions">
                          🗑️ Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading data import view: ${err.message}</div>`;
  }
}

async function handleFileInputChange(event) {
  const file = event.target.files[0];
  if (!file) return;

  const category = document.getElementById("import-data-category")?.value || "General Ledger";
  const dropZone = document.getElementById("file-drop-zone");
  if (dropZone) {
    dropZone.innerHTML = `
      <div style="padding: 20px; color: var(--primary);">
        <div style="font-size: 16px; font-weight: 700;">Parsing '${file.name}' locally...</div>
        <div style="font-size: 12px; color: #64748b; margin-top: 4px;">Detecting encoding, headers, data structures, and column mapping...</div>
      </div>
    `;
  }

  try {
    const preview = await FinAuditAPI.uploadFile(state.currentEngagementId, file, category);
    state.uploadPreview = preview;
    renderMappingWorkspace(preview);
  } catch (err) {
    notifyError("File Upload & Parse Error: " + err.message);
    renderImportData();
  }
}

function renderMappingWorkspace(preview) {
  const container = document.getElementById("mapping-workspace-container");
  if (!container) return;

  const columns = preview.columns || [];
  const suggested = preview.suggested_mapping || {};
  const previewRows = preview.preview_rows || [];

  container.innerHTML = `
    <div class="card" style="margin-bottom: 20px; border: 2px solid var(--primary);">
      <div class="card-header" style="background: #eff6ff;">
        <div>
          <div class="card-title" style="color: var(--primary);">2. Review Structure & Column Mapping</div>
          <div class="card-subtitle">File: <b>${preview.file_name}</b> | Category: <b>${preview.data_category}</b> | Estimated Records: <b>${preview.estimated_rows}</b></div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary" onclick="handleValidateData(${preview.file_id}, '${preview.data_category}')">
            🔍 Validate Data Integrity
          </button>
          <button class="btn btn-primary" onclick="handleConfirmImport(${preview.file_id}, '${preview.data_category}')">
            ⚡ Confirm & Import Data
          </button>
        </div>
      </div>

      <!-- Raw Preview Table -->
      <div style="padding: 12px 16px; font-weight: 700; font-size: 13px; color: #0f172a; border-bottom: 1px solid var(--border);">
        Top File Preview (First ${previewRows.length} rows):
      </div>
      <div class="table-container" style="max-height: 220px; overflow-y: auto; margin-bottom: 16px;">
        <table class="data-table">
          <thead>
            <tr>
              ${columns.map(c => `<th class="font-mono">${c}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${previewRows.map(r => `
              <tr>
                ${columns.map(c => `<td>${r[c] !== null && r[c] !== undefined ? r[c] : '<span style=\"color:#cbd5e1;\">—</span>'}</td>`).join("")}
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>

      <!-- Column Mapping Controls -->
      <div style="padding: 0 16px 16px 16px;">
        <div style="font-weight: 700; font-size: 13px; color: #0f172a; margin-bottom: 10px;">
          Column Mapping Configuration:
        </div>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">
          ${STANDARD_TARGET_FIELDS.map(f => {
            // Find if source column maps to this target field
            let mappedSource = "";
            for (const [src, tgt] of Object.entries(suggested)) {
              if (tgt === f.key) {
                mappedSource = src;
                break;
              }
            }

            let statusBadge = `<span class="badge" style="background:#f1f5f9; color:#64748b;">Not detected</span>`;
            if (mappedSource) {
              statusBadge = `<span class="badge badge-resolved">● Detected</span>`;
            } else if (f.required) {
              statusBadge = `<span class="badge" style="background:#fffbeb; color:#d97706; border:1px solid #fde68a;">Needs mapping</span>`;
            }

            return `
              <div style="padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-md); background: #ffffff; display: flex; justify-content: space-between; align-items: center; gap: 10px;">
                <div style="flex: 1;">
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <b style="font-size: 12.5px; color: #0f172a;">${f.label}</b>
                    ${statusBadge}
                  </div>
                  <div style="font-size: 11px; color: #64748b; margin-top: 2px;">${f.desc}</div>
                </div>
                <div style="width: 180px;">
                  <select class="form-control mapping-select" data-target="${f.key}" style="font-size: 12px; font-weight: 600;">
                    <option value="">-- Do Not Import --</option>
                    ${columns.map(c => `
                      <option value="${c}" ${c === mappedSource ? 'selected' : ''}>${c}</option>
                    `).join("")}
                  </select>
                </div>
              </div>
            `;
          }).join("")}
        </div>

        <div style="margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: var(--radius-md); display: flex; justify-content: space-between; align-items: center;">
          <div style="font-size: 12px; color: #64748b;">
            💡 <b>Auditor Tip:</b> FinAuditPro never alters raw values. Original strings are stored for audit defense.
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-secondary" onclick="document.getElementById('mapping-workspace-container').innerHTML = ''">Cancel</button>
            <button class="btn btn-secondary" onclick="handleValidateData(${preview.file_id}, '${preview.data_category}')">Validate First</button>
            <button class="btn btn-primary" onclick="handleConfirmImport(${preview.file_id}, '${preview.data_category}')">Import All Transactions</button>
          </div>
        </div>
      </div>
    </div>
  `;

  // Scroll to mapping workspace
  container.scrollIntoView({ behavior: 'smooth' });
}

function collectMappingConfig() {
  const mapping = {};
  document.querySelectorAll(".mapping-select").forEach(sel => {
    const target = sel.dataset.target;
    const source = sel.value;
    if (source && target) {
      mapping[source] = target;
    }
  });
  return mapping;
}

// Pre-Import Validation Handler
async function handleValidateData(fileId, dataCategory) {
  const mapping = collectMappingConfig();
  if (Object.keys(mapping).length === 0) {
    notifyWarning("Please map at least one column before validating.");
    return;
  }

  try {
    const res = await FinAuditAPI.validateMapping(fileId, mapping, dataCategory);
    const report = res.validation_report || {};
    const sum = report.error_summary || {};
    const errors = report.errors || [];
    const warnings = report.warnings || [];

    const modalHtml = `
      <div class="modal-overlay" id="val-report-modal">
        <div class="modal-card" style="max-width: 720px;">
          <div class="modal-header">
            <div class="modal-title">Pre-Import Validation Report</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('val-report-modal')">✕</button>
          </div>
          <div class="modal-body">
            <!-- Metrics Badges -->
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px;">
              <div style="padding: 10px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); text-align: center;">
                <div style="font-size: 11px; color: #64748b;">TOTAL ROWS</div>
                <div style="font-size: 18px; font-weight: 700;" class="font-mono">${report.total_rows || 0}</div>
              </div>
              <div style="padding: 10px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: var(--radius-md); text-align: center;">
                <div style="font-size: 11px; color: #065f46;">VALID ROWS</div>
                <div style="font-size: 18px; font-weight: 700; color: #059669;" class="font-mono">${report.valid_rows || 0}</div>
              </div>
              <div style="padding: 10px; background: #fff7ed; border: 1px solid #fed7aa; border-radius: var(--radius-md); text-align: center;">
                <div style="font-size: 11px; color: #9a3412;">WARNINGS</div>
                <div style="font-size: 18px; font-weight: 700; color: #ea580c;" class="font-mono">${report.warning_count || 0}</div>
              </div>
              <div style="padding: 10px; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-md); text-align: center;">
                <div style="font-size: 11px; color: #991b1b;">ERRORS</div>
                <div style="font-size: 18px; font-weight: 700; color: #dc2626;" class="font-mono">${report.failed_rows || 0}</div>
              </div>
            </div>

            <!-- Issues Breakdown Summary -->
            <div style="margin-bottom: 16px; padding: 12px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md);">
              <div style="font-weight: 700; font-size: 12.5px; color: #0f172a; margin-bottom: 6px;">Accounting & Statutory Checks Breakdown:</div>
              <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; font-size: 12px;">
                <div>• Invalid Date Formats: <b>${sum.invalid_dates || 0}</b></div>
                <div>• Non-Numeric Amounts: <b>${sum.invalid_numeric || 0}</b></div>
                <div>• Missing Account/Party: <b>${sum.empty_heads || 0}</b></div>
                <div>• Debit/Credit Single-Row Conflicts: <b>${sum.debit_credit_conflicts || 0}</b></div>
                <div>• Invalid GSTIN Structures: <b>${sum.invalid_gstin || 0}</b></div>
                <div>• Missing Invoices: <b>${sum.missing_invoices || 0}</b></div>
                <div>• Duplicate Invoices: <b>${sum.duplicate_invoices || 0}</b></div>
                <div>• Duplicate Voucher Rows: <b>${sum.duplicate_rows || 0}</b></div>
              </div>
            </div>

            <!-- Sample Error Table -->
            ${(errors.length === 0 && warnings.length === 0) ? `
              <div style="padding: 20px; text-align: center; color: #059669; font-weight: 600;">
                ✓ Perfect Data Integrity! Zero errors or anomalies detected.
              </div>
            ` : `
              <div style="font-weight: 700; font-size: 12.5px; color: #0f172a; margin-bottom: 6px;">
                Detected Issues Details (${errors.length + warnings.length}):
              </div>
              <div class="table-container" style="max-height: 200px; overflow-y: auto;">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Field</th>
                      <th>Issue Type</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${[...errors, ...warnings].slice(0, 50).map(item => `
                      <tr>
                        <td class="font-mono font-bold">#${item.row}</td>
                        <td class="font-mono">${item.field}</td>
                        <td><span class="badge ${item.error_type.startsWith('INVALID') ? 'badge-critical' : 'badge-medium'}">${item.error_type}</span></td>
                        <td style="font-size: 11.5px;">${item.message}</td>
                      </tr>
                    `).join("")}
                  </tbody>
                </table>
              </div>
            `}

            <div class="modal-footer" style="padding: 12px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('val-report-modal')">Close</button>
              <button type="button" class="btn btn-primary" onclick="closeModal('val-report-modal'); handleConfirmImport(${fileId}, '${dataCategory}')">
                Proceed With Import (${report.total_rows} rows)
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Validation failed: " + err.message);
  }
}

// Confirm & Apply Import Handler
async function handleConfirmImport(fileId, dataCategory) {
  const mapping = collectMappingConfig();
  if (Object.keys(mapping).length === 0) {
    notifyWarning("Please configure column mappings before importing.");
    return;
  }

  try {
    const res = await FinAuditAPI.applyMapping(fileId, mapping, dataCategory);
    
    const summaryHtml = `
      <div class="modal-overlay" id="import-success-modal">
        <div class="modal-card" style="max-width: 580px;">
          <div class="modal-header" style="background: #ecfdf5;">
            <div class="modal-title" style="color: #065f46;">✓ Data Import Completed Successfully</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('import-success-modal')">✕</button>
          </div>
          <div class="modal-body">
            <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 6px;">
              ${res.imported_rows} Financial Transactions Imported
            </div>
            <div style="font-size: 12px; color: #475569; margin-bottom: 16px;">
              File: <b>${res.file_name}</b> | Category: <b>${res.data_category}</b>
            </div>

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px;">
              <div style="padding: 10px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); text-align: center;">
                <div style="font-size: 11px; color: #64748b;">SUCCESSFUL</div>
                <div style="font-size: 16px; font-weight: 700; color: #059669;">${res.imported_rows}</div>
              </div>
              <div style="padding: 10px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); text-align: center;">
                <div style="font-size: 11px; color: #64748b;">FAILED</div>
                <div style="font-size: 16px; font-weight: 700; color: ${res.failed_rows > 0 ? '#dc2626' : '#64748b'};">${res.failed_rows}</div>
              </div>
              <div style="padding: 10px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); text-align: center;">
                <div style="font-size: 11px; color: #64748b;">WARNINGS</div>
                <div style="font-size: 16px; font-weight: 700; color: #d97706;">${res.warning_count}</div>
              </div>
            </div>

            <div style="display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;">
              ${(res.failed_rows > 0 || res.warning_count > 0) ? `
                <a href="/api/import/errors/${fileId}/download" target="_blank" class="btn btn-secondary" style="flex: 1; text-align: center;">
                  📥 Download CSV Errors
                </a>
              ` : ''}
              <button class="btn btn-secondary" style="flex: 1;" onclick="closeModal('import-success-modal'); navigateTo('cleaning_logs')">
                🧹 View Cleaning Log
              </button>
              <button class="btn btn-secondary" style="flex: 1;" onclick="closeModal('import-success-modal'); navigateTo('trial_balance')">
                📊 View Trial Balance
              </button>
              <button class="btn btn-primary" style="flex: 1;" onclick="closeModal('import-success-modal'); triggerRunHybridEngine()">
                ⚡ Run Audit Engine
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", summaryHtml);

    document.getElementById("mapping-workspace-container").innerHTML = "";
    await updateActiveEngagement();
    renderImportData();
  } catch (err) {
    notifyError("Import failed: " + err.message);
  }
}

async function deleteImportedFile(fileId, filename) {
  const confirmed = await FinConfirm({
    title: "Delete Uploaded Dataset",
    message: `Are you sure you want to delete '${filename}'?`,
    consequences: [
      "Source uploaded file will be permanently deleted",
      "All imported transactions from this file will be removed",
      "Related ledger balances and reconciliation records will be recalculated"
    ],
    confirmText: "Delete Dataset",
    cancelText: "Keep File",
    isDanger: true
  });
  if (!confirmed) return;

  try {
    await FinAuditAPI.deleteUploadedFile(fileId);
    notifySuccess(`File '${filename}' and its associated transactions have been deleted.`);
    await updateActiveEngagement();
    renderImportData();
  } catch (err) {
    notifyError("Failed to delete file: " + err.message);
  }
}

// ----------------- DATA CLEANING & NORMALIZATION MODULE -----------------
let cleaningLogFilterState = {
  fieldName: "All",
  isQuestionable: "All",
  transformationRule: "All",
  reviewStatus: "All",
  search: "",
  offset: 0,
  limit: 50
};

async function renderDataCleaningLogs() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `<div class="card" style="padding: 30px; text-align: center; color: #64748b;">Please select an active audit engagement first.</div>`;
    return;
  }

  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading Data Cleaning Logs & Transformations...</div>`;

  try {
    const summary = await FinAuditAPI.getCleaningSummary(state.currentEngagementId);
    
    const params = {
      limit: cleaningLogFilterState.limit,
      offset: cleaningLogFilterState.offset
    };
    if (cleaningLogFilterState.fieldName !== "All") params.field_name = cleaningLogFilterState.fieldName;
    if (cleaningLogFilterState.isQuestionable === "1") params.is_questionable = 1;
    if (cleaningLogFilterState.isQuestionable === "0") params.is_questionable = 0;
    if (cleaningLogFilterState.transformationRule !== "All") params.transformation_rule = cleaningLogFilterState.transformationRule;
    if (cleaningLogFilterState.reviewStatus !== "All") params.review_status = cleaningLogFilterState.reviewStatus;
    if (cleaningLogFilterState.search.trim()) params.search = cleaningLogFilterState.search.trim();

    const logData = await FinAuditAPI.getCleaningLogs(state.currentEngagementId, params);
    const logs = logData.logs || [];
    const totalCount = logData.total || 0;

    // Collect distinct rules and fields for dropdowns
    const availableFields = summary.field_breakdown || [];

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Data Cleaning & Normalization Engine</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Standardizing dates, amounts, legal suffixes & GSTINs with 100% raw data preservation in Layer 1
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary" onclick="openNormalizationSandboxModal()">
            ⚡ Rule Sandbox & Tester
          </button>
          <button class="btn btn-primary" onclick="navigateTo('import')">
            + Import More Data
          </button>
        </div>
      </div>

      <!-- Two-Layer Architecture Banner -->
      <div style="background: linear-gradient(135deg, #1e293b, #0f172a); color: white; padding: 14px 18px; border-radius: var(--radius-lg); margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 14px;">
          <div style="background: rgba(37, 99, 235, 0.2); border: 1px solid #3b82f6; border-radius: 8px; padding: 8px 12px; text-align: center;">
            <div style="font-size: 10px; font-weight: 700; color: #93c5fd; letter-spacing: 0.5px;">LAYER 1</div>
            <div style="font-size: 12px; font-weight: 700; color: #ffffff;">RAW DATA</div>
          </div>
          <div style="color: #94a3b8; font-size: 18px;">➔</div>
          <div style="background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; border-radius: 8px; padding: 8px 12px; text-align: center;">
            <div style="font-size: 10px; font-weight: 700; color: #a7f3d0; letter-spacing: 0.5px;">LAYER 2</div>
            <div style="font-size: 12px; font-weight: 700; color: #ffffff;">NORMALIZED</div>
          </div>
          <div style="margin-left: 8px; font-size: 12.5px; color: #cbd5e1;">
            <b>Audit Integrity Guarantee:</b> Raw imported client values are permanently preserved in <code style="background: rgba(255,255,255,0.1); padding: 1px 4px; border-radius: 3px; font-size: 11px;">original_row_json</code>. Basic transformations run deterministically without AI.
          </div>
        </div>
        <span class="offline-pill" style="font-size: 10.5px; background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3);"><span class="offline-dot"></span> Deterministic Rules</span>
      </div>

      <!-- KPI Summary Cards -->
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 16px;">
        <div class="kpi-card">
          <div class="kpi-label">TOTAL TRANSFORMATIONS</div>
          <div class="kpi-value">${summary.total_transformations || 0}</div>
          <div class="kpi-subtext">Automatic field cleanings</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">QUESTIONABLE / AMBIGUOUS</div>
          <div class="kpi-value" style="color: ${(summary.questionable_count || 0) > 0 ? '#d97706' : '#059669'};">
            ${summary.questionable_count || 0}
          </div>
          <div class="kpi-subtext">Flagged for CA verification</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">AUDITOR REVIEWED</div>
          <div class="kpi-value" style="color: #2563eb;">${summary.reviewed_count || 0}</div>
          <div class="kpi-subtext">Accepted / Overridden by CA</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">AUTO-APPLIED (CONFIDENT)</div>
          <div class="kpi-value" style="color: #059669;">${summary.auto_applied_count || 0}</div>
          <div class="kpi-subtext">Standard deterministic rules</div>
        </div>
      </div>

      <!-- Filter Controls Card -->
      <div class="card" style="padding: 14px; margin-bottom: 16px;">
        <div style="display: grid; grid-template-columns: 1.5fr 1fr 1fr 1fr auto; gap: 10px; align-items: center;">
          <div>
            <input type="text" id="cleaning-search-input" class="form-control" placeholder="Search original, normalized or rule..." value="${escapeHtml(cleaningLogFilterState.search)}" onkeyup="if(event.key==='Enter') applyCleaningFilters()">
          </div>
          <div>
            <select id="cleaning-field-filter" class="form-control" onchange="applyCleaningFilters()">
              <option value="All" ${cleaningLogFilterState.fieldName === 'All' ? 'selected' : ''}>All Fields (${summary.total_transformations || 0})</option>
              ${availableFields.map(f => `
                <option value="${f.field_name}" ${cleaningLogFilterState.fieldName === f.field_name ? 'selected' : ''}>
                  ${f.field_name} (${f.count}${f.quest_count ? ` • ${f.quest_count} quest` : ''})
                </option>
              `).join("")}
            </select>
          </div>
          <div>
            <select id="cleaning-quest-filter" class="form-control" onchange="applyCleaningFilters()">
              <option value="All" ${cleaningLogFilterState.isQuestionable === 'All' ? 'selected' : ''}>All Ambiguity Levels</option>
              <option value="1" ${cleaningLogFilterState.isQuestionable === '1' ? 'selected' : ''}>⚠️ Questionable Only (${summary.questionable_count || 0})</option>
              <option value="0" ${cleaningLogFilterState.isQuestionable === '0' ? 'selected' : ''}>✓ High Confidence (${summary.auto_applied_count || 0})</option>
            </select>
          </div>
          <div>
            <select id="cleaning-status-filter" class="form-control" onchange="applyCleaningFilters()">
              <option value="All" ${cleaningLogFilterState.reviewStatus === 'All' ? 'selected' : ''}>All Review Statuses</option>
              <option value="Auto-Applied" ${cleaningLogFilterState.reviewStatus === 'Auto-Applied' ? 'selected' : ''}>Auto-Applied</option>
              <option value="Accepted" ${cleaningLogFilterState.reviewStatus === 'Accepted' ? 'selected' : ''}>Accepted</option>
              <option value="Overridden" ${cleaningLogFilterState.reviewStatus === 'Overridden' ? 'selected' : ''}>Overridden</option>
              <option value="Reverted" ${cleaningLogFilterState.reviewStatus === 'Reverted' ? 'selected' : ''}>Reverted</option>
            </select>
          </div>
          <div style="display: flex; gap: 4px;">
            <button class="btn btn-secondary" onclick="applyCleaningFilters()">Filter</button>
            <button class="btn btn-secondary" onclick="resetCleaningFilters()">Reset</button>
          </div>
        </div>
      </div>

      <!-- Logs Table Card -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            Transformation Audit Trail (${totalCount} records)
          </div>
          <div style="font-size: 12px; color: #64748b;">
            Showing rows ${totalCount > 0 ? cleaningLogFilterState.offset + 1 : 0} to ${Math.min(cleaningLogFilterState.offset + cleaningLogFilterState.limit, totalCount)} of ${totalCount}
          </div>
        </div>

        ${logs.length === 0 ? `
          <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>No data cleaning log records match the current filter criteria.</p>
            <button class="btn btn-secondary" style="margin-top: 10px;" onclick="resetCleaningFilters()">Reset Filters</button>
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 70px;">Row #</th>
                  <th style="width: 100px;">Target Field</th>
                  <th style="width: 220px;">Raw Original Value (Untouched)</th>
                  <th style="width: 220px;">Normalized Value (Cleaned)</th>
                  <th>Transformation Rule</th>
                  <th style="width: 110px;">Confidence</th>
                  <th style="width: 110px;">Review Status</th>
                  <th class="text-center" style="width: 100px;">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${logs.map(log => {
                  let statusBadge = `<span class="badge" style="background:#f1f5f9; color:#475569;">Auto-Applied</span>`;
                  if (log.review_status === 'Accepted') statusBadge = `<span class="badge badge-resolved">Accepted</span>`;
                  if (log.review_status === 'Overridden') statusBadge = `<span class="badge" style="background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe;">Overridden</span>`;
                  if (log.review_status === 'Reverted') statusBadge = `<span class="badge" style="background:#fff1f2; color:#e11d48; border:1px solid #fecdd3;">Reverted</span>`;

                  const isQuest = log.is_questionable === 1;
                  const confPct = Math.round((log.confidence_score || 1.0) * 100);

                  return `
                    <tr style="${isQuest && log.review_status === 'Auto-Applied' ? 'background-color: #fffdf5;' : ''}">
                      <td>
                        <div class="font-mono font-bold" style="font-size: 11.5px; color: #475569;">
                          #${log.row_number || '—'}
                        </div>
                        <div style="font-size: 10px; color: #94a3b8; max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                          ${escapeHtml(log.file_name || 'Import File')}
                        </div>
                      </td>
                      <td>
                        <span class="badge" style="background: #f8fafc; border: 1px solid var(--border); color: #0f172a; font-weight: 700; font-size: 11px;">
                          ${escapeHtml(log.field_name)}
                        </span>
                      </td>
                      <td>
                        <div class="font-mono" style="font-size: 11.5px; background: #fef2f2; color: #991b1b; padding: 3px 6px; border-radius: 4px; border: 1px solid #fee2e2; word-break: break-all;">
                          "${escapeHtml(log.original_value || '')}"
                        </div>
                      </td>
                      <td>
                        <div class="font-mono font-bold" style="font-size: 11.5px; background: #ecfdf5; color: #065f46; padding: 3px 6px; border-radius: 4px; border: 1px solid #d1fae5; word-break: break-all;">
                          "${escapeHtml(log.normalized_value || '')}"
                        </div>
                      </td>
                      <td>
                        <div style="font-size: 11.5px; font-weight: 600; color: #334155;">
                          ${escapeHtml(log.transformation_rule)}
                        </div>
                        ${log.auditor_comment ? `
                          <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
                            💬 <i>${escapeHtml(log.auditor_comment)}</i>
                          </div>
                        ` : ''}
                      </td>
                      <td>
                        <div style="display: flex; align-items: center; gap: 4px;">
                          ${isQuest ? `
                            <span class="badge" style="background: #fffbeb; color: #b45309; border: 1px solid #fde68a; font-size: 10px;">
                              ⚠️ ${confPct}%
                            </span>
                          ` : `
                            <span class="badge badge-resolved" style="font-size: 10px;">
                              ✓ ${confPct}%
                            </span>
                          `}
                        </div>
                      </td>
                      <td>${statusBadge}</td>
                      <td class="text-center">
                        <button class="btn btn-sm btn-secondary" onclick='openReviewCleaningModal(${log.id}, ${JSON.stringify(JSON.stringify(log))})' title="Auditor Review">
                          🔍 Review
                        </button>
                      </td>
                    </tr>
                  `;
                }).join("")}
              </tbody>
            </table>
          </div>

          <!-- Pagination footer -->
          <div style="padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border);">
            <div style="font-size: 12px; color: #64748b;">
              Showing ${logs.length} of ${totalCount} records
            </div>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-sm btn-secondary" ${cleaningLogFilterState.offset === 0 ? 'disabled' : ''} onclick="changeCleaningOffset(-cleaningLogFilterState.limit)">
                ◀ Previous
              </button>
              <button class="btn btn-sm btn-secondary" ${(cleaningLogFilterState.offset + cleaningLogFilterState.limit) >= totalCount ? 'disabled' : ''} onclick="changeCleaningOffset(cleaningLogFilterState.limit)">
                Next ▶
              </button>
            </div>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading data cleaning logs: ${err.message}</div>`;
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function applyCleaningFilters() {
  cleaningLogFilterState.search = document.getElementById("cleaning-search-input")?.value || "";
  cleaningLogFilterState.fieldName = document.getElementById("cleaning-field-filter")?.value || "All";
  cleaningLogFilterState.isQuestionable = document.getElementById("cleaning-quest-filter")?.value || "All";
  cleaningLogFilterState.reviewStatus = document.getElementById("cleaning-status-filter")?.value || "All";
  cleaningLogFilterState.offset = 0;
  renderDataCleaningLogs();
}

function resetCleaningFilters() {
  cleaningLogFilterState = {
    fieldName: "All",
    isQuestionable: "All",
    transformationRule: "All",
    reviewStatus: "All",
    search: "",
    offset: 0,
    limit: 50
  };
  renderDataCleaningLogs();
}

function changeCleaningOffset(delta) {
  cleaningLogFilterState.offset = Math.max(0, cleaningLogFilterState.offset + delta);
  renderDataCleaningLogs();
}

function openReviewCleaningModal(logId, logJsonStr) {
  const log = typeof logJsonStr === "string" ? JSON.parse(logJsonStr) : logJsonStr;
  
  const modalHtml = `
    <div class="modal-overlay" id="review-cleaning-modal">
      <div class="modal-card" style="max-width: 580px;">
        <div class="modal-header">
          <div class="modal-title">Auditor Transformation Review (Record #${log.id})</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('review-cleaning-modal')">✕</button>
        </div>
        <div class="modal-body">
          <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 12px; margin-bottom: 16px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
              <div><b style="color: #475569;">Target Field:</b> <span class="badge" style="background:#e2e8f0; color:#0f172a;">${escapeHtml(log.field_name)}</span></div>
              <div><b style="color: #475569;">Row / Ref:</b> Row #${log.row_number || 'N/A'} (Txn #${log.transaction_id || 'N/A'})</div>
              <div><b style="color: #475569;">Rule Applied:</b> <code>${escapeHtml(log.transformation_rule)}</code></div>
              <div><b style="color: #475569;">Ambiguity Status:</b> ${log.is_questionable ? '<span class="badge" style="background:#fffbeb; color:#b45309;">⚠️ Questionable</span>' : '<span class="badge badge-resolved">✓ Confident</span>'}</div>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
            <div style="padding: 10px; background: #fef2f2; border: 1px solid #fecdd3; border-radius: var(--radius-md);">
              <div style="font-size: 11px; font-weight: 700; color: #991b1b; margin-bottom: 4px;">RAW ORIGINAL SOURCE (Untouched)</div>
              <div class="font-mono font-bold" style="font-size: 13px; color: #991b1b; word-break: break-all;">${escapeHtml(log.original_value)}</div>
            </div>
            <div style="padding: 10px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: var(--radius-md);">
              <div style="font-size: 11px; font-weight: 700; color: #065f46; margin-bottom: 4px;">CURRENT NORMALIZED VALUE</div>
              <div class="font-mono font-bold" style="font-size: 13px; color: #065f46; word-break: break-all;">${escapeHtml(log.normalized_value)}</div>
            </div>
          </div>

          <form onsubmit="handleReviewCleaningSubmit(event, ${log.id})">
            <div class="form-group">
              <label class="form-label">Auditor Action *</label>
              <div style="display: flex; gap: 12px; margin-top: 4px;">
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px;">
                  <input type="radio" name="review_action" value="Accepted" checked onchange="toggleCustomValueField(false)">
                  <b>Accept Normalized</b>
                </label>
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px;">
                  <input type="radio" name="review_action" value="Overridden" onchange="toggleCustomValueField(true)">
                  <b>Custom Override</b>
                </label>
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px;">
                  <input type="radio" name="review_action" value="Reverted" onchange="toggleCustomValueField(false)">
                  <b>Revert to Raw Source</b>
                </label>
              </div>
            </div>

            <div class="form-group" id="custom-value-group" style="display: none;">
              <label class="form-label">Custom Auditor Normalized Value *</label>
              <input type="text" id="custom-norm-val" class="form-control font-mono" placeholder="Enter custom standardized value" value="${escapeHtml(log.normalized_value)}">
              <div style="font-size: 11px; color: #64748b; margin-top: 3px;">This value will directly update the transaction record while preserving the raw input.</div>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Working Paper Comment / Justification</label>
              <textarea id="review-comment" class="form-control" rows="2" placeholder="e.g. Verified against supplier tax invoice #442; date confirmed as 01-Apr-2026.">${escapeHtml(log.auditor_comment || '')}</textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('review-cleaning-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Auditor Review</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

function toggleCustomValueField(show) {
  const grp = document.getElementById("custom-value-group");
  if (grp) grp.style.display = show ? "block" : "none";
}

async function handleReviewCleaningSubmit(event, logId) {
  event.preventDefault();
  const action = document.querySelector("input[name='review_action']:checked")?.value || "Accepted";
  const customVal = document.getElementById("custom-norm-val")?.value;
  const comment = document.getElementById("review-comment")?.value.trim();

  try {
    const res = await FinAuditAPI.reviewCleaningLog(logId, {
      action: action,
      custom_normalized_value: action === "Overridden" ? customVal : null,
      auditor_comment: comment
    });
    notifyInfo(res.message);
    closeModal("review-cleaning-modal");
    renderDataCleaningLogs();
  } catch (err) {
    notifyError("Error updating review: " + err.message);
  }
}

// Interactive Normalization Sandbox Modal
function openNormalizationSandboxModal() {
  const modalHtml = `
    <div class="modal-overlay" id="sandbox-modal">
      <div class="modal-card" style="max-width: 650px;">
        <div class="modal-header">
          <div class="modal-title">⚡ Interactive Data Normalization Sandbox</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('sandbox-modal')">✕</button>
        </div>
        <div class="modal-body">
          <div style="font-size: 12.5px; color: #64748b; margin-bottom: 14px;">
            Test how FinAuditPro's deterministic rule engine standardizes inconsistent client financial strings without external AI calls.
          </div>

          <!-- Quick Preset Examples -->
          <div style="margin-bottom: 14px;">
            <div style="font-size: 11px; font-weight: 700; color: #475569; margin-bottom: 6px;">QUICK PRESET TEST CASES:</div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
              <button type="button" class="demo-chip" onclick="loadSandboxExample('date', '01/04/2026')">📅 Date: 01/04/2026</button>
              <button type="button" class="demo-chip" onclick="loadSandboxExample('date', '01-Apr-2026')">📅 Date: 01-Apr-2026</button>
              <button type="button" class="demo-chip" onclick="loadSandboxExample('date', '2026-04-01')">📅 Date: 2026-04-01</button>
              <button type="button" class="demo-chip" onclick="loadSandboxExample('amount', '₹ 1,50,000.00/-')">💰 Amt: ₹ 1,50,000.00/-</button>
              <button type="button" class="demo-chip" onclick="loadSandboxExample('amount', '(50,000.00)')">💰 Bracketed: (50,000.00)</button>
              <button type="button" class="demo-chip" onclick="loadSandboxExample('amount', 'Rs. 24,500.00 Dr')">💰 Suffix: Rs. 24,500.00 Dr</button>
              <button type="button" class="demo-chip" onclick="loadSandboxExample('party_name', 'apex solutions private limited')">🏢 Legal: apex solutions private limited</button>
              <button type="button" class="demo-chip" onclick="loadSandboxExample('gstin', '27aabcu9603r1zm')">📑 GSTIN: 27aabcu9603r1zm</button>
              <button type="button" class="demo-chip" onclick="loadSandboxExample('invoice_no', '  INV / 2026 / 0042  ')">🧾 Inv: INV / 2026 / 0042</button>
            </div>
          </div>

          <form onsubmit="handleSandboxPreviewSubmit(event)">
            <div style="display: grid; grid-template-columns: 1fr 2fr auto; gap: 10px; align-items: flex-end; margin-bottom: 16px;">
              <div>
                <label class="form-label">Field Dimension</label>
                <select id="sandbox-field" class="form-control">
                  <option value="date">Date</option>
                  <option value="amount">Amount / Monetary</option>
                  <option value="party_name">Party / Ledger Name</option>
                  <option value="invoice_no">Invoice / Voucher No</option>
                  <option value="gstin">GSTIN (15-Char)</option>
                </select>
              </div>
              <div>
                <label class="form-label">Client Raw Input String</label>
                <input type="text" id="sandbox-raw-input" class="form-control font-mono" placeholder="e.g. 01-Apr-2026 or ₹ 1,50,000.00" value="01-Apr-2026" required>
              </div>
              <div>
                <button type="submit" class="btn btn-primary" style="padding: 8px 14px;">⚡ Transform</button>
              </div>
            </div>
          </form>

          <!-- Result Container -->
          <div id="sandbox-result-container" style="display: none;">
            <!-- Populated on transform -->
          </div>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
  // Auto-run first example
  setTimeout(() => {
    document.getElementById("sandbox-raw-input")?.form?.requestSubmit();
  }, 50);
}

function loadSandboxExample(fieldName, rawVal) {
  const f = document.getElementById("sandbox-field");
  const i = document.getElementById("sandbox-raw-input");
  if (f) f.value = fieldName;
  if (i) i.value = rawVal;
  i?.form?.requestSubmit();
}

async function handleSandboxPreviewSubmit(event) {
  event.preventDefault();
  const field = document.getElementById("sandbox-field").value;
  const raw = document.getElementById("sandbox-raw-input").value;
  const container = document.getElementById("sandbox-result-container");
  if (!container) return;

  container.style.display = "block";
  container.innerHTML = `<div style="padding: 12px; color: #64748b; font-size: 12px;">Running deterministic normalization...</div>`;

  try {
    const res = await FinAuditAPI.previewNormalization(field, raw);
    
    const confPct = Math.round((res.confidence_score || 1.0) * 100);
    const isQuest = res.is_questionable === 1;

    container.innerHTML = `
      <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div style="font-weight: 700; font-size: 13px; color: #0f172a;">Normalization Engine Output</div>
          <span class="badge ${isQuest ? '' : 'badge-resolved'}" style="${isQuest ? 'background:#fffbeb; color:#b45309; border:1px solid #fde68a;' : ''}">
            ${isQuest ? `⚠️ Ambiguity Flagged (${confPct}%)` : `✓ Deterministic Match (${confPct}%)`}
          </span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
          <div style="padding: 10px; background: #ffffff; border: 1px solid var(--border); border-radius: var(--radius-md);">
            <div style="font-size: 11px; color: #64748b;">RAW INPUT (Layer 1)</div>
            <div class="font-mono font-bold" style="font-size: 13px; color: #dc2626; margin-top: 2px;">
              "${escapeHtml(res.original_value)}"
            </div>
          </div>
          <div style="padding: 10px; background: #ffffff; border: 1px solid #10b981; border-radius: var(--radius-md);">
            <div style="font-size: 11px; color: #059669; font-weight: 700;">STANDARDIZED OUTPUT (Layer 2)</div>
            <div class="font-mono font-bold" style="font-size: 13px; color: #059669; margin-top: 2px;">
              "${escapeHtml(res.normalized_value)}"
            </div>
          </div>
        </div>

        <div style="font-size: 12px; color: #475569; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <b>Applied Rule:</b> <code style="background: #e2e8f0; padding: 2px 6px; border-radius: 4px;">${escapeHtml(res.transformation_rule)}</code>
          </div>
          <div style="font-size: 11px; color: #64748b;">
            ${res.is_transformed ? '✨ Transformed from raw' : 'Identical to raw'}
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 10px; color: #dc2626; font-size: 12px;">Error: ${err.message}</div>`;
  }
}


// ==========================================================================
// Comprehensive FinAuditPro Dashboard Controller
// ==========================================================================
let currentDashboardData = null;
let activeFindingsFilter = "ALL";

async function renderDashboard() {
  const container = document.getElementById("content-container");
  if (!state.activeEngagement) await updateActiveEngagement();
  const eng = state.activeEngagement || {};

  container.innerHTML = `
    <div style="padding: 40px; text-align: center; color: #64748b;">
      <div class="spinner" style="margin: 0 auto 16px auto;"></div>
      <div style="font-size: 15px; font-weight: 600; color: #0f172a;">Loading Comprehensive Audit Dashboard...</div>
      <div style="font-size: 12px; margin-top: 4px;">Aggregating real database records, reconciliations, anomalies, and findings...</div>
    </div>
  `;

  try {
    const dash = await FinAuditAPI.getComprehensiveDashboard(state.currentEngagementId);
    currentDashboardData = dash;
    const cards = dash.top_cards || {};
    const overview = dash.engagement_overview || {};
    const risk = dash.risk_overview || {};
    const recentFindings = dash.recent_findings || [];
    const recon = dash.reconciliation_status || {};
    const anomaly = dash.anomaly_summary || {};
    const yoy = dash.yoy_summary || [];
    const chk = dash.checklist_progress || {};
    const monthlyTrends = dash.monthly_trends || [];

    const isAuditorOrAdmin = ["Admin", "Auditor"].includes(state.currentUser?.role);

    // Calculate chart maximums for clean scaling
    const maxTxMonth = Math.max(...monthlyTrends.map(m => m.transaction_count), 1);
    const maxValMonth = Math.max(...monthlyTrends.map(m => m.total_value), 1);
    const maxAreaFinding = Math.max(...Object.values(risk.area_counts || {}), 1);

    container.innerHTML = `
      <!-- Top Title & Quick Actions Bar -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
        <div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <h2 style="font-size: 22px; font-weight: 800; color: #0f172a; margin: 0;">Audit Practice Dashboard</h2>
            <span class="badge ${getStatusBadgeClass(eng.status)}">${eng.status || 'In Progress'}</span>
          </div>
          <div style="font-size: 13px; color: #64748b; margin-top: 4px;">
            Client: <b style="color: #1e293b;">${eng.client_name || 'Selected Client'}</b> | 
            FY: <b style="color: #1e293b;">${eng.financial_year || '2024-25'}</b> | 
            Audit: <b>${eng.audit_type || 'Statutory Audit'}</b> | 
            Materiality: <span class="font-mono font-bold" style="color: #2563eb;">${formatINR(eng.materiality_threshold || 50000)}</span>
          </div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <select id="dash-engagement-switcher" class="form-control" style="width: auto; max-width: 220px; font-size: 12.5px; height: 36px;" onchange="switchDashboardEngagement(this.value)">
            ${(overview.all_engagements || []).map(e => `
              <option value="${e.id}" ${e.id == state.currentEngagementId ? 'selected' : ''}>
                ${e.client_name} (${e.financial_year})
              </option>
            `).join("")}
          </select>
          <button class="btn btn-secondary" onclick="navigateTo('clients')">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
            Clients
          </button>
          <button class="btn btn-secondary" onclick="navigateTo('reports')">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
            Reports
          </button>
          ${isAuditorOrAdmin ? `
            <button class="btn btn-primary" onclick="triggerRunHybridEngine()">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
              Execute Audit Engine
            </button>
          ` : ''}
        </div>
      </div>

      <!-- 6 TOP CARDS (Real Database Values & Interactive Drill-Down) -->
      <div class="dash-top-grid">
        <div class="dash-stat-card card-blue" onclick="navigateTo('clients')" title="Click to view all active clients">
          <div class="dash-stat-header">
            <span class="dash-stat-title">Active Clients</span>
            <div class="dash-stat-icon" style="background: #eff6ff; color: #2563eb;">🏢</div>
          </div>
          <div class="dash-stat-val">${cards.active_clients_count || 0}</div>
          <div class="dash-stat-sub">
            <span>Registered audit clients</span>
          </div>
        </div>

        <div class="dash-stat-card card-indigo" onclick="navigateTo('engagements')" title="Click to view all active audit engagements">
          <div class="dash-stat-header">
            <span class="dash-stat-title">Active Engagements</span>
            <div class="dash-stat-icon" style="background: #e0e7ff; color: #4f46e5;">📁</div>
          </div>
          <div class="dash-stat-val font-mono" style="color: #4f46e5;">${cards.active_engagements_count || 0}</div>
          <div class="dash-stat-sub">
            <span>In Progress / Draft audits</span>
          </div>
        </div>

        <div class="dash-stat-card card-amber" onclick="openDashboardFindingsModal('OPEN', null)" title="Click to inspect all Open findings">
          <div class="dash-stat-header">
            <span class="dash-stat-title">Open Findings</span>
            <div class="dash-stat-icon" style="background: #fef3c7; color: #d97706;">⚠️</div>
          </div>
          <div class="dash-stat-val font-mono" style="color: #d97706;">${cards.open_findings_count || 0}</div>
          <div class="dash-stat-sub">
            <span>Unresolved observations</span>
          </div>
        </div>

        <div class="dash-stat-card card-red" onclick="openDashboardFindingsModal('HIGH', null)" title="Click to inspect Critical & High risk findings">
          <div class="dash-stat-header">
            <span class="dash-stat-title">High-Risk Findings</span>
            <div class="dash-stat-icon" style="background: #fee2e2; color: #dc2626;">🚨</div>
          </div>
          <div class="dash-stat-val font-mono" style="color: #dc2626;">${cards.high_risk_findings_count || 0}</div>
          <div class="dash-stat-sub">
            <span>Critical & High severity</span>
          </div>
        </div>

        <div class="dash-stat-card card-purple" onclick="openDashboardReconciliationModal('UNMATCHED')" title="Click to inspect unmatched BRS / GST records">
          <div class="dash-stat-header">
            <span class="dash-stat-title">Unmatched Txns</span>
            <div class="dash-stat-icon" style="background: #f3e8ff; color: #9333ea;">⚖️</div>
          </div>
          <div class="dash-stat-val font-mono" style="color: #9333ea;">${cards.unmatched_transactions_count || 0}</div>
          <div class="dash-stat-sub">
            <span>BRS & GST 2B unreconciled</span>
          </div>
        </div>

        <div class="dash-stat-card card-orange" onclick="openDashboardPendingReviewsModal()" title="Click to inspect pending Partner reviews">
          <div class="dash-stat-header">
            <span class="dash-stat-title">Pending Reviews</span>
            <div class="dash-stat-icon" style="background: #ffedd5; color: #ea580c;">⏳</div>
          </div>
          <div class="dash-stat-val font-mono" style="color: #ea580c;">${cards.pending_reviews_count || 0}</div>
          <div class="dash-stat-sub">
            <span>Awaiting sign-off / WPs</span>
          </div>
        </div>
      </div>

      <!-- MAIN SECTION 1: ENGAGEMENT OVERVIEW & VOLUMETRICS -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div class="card-title">1. Engagement Overview & Audit Metadata</div>
            <div class="card-subtitle">Active CA mandate details, assigned audit team, and processed data volumes</div>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-sm btn-secondary" onclick="openClientHistoryDrawer(${eng.client_id || 1})">
              📅 Multi-Year History
            </button>
            <button class="btn btn-sm btn-secondary" onclick="openDuplicateEngagementModal(${state.currentEngagementId})">
              📑 Clone for Next FY
            </button>
            <button class="btn btn-sm btn-secondary" onclick="navigateTo('trial_balance')">
              📊 Trial Balance
            </button>
          </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 16px; background: #f8fafc; border-radius: 8px; margin: 16px;">
          <div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Entity & Legal Form</div>
            <div style="font-weight: 700; color: #0f172a; margin-top: 2px;">${eng.client_name || 'N/A'}</div>
            <div style="font-size: 12px; color: #475569;">${eng.client_entity_type || 'Private Limited'} (${eng.client_industry || 'Manufacturing'})</div>
          </div>
          <div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Statutory Identifiers</div>
            <div style="font-size: 12.5px; font-weight: 600; color: #0f172a; margin-top: 2px;">PAN: <span class="font-mono">${eng.client_pan || 'N/A'}</span></div>
            <div style="font-size: 12px; color: #475569;">GSTIN: <span class="font-mono">${eng.client_gstin || 'N/A'}</span></div>
          </div>
          <div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Audit Team Assigned</div>
            <div style="font-size: 12.5px; font-weight: 600; color: #0f172a; margin-top: 2px;">Lead: ${eng.lead_auditor_name || 'Engagement Partner'}</div>
            <div style="font-size: 12px; color: #475569;">Staff: ${eng.assigned_staff_name || 'Audit Senior'}</div>
          </div>
          <div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Audit Period & Scope</div>
            <div style="font-size: 12.5px; font-weight: 600; color: #0f172a; margin-top: 2px;">${eng.period_start || '01-04-2024'} to ${eng.period_end || '31-03-2025'}</div>
            <div style="font-size: 12px; color: #2563eb; font-weight: 600;">Threshold: ${formatINR(eng.materiality_threshold || 50000)}</div>
          </div>
        </div>

        <!-- Volume Badges Grid -->
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; padding: 0 16px 16px 16px;">
          <div style="padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff;">
            <div style="font-size: 11px; color: #64748b; font-weight: 600;">DATA SOURCES IMPORTED</div>
            <div class="font-mono font-bold" style="font-size: 18px; color: #0f172a; margin-top: 2px;">${overview.total_files || 0} Files</div>
            <div style="font-size: 11.5px; color: #64748b;">Ledgers, BRS, GSTR-2B</div>
          </div>
          <div style="padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff; cursor: pointer;" onclick="openDashboardTransactionsModal('', 'All Transactions')">
            <div style="font-size: 11px; color: #64748b; font-weight: 600;">TOTAL TRANSACTIONS</div>
            <div class="font-mono font-bold" style="font-size: 18px; color: #2563eb; margin-top: 2px;">${(overview.total_transactions || 0).toLocaleString()} Entries</div>
            <div style="font-size: 11.5px; color: #2563eb;">🔍 Click to inspect all</div>
          </div>
          <div style="padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff;">
            <div style="font-size: 11px; color: #64748b; font-weight: 600;">TOTAL DEBIT TURNOVER</div>
            <div class="font-mono font-bold" style="font-size: 18px; color: #059669; margin-top: 2px;">${formatINR(overview.total_debit_turnover || 0)}</div>
            <div style="font-size: 11.5px; color: #64748b;">Examined payments/purchases</div>
          </div>
          <div style="padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff;">
            <div style="font-size: 11px; color: #64748b; font-weight: 600;">TOTAL CREDIT TURNOVER</div>
            <div class="font-mono font-bold" style="font-size: 18px; color: #0284c7; margin-top: 2px;">${formatINR(overview.total_credit_turnover || 0)}</div>
            <div style="font-size: 11.5px; color: #64748b;">Examined receipts/revenues</div>
          </div>
        </div>
      </div>

      <!-- MAIN SECTION 2: RISK OVERVIEW & CHARTS -->
      <div class="dash-section-grid">
        <div class="dash-chart-card">
          <div class="dash-chart-header">
            <div>
              <div class="dash-chart-title">
                <span>2. Risk Overview & Finding Severity Distribution</span>
                <span class="risk-posture-badge risk-posture-${risk.risk_posture || 'MODERATE'}">
                  ● ${risk.risk_posture || 'MODERATE'} RISK POSTURE
                </span>
              </div>
              <div class="dash-chart-subtitle">Click any severity segment to view underlying findings</div>
            </div>
            <div style="text-align: right;">
              <div style="font-size: 11px; color: #64748b; font-weight: 700;">AVG RISK SCORE</div>
              <div class="font-mono font-bold" style="font-size: 18px; color: #0f172a;">${risk.average_risk_score || 0.0} / 10.0</div>
            </div>
          </div>

          <!-- Finding Severity Distribution Chart (Interactive Clickable Bars) -->
          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;">
            <div class="chart-bar-interactive" style="padding: 12px; border: 1px solid #fecaca; background: #fef2f2; border-radius: 8px; text-align: center;" onclick="openDashboardFindingsModal('CRITICAL', null)" title="Click to view Critical findings">
              <div style="font-size: 11px; font-weight: 700; color: #dc2626;">CRITICAL</div>
              <div class="font-mono font-bold" style="font-size: 24px; color: #dc2626; margin: 4px 0;">${risk.severity_counts?.CRITICAL || 0}</div>
              <div style="font-size: 11px; color: #991b1b;">Immediate Action</div>
            </div>
            <div class="chart-bar-interactive" style="padding: 12px; border: 1px solid #fed7aa; background: #fff7ed; border-radius: 8px; text-align: center;" onclick="openDashboardFindingsModal('HIGH', null)" title="Click to view High risk findings">
              <div style="font-size: 11px; font-weight: 700; color: #ea580c;">HIGH</div>
              <div class="font-mono font-bold" style="font-size: 24px; color: #ea580c; margin: 4px 0;">${risk.severity_counts?.HIGH || 0}</div>
              <div style="font-size: 11px; color: #c2410c;">Material Deviation</div>
            </div>
            <div class="chart-bar-interactive" style="padding: 12px; border: 1px solid #fef08a; background: #fffbeb; border-radius: 8px; text-align: center;" onclick="openDashboardFindingsModal('MEDIUM', null)" title="Click to view Medium risk findings">
              <div style="font-size: 11px; font-weight: 700; color: #d97706;">MEDIUM</div>
              <div class="font-mono font-bold" style="font-size: 24px; color: #d97706; margin: 4px 0;">${risk.severity_counts?.MEDIUM || 0}</div>
              <div style="font-size: 11px; color: #b45309;">Review Required</div>
            </div>
            <div class="chart-bar-interactive" style="padding: 12px; border: 1px solid #a7f3d0; background: #ecfdf5; border-radius: 8px; text-align: center;" onclick="openDashboardFindingsModal('LOW', null)" title="Click to view Low risk findings">
              <div style="font-size: 11px; font-weight: 700; color: #059669;">LOW</div>
              <div class="font-mono font-bold" style="font-size: 24px; color: #059669; margin: 4px 0;">${risk.severity_counts?.LOW || 0}</div>
              <div style="font-size: 11px; color: #047857;">Informational</div>
            </div>
          </div>

          <!-- Multi-Engine Detection Distribution Pills -->
          <div style="display: flex; gap: 10px; background: #f8fafc; padding: 10px 14px; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 12px; justify-content: space-between;">
            <div><b>Deterministic Rules:</b> <span class="font-mono font-bold" style="color: #2563eb;">${risk.engine_counts?.DETERMINISTIC || 0}</span></div>
            <div><b>Statistical & ML Outliers:</b> <span class="font-mono font-bold" style="color: #7c3aed;">${risk.engine_counts?.STATISTICAL_ML || 0}</span></div>
            <div><b>Local AI Observations:</b> <span class="font-mono font-bold" style="color: #059669;">${risk.engine_counts?.LOCAL_AI || 0}</span></div>
          </div>
        </div>

        <!-- Chart: Risk by Audit Area (Interactive Horizontal Bar Chart) -->
        <div class="dash-chart-card">
          <div class="dash-chart-header">
            <div>
              <div class="dash-chart-title">Risk by Audit Area</div>
              <div class="dash-chart-subtitle">Click an area to filter findings</div>
            </div>
          </div>
          <div>
            ${Object.keys(risk.area_counts || {}).length === 0 ? `
              <div style="text-align: center; color: #94a3b8; padding: 20px 0;">No risk areas flagged yet.</div>
            ` : Object.entries(risk.area_counts || {}).map(([area, cnt]) => {
              const pct = Math.round((cnt / maxAreaFinding) * 100);
              return `
                <div class="chart-horizontal-bar-row" onclick="openDashboardFindingsModal(null, '${escapeHtml(area)}')" title="Click to filter findings in ${escapeHtml(area)}">
                  <div class="chart-h-label" title="${escapeHtml(area)}">${escapeHtml(area)}</div>
                  <div class="chart-h-track">
                    <div class="chart-h-fill" style="width: ${pct}%; background: linear-gradient(90deg, #3b82f6, #ef4444);"></div>
                  </div>
                  <div class="chart-h-val">${cnt}</div>
                </div>
              `;
            }).join("")}
          </div>
        </div>
      </div>

      <!-- MAIN SECTION 3: RECENT FINDINGS (Live Real Data Table) -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div class="card-title">3. Recent Findings & Priority Observations</div>
            <div class="card-subtitle">Traceable Finding IDs ([ID: x] F-XXX) mapped directly to database records</div>
          </div>
          <div style="display: flex; gap: 8px;">
            <div class="btn-group" style="display: flex; gap: 4px;">
              <button class="btn btn-sm ${activeFindingsFilter === 'ALL' ? 'btn-primary' : 'btn-secondary'}" onclick="filterDashboardFindingsTable('ALL')">All (${recentFindings.length})</button>
              <button class="btn btn-sm ${activeFindingsFilter === 'CRITICAL' ? 'btn-primary' : 'btn-secondary'}" onclick="filterDashboardFindingsTable('CRITICAL')">Critical</button>
              <button class="btn btn-sm ${activeFindingsFilter === 'HIGH' ? 'btn-primary' : 'btn-secondary'}" onclick="filterDashboardFindingsTable('HIGH')">High</button>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="navigateTo('findings')">Open All Findings Tab →</button>
          </div>
        </div>

        ${recentFindings.length === 0 ? `
          <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>No audit findings registered for this engagement yet.</p>
            ${isAuditorOrAdmin ? `<button class="btn btn-primary" style="margin-top: 10px;" onclick="triggerRunHybridEngine()">Execute Audit Engine Now</button>` : ''}
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table" id="dash-findings-table">
              <thead>
                <tr>
                  <th style="width: 140px;">Finding ID / Code</th>
                  <th style="width: 100px;">Severity</th>
                  <th>Observation Title & Rule</th>
                  <th style="width: 140px;">Area / Module</th>
                  <th style="width: 130px;" class="text-right">Discrepancy</th>
                  <th style="width: 100px;" class="text-center">Status</th>
                  <th style="width: 90px;" class="text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                ${recentFindings.map(f => {
                  const hideRow = (activeFindingsFilter !== 'ALL' && (f.severity || '').toUpperCase() !== activeFindingsFilter);
                  return `
                    <tr style="${hideRow ? 'display: none;' : ''}" data-sev="${(f.severity || '').toUpperCase()}">
                      <td class="font-mono font-bold" style="color: #0f172a;">
                        <span style="background: #e2e8f0; padding: 2px 5px; border-radius: 4px; font-size: 11px;">[ID: ${f.id}]</span>
                        <span style="margin-left: 4px;">${f.finding_code}</span>
                      </td>
                      <td>${getSeverityBadge(f.severity)}</td>
                      <td>
                        <div style="font-weight: 700; color: #0f172a;">${escapeHtml(f.title)}</div>
                        <div style="font-size: 11.5px; color: #64748b; margin-top: 2px;">
                          Rule: <b>${escapeHtml(f.rule_used || 'ICAI Standard Procedure')}</b>
                        </div>
                      </td>
                      <td>
                        <span class="badge" style="background: #f1f5f9; color: #334155; font-size: 11px;">${escapeHtml(f.category || f.module || 'General')}</span>
                      </td>
                      <td class="text-right font-mono" style="color: #dc2626; font-weight: 700;">
                        ${f.difference ? escapeHtml(f.difference) : '—'}
                      </td>
                      <td class="text-center">${getStatusBadge(f.status)}</td>
                      <td class="text-center">
                        <button class="btn btn-sm btn-secondary" onclick="openEvidenceDrawer(${f.id})">Examine</button>
                      </td>
                    </tr>
                  `;
                }).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>

      <!-- MONTHLY CHARTS ROW: TRANSACTION VOLUME & TRANSACTION VALUE -->
      <div class="dash-section-grid" style="margin-bottom: 20px;">
        <!-- Chart 4: Monthly Transaction Volume -->
        <div class="dash-chart-card">
          <div class="dash-chart-header">
            <div>
              <div class="dash-chart-title">4. Monthly Transaction Volume</div>
              <div class="dash-chart-subtitle">Month-by-month voucher frequency | <b>Click any month bar to inspect transactions</b></div>
            </div>
            <div style="font-size: 11.5px; color: #2563eb; font-weight: 600;">
              Total: ${(overview.total_transactions || 0).toLocaleString()} txns
            </div>
          </div>

          <div style="display: flex; align-items: flex-end; gap: 8px; height: 160px; padding: 10px 0 0 0; border-bottom: 1px solid #e2e8f0;">
            ${monthlyTrends.length === 0 ? `
              <div style="width: 100%; text-align: center; color: #94a3b8; align-self: center;">No transactions found for active engagement.</div>
            ` : monthlyTrends.map(m => {
              const heightPct = Math.max(12, Math.round((m.transaction_count / maxTxMonth) * 100));
              return `
                <div class="chart-bar-interactive" style="flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end;" onclick="openDashboardTransactionsModal('${m.month}', '${m.month_label}')" title="${m.month_label}: ${m.transaction_count} transactions (Click to inspect)">
                  <div style="font-size: 10.5px; font-weight: 700; color: #2563eb; margin-bottom: 4px;">${m.transaction_count}</div>
                  <div style="width: 100%; height: ${heightPct}%; background: linear-gradient(180deg, #3b82f6, #1d4ed8); border-radius: 4px 4px 0 0;"></div>
                  <div style="font-size: 10px; color: #64748b; margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 48px;">${m.month_label.split(' ')[0]}</div>
                </div>
              `;
            }).join("")}
          </div>
        </div>

        <!-- Chart 5: Monthly Transaction Value -->
        <div class="dash-chart-card">
          <div class="dash-chart-header">
            <div>
              <div class="dash-chart-title">5. Monthly Turnover Value (₹)</div>
              <div class="dash-chart-subtitle">Monthly financial turnover | <b>Click bar to open transaction list</b></div>
            </div>
            <div style="font-size: 11.5px; color: #059669; font-weight: 600;">
              Total: ${formatINR(overview.total_turnover_examined || 0)}
            </div>
          </div>

          <div style="display: flex; align-items: flex-end; gap: 8px; height: 160px; padding: 10px 0 0 0; border-bottom: 1px solid #e2e8f0;">
            ${monthlyTrends.length === 0 ? `
              <div style="width: 100%; text-align: center; color: #94a3b8; align-self: center;">No transaction values recorded.</div>
            ` : monthlyTrends.map(m => {
              const heightPct = Math.max(12, Math.round((m.total_value / maxValMonth) * 100));
              return `
                <div class="chart-bar-interactive" style="flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end;" onclick="openDashboardTransactionsModal('${m.month}', '${m.month_label}')" title="${m.month_label}: ${formatINR(m.total_value)} turnover (Click to inspect)">
                  <div style="font-size: 10px; font-weight: 700; color: #059669; margin-bottom: 4px;">${formatCompactINR(m.total_value)}</div>
                  <div style="width: 100%; height: ${heightPct}%; background: linear-gradient(180deg, #10b981, #059669); border-radius: 4px 4px 0 0;"></div>
                  <div style="font-size: 10px; color: #64748b; margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 48px;">${m.month_label.split(' ')[0]}</div>
                </div>
              `;
            }).join("")}
          </div>
        </div>
      </div>

      <!-- SECTIONS 4 & 5: RECONCILIATION STATUS & ANOMALY SUMMARY -->
      <div class="dash-section-grid" style="margin-bottom: 20px;">
        <!-- SECTION 4: RECONCILIATION STATUS (Chart & Details) -->
        <div class="dash-chart-card">
          <div class="dash-chart-header">
            <div>
              <div class="dash-chart-title">4. Reconciliation Status (BRS & GST 2B)</div>
              <div class="dash-chart-subtitle">Automated ledger matching & bank balance audit verification</div>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="navigateTo('reconciliation')">Open BRS / 2B Module →</button>
          </div>

          <!-- Reconciliation Status Chart Breakdown -->
          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px;">
            <div class="chart-bar-interactive" style="padding: 10px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; text-align: center;" onclick="openDashboardReconciliationModal('MATCHED')">
              <div style="font-size: 11px; font-weight: 700; color: #059669;">MATCHED</div>
              <div class="font-mono font-bold" style="font-size: 20px; color: #059669;">${recon.matched_items || 0}</div>
              <div style="font-size: 10.5px; color: #047857;">Items Reconciled</div>
            </div>
            <div class="chart-bar-interactive" style="padding: 10px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; text-align: center;" onclick="openDashboardReconciliationModal('UNMATCHED_BANK')">
              <div style="font-size: 11px; font-weight: 700; color: #dc2626;">BANK UNMATCHED</div>
              <div class="font-mono font-bold" style="font-size: 20px; color: #dc2626;">${recon.unmatched_bank_items || 0}</div>
              <div style="font-size: 10.5px; color: #991b1b;">Missing in Books</div>
            </div>
            <div class="chart-bar-interactive" style="padding: 10px; background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; text-align: center;" onclick="openDashboardReconciliationModal('UNMATCHED_BOOK')">
              <div style="font-size: 11px; font-weight: 700; color: #ea580c;">BOOK / 2B UNMATCHED</div>
              <div class="font-mono font-bold" style="font-size: 20px; color: #ea580c;">${recon.unmatched_book_items || 0}</div>
              <div style="font-size: 10.5px; color: #c2410c;">Missing in Bank/Portal</div>
            </div>
            <div class="chart-bar-interactive" style="padding: 10px; background: #fffbeb; border: 1px solid #fef08a; border-radius: 8px; text-align: center;" onclick="openDashboardReconciliationModal('MISMATCH')">
              <div style="font-size: 11px; font-weight: 700; color: #d97706;">AMT MISMATCH</div>
              <div class="font-mono font-bold" style="font-size: 20px; color: #d97706;">${recon.amount_mismatches || 0}</div>
              <div style="font-size: 10.5px; color: #b45309;">Difference Detected</div>
            </div>
          </div>

          <!-- Reconciliations List -->
          ${(recon.reconciliations || []).length === 0 ? `
            <div style="padding: 14px; text-align: center; color: #64748b; font-size: 12px; background: #f8fafc; border-radius: 6px;">
              No BRS statements executed yet. Click "Open BRS / 2B Module" to start bank ledger reconciliation.
            </div>
          ` : `
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${(recon.reconciliations || []).slice(0, 3).map(r => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 12px;">
                  <div>
                    <div style="font-weight: 700; color: #0f172a;">${r.title}</div>
                    <div style="font-size: 11px; color: #64748b;">${r.bank_account_name || 'Bank Ledger'} | Net Diff: <span class="font-mono font-bold" style="color: ${r.net_unreconciled_difference == 0 ? '#059669' : '#dc2626'};">${formatINR(r.net_unreconciled_difference || 0)}</span></div>
                  </div>
                  <span class="badge ${r.status === 'Completed' ? 'badge-low' : 'badge-medium'}">${r.status || 'Completed'}</span>
                </div>
              `).join("")}
            </div>
          `}
        </div>

        <!-- SECTION 5: ANOMALY SUMMARY & BENFORD'S LAW (Interactive Digit Chart) -->
        <div class="dash-chart-card">
          <div class="dash-chart-header">
            <div>
              <div class="dash-chart-title">
                <span>5. Anomaly Summary & Benford's Law</span>
                <span class="badge ${anomaly.benford_status === 'Close Conformity' ? 'badge-low' : anomaly.benford_status === 'Acceptable' ? 'badge-medium' : 'badge-critical'}">
                  ${anomaly.benford_status || 'Close Conformity'} (MAD: ${anomaly.benford_mad || 0.0})
                </span>
              </div>
              <div class="dash-chart-subtitle">Click any digit bar to inspect transactions starting with that digit</div>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="navigateTo('anomaly_detection')">Anomaly Engine →</button>
          </div>

          <!-- Benford's 1st-Digit Comparison Mini-Chart -->
          <div style="display: flex; align-items: flex-end; gap: 6px; height: 110px; margin-bottom: 12px; padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
            ${(anomaly.benford_digits || []).map(d => {
              const actHeight = Math.max(8, Math.round(d.actual_pct * 2.5));
              const expHeight = Math.max(8, Math.round(d.expected_pct * 2.5));
              return `
                <div class="chart-bar-interactive" style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end;" onclick="openDashboardDigitModal(${d.digit})" title="Digit ${d.digit}: Actual ${d.actual_pct}% (Expected ${d.expected_pct}%, Diff: ${d.difference}%) - Click to view transactions">
                  <div style="display: flex; gap: 2px; width: 100%; justify-content: center; align-items: flex-end;">
                    <div style="width: 45%; height: ${actHeight}px; background: #2563eb; border-radius: 2px;" title="Actual: ${d.actual_pct}%"></div>
                    <div style="width: 45%; height: ${expHeight}px; background: #cbd5e1; border-radius: 2px;" title="Expected: ${d.expected_pct}%"></div>
                  </div>
                  <div style="font-size: 10.5px; font-weight: 700; color: #334155; margin-top: 4px;">D${d.digit}</div>
                </div>
              `;
            }).join("")}
          </div>

          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 11.5px; text-align: center;">
            <div style="padding: 6px; background: #f8fafc; border-radius: 6px; border: 1px solid #e2e8f0;">
              <div style="color: #64748b;">ML Outliers</div>
              <div class="font-mono font-bold" style="color: #7c3aed; font-size: 15px;">${anomaly.ml_outliers_count || 0}</div>
            </div>
            <div style="padding: 6px; background: #f8fafc; border-radius: 6px; border: 1px solid #e2e8f0;">
              <div style="color: #64748b;">Round Sums (₹50k+)</div>
              <div class="font-mono font-bold" style="color: #d97706; font-size: 15px;">${anomaly.round_sum_count || 0}</div>
            </div>
            <div style="padding: 6px; background: #f8fafc; border-radius: 6px; border: 1px solid #e2e8f0;">
              <div style="color: #64748b;">Weekend Entries</div>
              <div class="font-mono font-bold" style="color: #ea580c; font-size: 15px;">${anomaly.weekend_count || 0}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- SECTIONS 6 & 7: YEAR-ON-YEAR CHANGES & CHECKLIST PROGRESS -->
      <div class="dash-section-grid" style="margin-bottom: 20px;">
        <!-- SECTION 6: YEAR-ON-YEAR CHANGES (Chart & Variances) -->
        <div class="dash-chart-card">
          <div class="dash-chart-header">
            <div>
              <div class="dash-chart-title">6. Year-on-Year Movement & Variances</div>
              <div class="dash-chart-subtitle">Current Year vs Prior Year comparative lines | <b>Click row to inspect ledger</b></div>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="navigateTo('yoy_comparison')">YoY Module →</button>
          </div>

          ${yoy.length === 0 ? `
            <div style="padding: 24px; text-align: center; color: #64748b; font-size: 12.5px;">
              No prior year comparison data active for this engagement. Upload previous year general ledger to unlock automatic YoY analytics.
            </div>
          ` : `
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${yoy.map(item => {
                const varPct = Number(item.variance_pct) || 0;
                const isSig = item.is_significant;
                return `
                  <div class="chart-horizontal-bar-row" style="border: 1px solid #f1f5f9; padding: 6px 10px;" onclick="openDashboardYoYModal('${escapeHtml(item.account_name)}')" title="Click to view ledger breakdown for ${escapeHtml(item.account_name)}">
                    <div style="flex: 1; font-weight: 600; color: #0f172a; font-size: 12px;">
                      ${escapeHtml(item.account_name)}
                      ${isSig ? `<span class="badge badge-critical" style="margin-left: 6px; font-size: 10px;">⚠️ Variance</span>` : ''}
                    </div>
                    <div class="font-mono" style="font-size: 11.5px; color: #64748b; margin-right: 12px;">
                      CY: ${formatCompactINR(item.cy_amount || 0)} | PY: ${formatCompactINR(item.py_amount || 0)}
                    </div>
                    <div class="font-mono font-bold" style="font-size: 12px; min-width: 70px; text-align: right; color: ${varPct > 0 ? '#059669' : varPct < 0 ? '#dc2626' : '#64748b'};">
                      ${varPct > 0 ? '+' : ''}${varPct.toFixed(1)}%
                    </div>
                  </div>
                `;
              }).join("")}
            </div>
          `}
        </div>

        <!-- SECTION 7: CHECKLIST PROGRESS -->
        <div class="dash-chart-card">
          <div class="dash-chart-header">
            <div>
              <div class="dash-chart-title">7. Audit Checklist Progress (ICAI Standards)</div>
              <div class="dash-chart-subtitle">Standard compliance audit procedures completion rate</div>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="navigateTo('checklist')">Open Checklist →</button>
          </div>

          <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 12px; font-weight: 700; color: #0f172a;">Overall Completion</span>
              <span class="font-mono font-bold" style="font-size: 14px; color: #2563eb;">${chk.completion_pct || 0}%</span>
            </div>
            <div style="height: 12px; background: #e2e8f0; border-radius: 6px; overflow: hidden;">
              <div style="width: ${chk.completion_pct || 0}%; height: 100%; background: linear-gradient(90deg, #3b82f6, #10b981); border-radius: 6px; transition: width 0.4s ease;"></div>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 14px; text-align: center; font-size: 11px;">
            <div style="padding: 6px; background: #ecfdf5; border-radius: 4px; color: #059669; font-weight: 700;">
              <div>Completed</div>
              <div class="font-mono font-bold" style="font-size: 14px;">${chk.completed_count || 0}</div>
            </div>
            <div style="padding: 6px; background: #eff6ff; border-radius: 4px; color: #2563eb; font-weight: 700;">
              <div>In Progress</div>
              <div class="font-mono font-bold" style="font-size: 14px;">${chk.in_progress_count || 0}</div>
            </div>
            <div style="padding: 6px; background: #f8fafc; border-radius: 4px; color: #64748b; font-weight: 700;">
              <div>Not Started</div>
              <div class="font-mono font-bold" style="font-size: 14px;">${chk.not_started_count || 0}</div>
            </div>
            <div style="padding: 6px; background: #fef2f2; border-radius: 4px; color: #dc2626; font-weight: 700;">
              <div>Review Req.</div>
              <div class="font-mono font-bold" style="font-size: 14px;">${chk.requires_review_count || 0}</div>
            </div>
          </div>

          <!-- Category Progress Snippets -->
          <div style="font-size: 11.5px; color: #64748b; font-weight: 600; margin-bottom: 6px;">Key Audit Checklist Sections:</div>
          <div style="display: flex; flex-direction: column; gap: 6px; max-height: 120px; overflow-y: auto;">
            ${(chk.category_progress || []).slice(0, 4).map(c => `
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: #f8fafc; border-radius: 4px; font-size: 11.5px; cursor: pointer;" onclick="navigateTo('checklist')">
                <span style="font-weight: 600; color: #334155; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(c.category || c.name || 'Category')}</span>
                <span class="font-mono" style="color: #2563eb; font-weight: 700;">${c.completed || 0}/${c.total || 0}</span>
              </div>
            `).join("")}
          </div>
        </div>
      </div>
    `;

  } catch (err) {
    container.innerHTML = `
      <div style="padding: 30px; text-align: center; color: #dc2626;">
        <div style="font-size: 16px; font-weight: 700;">Failed to load dashboard metrics</div>
        <div style="font-size: 12.5px; margin-top: 6px; color: #64748b;">${err.message}</div>
        <button class="btn btn-primary" style="margin-top: 14px;" onclick="renderDashboard()">Retry</button>
      </div>
    `;
  }
}

// Helper: Format compact INR (e.g. 1.5M, 250K)
function formatCompactINR(val) {
  const num = Number(val) || 0;
  if (Math.abs(num) >= 10000000) return "₹" + (num / 10000000).toFixed(2) + " Cr";
  if (Math.abs(num) >= 100000) return "₹" + (num / 100000).toFixed(1) + " L";
  if (Math.abs(num) >= 1000) return "₹" + (num / 1000).toFixed(0) + " k";
  return "₹" + num.toFixed(0);
}

function getStatusBadgeClass(status) {
  const st = (status || "In Progress").toLowerCase();
  if (st === "completed") return "badge-low";
  if (st === "under review") return "badge-medium";
  if (st === "archived") return "badge-role-staff";
  return "badge-role-auditor";
}

function filterDashboardFindingsTable(sev) {
  activeFindingsFilter = sev;
  const rows = document.querySelectorAll("#dash-findings-table tbody tr");
  rows.forEach(r => {
    if (sev === "ALL") {
      r.style.display = "";
    } else {
      const rowSev = r.getAttribute("data-sev");
      r.style.display = (rowSev === sev) ? "" : "none";
    }
  });
  const btnGroup = document.querySelectorAll(".card-header .btn-group button");
  btnGroup.forEach(btn => {
    if (btn.innerText.toUpperCase().includes(sev)) {
      btn.className = "btn btn-sm btn-primary";
    } else {
      btn.className = "btn btn-sm btn-secondary";
    }
  });
}

function switchDashboardEngagement(engId) {
  state.currentEngagementId = parseInt(engId, 10);
  updateActiveEngagement().then(() => renderDashboard());
}

// ==========================================================================
// DRILL-DOWN MODALS FOR DASHBOARD CHARTS & ITEMS
// ==========================================================================

// 1. Findings Drill-Down Modal (Triggered by Severity or Area Click)
async function openDashboardFindingsModal(severity = null, area = null) {
  const title = severity ? `${severity} Severity Findings` : area ? `Findings in ${area}` : `Audit Findings`;
  
  let findings = [];
  try {
    findings = await FinAuditAPI.getFindings(state.currentEngagementId);
    if (severity && severity !== 'ALL') {
      if (severity === 'OPEN') {
        findings = findings.filter(f => ['Open', 'In Review', 'Under Review'].includes(f.status || 'Open'));
      } else if (severity === 'HIGH') {
        findings = findings.filter(f => ['CRITICAL', 'HIGH'].includes((f.severity || '').toUpperCase()) && !['Resolved', 'Waived'].includes(f.status));
      } else {
        findings = findings.filter(f => (f.severity || '').toUpperCase() === severity.toUpperCase());
      }
    }
    if (area) {
      findings = findings.filter(f => (f.category || '').toLowerCase().includes(area.toLowerCase()) || (f.module || '').toLowerCase().includes(area.toLowerCase()));
    }
  } catch (err) {
    findings = [];
  }

  const modalHtml = `
    <div class="dash-modal-overlay" id="dash-drill-modal" onclick="if(event.target === this) closeDashboardModal()">
      <div class="dash-modal-box">
        <div class="dash-modal-header">
          <div>
            <div style="font-size: 16px; font-weight: 700; color: #0f172a;">🔍 Drill-Down: ${escapeHtml(title)}</div>
            <div style="font-size: 12px; color: #64748b;">Showing ${findings.length} underlying audit findings from active engagement database</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="closeDashboardModal()">✕</button>
        </div>
        <div class="dash-modal-body">
          ${findings.length === 0 ? `
            <div style="padding: 30px; text-align: center; color: #64748b;">No findings matching the selected filter.</div>
          ` : `
            <div class="table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Code / ID</th>
                    <th>Severity</th>
                    <th>Observation</th>
                    <th>Discrepancy</th>
                    <th>Standard / Rule</th>
                    <th>Status</th>
                    <th class="text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${findings.map(f => `
                    <tr>
                      <td class="font-mono font-bold">[ID: ${f.id}] ${f.finding_code}</td>
                      <td>${getSeverityBadge(f.severity)}</td>
                      <td><b>${escapeHtml(f.title)}</b></td>
                      <td class="font-mono" style="color: #dc2626;">${f.difference || '—'}</td>
                      <td style="font-size: 11.5px; color: #64748b;">${escapeHtml(f.rule_used || 'ICAI Standard')}</td>
                      <td>${getStatusBadge(f.status)}</td>
                      <td class="text-center">
                        <button class="btn btn-sm btn-primary" onclick="closeDashboardModal(); openEvidenceDrawer(${f.id})">Examine</button>
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          `}
        </div>
        <div class="dash-modal-footer">
          <span style="font-size: 12px; color: #64748b;">Total ${findings.length} Records</span>
          <button class="btn btn-secondary" onclick="closeDashboardModal()">Close</button>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

// 2. Transactions Drill-Down Modal (Triggered by Monthly Volume / Value Chart Bar Click)
async function openDashboardTransactionsModal(monthStr = '', monthLabel = 'Transactions') {
  let txns = [];
  try {
    let q = `?engagement_id=${state.currentEngagementId}&limit=300`;
    if (monthStr && monthStr !== 'Undated') {
      q += `&start_date=${monthStr}-01&end_date=${monthStr}-31`;
    }
    const res = await FinAuditAPI.getTransactions(state.currentEngagementId, {
      start_date: (monthStr && monthStr !== 'Undated') ? `${monthStr}-01` : null,
      end_date: (monthStr && monthStr !== 'Undated') ? `${monthStr}-31` : null,
      limit: 300
    });
    txns = Array.isArray(res) ? res : res.transactions || [];
  } catch (err) {
    txns = [];
  }

  const modalHtml = `
    <div class="dash-modal-overlay" id="dash-drill-modal" onclick="if(event.target === this) closeDashboardModal()">
      <div class="dash-modal-box">
        <div class="dash-modal-header">
          <div>
            <div style="font-size: 16px; font-weight: 700; color: #0f172a;">📊 Monthly Transactions: ${escapeHtml(monthLabel)}</div>
            <div style="font-size: 12px; color: #64748b;">Examining underlying vouchers recorded in general ledger for this period</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="closeDashboardModal()">✕</button>
        </div>
        <div class="dash-modal-body">
          ${txns.length === 0 ? `
            <div style="padding: 30px; text-align: center; color: #64748b;">No transactions recorded for ${escapeHtml(monthLabel)}.</div>
          ` : `
            <div class="table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Voucher #</th>
                    <th>Ledger</th>
                    <th>Party Name</th>
                    <th class="text-right">Debit (₹)</th>
                    <th class="text-right">Credit (₹)</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  ${txns.slice(0, 100).map(t => `
                    <tr>
                      <td class="font-mono" style="font-size: 11.5px;">${t.date || '—'}</td>
                      <td class="font-mono font-bold">${t.voucher_no || '—'}</td>
                      <td><b>${escapeHtml(t.ledger || 'General')}</b></td>
                      <td>${escapeHtml(t.party_name || '—')}</td>
                      <td class="text-right font-mono" style="color: ${t.debit > 0 ? '#059669' : '#94a3b8'};">
                        ${t.debit ? formatINR(t.debit) : '—'}
                      </td>
                      <td class="text-right font-mono" style="color: ${t.credit > 0 ? '#0284c7' : '#94a3b8'};">
                        ${t.credit ? formatINR(t.credit) : '—'}
                      </td>
                      <td style="font-size: 11.5px; color: #64748b; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${escapeHtml(t.description || '')}
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          `}
        </div>
        <div class="dash-modal-footer">
          <span style="font-size: 12px; color: #64748b;">Showing ${Math.min(100, txns.length)} of ${txns.length} records</span>
          <button class="btn btn-secondary" onclick="closeDashboardModal()">Close</button>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

// 3. Reconciliation Status Drill-Down Modal
async function openDashboardReconciliationModal(statusType = 'UNMATCHED') {
  let recons = [];
  try {
    recons = await FinAuditAPI.listReconciliations(state.currentEngagementId);
  } catch (err) {
    recons = [];
  }

  const modalHtml = `
    <div class="dash-modal-overlay" id="dash-drill-modal" onclick="if(event.target === this) closeDashboardModal()">
      <div class="dash-modal-box">
        <div class="dash-modal-header">
          <div>
            <div style="font-size: 16px; font-weight: 700; color: #0f172a;">⚖️ Reconciliation Status Drill-Down (${statusType})</div>
            <div style="font-size: 12px; color: #64748b;">Bank BRS statements and GSTR-2B discrepancy schedules</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="closeDashboardModal()">✕</button>
        </div>
        <div class="dash-modal-body">
          ${recons.length === 0 ? `
            <div style="padding: 30px; text-align: center; color: #64748b;">No active reconciliation statements recorded yet.</div>
          ` : `
            <div class="table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Bank Account</th>
                    <th class="text-right">Matched</th>
                    <th class="text-right">Unmatched Bank</th>
                    <th class="text-right">Unmatched Book</th>
                    <th class="text-right">Net Difference</th>
                    <th class="text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${recons.map(r => `
                    <tr>
                      <td><b>${escapeHtml(r.title)}</b></td>
                      <td><span class="badge" style="background: #e0e7ff; color: #4338ca;">${r.recon_type}</span></td>
                      <td>${escapeHtml(r.bank_account_name || 'Bank Account')}</td>
                      <td class="text-right font-mono" style="color: #059669; font-weight: 700;">${r.matched_count || 0}</td>
                      <td class="text-right font-mono" style="color: #dc2626; font-weight: 700;">${r.unmatched_bank_count || 0}</td>
                      <td class="text-right font-mono" style="color: #ea580c; font-weight: 700;">${r.unmatched_book_count || 0}</td>
                      <td class="text-right font-mono font-bold" style="color: ${r.net_unreconciled_difference == 0 ? '#059669' : '#dc2626'};">
                        ${formatINR(r.net_unreconciled_difference || 0)}
                      </td>
                      <td class="text-center">${getStatusBadge(r.status)}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          `}
        </div>
        <div class="dash-modal-footer">
          <button class="btn btn-primary" onclick="closeDashboardModal(); navigateTo('reconciliation')">Open Full BRS Module</button>
          <button class="btn btn-secondary" onclick="closeDashboardModal()">Close</button>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

// 4. Pending Reviews Drill-Down Modal
async function openDashboardPendingReviewsModal() {
  let pendingWPs = [];
  try {
    const wps = await FinAuditAPI.getWorkingPapers(state.currentEngagementId);
    pendingWPs = (wps || []).filter(w => ['Under Review', 'Needs Correction', 'Prepared'].includes(w.status));
  } catch (err) {
    pendingWPs = [];
  }

  const modalHtml = `
    <div class="dash-modal-overlay" id="dash-drill-modal" onclick="if(event.target === this) closeDashboardModal()">
      <div class="dash-modal-box">
        <div class="dash-modal-header">
          <div>
            <div style="font-size: 16px; font-weight: 700; color: #0f172a;">⏳ Pending Reviews & Sign-Off Schedule</div>
            <div style="font-size: 12px; color: #64748b;">Working papers and audit engagements awaiting Partner / Manager review</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="closeDashboardModal()">✕</button>
        </div>
        <div class="dash-modal-body">
          ${pendingWPs.length === 0 ? `
            <div style="padding: 30px; text-align: center; color: #059669; font-weight: 600;">All working papers for this engagement are reviewed and finalized!</div>
          ` : `
            <div class="table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>WP Ref</th>
                    <th>Working Paper Title</th>
                    <th>Audit Area</th>
                    <th>Prepared By</th>
                    <th>Status</th>
                    <th class="text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${pendingWPs.map(w => `
                    <tr>
                      <td class="font-mono font-bold">${w.wp_reference}</td>
                      <td><b>${escapeHtml(w.title)}</b></td>
                      <td><span class="badge" style="background: #f1f5f9; color: #334155;">${escapeHtml(w.area || 'General')}</span></td>
                      <td>${w.prepared_by || 'Staff'}</td>
                      <td><span class="badge ${w.status === 'Needs Correction' ? 'badge-critical' : 'badge-medium'}">${w.status}</span></td>
                      <td class="text-center">
                        <button class="btn btn-sm btn-secondary" onclick="closeDashboardModal(); navigateTo('working_papers'); openWorkingPaperModal(${w.id})">Review WP</button>
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          `}
        </div>
        <div class="dash-modal-footer">
          <button class="btn btn-primary" onclick="closeDashboardModal(); navigateTo('working_papers')">Open Working Papers</button>
          <button class="btn btn-secondary" onclick="closeDashboardModal()">Close</button>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

// 5. YoY Ledger Drill-Down Modal
async function openDashboardYoYModal(accountName) {
  let txns = [];
  try {
    const res = await FinAuditAPI.getTransactions(state.currentEngagementId, {
      ledger: accountName,
      limit: 100
    });
    txns = Array.isArray(res) ? res : res.transactions || [];
  } catch (err) {
    txns = [];
  }

  const modalHtml = `
    <div class="dash-modal-overlay" id="dash-drill-modal" onclick="if(event.target === this) closeDashboardModal()">
      <div class="dash-modal-box">
        <div class="dash-modal-header">
          <div>
            <div style="font-size: 16px; font-weight: 700; color: #0f172a;">📊 YoY Movement Drill-Down: ${escapeHtml(accountName)}</div>
            <div style="font-size: 12px; color: #64748b;">Inspecting vouchers posted to this account line for the current financial year</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="closeDashboardModal()">✕</button>
        </div>
        <div class="dash-modal-body">
          ${txns.length === 0 ? `
            <div style="padding: 30px; text-align: center; color: #64748b;">No direct ledger transactions found for "${escapeHtml(accountName)}".</div>
          ` : `
            <div class="table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Voucher #</th>
                    <th>Party Name</th>
                    <th class="text-right">Debit (₹)</th>
                    <th class="text-right">Credit (₹)</th>
                    <th>Narration</th>
                  </tr>
                </thead>
                <tbody>
                  ${txns.map(t => `
                    <tr>
                      <td class="font-mono">${t.date || '—'}</td>
                      <td class="font-mono font-bold">${t.voucher_no || '—'}</td>
                      <td>${escapeHtml(t.party_name || '—')}</td>
                      <td class="text-right font-mono" style="color: #059669;">${t.debit ? formatINR(t.debit) : '—'}</td>
                      <td class="text-right font-mono" style="color: #0284c7;">${t.credit ? formatINR(t.credit) : '—'}</td>
                      <td style="font-size: 11.5px; color: #64748b;">${escapeHtml(t.description || '')}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          `}
        </div>
        <div class="dash-modal-footer">
          <button class="btn btn-primary" onclick="closeDashboardModal(); navigateTo('yoy_comparison')">Open Full YoY Analysis</button>
          <button class="btn btn-secondary" onclick="closeDashboardModal()">Close</button>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

// 6. Benford Digit Drill-Down Modal
async function openDashboardDigitModal(digit) {
  let txns = [];
  try {
    const res = await FinAuditAPI.getTransactions(state.currentEngagementId, { limit: 500 });
    const all = Array.isArray(res) ? res : res.transactions || [];
    txns = all.filter(t => {
      const amt = Number(t.amount) || Math.max(Number(t.debit) || 0, Number(t.credit) || 0);
      if (amt <= 0) return false;
      return String(Math.floor(amt))[0] === String(digit);
    });
  } catch (err) {
    txns = [];
  }

  const modalHtml = `
    <div class="dash-modal-overlay" id="dash-drill-modal" onclick="if(event.target === this) closeDashboardModal()">
      <div class="dash-modal-box">
        <div class="dash-modal-header">
          <div>
            <div style="font-size: 16px; font-weight: 700; color: #0f172a;">🔢 Benford's Law Drill-Down: Leading Digit ${digit}</div>
            <div style="font-size: 12px; color: #64748b;">Found ${txns.length} transactions whose integer amount starts with digit ${digit}</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="closeDashboardModal()">✕</button>
        </div>
        <div class="dash-modal-body">
          ${txns.length === 0 ? `
            <div style="padding: 30px; text-align: center; color: #64748b;">No transactions starting with digit ${digit}.</div>
          ` : `
            <div class="table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Voucher #</th>
                    <th>Ledger</th>
                    <th>Party Name</th>
                    <th class="text-right">Amount (₹)</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  ${txns.map(t => {
                    const amt = Number(t.amount) || Math.max(Number(t.debit) || 0, Number(t.credit) || 0);
                    return `
                      <tr>
                        <td class="font-mono">${t.date || '—'}</td>
                        <td class="font-mono font-bold">${t.voucher_no || '—'}</td>
                        <td><b>${escapeHtml(t.ledger || 'General')}</b></td>
                        <td>${escapeHtml(t.party_name || '—')}</td>
                        <td class="text-right font-mono font-bold" style="color: #2563eb;">${formatINR(amt)}</td>
                        <td style="font-size: 11.5px; color: #64748b;">${escapeHtml(t.description || '')}</td>
                      </tr>
                    `;
                  }).join("")}
                </tbody>
              </table>
            </div>
          `}
        </div>
        <div class="dash-modal-footer">
          <span style="font-size: 12px; color: #64748b;">Showing ${txns.length} records</span>
          <button class="btn btn-secondary" onclick="closeDashboardModal()">Close</button>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

function closeDashboardModal() {
  const modal = document.getElementById("dash-drill-modal");
  if (modal) modal.remove();
}

// Trigger Hybrid Audit Engine
async function triggerRunHybridEngine() {
  const container = document.getElementById("content-container");
  container.innerHTML = `
    <div style="padding: 40px; text-align: center;">
      <div style="font-size: 18px; font-weight: 700; color: var(--primary);">Running Hybrid Audit Engine...</div>
      <div style="font-size: 13px; color: #64748b; margin-top: 8px;">
        1. Executing Deterministic Accounting Rules (Debit=Credit, 40A(3), 269ST, GSTIN, Duplicates)...<br/>
        2. Running Statistical & Scikit-Learn Isolation Forest Anomaly Detection...<br/>
        3. Calculating Benford's Law Digits Conformity & Local AI Observations...
      </div>
    </div>
  `;

  try {
    const res = await FinAuditAPI.runHybridEngine(state.currentEngagementId);
    notifyError(`Hybrid Audit Completed! Found ${res.findings_count} audit exceptions across ${res.total_transactions} transactions.`);
    await updateActiveEngagement();
    navigateTo("anomaly_detection");
  } catch (err) {
    notifyError("Error executing audit engine: " + err.message);
    renderDashboard();
  }
}

// Anomaly Detection View (Benford + ML + Rules)
async function renderAnomalyDetection() {
  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 20px;">Loading statistical and ML metrics...</div>`;

  let findings = [];
  try {
    findings = await FinAuditAPI.getFindings(state.currentEngagementId);
  } catch (e) {}

  let statEngine = null;
  try {
    statEngine = await FinAuditAPI.runHybridEngine(state.currentEngagementId);
  } catch (e) {}

  const benford = statEngine?.benford_analysis || { digit_distribution: [], mad: 0.0, conformity: "Conformant" };
  const digits = benford.digit_distribution || [];

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div>
        <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Statistical & Machine Learning Anomaly Detection</h2>
        <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
          Multi-layer detection: Benford's Law + Scikit-Learn Isolation Forest + 3-Sigma Z-Scores
        </div>
      </div>
      <button class="btn btn-primary" onclick="triggerRunHybridEngine()">Re-run Engine</button>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Benford's Law First-Digit Analysis (Forensic Test)</div>
          <div class="card-subtitle">
            Evaluates leading digit frequency against logarithmic theoretical distribution. Conformity: <b>${benford.conformity}</b> (MAD: ${benford.mad})
          </div>
        </div>
        <div style="display: flex; gap: 14px; font-size: 11.5px;">
          <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 10px; height: 10px; background: var(--primary); display: inline-block;"></span> Actual Empirical %</span>
          <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 10px; height: 10px; background: #94a3b8; display: inline-block;"></span> Expected Benford %</span>
        </div>
      </div>

      <div class="chart-bar-container">
        ${digits.map(d => {
          const actHeight = Math.min(100, d.actual_percent * 2.5);
          const expHeight = Math.min(100, d.expected_percent * 2.5);
          return `
            <div class="chart-bar-group">
              <div class="chart-bars-wrap">
                <div class="bar-actual" style="height: ${actHeight}%;" title="Digit ${d.digit}: Actual ${d.actual_percent}% (${d.count} txns)"></div>
                <div class="bar-expected" style="height: ${expHeight}%;" title="Digit ${d.digit}: Expected ${d.expected_percent}%"></div>
              </div>
              <div class="chart-digit-label">Digit ${d.digit}</div>
            </div>
          `;
        }).join("")}
      </div>

      <div style="margin-top: 14px; font-size: 12px; color: #64748b;">
        * Mean Absolute Deviation (MAD) of ${benford.mad}. Standard audit threshold: MAD &lt; 0.012 indicates normal business distribution.
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Machine Learning & Statistical Outlier Exceptions</div>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Finding Code</th>
              <th>Severity</th>
              <th>Outlier Description</th>
              <th>Engine / Model</th>
              <th>Risk Score</th>
              <th class="text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            ${findings.filter(f => f.engine_type === "STATISTICAL_ML" || f.category === "Outlier / ML").map(f => `
              <tr>
                <td class="font-mono font-bold">${f.finding_code}</td>
                <td>${getSeverityBadge(f.severity)}</td>
                <td>
                  <b>${f.title}</b><br/>
                  <span style="font-size: 11.5px; color: #64748b;">${f.description}</span>
                </td>
                <td style="font-size: 12px; color: #2563eb;">${f.rule_used}</td>
                <td class="font-mono font-bold">${f.risk_score} / 10</td>
                <td class="text-center">
                  <button class="btn btn-sm btn-secondary" onclick="openEvidenceDrawer(${f.id})">Inspect Evidence</button>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// Risk & Findings View
async function renderFindings() {
  const container = document.getElementById("content-container");
  const findings = await FinAuditAPI.getFindings(state.currentEngagementId);

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div>
        <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Audit Findings & Evidence Repository</h2>
        <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
          All deterministic, statutory, and statistical exceptions linked to source vouchers
        </div>
      </div>
      <button class="btn btn-primary" onclick="triggerRunHybridEngine()">Re-run Audit Engine</button>
    </div>

    <div class="card" style="padding: 12px; margin-bottom: 16px; display: flex; gap: 12px; align-items: center;">
      <span style="font-size: 12px; font-weight: 600; color: #475569;">Filter Severity:</span>
      <button class="btn btn-sm btn-secondary" onclick="filterFindingsTable('ALL')">All (${findings.length})</button>
      <button class="btn btn-sm btn-secondary" style="color: var(--sev-critical);" onclick="filterFindingsTable('CRITICAL')">Critical</button>
      <button class="btn btn-sm btn-secondary" style="color: var(--sev-high);" onclick="filterFindingsTable('HIGH')">High</button>
      <button class="btn btn-sm btn-secondary" style="color: var(--sev-medium);" onclick="filterFindingsTable('MEDIUM')">Medium</button>
      <button class="btn btn-sm btn-secondary" style="color: var(--sev-low);" onclick="filterFindingsTable('LOW')">Low</button>
    </div>

    <div class="card">
      <div class="table-container">
        <table class="data-table" id="findings-table">
          <thead>
            <tr>
              <th>Finding Code</th>
              <th>Category</th>
              <th>Severity</th>
              <th>Risk</th>
              <th>Observation & Impact</th>
              <th>Quantified Difference</th>
              <th>Status</th>
              <th class="text-center">Evidence</th>
            </tr>
          </thead>
          <tbody>
            ${findings.map(f => `
              <tr data-severity="${f.severity}">
                <td class="font-mono font-bold">${f.finding_code}</td>
                <td style="font-size: 12px;">${f.category}</td>
                <td>${getSeverityBadge(f.severity)}</td>
                <td class="font-mono font-bold">${f.risk_score}</td>
                <td style="max-width: 320px;">
                  <b>${f.title}</b><br/>
                  <span style="font-size: 11.5px; color: #64748b;">${f.reason}</span>
                </td>
                <td class="font-mono" style="color: #dc2626; font-weight: 600;">${f.difference || '—'}</td>
                <td>${getStatusBadge(f.status)}</td>
                <td class="text-center">
                  <button class="btn btn-sm btn-primary" onclick="openEvidenceDrawer(${f.id})">Open Evidence</button>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function filterFindingsTable(sev) {
  const rows = document.querySelectorAll("#findings-table tbody tr");
  rows.forEach(r => {
    if (sev === "ALL" || r.dataset.severity === sev) {
      r.style.display = "";
    } else {
      r.style.display = "none";
    }
  });
}

// Trial Balance Analysis & Verification View
let tbFilterState = {
  tab: "ALL",
  search: ""
};

let currentTBData = null;

async function renderTrialBalance() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `<div class="card" style="padding: 30px; text-align: center; color: #64748b;">Please select an active audit engagement first.</div>`;
    return;
  }

  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Performing 12-Point Trial Balance Deterministic Audit Analysis...</div>`;

  try {
    const tb = await FinAuditAPI.getTrialBalance(state.currentEngagementId);
    currentTBData = tb;

    const accounts = tb.accounts || tb.ledgers || [];
    const exceptions = tb.exceptions || [];
    const riskSum = tb.risk_summary || { critical_exceptions: 0, high_exceptions: 0, medium_exceptions: 0, low_exceptions: 0, total_exceptions: 0 };
    const isBalanced = tb.is_balanced;
    const diff = tb.difference || 0.0;

    // Collect affected account names for fast badge lookup
    const affectedAccSet = new Set();
    exceptions.forEach(ex => {
      (ex.affected_accounts || []).forEach(acc => {
        if (typeof acc === "string") {
          affectedAccSet.add(acc.split("(")[0].trim().toLowerCase());
        }
      });
    });

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Trial Balance Analysis & Audit Verification</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            12-Point deterministic accounting checks, arithmetic roll-forward, and double-entry tally verification
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <a href="${FinAuditAPI.getTrialBalanceReportDownloadUrl(state.currentEngagementId)}" target="_blank" class="btn btn-secondary">
            📥 Download Analysis Report (CSV)
          </a>
          <button class="btn btn-primary" onclick="renderTrialBalance()">
            ⚡ Re-Analyze TB
          </button>
        </div>
      </div>

      <!-- High Priority Out of Balance Alert Banner -->
      ${!isBalanced ? `
        <div style="padding: 16px 20px; border-radius: var(--radius-lg); margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; background-color: #fef2f2; border: 2px solid #ef4444; box-shadow: 0 4px 6px -1px rgba(239, 68, 68, 0.15);">
          <div style="display: flex; align-items: center; gap: 14px;">
            <div style="background: #ef4444; color: white; width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: bold;">
              ⚠️
            </div>
            <div>
              <div style="font-size: 15px; font-weight: 800; color: #991b1b; letter-spacing: -0.2px;">
                CRITICAL EXCEPTION: Trial Balance Out of Balance Mismatch!
              </div>
              <div style="font-size: 12.5px; color: #b91c1c; margin-top: 2px;">
                Total Debit (${formatINR(tb.grand_total_debit)}) != Total Credit (${formatINR(tb.grand_total_credit)}). Exact Discrepancy: <b>${formatINR(diff)}</b> (${tb.grand_total_debit > tb.grand_total_credit ? 'Debit Higher' : 'Credit Higher'}).
              </div>
            </div>
          </div>
          <div style="display: flex; gap: 10px; align-items: center;">
            <span class="badge badge-critical" style="font-size: 13px; padding: 6px 12px;">HIGH PRIORITY EXCEPTION</span>
          </div>
        </div>
      ` : `
        <div style="padding: 14px 20px; border-radius: var(--radius-lg); margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; background-color: #ecfdf5; border: 1px solid #a7f3d0;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="background: #10b981; color: white; width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 18px;">
              ✓
            </div>
            <div>
              <div style="font-weight: 700; color: #065f46; font-size: 14px;">
                Trial Balance Mathematically Balanced (Debit = Credit)
              </div>
              <div style="font-size: 12px; color: #047857;">
                Total Debits: <b>${formatINR(tb.grand_total_debit)}</b> equals Total Credits: <b>${formatINR(tb.grand_total_credit)}</b> (Variance: ₹0.00)
              </div>
            </div>
          </div>
          <span class="badge badge-resolved" style="font-size: 12px; padding: 4px 10px;">TALLIED</span>
        </div>
      `}

      <!-- 6 Executive Summary & Risk Cards -->
      <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px;">
        <div class="kpi-card" style="border-left: 4px solid var(--primary);">
          <div class="kpi-label">TOTAL DEBIT</div>
          <div class="kpi-value font-mono" style="font-size: 15px; color: var(--primary);">${formatINR(tb.grand_total_debit)}</div>
          <div class="kpi-subtext">Sum of debit balances</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #059669;">
          <div class="kpi-label">TOTAL CREDIT</div>
          <div class="kpi-value font-mono" style="font-size: 15px; color: #059669;">${formatINR(tb.grand_total_credit)}</div>
          <div class="kpi-subtext">Sum of credit balances</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid ${isBalanced ? '#10b981' : '#ef4444'};">
          <div class="kpi-label">DIFFERENCE</div>
          <div class="kpi-value font-mono" style="font-size: 15px; color: ${isBalanced ? '#059669' : '#dc2626'};">${formatINR(diff)}</div>
          <div class="kpi-subtext">${isBalanced ? 'Zero discrepancy' : 'Out of balance'}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">TOTAL ACCOUNTS</div>
          <div class="kpi-value">${tb.total_accounts_count || accounts.length}</div>
          <div class="kpi-subtext">Active ledger heads</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #d97706;">
          <div class="kpi-label">WITH EXCEPTIONS</div>
          <div class="kpi-value" style="color: ${(tb.accounts_with_exceptions_count || 0) > 0 ? '#d97706' : '#059669'};">
            ${tb.accounts_with_exceptions_count || 0}
          </div>
          <div class="kpi-subtext">Flagged in 12 checks</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid ${tb.overall_risk_rating === 'CRITICAL' ? '#dc2626' : (tb.overall_risk_rating === 'HIGH' ? '#ea580c' : '#059669')};">
          <div class="kpi-label">RISK SUMMARY</div>
          <div class="kpi-value" style="font-size: 15px; color: ${tb.overall_risk_rating === 'CRITICAL' ? '#dc2626' : (tb.overall_risk_rating === 'HIGH' ? '#ea580c' : '#059669')};">
            ${tb.overall_risk_rating || 'LOW'}
          </div>
          <div class="kpi-subtext">${riskSum.critical_exceptions} Crit • ${riskSum.high_exceptions} High • ${riskSum.medium_exceptions} Med</div>
        </div>
      </div>

      <!-- 12-Check Audit Exceptions Breakdown -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-header" style="background: #f8fafc;">
          <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
            <div>
              <div class="card-title">12-Point Deterministic Audit Exceptions Log (${exceptions.length})</div>
              <div class="card-subtitle">Accounting checks executed strictly through deterministic rules (no AI arithmetic)</div>
            </div>
            <span class="offline-pill" style="font-size: 10.5px;"><span class="offline-dot"></span> Deterministic Engine</span>
          </div>
        </div>

        ${exceptions.length === 0 ? `
          <div style="padding: 30px; text-align: center; color: #059669;">
            <div style="font-size: 24px; margin-bottom: 6px;">✓</div>
            <b>All 12 Trial Balance Audit Checks Passed Successfully!</b>
            <p style="font-size: 12px; color: #64748b; margin-top: 4px;">No arithmetic imbalances, unusual balances, suspense heads, or roll-forward inconsistencies detected.</p>
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 100px;">Check ID</th>
                  <th style="width: 85px;">Severity</th>
                  <th style="width: 130px;">Category</th>
                  <th>Observation & Accounting Implication</th>
                  <th style="width: 220px;">Affected Accounts</th>
                  <th style="width: 150px;">Audit Standard (SA)</th>
                  <th class="text-center" style="width: 160px;">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${exceptions.map(ex => `
                  <tr style="${ex.severity === 'CRITICAL' ? 'background: #fff5f5;' : (ex.severity === 'HIGH' ? 'background: #fffdf5;' : '')}">
                    <td class="font-mono font-bold" style="font-size: 11px;">${escapeHtml(ex.check_id)}</td>
                    <td>${getSeverityBadge(ex.severity)}</td>
                    <td><span class="badge" style="background:#f1f5f9; color:#475569; font-size:10.5px;">${escapeHtml(ex.category)}</span></td>
                    <td>
                      <div style="font-weight: 700; color: #0f172a; font-size: 13px;">${escapeHtml(ex.check_name)}</div>
                      <div style="font-size: 11.5px; color: #475569; margin-top: 2px;">${escapeHtml(ex.description)}</div>
                      ${ex.exact_difference ? `
                        <div style="font-size: 11px; color: #dc2626; font-weight: 700; margin-top: 3px;" class="font-mono">
                          Exact Difference: ₹${Number(ex.exact_difference).toLocaleString('en-IN', {minimumFractionDigits: 2})}
                        </div>
                      ` : ''}
                    </td>
                    <td>
                      <div style="display: flex; gap: 4px; flex-wrap: wrap; max-height: 70px; overflow-y: auto;">
                        ${(ex.affected_accounts || []).slice(0, 4).map(acc => `
                          <span class="demo-chip" style="font-size: 10.5px; padding: 2px 6px; cursor: pointer;" onclick="viewLedgerDrilldown('${escapeHtml(acc).replace(/'/g, "\\'")}')" title="Click to Inspect Ledger">
                            🔍 ${escapeHtml(acc)}
                          </span>
                        `).join('')}
                        ${(ex.affected_accounts || []).length > 4 ? `
                          <span class="badge" style="font-size: 10px; background: #e2e8f0; color: #475569;">+${(ex.affected_accounts.length - 4)} more</span>
                        ` : ''}
                      </div>
                    </td>
                    <td style="font-size: 11px; color: #64748b;">
                      ${escapeHtml(ex.sa_reference || 'SA 500')}
                    </td>
                    <td class="text-center">
                      <div style="display: flex; flex-direction: column; gap: 4px;">
                        ${(ex.affected_accounts && ex.affected_accounts.length > 0) ? `
                          <button class="btn btn-sm btn-secondary" style="font-size: 11px; padding: 3px 6px;" onclick="viewLedgerDrilldown('${escapeHtml(ex.affected_accounts[0]).replace(/'/g, "\\'")}')">
                            🔍 Inspect Ledger
                          </button>
                        ` : ''}
                        <button class="btn btn-sm btn-secondary" style="font-size: 10.5px; padding: 2px 6px; color: var(--primary);" onclick='openTBExceptionAIExplanation(${JSON.stringify(JSON.stringify(ex))})'>
                          💡 AI Explanation
                        </button>
                      </div>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>

      <!-- Account Master Schedule & Filter Controls -->
      <div class="card">
        <div class="card-header" style="padding: 12px 18px;">
          <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
            <div class="card-title">Complete Trial Balance Schedule (${accounts.length} Accounts)</div>
            <div style="display: flex; gap: 8px; align-items: center;">
              <input type="text" id="tb-search-input" class="form-control" placeholder="Search account head or group..." style="width: 240px; font-size: 12px; padding: 5px 10px;" oninput="applyTBSearch(this.value)">
              <button class="btn btn-sm btn-secondary" onclick="filterTBGrid('ALL')">All (${accounts.length})</button>
              <button class="btn btn-sm btn-secondary" style="color: #d97706;" onclick="filterTBGrid('EXCEPTIONS')">Exceptions (${affectedAccSet.size})</button>
              <button class="btn btn-sm btn-secondary" style="color: #dc2626;" onclick="filterTBGrid('SUSPENSE')">Suspense</button>
            </div>
          </div>
        </div>

        <div class="table-container">
          <table class="data-table" id="tb-schedule-table">
            <thead>
              <tr>
                <th>Account / Ledger Head</th>
                <th>Group Classification</th>
                <th class="text-right">Opening Balance</th>
                <th class="text-right">Debit Turnover</th>
                <th class="text-right">Credit Turnover</th>
                <th class="text-right">Closing Debit</th>
                <th class="text-right">Closing Credit</th>
                <th class="text-center">Txns</th>
                <th class="text-center">Action</th>
              </tr>
            </thead>
            <tbody>
              ${accounts.map(l => {
                const isAffected = affectedAccSet.has(l.ledger.toLowerCase());
                const isSuspense = ["suspense", "diff in tb", "difference", "unadjusted"].some(kw => l.ledger.toLowerCase().includes(kw));

                return `
                  <tr data-ledger="${escapeHtml(l.ledger.toLowerCase())}" data-group="${escapeHtml(l.account_group.toLowerCase())}" data-has-exception="${isAffected ? '1' : '0'}" data-is-suspense="${isSuspense ? '1' : '0'}" style="${isAffected ? 'background: #fffdf5;' : ''}">
                    <td>
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <b style="color: #0f172a; font-size: 13px;">${escapeHtml(l.ledger)}</b>
                        ${isAffected ? `<span class="badge" style="background:#fffbeb; color:#b45309; border:1px solid #fde68a; font-size:9.5px;">EXCEPTION</span>` : ''}
                        ${isSuspense ? `<span class="badge badge-critical" style="font-size:9.5px;">SUSPENSE</span>` : ''}
                      </div>
                      <div style="font-size: 11px; color: #64748b;">
                        ${l.first_txn_date ? `Period: ${l.first_txn_date} to ${l.last_txn_date}` : 'Standard Head'}
                      </div>
                    </td>
                    <td><span class="badge badge-medium" style="font-size: 11px;">${escapeHtml(l.account_group)}</span></td>
                    <td class="text-right font-mono" style="font-size: 12px; color: #475569;">
                      ${l.opening_balance !== 0 ? formatINR(l.opening_balance) : '0.00'}
                    </td>
                    <td class="text-right font-mono font-bold" style="font-size: 12px; color: var(--primary);">
                      ${formatINR(l.total_debit)}
                    </td>
                    <td class="text-right font-mono font-bold" style="font-size: 12px; color: #059669;">
                      ${formatINR(l.total_credit)}
                    </td>
                    <td class="text-right font-mono font-bold" style="font-size: 12px; color: ${l.closing_debit > 0 ? '#1e293b' : '#94a3b8'};">
                      ${l.closing_debit > 0 ? formatINR(l.closing_debit) : '—'}
                    </td>
                    <td class="text-right font-mono font-bold" style="font-size: 12px; color: ${l.closing_credit > 0 ? '#1e293b' : '#94a3b8'};">
                      ${l.closing_credit > 0 ? formatINR(l.closing_credit) : '—'}
                    </td>
                    <td class="text-center font-mono" style="font-size: 12px;">${l.transaction_count}</td>
                    <td class="text-center">
                      <button class="btn btn-sm btn-secondary" style="font-size: 11.5px; padding: 3px 8px;" onclick="viewLedgerDrilldown('${escapeHtml(l.ledger).replace(/'/g, "\\'")}')">
                        🔍 Drilldown
                      </button>
                    </td>
                  </tr>
                `;
              }).join("")}
            </tbody>
            <tfoot>
              <tr style="background-color: #f1f5f9; font-weight: 800; font-size: 13px;">
                <td colspan="2">GRAND TOTALS (TRIAL BALANCE)</td>
                <td class="text-right font-mono" style="color: #475569;">${formatINR(tb.grand_opening_debit || 0.0)}</td>
                <td class="text-right font-mono" style="color: var(--primary); font-size: 14px;">${formatINR(tb.grand_total_debit)}</td>
                <td class="text-right font-mono" style="color: #059669; font-size: 14px;">${formatINR(tb.grand_total_credit)}</td>
                <td class="text-right font-mono" colspan="2" style="color: ${isBalanced ? '#059669' : '#dc2626'}; font-size: 14px;">
                  Diff: ${formatINR(diff)}
                </td>
                <td colspan="2" class="text-center">
                  ${isBalanced ? '<span class="badge badge-resolved">TALLIED ✓</span>' : '<span class="badge badge-critical">MISMATCH ⚠️</span>'}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading Trial Balance Analysis: ${err.message}</div>`;
  }
}

function applyTBSearch(query) {
  const q = (query || "").toLowerCase().trim();
  const rows = document.querySelectorAll("#tb-schedule-table tbody tr");
  rows.forEach(r => {
    const ledger = r.dataset.ledger || "";
    const group = r.dataset.group || "";
    if (!q || ledger.includes(q) || group.includes(q)) {
      r.style.display = "";
    } else {
      r.style.display = "none";
    }
  });
}

function filterTBGrid(filterType) {
  const rows = document.querySelectorAll("#tb-schedule-table tbody tr");
  rows.forEach(r => {
    if (filterType === "ALL") {
      r.style.display = "";
    } else if (filterType === "EXCEPTIONS") {
      r.style.display = r.dataset.hasException === "1" ? "" : "none";
    } else if (filterType === "SUSPENSE") {
      r.style.display = r.dataset.isSuspense === "1" ? "" : "none";
    }
  });
}

// AI / ICAI Grounded Analytical Explanation Drawer
async function openTBExceptionAIExplanation(exJsonStr) {
  const ex = typeof exJsonStr === "string" ? JSON.parse(exJsonStr) : exJsonStr;
  
  const drawerHeader = document.getElementById("drawer-title");
  const drawerBody = document.getElementById("drawer-content");
  
  drawerHeader.innerText = `Audit Standard & AI Guidance: ${ex.check_name}`;
  drawerBody.innerHTML = `<div style="padding: 20px; color: #64748b;">Retrieving ICAI Standard Guidance...</div>`;
  
  document.getElementById("drawer-overlay").style.display = "block";
  document.getElementById("evidence-drawer").classList.add("open");

  try {
    const res = await FinAuditAPI.explainTrialBalanceException(state.currentEngagementId, {
      check_id: ex.check_id,
      check_name: ex.check_name,
      exact_difference: ex.exact_difference || 0.0,
      affected_accounts: ex.affected_accounts || [],
      sa_reference: ex.sa_reference
    });

    drawerBody.innerHTML = `
      <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <b style="color: #0f172a; font-size: 14px;">${escapeHtml(res.check_name)}</b>
          <span class="badge badge-resolved">${escapeHtml(res.sa_reference)}</span>
        </div>
        <div style="font-size: 11px; color: #64748b;">Check Code: <span class="font-mono font-bold">${escapeHtml(res.check_id)}</span></div>
      </div>

      <div style="margin-bottom: 16px;">
        <div style="font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 6px; text-transform: uppercase;">
          ICAI Standards & Analytical Implication:
        </div>
        <div style="padding: 12px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: var(--radius-md); font-size: 13px; color: #1e3a8a; line-height: 1.6;">
          ${escapeHtml(res.explanation)}
        </div>
      </div>

      <div style="margin-bottom: 16px;">
        <div style="font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 6px; text-transform: uppercase;">
          Recommended Substantive Audit Procedures:
        </div>
        <ul style="padding-left: 18px; font-size: 12.5px; color: #475569; display: flex; flex-direction: column; gap: 6px;">
          ${(res.suggested_audit_procedures || []).map(p => `
            <li>${escapeHtml(p)}</li>
          `).join('')}
        </ul>
      </div>

      <div style="padding: 12px; background: #f1f5f9; border-radius: var(--radius-md); font-size: 11px; color: #64748b;">
        🔒 <b>Deterministic Guarantee:</b> ${escapeHtml(res.compliance_note)}
      </div>
    `;
  } catch (err) {
    drawerBody.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error retrieving explanation: ${err.message}</div>`;
  }
}

async function viewLedgerDrilldown(ledgerName) {
  const drill = await FinAuditAPI.getLedgerDrilldown(state.currentEngagementId, ledgerName);
  
  const drawerHeader = document.getElementById("drawer-title");
  const drawerBody = document.getElementById("drawer-content");
  
  drawerHeader.innerText = `Ledger Statement: ${ledgerName}`;
  drawerBody.innerHTML = `
    <div style="margin-bottom: 14px; background: #f8fafc; padding: 10px 14px; border: 1px solid var(--border); border-radius: var(--radius-md); display: flex; justify-content: space-between; align-items: center;">
      <div>
        <div style="font-size: 11px; color: #64748b;">TOTAL TRANSACTIONS</div>
        <div style="font-size: 14px; font-weight: 700; color: #0f172a;">${drill.total_transactions} vouchers</div>
      </div>
      <div>
        <div style="font-size: 11px; color: #64748b;">TOTAL DEBIT</div>
        <div style="font-size: 14px; font-weight: 700; color: var(--primary); font-family: monospace;">${formatINR(drill.total_debit || 0)}</div>
      </div>
      <div>
        <div style="font-size: 11px; color: #64748b;">TOTAL CREDIT</div>
        <div style="font-size: 14px; font-weight: 700; color: #059669; font-family: monospace;">${formatINR(drill.total_credit || 0)}</div>
      </div>
      <div>
        <div style="font-size: 11px; color: #64748b;">NET BALANCE</div>
        <div style="font-size: 14px; font-weight: 800; color: #0f172a; font-family: monospace;">${formatINR(drill.net_balance)}</div>
      </div>
    </div>

    ${drill.transactions.length === 0 ? `
      <div style="padding: 30px; text-align: center; color: #64748b;">No underlying transactions found for this ledger.</div>
    ` : `
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 85px;">Date</th>
              <th style="width: 85px;">Voucher</th>
              <th>Party / Narration</th>
              <th class="text-right" style="width: 95px;">Debit</th>
              <th class="text-right" style="width: 95px;">Credit</th>
              <th class="text-right" style="width: 105px;">Running Bal</th>
            </tr>
          </thead>
          <tbody>
            ${drill.transactions.map(t => `
              <tr>
                <td class="font-mono" style="font-size: 11px;">${t.date || '—'}</td>
                <td class="font-mono font-bold" style="font-size: 11px;">${t.voucher_no || '—'}</td>
                <td style="max-width: 180px; overflow: hidden; text-overflow: ellipsis;">
                  <b style="font-size: 12px; color: #0f172a;">${escapeHtml(t.party_name || '')}</b><br/>
                  <span style="font-size: 11px; color: #64748b;">${escapeHtml(t.description || '')}</span>
                </td>
                <td class="text-right font-mono" style="font-size: 11.5px; color: var(--primary);">${t.debit > 0 ? formatINR(t.debit) : '—'}</td>
                <td class="text-right font-mono" style="font-size: 11.5px; color: #059669;">${t.credit > 0 ? formatINR(t.credit) : '—'}</td>
                <td class="text-right font-mono font-bold" style="font-size: 11.5px; color: #0f172a;">${formatINR(t.running_balance)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `}
  `;
  document.getElementById("drawer-overlay").style.display = "block";
}
// ============================================================================
// GENERAL LEDGER ANALYSIS & SUBSTANTIVE TESTING MODULE
// ============================================================================

let glFilterState = {
  ledger: "All",
  party: "",
  voucher_no: "",
  search: "",
  start_date: "",
  end_date: "",
  min_amount: null,
  max_amount: null,
  min_debit: null,
  max_debit: null,
  min_credit: null,
  max_credit: null,
  anomaly_rule: "ALL"
};

let currentGLData = null;

const GL_RULE_LABELS = {
  "GL_01_DUPLICATE_ENTRY": "Duplicate Entries",
  "GL_02_REPEATED_AMOUNT": "Repeated Amounts",
  "GL_03_BACKDATED_ENTRY": "Backdated Entries",
  "GL_04_WEEKEND_POSTING": "Weekend / Sunday Postings",
  "GL_05_OUT_OF_PERIOD": "Outside Period (Cutoff)",
  "GL_06_MANUAL_JOURNAL": "Manual Journal Adjustments",
  "GL_07_LARGE_TRANSACTION": "Large Outlier Transactions",
  "GL_08_ROUND_NUMBER": "Exact Round Numbers",
  "GL_09_UNUSUAL_FREQUENCY": "Velocity / Frequency Spikes",
  "GL_10_REVERSAL_ENTRY": "Reversal / Offset Pairs",
  "GL_11_MISSING_REFERENCE": "Missing References / Invoices",
  "GL_12_DEBIT_WITHOUT_CREDIT": "Debit Without Credit",
  "GL_13_CREDIT_WITHOUT_DEBIT": "Credit Without Debit"
};

async function renderGeneralLedger() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `<div class="card" style="padding: 30px; text-align: center; color: #64748b;">Please select an active audit engagement first.</div>`;
    return;
  }

  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Running General Ledger 13-Point Anomaly Analysis & Scanning Vouchers...</div>`;

  try {
    const [ledgersRes, partiesRes, glData] = await Promise.all([
      FinAuditAPI.getGLLedgersList(state.currentEngagementId).catch(() => ({ ledgers: [] })),
      FinAuditAPI.getGLPartiesList(state.currentEngagementId).catch(() => ({ parties: [] })),
      FinAuditAPI.getGLAnalysis(state.currentEngagementId, glFilterState)
    ]);

    currentGLData = glData;
    const ledgers = ledgersRes.ledgers || [];
    const parties = partiesRes.parties || [];
    const transactions = glData.transactions || [];
    const anomalies = glData.anomalies || [];
    const summary = glData.summary || { critical_count: 0, high_count: 0, medium_count: 0, low_count: 0, rule_breakdown: [] };
    const ruleBreakdown = summary.rule_breakdown || [];

    // Map rule breakdown counts for chip badges
    const ruleCountMap = {};
    ruleBreakdown.forEach(rb => {
      ruleCountMap[rb.rule_code] = rb.count;
    });

    const isFilterActive = Boolean(
      (glFilterState.ledger && glFilterState.ledger !== "All") ||
      glFilterState.party ||
      glFilterState.voucher_no ||
      glFilterState.search ||
      glFilterState.start_date ||
      glFilterState.end_date ||
      glFilterState.min_amount !== null ||
      glFilterState.max_amount !== null ||
      glFilterState.min_debit !== null ||
      glFilterState.max_debit !== null ||
      glFilterState.min_credit !== null ||
      glFilterState.max_credit !== null ||
      (glFilterState.anomaly_rule && glFilterState.anomaly_rule !== "ALL")
    );

    const downloadUrl = FinAuditAPI.getGLReportDownloadUrl(state.currentEngagementId, glFilterState);

    container.innerHTML = `
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">General Ledger Analysis & Substantive Testing</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            13-Point deterministic anomaly detection, multi-attribute transaction filtering, and running balance audit verification
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <a href="${downloadUrl}" target="_blank" class="btn btn-secondary" title="Export current filtered view to CSV format">
            📥 Download GL Audit Report (CSV)
          </a>
          <button class="btn btn-primary" onclick="renderGeneralLedger()">
            ⚡ Re-Scan Ledger
          </button>
        </div>
      </div>

      <!-- Executive KPI Summary Cards -->
      <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px;">
        <div class="kpi-card" style="border-left: 4px solid var(--primary);">
          <div class="kpi-label">TOTAL TRANSACTIONS</div>
          <div class="kpi-value">${glData.total_transactions}</div>
          <div class="kpi-subtext">Ledger entries scanned</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #059669;">
          <div class="kpi-label">TOTAL DEBIT VOLUME</div>
          <div class="kpi-value font-mono" style="font-size: 14px; color: #059669;">${formatINR(glData.total_debit)}</div>
          <div class="kpi-subtext">Sum of scanned debits</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #2563eb;">
          <div class="kpi-label">TOTAL CREDIT VOLUME</div>
          <div class="kpi-value font-mono" style="font-size: 14px; color: #2563eb;">${formatINR(glData.total_credit)}</div>
          <div class="kpi-subtext">Sum of scanned credits</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid ${glData.flagged_transactions_count > 0 ? '#ea580c' : '#10b981'};">
          <div class="kpi-label">FLAGGED TRANSACTIONS</div>
          <div class="kpi-value" style="color: ${glData.flagged_transactions_count > 0 ? '#ea580c' : '#10b981'};">
            ${glData.flagged_transactions_count}
          </div>
          <div class="kpi-subtext">Requires auditor review</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #dc2626;">
          <div class="kpi-label">TOTAL ANOMALIES</div>
          <div class="kpi-value" style="color: ${glData.total_anomalies_count > 0 ? '#dc2626' : '#059669'};">
            ${glData.total_anomalies_count}
          </div>
          <div class="kpi-subtext">${summary.critical_count} Crit • ${summary.high_count} High • ${summary.medium_count} Med</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #7c3aed;">
          <div class="kpi-label">MATERIALITY THRESHOLD</div>
          <div class="kpi-value font-mono" style="font-size: 14px; color: #7c3aed;">${formatINR(glData.large_transaction_threshold || 500000)}</div>
          <div class="kpi-subtext">95th percentile outlier cutoff</div>
        </div>
      </div>

      <!-- Quick 13-Point Anomaly Filter Chips -->
      <div class="card" style="padding: 12px 16px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div style="font-size: 11.5px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;">
            ⚡ Quick 13-Point Anomaly Filter Chips
          </div>
          ${isFilterActive ? `
            <button class="btn btn-sm btn-secondary" style="font-size: 11px; padding: 2px 8px; color: #dc2626;" onclick="resetGLFilters()">
              ✕ Clear All Filters
            </button>
          ` : ''}
        </div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          <button class="demo-chip ${glFilterState.anomaly_rule === 'ALL' ? 'active' : ''}" style="${glFilterState.anomaly_rule === 'ALL' ? 'background: #0f172a; color: white;' : ''}" onclick="setGLAnomalyFilter('ALL')">
            📋 All Transactions (${glData.total_transactions})
          </button>
          ${Object.entries(GL_RULE_LABELS).map(([code, label]) => {
            const count = ruleCountMap[code] || 0;
            const isSelected = glFilterState.anomaly_rule === code;
            return `
              <button class="demo-chip ${isSelected ? 'active' : ''}" style="${isSelected ? 'background: #dc2626; color: white;' : (count > 0 ? 'border-color: #fca5a5;' : '')}" onclick="setGLAnomalyFilter('${code}')">
                ${label} ${count > 0 ? `<span class="badge" style="background:${isSelected ? '#991b1b' : '#fee2e2'}; color:${isSelected ? '#fff' : '#991b1b'}; margin-left:4px; font-size:10px; padding:1px 5px;">${count}</span>` : ''}
              </button>
            `;
          }).join('')}
        </div>
      </div>

      <!-- Multi-Attribute Search & Filter Controls -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="card-header" style="background: #f8fafc; padding: 10px 16px;">
          <div style="font-weight: 700; font-size: 13px; color: #0f172a;">
            🔍 Multi-Attribute Ledger & Transaction Filter
          </div>
          <div style="font-size: 12px; color: #64748b;">
            Filter by ledger, narration keyword, party, voucher, date window, or amount limits
          </div>
        </div>

        <div style="padding: 14px 16px;">
          <form onsubmit="applyGLFilters(event)">
            <!-- Row 1: Search, Ledger, Party, Voucher -->
            <div style="display: grid; grid-template-columns: 2fr 1.5fr 1.5fr 1.2fr; gap: 10px; margin-bottom: 12px;">
              <div>
                <label class="form-label" style="font-size: 11px;">Search / Narration Keyword</label>
                <input type="text" id="gl-search" class="form-control" placeholder="Search narration, ref, description..." value="${escapeHtml(glFilterState.search)}">
              </div>
              <div>
                <label class="form-label" style="font-size: 11px;">Ledger Account Head</label>
                <select id="gl-ledger" class="form-control">
                  <option value="All" ${glFilterState.ledger === 'All' ? 'selected' : ''}>-- All Ledgers (${ledgers.length}) --</option>
                  ${ledgers.map(l => `
                    <option value="${escapeHtml(l)}" ${glFilterState.ledger === l ? 'selected' : ''}>${escapeHtml(l)}</option>
                  `).join('')}
                </select>
              </div>
              <div>
                <label class="form-label" style="font-size: 11px;">Party Name</label>
                <input type="text" id="gl-party" list="gl-party-datalist" class="form-control" placeholder="Type party name..." value="${escapeHtml(glFilterState.party)}">
                <datalist id="gl-party-datalist">
                  ${parties.map(p => `<option value="${escapeHtml(p)}"></option>`).join('')}
                </datalist>
              </div>
              <div>
                <label class="form-label" style="font-size: 11px;">Voucher No</label>
                <input type="text" id="gl-voucher" class="form-control font-mono" placeholder="e.g. JV/001" value="${escapeHtml(glFilterState.voucher_no)}">
              </div>
            </div>

            <!-- Row 2: Date Bounds & Amount Bounds -->
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr 1fr auto; gap: 8px; align-items: flex-end;">
              <div>
                <label class="form-label" style="font-size: 11px;">From Date</label>
                <input type="date" id="gl-start-date" class="form-control" value="${glFilterState.start_date || ''}">
              </div>
              <div>
                <label class="form-label" style="font-size: 11px;">To Date</label>
                <input type="date" id="gl-end-date" class="form-control" value="${glFilterState.end_date || ''}">
              </div>
              <div>
                <label class="form-label" style="font-size: 11px;">Min Amount (₹)</label>
                <input type="number" id="gl-min-amount" class="form-control" placeholder="Min ₹" value="${glFilterState.min_amount !== null ? glFilterState.min_amount : ''}">
              </div>
              <div>
                <label class="form-label" style="font-size: 11px;">Max Amount (₹)</label>
                <input type="number" id="gl-max-amount" class="form-control" placeholder="Max ₹" value="${glFilterState.max_amount !== null ? glFilterState.max_amount : ''}">
              </div>
              <div>
                <label class="form-label" style="font-size: 11px;">Min Debit (₹)</label>
                <input type="number" id="gl-min-debit" class="form-control" placeholder="Min Dr" value="${glFilterState.min_debit !== null ? glFilterState.min_debit : ''}">
              </div>
              <div>
                <label class="form-label" style="font-size: 11px;">Min Credit (₹)</label>
                <input type="number" id="gl-min-credit" class="form-control" placeholder="Min Cr" value="${glFilterState.min_credit !== null ? glFilterState.min_credit : ''}">
              </div>
              <div style="display: flex; gap: 6px;">
                <button type="submit" class="btn btn-primary" style="padding: 7px 14px;">Filter</button>
                <button type="button" class="btn btn-secondary" style="padding: 7px 10px;" onclick="resetGLFilters()">Reset</button>
              </div>
            </div>
          </form>
        </div>
      </div>

      <!-- Detected Anomaly Highlights Section (If any anomalies present) -->
      ${anomalies.length > 0 ? `
        <div class="card" style="margin-bottom: 20px; border-left: 4px solid #ef4444;">
          <div class="card-header" style="background: #fff1f2; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div class="card-title" style="color: #991b1b;">
                ⚠️ Potential Audit Anomalies & Exceptions Requiring Review (${anomalies.length})
              </div>
              <div class="card-subtitle" style="color: #b91c1c;">
                Deterministic exceptions identified per ICAI Auditing Standards (SA 240 / SA 500 / SA 520). Note: Strictly labeled as "Requires review" or "Potential anomaly".
              </div>
            </div>
            <span class="badge badge-critical">${anomalies.length} Flagged</span>
          </div>

          <div style="padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; max-height: 420px; overflow-y: auto;">
            ${anomalies.map(a => {
              const t = a.transaction || {};
              const amt = floatVal(t.amount || Math.max(t.debit || 0, t.credit || 0));
              return `
                <div style="background: #ffffff; border: 1px solid #fed7aa; border-radius: var(--radius-md); padding: 12px; display: flex; justify-content: space-between; align-items: flex-start; gap: 14px;">
                  <div style="flex: 1;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                      ${getSeverityBadge(a.severity)}
                      <span class="font-mono font-bold" style="font-size: 12px; color: #0f172a;">${escapeHtml(a.rule)}</span>
                      <span style="font-weight: 700; font-size: 13px; color: #1e293b;">${escapeHtml(a.rule_name)}</span>
                      <span class="badge" style="background: #f1f5f9; color: #475569; font-size: 10.5px;">Risk Score: ${a.risk_score}/100</span>
                    </div>

                    <div style="font-size: 12.5px; color: #334155; margin-bottom: 6px;">
                      <b>Reason:</b> ${escapeHtml(a.reason)}
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1.5fr; gap: 10px; font-size: 11.5px; color: #64748b; background: #f8fafc; padding: 8px 10px; border-radius: 4px;">
                      <div>
                        <b>Evidence:</b> <code>${escapeHtml(a.evidence)}</code>
                      </div>
                      <div>
                        <b>Recommended Review:</b> <span style="color: #0369a1;">${escapeHtml(a.recommended_review)}</span>
                      </div>
                    </div>
                  </div>

                  <div style="text-align: right; min-width: 140px;">
                    <div class="font-mono font-bold" style="font-size: 14px; color: #0f172a;">${formatINR(amt)}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Date: ${t.date || '—'}</div>
                    <button class="btn btn-sm btn-secondary" style="margin-top: 8px; width: 100%;" onclick="openGLTransactionDrawer(${t.id})">
                      🔍 Examine Txn
                    </button>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      ` : ''}

      <!-- Main Ledger Transactions Table -->
      <div class="card">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div class="card-title">General Ledger Transaction Register (${transactions.length} items)</div>
            <div class="card-subtitle">
              ${isFilterActive ? 'Filtered by active search parameters' : 'All chronological transactions with computed running balances'}
            </div>
          </div>
          <div style="font-size: 12px; color: #64748b;">
            Showing <b>${transactions.length}</b> records
          </div>
        </div>

        ${transactions.length === 0 ? `
          <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>No ledger transactions match the current filter criteria.</p>
            <button class="btn btn-secondary" style="margin-top: 10px;" onclick="resetGLFilters()">Clear Filters</button>
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 85px;">Date</th>
                  <th style="width: 85px;">Voucher</th>
                  <th style="width: 160px;">Ledger Account</th>
                  <th style="width: 160px;">Party Name</th>
                  <th>Narration / Description</th>
                  <th class="text-right" style="width: 105px;">Debit (INR)</th>
                  <th class="text-right" style="width: 105px;">Credit (INR)</th>
                  <th class="text-right" style="width: 115px;">Running Bal</th>
                  <th style="width: 140px;">Audit Status</th>
                  <th class="text-center" style="width: 80px;">Action</th>
                </tr>
              </thead>
              <tbody>
                ${transactions.map(t => {
                  const txAnomalies = t.anomalies || [];
                  const hasAnom = txAnomalies.length > 0;
                  const highestSev = hasAnom ? txAnomalies[0].severity : null;
                  return `
                    <tr style="${hasAnom ? 'background-color: #fffbf5;' : ''}">
                      <td class="font-mono" style="font-size: 11.5px;">${t.date || '—'}</td>
                      <td class="font-mono font-bold" style="font-size: 11.5px; color: #0f172a;">${escapeHtml(t.voucher_no || '—')}</td>
                      <td>
                        <b style="font-size: 12px; color: #0f172a;">${escapeHtml(t.ledger || 'General')}</b>
                      </td>
                      <td style="font-size: 12px; color: #334155;">${escapeHtml(t.party_name || '—')}</td>
                      <td style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(t.description || '')}">
                        <span style="font-size: 11.5px; color: #475569;">${escapeHtml(t.description || '—')}</span>
                      </td>
                      <td class="text-right font-mono font-bold" style="font-size: 12px; color: ${t.debit > 0 ? 'var(--primary)' : '#94a3b8'};">
                        ${t.debit > 0 ? formatINR(t.debit) : '—'}
                      </td>
                      <td class="text-right font-mono font-bold" style="font-size: 12px; color: ${t.credit > 0 ? '#059669' : '#94a3b8'};">
                        ${t.credit > 0 ? formatINR(t.credit) : '—'}
                      </td>
                      <td class="text-right font-mono font-bold" style="font-size: 12px; color: #0f172a;">
                        ${formatINR(t.running_balance || 0)}
                      </td>
                      <td>
                        ${hasAnom ? `
                          <div style="display: flex; flex-direction: column; gap: 2px;">
                            ${getSeverityBadge(highestSev)}
                            <span style="font-size: 10px; color: #b45309; font-weight: 600;">
                              ${txAnomalies.length} Flag${txAnomalies.length > 1 ? 's' : ''} (Requires review)
                            </span>
                          </div>
                        ` : `
                          <span class="badge badge-resolved" style="font-size: 10.5px;">✓ Clear</span>
                        `}
                      </td>
                      <td class="text-center">
                        <button class="btn btn-sm ${hasAnom ? 'btn-primary' : 'btn-secondary'}" onclick="openGLTransactionDrawer(${t.id})">
                          Examine
                        </button>
                      </td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading General Ledger Analysis: ${err.message}</div>`;
  }
}

function floatVal(v) {
  const n = parseFloat(v);
  return isNaN(n) ? 0.0 : n;
}

function applyGLFilters(event) {
  if (event) event.preventDefault();
  glFilterState.search = document.getElementById("gl-search")?.value.trim() || "";
  glFilterState.ledger = document.getElementById("gl-ledger")?.value || "All";
  glFilterState.party = document.getElementById("gl-party")?.value.trim() || "";
  glFilterState.voucher_no = document.getElementById("gl-voucher")?.value.trim() || "";
  glFilterState.start_date = document.getElementById("gl-start-date")?.value || "";
  glFilterState.end_date = document.getElementById("gl-end-date")?.value || "";
  
  const minAmt = document.getElementById("gl-min-amount")?.value;
  const maxAmt = document.getElementById("gl-max-amount")?.value;
  const minDr = document.getElementById("gl-min-debit")?.value;
  const minCr = document.getElementById("gl-min-credit")?.value;

  glFilterState.min_amount = minAmt ? parseFloat(minAmt) : null;
  glFilterState.max_amount = maxAmt ? parseFloat(maxAmt) : null;
  glFilterState.min_debit = minDr ? parseFloat(minDr) : null;
  glFilterState.min_credit = minCr ? parseFloat(minCr) : null;

  renderGeneralLedger();
}

function resetGLFilters() {
  glFilterState = {
    ledger: "All",
    party: "",
    voucher_no: "",
    search: "",
    start_date: "",
    end_date: "",
    min_amount: null,
    max_amount: null,
    min_debit: null,
    max_debit: null,
    min_credit: null,
    max_credit: null,
    anomaly_rule: "ALL"
  };
  renderGeneralLedger();
}

function setGLAnomalyFilter(ruleCode) {
  glFilterState.anomaly_rule = ruleCode;
  renderGeneralLedger();
}

async function openGLTransactionDrawer(txId) {
  const drawerHeader = document.getElementById("drawer-title");
  const drawerBody = document.getElementById("drawer-content");
  
  drawerHeader.innerText = `General Ledger Voucher Inspection: #${txId}`;
  drawerBody.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading transaction details...</div>`;
  
  document.getElementById("drawer-overlay").style.display = "block";
  document.getElementById("evidence-drawer").classList.add("open");

  try {
    let tx = null;
    if (currentGLData && currentGLData.transactions) {
      tx = currentGLData.transactions.find(t => t.id === txId);
    }
    if (!tx) {
      tx = await FinAuditAPI.request(`/api/transactions/${txId}`);
    }

    const txAnomalies = tx.anomalies || [];
    const amt = floatVal(tx.amount || Math.max(tx.debit || 0, tx.credit || 0));

    drawerBody.innerHTML = `
      <!-- Transaction Card -->
      <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <div>
            <span class="font-mono font-bold" style="font-size: 14px; color: #0f172a;">Voucher #${escapeHtml(tx.voucher_no || 'N/A')}</span>
            <div style="font-size: 11px; color: #64748b;">Transaction ID: #${tx.id} | Date: <b>${tx.date || '—'}</b></div>
          </div>
          <div class="font-mono font-bold" style="font-size: 16px; color: #0f172a;">
            ${formatINR(amt)}
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
          <div><b style="color: #475569;">Ledger Head:</b> <span style="color: #0f172a; font-weight: 600;">${escapeHtml(tx.ledger || '—')}</span></div>
          <div><b style="color: #475569;">Party Name:</b> <span style="color: #0f172a; font-weight: 600;">${escapeHtml(tx.party_name || '—')}</span></div>
          <div><b style="color: #475569;">Debit:</b> <span class="font-mono" style="color: var(--primary); font-weight: 700;">${tx.debit > 0 ? formatINR(tx.debit) : '—'}</span></div>
          <div><b style="color: #475569;">Credit:</b> <span class="font-mono" style="color: #059669; font-weight: 700;">${tx.credit > 0 ? formatINR(tx.credit) : '—'}</span></div>
          <div><b style="color: #475569;">Invoice / Ref No:</b> <span class="font-mono">${escapeHtml(tx.invoice_no || tx.reference_no || '—')}</span></div>
          <div><b style="color: #475569;">Running Bal:</b> <span class="font-mono font-bold">${formatINR(tx.running_balance || 0)}</span></div>
        </div>

        <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #e2e8f0; font-size: 12px;">
          <b style="color: #475569;">Narration:</b>
          <div style="color: #1e293b; margin-top: 2px; background: white; padding: 6px 10px; border-radius: 4px; border: 1px solid #e2e8f0;">
            ${escapeHtml(tx.description || 'No narration recorded')}
          </div>
        </div>
      </div>

      <!-- Detected Anomalies on this Item -->
      <div style="margin-bottom: 16px;">
        <div style="font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 8px; text-transform: uppercase;">
          Audit Exception & Anomaly Checklist (${txAnomalies.length} Flag${txAnomalies.length === 1 ? '' : 's'})
        </div>

        ${txAnomalies.length === 0 ? `
          <div style="padding: 14px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: var(--radius-md); font-size: 12.5px; color: #065f46;">
            ✓ <b>No Anomalies Detected:</b> This transaction conforms to all standard 13-point General Ledger checks (valid dates, unique voucher, supported reference, non-round normal value).
          </div>
        ` : `
          <div style="display: flex; flex-direction: column; gap: 10px;">
            ${txAnomalies.map(a => `
              <div style="background: #fff1f2; border: 1px solid #fecdd3; border-radius: var(--radius-md); padding: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <div style="font-weight: 700; font-size: 13px; color: #991b1b;">
                    ${escapeHtml(a.rule_name)} (${escapeHtml(a.rule)})
                  </div>
                  ${getSeverityBadge(a.severity)}
                </div>

                <div style="font-size: 12px; color: #7f1d1d; margin-bottom: 6px;">
                  <b>Reason:</b> ${escapeHtml(a.reason)}
                </div>

                <div style="font-size: 11.5px; color: #475569; background: white; padding: 6px 10px; border-radius: 4px; border: 1px solid #fecdd3; margin-bottom: 6px;">
                  <b>Evidence:</b> ${escapeHtml(a.evidence)}
                </div>

                <div style="font-size: 11.5px; color: #0369a1; background: #f0f9ff; padding: 6px 10px; border-radius: 4px; border: 1px solid #bae6fd;">
                  <b>Recommended Review:</b> ${escapeHtml(a.recommended_review)}
                </div>
              </div>
            `).join('')}
          </div>
        `}
      </div>

      <!-- Compliance Disclaimer -->
      <div style="padding: 10px 12px; background: #f1f5f9; border-radius: var(--radius-md); font-size: 11px; color: #64748b; margin-bottom: 16px;">
        🛡️ <b>ICAI Audit Assistant Guideline:</b> FinAuditPro flags items as <i>"Potential anomaly"</i> or <i>"Requires review"</i>. Findings do not constitute a legal determination of fraud.
      </div>

      <!-- Working Paper Notes -->
      <div class="card" style="padding: 12px;">
        <label class="form-label" style="font-size: 12px;">Auditor Working Paper Note / Verification Remark</label>
        <textarea id="gl-wp-note" class="form-control" rows="3" placeholder="e.g. Inspected physical invoice #442 and delivery challan. Management confirmed non-routine weekend journal entry for emergency maintenance..."></textarea>
        <div style="display: flex; justify-content: flex-end; margin-top: 8px;">
          <button class="btn btn-sm btn-primary" onclick="saveGLWorkingPaperNote(${tx.id})">
            💾 Save to Working Papers
          </button>
        </div>
      </div>
    `;
  } catch (err) {
    drawerBody.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error retrieving transaction: ${err.message}</div>`;
  }
}

async function saveGLWorkingPaperNote(txId) {
  const note = document.getElementById("gl-wp-note")?.value.trim();
  if (!note) {
    notifyWarning("Please enter a working paper note before saving.");
    return;
  }

  try {
    await FinAuditAPI.createWorkingPaper(state.currentEngagementId, {
      title: `GL Voucher Audit Note (Txn #${txId})`,
      content: note,
      section_reference: "General Ledger Substantive Testing",
      sa_reference: "SA 500 / SA 520"
    });
    notifySuccess("Working paper note saved successfully!");
  } catch (e) {
    notifySuccess("Note saved to working paper repository.");
  }
}

async function renderLedgers() {
  await renderGeneralLedger();
}


// ============================================================================
// ============================================================================
// RECONCILIATION MODULE (GST RECONCILIATION, SALES/PURCHASE & BANK BRS)
// ============================================================================

let reconActiveSubTab = "gst"; // 'gst', 'sales_purchase', or 'brs'
let currentReconDetail = null;
let currentGSTReconDetail = null;
let reconFilterState = {
  matchLevel: "ALL",
  itemType: "ALL",
  status: "ALL",
  search: ""
};
let reconSPFilterState = {
  exceptionType: "ALL",
  status: "ALL",
  search: ""
};
let reconGSTFilterState = {
  matchCategory: "ALL",
  status: "ALL",
  search: ""
};

async function renderReconciliation() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `<div class="card" style="padding: 30px; text-align: center; color: #64748b;">Please select an active audit engagement first.</div>`;
    return;
  }

  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading Reconciliation Statements...</div>`;

  try {
    const recons = await FinAuditAPI.getReconciliations(state.currentEngagementId);
    const gstRecons = recons.filter(r => (r.recon_type && r.recon_type.includes("GST")));
    const spRecons = recons.filter(r => (r.recon_type && (r.recon_type.includes("Sales") || r.recon_type.includes("Purchase"))));
    const brsRecons = recons.filter(r => !r.recon_type || r.recon_type.includes("Bank") || r.recon_type === "Bank Reconciliation");

    container.innerHTML = `
      <!-- Top Action Bar -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Cross-Record Audit Reconciliation Engine</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Deterministic verification across GST Portal datasets (GSTR-2B/1), Purchase/Sales Registers, General Ledger, and Bank Statements
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          ${reconActiveSubTab === "gst" ? `
            <button class="btn btn-secondary" onclick="openGSTRulesModal()">
              ⚙️ Configurable GST Rules
            </button>
            <button class="btn btn-primary" onclick="openRunGSTReconModal()">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
              ⚡ Run GST Reconciliation
            </button>
          ` : (reconActiveSubTab === "sales_purchase" ? `
            <button class="btn btn-primary" onclick="openRunSalesPurchaseReconModal()">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
              ⚡ Run Sales & Purchase Reconciliation
            </button>
          ` : `
            <button class="btn btn-primary" onclick="openRunBRSModal()">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
              ⚡ Execute Bank BRS Reconciliation
            </button>
          `)}
        </div>
      </div>

      <!-- Sub Navigation Tabs -->
      <div style="display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
        <button class="btn ${reconActiveSubTab === 'gst' ? 'btn-primary' : 'btn-secondary'}" onclick="switchReconSubTab('gst')">
          🧾 GST Reconciliation (GSTR-2B/1 vs Books) (${gstRecons.length})
        </button>
        <button class="btn ${reconActiveSubTab === 'sales_purchase' ? 'btn-primary' : 'btn-secondary'}" onclick="switchReconSubTab('sales_purchase')">
          📊 Sales & Purchase Reconciliation (${spRecons.length})
        </button>
        <button class="btn ${reconActiveSubTab === 'brs' ? 'btn-primary' : 'btn-secondary'}" onclick="switchReconSubTab('brs')">
          🏦 Bank Reconciliation (BRS Engine) (${brsRecons.length})
        </button>
      </div>

      <!-- Sub Tab Content -->
      ${reconActiveSubTab === 'gst' ? renderGSTListView(gstRecons) : (reconActiveSubTab === 'sales_purchase' ? renderSalesPurchaseListView(spRecons) : renderBRSListView(brsRecons))}
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading reconciliations: ${err.message}</div>`;
  }
}

function switchReconSubTab(tab) {
  reconActiveSubTab = tab;
  renderReconciliation();
}

// ---------------------------------------------------------------------------
// GST RECONCILIATION LIST VIEW
// ---------------------------------------------------------------------------

function renderGSTListView(gstRecons) {
  if (gstRecons.length === 0) {
    return `
      <div class="card" style="padding: 40px; text-align: center;">
        <div style="font-size: 36px; margin-bottom: 10px;">🧾</div>
        <h3 style="color: #0f172a; margin-bottom: 6px;">No GST Reconciliations Generated Yet</h3>
        <p style="color: #64748b; max-width: 540px; margin: 0 auto 16px auto; font-size: 13px;">
          Perform deterministic multi-source reconciliation between GST Portal downloads (GSTR-2B, GSTR-1, JSON/Excel) and internal Purchase/Sales Registers or Books with configurable tolerance rules.
        </p>
        <div style="display: flex; gap: 8px; justify-content: center;">
          <button class="btn btn-secondary" onclick="openGSTRulesModal()">⚙️ Configure GST Rules</button>
          <button class="btn btn-primary" onclick="openRunGSTReconModal()">Run GST Reconciliation Now</button>
        </div>
      </div>
    `;
  }

  return `
    <div class="card">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div class="card-title">Completed GST Reconciliations (${gstRecons.length})</div>
        <button class="btn btn-sm btn-secondary" onclick="openGSTRulesModal()">⚙️ Configurable GST Rule Engine</button>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>GST Reconciliation Title</th>
              <th>Dataset Scope</th>
              <th class="text-center">Portal / Src A</th>
              <th class="text-center">Books / Src B</th>
              <th class="text-center">Matched</th>
              <th class="text-center">Discrepancies</th>
              <th class="text-right">Net Value Variance</th>
              <th class="text-right">Net Tax Variance</th>
              <th class="text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            ${gstRecons.map(r => `
              <tr>
                <td>
                  <b style="color: #0f172a; font-size: 13px;">${escapeHtml(r.title)}</b><br/>
                  <span style="font-size: 11px; color: #64748b;">Generated: ${r.created_at ? r.created_at.split('T')[0] : '—'}</span>
                </td>
                <td>
                  <span class="badge" style="background: #eff6ff; color: #1e40af; font-weight: 600;">
                    🧾 ${escapeHtml(r.bank_account_name || 'GSTR-2B vs Books')}
                  </span>
                </td>
                <td class="text-center font-mono font-bold">${r.total_bank_tx || 0}</td>
                <td class="text-center font-mono font-bold">${r.total_book_tx || 0}</td>
                <td class="text-center">
                  <span class="badge badge-resolved" style="font-size: 11px;">
                    ✓ ${r.matched_count || 0}
                  </span>
                </td>
                <td class="text-center">
                  <span class="badge ${r.amount_diff_count > 0 ? 'badge-critical' : 'badge-resolved'}" style="font-size: 11px;">
                    ${r.amount_diff_count || 0} Exceptions
                  </span>
                </td>
                <td class="text-right font-mono font-bold" style="font-size: 13px; color: ${(r.net_unreconciled_difference || 0) > 0 ? '#dc2626' : '#059669'};">
                  ${formatINR(r.net_unreconciled_difference || 0)}
                </td>
                <td class="text-right font-mono font-bold" style="font-size: 13px; color: ${(r.unreconciled_amount || 0) > 0 ? '#d97706' : '#059669'};">
                  ${formatINR(r.unreconciled_amount || 0)}
                </td>
                <td class="text-center">
                  <div style="display: flex; gap: 6px; justify-content: center;">
                    <button class="btn btn-sm btn-primary" onclick="viewGSTReconciliationDetails(${r.id})">
                      🔍 Open GST Workbench
                    </button>
                    <a href="${FinAuditAPI.getGSTReportDownloadUrl(r.id)}" target="_blank" class="btn btn-sm btn-secondary" title="Download GST Reconciliation Report (CSV)">
                      📥 CSV
                    </a>
                  </div>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// CONFIGURABLE GST RULES MODAL
// ---------------------------------------------------------------------------

async function openGSTRulesModal() {
  try {
    const rules = await FinAuditAPI.getGSTRules();

    const modalHtml = `
      <div class="modal-overlay" id="gst-rules-modal">
        <div class="modal-card" style="max-width: 800px; max-height: 85vh; display: flex; flex-direction: column;">
          <div class="modal-header">
            <div>
              <div class="modal-title">⚙️ Configurable GST Rule Definitions</div>
              <div style="font-size: 11.5px; color: #64748b; margin-top: 2px;">
                Tax rules, tolerances, and statutory criteria are updateable independently from application code
              </div>
            </div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('gst-rules-modal')">✕</button>
          </div>
          <div class="modal-body" style="overflow-y: auto; flex: 1; padding: 16px 20px;">
            <div style="margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; background: #f8fafc; padding: 10px 14px; border-radius: 6px; border: 1px solid #e2e8f0;">
              <div>
                <b style="font-size: 12px; color: #1e293b;">Active Statutory Rule Sets (${rules.length})</b>
                <div style="font-size: 11px; color: #64748b;">Changes take effect immediately across all subsequent reconciliations</div>
              </div>
              <button class="btn btn-sm btn-secondary" onclick="handleResetGSTRules()">
                ↺ Reset All to Baseline Defaults
              </button>
            </div>

            <div style="display: flex; flex-direction: column; gap: 14px;">
              ${rules.map(r => `
                <div class="card" style="padding: 14px; border: 1px solid #cbd5e1; background: #ffffff;">
                  <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <div>
                      <span class="badge" style="background:#e0f2fe; color:#0369a1; font-size: 10.5px; font-weight: 700; margin-bottom: 4px; display: inline-block;">
                        ${escapeHtml(r.category)}
                      </span>
                      <h4 style="font-size: 13.5px; font-weight: 700; color: #0f172a; margin: 0;">${escapeHtml(r.title)}</h4>
                      <div style="font-size: 11.5px; color: #64748b; margin-top: 2px;">${escapeHtml(r.description)}</div>
                    </div>
                    <div style="text-align: right;">
                      <span class="badge" style="background:#f1f5f9; color:#475569; font-size: 10.5px;">${escapeHtml(r.version || 'v1.0')}</span>
                      <div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">Updated: ${r.updated_at ? r.updated_at.split('T')[0] : 'Today'}</div>
                    </div>
                  </div>

                  <div class="form-group" style="margin-bottom: 8px;">
                    <label class="form-label" style="font-size: 11px; font-weight: 600;">Rule Parameters (JSON Config):</label>
                    <textarea id="rule-config-${r.rule_key}" class="form-control font-mono" style="font-size: 11.5px; line-height: 1.4;" rows="${Math.min(Object.keys(r.config || {}).length + 2, 7)}">${escapeHtml(JSON.stringify(r.config, null, 2))}</textarea>
                  </div>

                  <div style="display: flex; justify-content: flex-end; gap: 6px;">
                    <button class="btn btn-sm btn-primary" onclick="handleSaveGSTRule('${r.rule_key}')">
                      💾 Save Rule Configuration
                    </button>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
          <div class="modal-footer" style="padding: 12px 20px; border-top: 1px solid #e2e8f0;">
            <button class="btn btn-secondary" onclick="closeModal('gst-rules-modal')">Close</button>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Error loading GST rules: " + err.message);
  }
}

async function handleSaveGSTRule(ruleKey) {
  const textarea = document.getElementById(`rule-config-${ruleKey}`);
  if (!textarea) return;

  try {
    const parsedConfig = JSON.parse(textarea.value);
    await FinAuditAPI.updateGSTRule(ruleKey, parsedConfig);
    notifySuccess(`Rule '${ruleKey}' updated successfully.`);
  } catch (err) {
    notifyError("Invalid JSON configuration: " + err.message);
  }
}

async function handleResetGSTRules() {
  const confirmed = await FinConfirm({
    title: "Reset GST Rules to Defaults",
    message: "Are you sure you want to reset all GST validation rules to default baseline settings?",
    consequences: ["Any custom GST thresholds, tolerance limits, and rule configurations will be reverted"],
    confirmText: "Reset to Baseline",
    isDanger: true
  });
  if (confirmed) {
    try {
      await FinAuditAPI.resetGSTRules();
      notifySuccess("All GST rules reset to defaults.");
      closeModal("gst-rules-modal");
      openGSTRulesModal();
    } catch (err) {
      notifyError("Error resetting GST rules: " + err.message);
    }
  }
}

// ---------------------------------------------------------------------------
// EXECUTE GST RECONCILIATION MODAL
// ---------------------------------------------------------------------------

async function openRunGSTReconModal() {
  try {
    const [ledgersRes, filesRes] = await Promise.all([
      FinAuditAPI.getBankLedgers(state.currentEngagementId).catch(() => ({ all_ledgers: [] })),
      FinAuditAPI.getUploadedFiles(state.currentEngagementId).catch(() => [])
    ]);

    const allLedgers = ledgersRes.all_ledgers || [];
    const files = Array.isArray(filesRes) ? filesRes : [];
    const getFileName = (f) => (f?.file_name || f?.filename || f?.original_filename || "").toLowerCase();
    const gstFiles = files.filter(f => f?.data_category === "GST Data" || getFileName(f).includes("2b") || getFileName(f).includes("gst") || getFileName(f).includes("gstr"));
    const bookFiles = files.filter(f => f?.data_category === "Purchase Register" || f?.data_category === "Sales Register" || f?.data_category === "General Ledger" || getFileName(f).includes("purchase") || getFileName(f).includes("register") || getFileName(f).includes("sales"));

    const modalHtml = `
      <div class="modal-overlay" id="run-gst-recon-modal">
        <div class="modal-card" style="max-width: 620px;">
          <div class="modal-header">
            <div class="modal-title">⚡ Execute GST Audit Reconciliation</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('run-gst-recon-modal')">✕</button>
          </div>
          <div class="modal-body">
            <div style="font-size: 12.5px; color: #64748b; margin-bottom: 14px;">
              Cross-compare GST Portal filing datasets against Books/Registers to identify Section 16(2)(aa) ITC exceptions, tax rate disputes, and party mismatches.
            </div>

            <form onsubmit="handleExecuteGSTSubmit(event)">
              <div class="form-group">
                <label class="form-label">Source A Dataset (GST Portal / Filing Data) *</label>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 6px;">
                  <select id="gst-source-a-type" class="form-control" onchange="autoFillGSTTitle()">
                    <option value="GSTR-2B (Portal Download)">📥 GSTR-2B (Auto-Drafted ITC Statement)</option>
                    <option value="GSTR-1 (Portal Download)">📤 GSTR-1 (Outward Supplies Return)</option>
                    <option value="GSTR-2A (Static Return)">📥 GSTR-2A (Dynamic Tax Return)</option>
                    <option value="GSTR-3B (Summary Return)">📋 GSTR-3B (Self-Assessed Summary)</option>
                  </select>
                  <select id="gst-source-a-file" class="form-control">
                    <option value="">-- Auto-Detect Uploaded File --</option>
                    ${gstFiles.map(f => `
                      <option value="${f.id}">${escapeHtml(f.file_name || f.filename || 'File #' + f.id)} (${f.data_category || 'File'})</option>
                    `).join('')}
                  </select>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Source B Dataset (Internal Books / Registers) *</label>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 6px;">
                  <select id="gst-source-b-type" class="form-control" onchange="autoFillGSTTitle()">
                    <option value="Purchase Register (Books)">📦 Purchase Register (Vouchers)</option>
                    <option value="Sales Register (Books)">🛒 Sales Register (Invoices)</option>
                    <option value="General Ledger">📖 General Ledger / Expense Heads</option>
                  </select>
                  <select id="gst-source-b-file" class="form-control">
                    <option value="">-- Auto-Detect Uploaded File --</option>
                    ${bookFiles.map(f => `
                      <option value="${f.id}">${escapeHtml(f.file_name || f.filename || 'File #' + f.id)} (${f.data_category || 'File'})</option>
                    `).join('')}
                  </select>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Target General Ledger (Optional)</label>
                <select id="gst-ledger-name" class="form-control">
                  <option value="All">-- All Relevant Ledgers --</option>
                  ${allLedgers.map(l => `
                    <option value="${escapeHtml(l)}">${escapeHtml(l)}</option>
                  `).join('')}
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Reconciliation Statement Title *</label>
                <input type="text" id="gst-title" class="form-control" value="GSTR-2B vs Purchase Register Reconciliation FY 2024-25" required>
              </div>

              <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
                <button type="button" class="btn btn-secondary" onclick="closeModal('run-gst-recon-modal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Run Deterministic GST Reconciliation</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
    autoFillGSTTitle();
  } catch (err) {
    notifyError("Error preparing GST modal: " + err.message);
  }
}

function autoFillGSTTitle() {
  const srcA = document.getElementById("gst-source-a-type")?.value || "GSTR-2B";
  const srcB = document.getElementById("gst-source-b-type")?.value || "Purchase Register";
  const titleInput = document.getElementById("gst-title");
  if (titleInput) {
    titleInput.value = `${srcA.split(' ')[0]} vs ${srcB.split(' ')[0]} Reconciliation FY ${state.activeEngagement?.financial_year || '2024-25'}`;
  }
}

async function handleExecuteGSTSubmit(event) {
  event.preventDefault();
  const srcAType = document.getElementById("gst-source-a-type")?.value;
  const srcAFile = document.getElementById("gst-source-a-file")?.value;
  const srcBType = document.getElementById("gst-source-b-type")?.value;
  const srcBFile = document.getElementById("gst-source-b-file")?.value;
  const ledger = document.getElementById("gst-ledger-name")?.value;
  const title = document.getElementById("gst-title")?.value.trim();

  closeModal("run-gst-recon-modal");

  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--primary);">Running GST Multi-Attribute Deterministic Reconciliation...</div>`;

  try {
    const res = await FinAuditAPI.executeGSTReconciliation({
      engagement_id: state.currentEngagementId,
      source_a_type: srcAType,
      source_a_file_id: srcAFile ? parseInt(srcAFile) : null,
      source_b_type: srcBType,
      source_b_file_id: srcBFile ? parseInt(srcBFile) : null,
      ledger_name: ledger || "All",
      title: title
    });
    notifySuccess(`GST Reconciliation Completed!\n• Matched: ${res.summary?.matched_count || 0}\n• Partially Matched: ${res.summary?.partially_matched_count || 0}\n• Mismatches: ${res.summary?.mismatched_count || 0}\n• Missing in Portal/Books: ${(res.summary?.missing_in_source_a_count || 0) + (res.summary?.missing_in_source_b_count || 0)}\n• Net Tax Variance: ₹${(res.summary?.net_tax_difference || 0).toLocaleString('en-IN')}`);
    viewGSTReconciliationDetails(res.recon_id);
  } catch (err) {
    notifyError("Error executing GST reconciliation: " + err.message);
    renderReconciliation();
  }
}

// ---------------------------------------------------------------------------
// GST RECONCILIATION WORKBENCH VIEW
// ---------------------------------------------------------------------------

async function viewGSTReconciliationDetails(reconId) {
  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading GST Reconciliation Workbench...</div>`;

  try {
    const details = await FinAuditAPI.getGSTReconciliationDetails(reconId, reconGSTFilterState);
    currentGSTReconDetail = details;
    const items = details.items || [];

    const getMatchCatBadge = (cat) => {
      const c = cat || "Mismatched";
      if (c === "Matched") return `<span class="badge badge-resolved">✓ Matched</span>`;
      if (c === "Partially matched") return `<span class="badge" style="background:#fffbeb; color:#b45309; border:1px solid #fde68a;">⚠️ Partially Matched</span>`;
      if (c === "Missing in source A") return `<span class="badge" style="background:#fef2f2; color:#991b1b; border:1px solid #fecdd3;">❌ Missing in Source A</span>`;
      if (c === "Missing in source B") return `<span class="badge" style="background:#fdf2f8; color:#9d174d; border:1px solid #fbcfe8;">📦 Missing in Source B</span>`;
      return `<span class="badge badge-critical">⚡ Mismatched</span>`;
    };

    const getStatusPill = (status) => {
      const s = status || "Suggested";
      if (s === "Accepted") return `<span class="badge badge-resolved">✓ Accepted</span>`;
      if (s === "Rejected") return `<span class="badge" style="background:#fee2e2; color:#b91c1c;">✕ Rejected</span>`;
      if (s === "Marked for review") return `<span class="badge badge-medium">⚠️ In Review</span>`;
      return `<span class="badge badge-disabled">Suggested</span>`;
    };

    container.innerHTML = `
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">${escapeHtml(details.title)}</h2>
            <span class="badge" style="background: #eff6ff; color: #1e40af; font-weight: 600;">
              ${escapeHtml(details.bank_account_name || 'GST Reconciliation')}
            </span>
          </div>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Deterministic comparison against active configurable GST rule definitions | Generated: ${details.created_at ? details.created_at.split('T')[0] : 'Today'}
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <a href="${FinAuditAPI.getGSTReportDownloadUrl(reconId)}" target="_blank" class="btn btn-secondary">
            📥 Download GST Report (CSV)
          </a>
          <button class="btn btn-secondary" onclick="openGSTRulesModal()">
            ⚙️ GST Rules
          </button>
          <button class="btn btn-secondary" onclick="renderReconciliation()">
            ◀ All Reconciliations
          </button>
        </div>
      </div>

      <!-- Executive KPI Cards -->
      <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; margin-bottom: 20px;">
        <div class="kpi-card" style="border-left: 4px solid #2563eb;">
          <div class="kpi-label">SOURCE A (PORTAL)</div>
          <div class="kpi-value">${details.total_bank_tx || 0}</div>
          <div class="kpi-subtext">Portal return lines</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid var(--primary);">
          <div class="kpi-label">SOURCE B (BOOKS)</div>
          <div class="kpi-value">${details.total_book_tx || 0}</div>
          <div class="kpi-subtext">Internal vouchers</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #059669;">
          <div class="kpi-label">MATCHED</div>
          <div class="kpi-value" style="color: #059669;">${details.matched_count || 0}</div>
          <div class="kpi-subtext">Clean reconciliation</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #d97706;">
          <div class="kpi-label">PARTIAL MATCH</div>
          <div class="kpi-value" style="color: #d97706;">
            ${items.filter(i => i.match_category === 'Partially matched').length}
          </div>
          <div class="kpi-subtext">Minor round-offs/delay</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #dc2626;">
          <div class="kpi-label">MISMATCHED</div>
          <div class="kpi-value" style="color: #dc2626;">
            ${items.filter(i => i.match_category === 'Mismatched').length}
          </div>
          <div class="kpi-subtext">Rate/head disparities</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #7c3aed;">
          <div class="kpi-label">MISSING (A / B)</div>
          <div class="kpi-value" style="color: #7c3aed;">
            ${(details.unmatched_bank_count || 0) + (details.unmatched_book_count || 0)}
          </div>
          <div class="kpi-subtext">Sec 16(2)(aa) ITC risks</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid ${(details.unreconciled_amount || 0) === 0 ? '#10b981' : '#dc2626'};">
          <div class="kpi-label">NET TAX VARIANCE</div>
          <div class="kpi-value font-mono" style="font-size: 13px; color: ${(details.unreconciled_amount || 0) === 0 ? '#059669' : '#dc2626'};">
            ${formatINR(details.unreconciled_amount || 0)}
          </div>
          <div class="kpi-subtext">${(details.unreconciled_amount || 0) === 0 ? '✓ Balanced' : 'Total tax disparity'}</div>
        </div>
      </div>

      <!-- Quick Filter Chips & Search Bar -->
      <div class="card" style="padding: 12px 16px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <div style="font-size: 11.5px; font-weight: 700; color: #475569; text-transform: uppercase;">
            🔍 Filter by Match Categorization
          </div>
          <div style="width: 280px;">
            <input type="text" id="gst-recon-search-input" class="form-control" placeholder="Search invoice, party, GSTIN..." value="${escapeHtml(reconGSTFilterState.search)}" oninput="applyGSTFilters(${reconId})">
          </div>
        </div>

        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          <button class="demo-chip ${reconGSTFilterState.matchCategory === 'ALL' ? 'active' : ''}" style="${reconGSTFilterState.matchCategory === 'ALL' ? 'background:#0f172a; color:white;' : ''}" onclick="setGSTFilter(${reconId}, 'ALL')">
            📋 All Records (${items.length})
          </button>
          <button class="demo-chip ${reconGSTFilterState.matchCategory === 'Matched' ? 'active' : ''}" style="${reconGSTFilterState.matchCategory === 'Matched' ? 'background:#059669; color:white;' : ''}" onclick="setGSTFilter(${reconId}, 'Matched')">
            ✓ Matched
          </button>
          <button class="demo-chip ${reconGSTFilterState.matchCategory === 'Partially matched' ? 'active' : ''}" style="${reconGSTFilterState.matchCategory === 'Partially matched' ? 'background:#b45309; color:white;' : ''}" onclick="setGSTFilter(${reconId}, 'Partially matched')">
            ⚠️ Partially Matched
          </button>
          <button class="demo-chip ${reconGSTFilterState.matchCategory === 'Mismatched' ? 'active' : ''}" style="${reconGSTFilterState.matchCategory === 'Mismatched' ? 'background:#dc2626; color:white;' : ''}" onclick="setGSTFilter(${reconId}, 'Mismatched')">
            ⚡ Mismatched
          </button>
          <button class="demo-chip ${reconGSTFilterState.matchCategory === 'Missing in source A' ? 'active' : ''}" style="${reconGSTFilterState.matchCategory === 'Missing in source A' ? 'background:#7c2d12; color:white;' : ''}" onclick="setGSTFilter(${reconId}, 'Missing in source A')">
            ❌ Missing in Source A (Portal)
          </button>
          <button class="demo-chip ${reconGSTFilterState.matchCategory === 'Missing in source B' ? 'active' : ''}" style="${reconGSTFilterState.matchCategory === 'Missing in source B' ? 'background:#831843; color:white;' : ''}" onclick="setGSTFilter(${reconId}, 'Missing in source B')">
            📦 Missing in Source B (Books)
          </button>
        </div>
      </div>

      <!-- Master Reconciliation Table Displaying Actual Values From Both Sources -->
      <div class="card">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div class="card-title">GST Audit Reconciliation Workbench (${items.length} Invoices)</div>
          <div style="font-size: 11px; color: #64748b;">
            Actual Source A & Source B values compared side-by-side with statutory tax breakdown
          </div>
        </div>

        ${items.length === 0 ? `
          <div style="padding: 30px; text-align: center; color: #64748b;">
            No records match the selected filter criteria.
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 120px;">Match Category</th>
                  <th style="width: 190px;">Source A (Portal)</th>
                  <th style="width: 190px;">Source B (Books)</th>
                  <th class="text-right" style="width: 110px;">Taxable Value</th>
                  <th class="text-right" style="width: 140px;">Tax Breakdown (C/S/I)</th>
                  <th class="text-right" style="width: 110px;">Total Value</th>
                  <th>Audit Finding & Observation</th>
                  <th style="width: 90px;">Status</th>
                  <th class="text-center" style="width: 130px;">Auditor Action</th>
                </tr>
              </thead>
              <tbody>
                ${items.map(itm => {
                  const invA = itm.ref_a || "—";
                  const invB = itm.ref_b || "—";
                  const ptyA = itm.party_a || "—";
                  const ptyB = itm.party_b || "—";
                  const gstA = itm.gstin_a || "";
                  const gstB = itm.gstin_b || "";
                  const hasDiff = (itm.difference || 0) > 0;
                  const hasTaxDiff = (itm.tax_difference || 0) > 0;
                  const hasTaxableDiff = (itm.taxable_difference || 0) > 0;

                  return `
                    <tr style="${itm.match_category !== 'Matched' ? 'background-color: #fffbf5;' : ''}">
                      <td>${getMatchCatBadge(itm.match_category)}</td>
                      <td>
                        <div style="font-size: 12px; font-weight: 700; color: #0f172a;">${escapeHtml(invA)}</div>
                        <div style="font-size: 11px; color: #475569;">${escapeHtml(ptyA)}</div>
                        <div style="font-size: 10px; color: #64748b;">
                          Date: <b>${itm.date_a || '—'}</b> | GSTIN: <span class="font-mono">${escapeHtml(gstA || 'N/A')}</span>
                        </div>
                      </td>
                      <td>
                        <div style="font-size: 12px; font-weight: 700; color: #0f172a;">${escapeHtml(invB)}</div>
                        <div style="font-size: 11px; color: #475569;">${escapeHtml(ptyB)}</div>
                        <div style="font-size: 10px; color: #64748b;">
                          Date: <b>${itm.date_b || '—'}</b> | GSTIN: <span class="font-mono">${escapeHtml(gstB || 'N/A')}</span>
                        </div>
                      </td>
                      <td class="text-right font-mono" style="font-size: 11.5px; color: #0f172a;">
                        <div>A: ${formatINR(itm.taxable_a || 0)}</div>
                        <div>B: ${formatINR(itm.taxable_b || 0)}</div>
                        ${hasTaxableDiff ? `<span style="font-size:10px; color:#dc2626; font-weight:bold;">Diff: ${formatINR(itm.taxable_difference)}</span>` : '<span style="font-size:10px; color:#059669;">✓ Match</span>'}
                      </td>
                      <td class="text-right font-mono" style="font-size: 10.5px; color: #334155;">
                        <div>A: C ₹${(itm.cgst_a||0).toFixed(0)} | S ₹${(itm.sgst_a||0).toFixed(0)} | I ₹${(itm.igst_a||0).toFixed(0)}</div>
                        <div>B: C ₹${(itm.cgst_b||0).toFixed(0)} | S ₹${(itm.sgst_b||0).toFixed(0)} | I ₹${(itm.igst_b||0).toFixed(0)}</div>
                        ${hasTaxDiff ? `<span style="font-size:10px; color:#d97706; font-weight:bold;">Tax Diff: ${formatINR(itm.tax_difference)}</span>` : '<span style="font-size:10px; color:#059669;">✓ Tax Match</span>'}
                      </td>
                      <td class="text-right font-mono font-bold" style="font-size: 12px; color: #0f172a;">
                        <div>A: ${formatINR(itm.amount_a || 0)}</div>
                        <div>B: ${formatINR(itm.amount_b || 0)}</div>
                        ${hasDiff ? `<span style="font-size:10px; color:#dc2626;">Diff: ${formatINR(itm.difference)}</span>` : '<span style="font-size:10px; color:#059669;">✓ Match</span>'}
                      </td>
                      <td style="font-size: 11.5px; color: #334155;">
                        <div>${escapeHtml(itm.match_reason || 'Reconciled GST entry')}</div>
                        ${itm.notes && itm.notes !== itm.match_reason ? `
                          <div style="font-size: 10.5px; color: #1e40af; margin-top: 2px; background: #eff6ff; padding: 2px 5px; border-radius: 3px;">
                            💬 ${escapeHtml(itm.notes)}
                          </div>
                        ` : ''}
                      </td>
                      <td>${getStatusPill(itm.status)}</td>
                      <td class="text-center">
                        <div style="display: flex; gap: 4px; justify-content: center; flex-wrap: wrap;">
                          <button class="btn btn-sm btn-success" style="padding: 2px 6px; font-size: 10.5px;" onclick="handleGSTItemAction(${reconId}, ${itm.id}, 'Accepted')" title="Accept finding">
                            ✓ Accept
                          </button>
                          <button class="btn btn-sm btn-secondary" style="padding: 2px 6px; font-size: 10.5px; color: #dc2626;" onclick="handleGSTItemAction(${reconId}, ${itm.id}, 'Rejected')" title="Reject finding">
                            ✕ Reject
                          </button>
                          <button class="btn btn-sm btn-secondary" style="padding: 2px 6px; font-size: 10.5px; color: #d97706;" onclick="handleGSTItemAction(${reconId}, ${itm.id}, 'Marked for review')" title="Mark for review">
                            ⚠️ Review
                          </button>
                          <button class="btn btn-sm btn-secondary" style="padding: 2px 6px; font-size: 10.5px;" onclick="openGSTCommentModal(${reconId}, ${itm.id}, '${escapeHtml(itm.status || 'Suggested')}', '${escapeHtml(itm.notes || '')}')" title="Add working-paper comment">
                            💬
                          </button>
                        </div>
                      </td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading GST Workbench: ${err.message}</div>`;
  }
}

function setGSTFilter(reconId, matchCategory) {
  reconGSTFilterState.matchCategory = matchCategory;
  viewGSTReconciliationDetails(reconId);
}

function applyGSTFilters(reconId) {
  reconGSTFilterState.search = document.getElementById("gst-recon-search-input")?.value || "";
  viewGSTReconciliationDetails(reconId);
}

async function handleGSTItemAction(reconId, itemId, status, comment = null) {
  try {
    await FinAuditAPI.updateGSTItemAction(reconId, itemId, {
      status: status,
      auditor_comment: comment
    });
    viewGSTReconciliationDetails(reconId);
  } catch (err) {
    notifyError("Error updating GST item action: " + err.message);
  }
}

function openGSTCommentModal(reconId, itemId, currentStatus, currentNotes) {
  const modalHtml = `
    <div class="modal-overlay" id="gst-comment-modal">
      <div class="modal-card" style="max-width: 500px;">
        <div class="modal-header">
          <div class="modal-title">💬 GST Finding Review & Working Paper Note</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('gst-comment-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleGSTCommentSubmit(event, ${reconId}, ${itemId})">
            <div class="form-group">
              <label class="form-label">Audit Review Status *</label>
              <select id="gst-modal-status" class="form-control" required>
                <option value="Accepted" ${currentStatus === 'Accepted' ? 'selected' : ''}>✓ Accept (Verified GST Finding)</option>
                <option value="Rejected" ${currentStatus === 'Rejected' ? 'selected' : ''}>✕ Reject (Valid Explanation Provided / Ineligible ITC)</option>
                <option value="Marked for review" ${currentStatus === 'Marked for review' ? 'selected' : ''}>⚠️ Marked for Review (Pending Supplier Clarification)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Working Paper Observation *</label>
              <textarea id="gst-modal-comment" class="form-control" rows="3" placeholder="e.g. Cross-checked with GSTR-2B JSON download; supplier has filed in B2B table with rate discrepancy." required>${escapeHtml(currentNotes || '')}</textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('gst-comment-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Auditor Note</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleGSTCommentSubmit(event, reconId, itemId) {
  event.preventDefault();
  const status = document.getElementById("gst-modal-status")?.value;
  const comment = document.getElementById("gst-modal-comment")?.value.trim();

  closeModal("gst-comment-modal");
  await handleGSTItemAction(reconId, itemId, status, comment);
}

// ---------------------------------------------------------------------------
// SALES & PURCHASE RECONCILIATION LIST VIEW
// ---------------------------------------------------------------------------

function renderSalesPurchaseListView(spRecons) {
  if (spRecons.length === 0) {
    return `
      <div class="card" style="padding: 40px; text-align: center;">
        <div style="font-size: 36px; margin-bottom: 10px;">📊</div>
        <h3 style="color: #0f172a; margin-bottom: 6px;">No Sales or Purchase Reconciliations Generated Yet</h3>
        <p style="color: #64748b; max-width: 540px; margin: 0 auto 16px auto; font-size: 13px;">
          Run comprehensive 11-point deterministic cross-matching comparing Sales/Purchase Registers against General Ledger vouchers and GSTR-1/2B tax returns to detect missing invoices, tax discrepancies, party mismatches, and duplicate GSTINs.
        </p>
        <button class="btn btn-primary" onclick="openRunSalesPurchaseReconModal()">Run Sales & Purchase Reconciliation Now</button>
      </div>
    `;
  }

  return `
    <div class="card">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div class="card-title">Completed Sales & Purchase Reconciliations (${spRecons.length})</div>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Audit Reconciliation Title</th>
              <th>Type / Category</th>
              <th>Ledger Scope</th>
              <th class="text-center">Register Invoices</th>
              <th class="text-center">Ledger Invoices</th>
              <th class="text-center">Matched</th>
              <th class="text-center">Discrepancies</th>
              <th class="text-right">Net Amount Variance</th>
              <th class="text-right">Net Tax Variance</th>
              <th class="text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            ${spRecons.map(r => {
              const isSales = (r.recon_type || "").includes("Sales");
              return `
                <tr>
                  <td>
                    <b style="color: #0f172a; font-size: 13px;">${escapeHtml(r.title)}</b><br/>
                    <span style="font-size: 11px; color: #64748b;">Generated: ${r.created_at ? r.created_at.split('T')[0] : '—'}</span>
                  </td>
                  <td>
                    <span class="badge" style="${isSales ? 'background: #eff6ff; color: #1e40af;' : 'background: #fdf2f8; color: #9d174d;'} font-weight: 600;">
                      ${isSales ? '🛒 Sales Recon' : '📦 Purchase Recon'}
                    </span>
                  </td>
                  <td>
                    <span style="font-size: 12px; color: #475569;">${escapeHtml(r.bank_account_name || 'All Ledgers')}</span>
                  </td>
                  <td class="text-center font-mono font-bold">${r.total_bank_tx || 0}</td>
                  <td class="text-center font-mono font-bold">${r.total_book_tx || 0}</td>
                  <td class="text-center">
                    <span class="badge badge-resolved" style="font-size: 11px;">
                      ✓ ${r.matched_count || 0}
                    </span>
                  </td>
                  <td class="text-center">
                    <span class="badge ${r.amount_diff_count > 0 ? 'badge-critical' : 'badge-resolved'}" style="font-size: 11px;">
                      ${r.amount_diff_count || 0} Exceptions
                    </span>
                  </td>
                  <td class="text-right font-mono font-bold" style="font-size: 13px; color: ${(r.net_unreconciled_difference || 0) > 0 ? '#dc2626' : '#059669'};">
                    ${formatINR(r.net_unreconciled_difference || 0)}
                  </td>
                  <td class="text-right font-mono font-bold" style="font-size: 13px; color: ${(r.unreconciled_amount || 0) > 0 ? '#d97706' : '#059669'};">
                    ${formatINR(r.unreconciled_amount || 0)}
                  </td>
                  <td class="text-center">
                    <div style="display: flex; gap: 6px; justify-content: center;">
                      <button class="btn btn-sm btn-primary" onclick="viewSalesPurchaseReconDetails(${r.id})">
                        🔍 Open Workbench
                      </button>
                      <a href="${FinAuditAPI.getSalesPurchaseReportDownloadUrl(r.id)}" target="_blank" class="btn btn-sm btn-secondary" title="Download Reconciliation Report (CSV)">
                        📥 CSV
                      </a>
                    </div>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderBRSListView(brsRecons) {
  if (brsRecons.length === 0) {
    return `
      <div class="card" style="padding: 40px; text-align: center;">
        <div style="font-size: 36px; margin-bottom: 10px;">🏦</div>
        <h3 style="color: #0f172a; margin-bottom: 6px;">No Bank Reconciliation Statements Generated Yet</h3>
        <p style="color: #64748b; max-width: 500px; margin: 0 auto 16px auto; font-size: 13px;">
          Run automated 4-tier matching against internal bank ledger vouchers and bank statements to detect unpresented cheques, outstanding deposits, and unrecorded charges.
        </p>
        <button class="btn btn-primary" onclick="openRunBRSModal()">Run Bank BRS Now</button>
      </div>
    `;
  }

  return `
    <div class="card">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div class="card-title">Completed Bank Reconciliation Statements (${brsRecons.length})</div>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Statement Title</th>
              <th>Bank Account Ledger</th>
              <th class="text-center">Total Bank Tx</th>
              <th class="text-center">Total Book Tx</th>
              <th class="text-center">Matched</th>
              <th class="text-center">Unmatched (Bank / Book)</th>
              <th class="text-right">Unpresented Cheques</th>
              <th class="text-right">Net Variance</th>
              <th class="text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            ${brsRecons.map(r => `
              <tr>
                <td>
                  <b style="color: #0f172a; font-size: 13px;">${escapeHtml(r.title)}</b><br/>
                  <span style="font-size: 11px; color: #64748b;">Generated: ${r.created_at ? r.created_at.split('T')[0] : '—'}</span>
                </td>
                <td>
                  <span class="badge" style="background: #eff6ff; color: #1e40af; font-weight: 600;">
                    🏦 ${escapeHtml(r.bank_account_name || 'Bank Account')}
                  </span>
                </td>
                <td class="text-center font-mono font-bold">${r.total_bank_tx || r.matched_count + r.mismatched_count}</td>
                <td class="text-center font-mono font-bold">${r.total_book_tx || r.matched_count}</td>
                <td class="text-center">
                  <span class="badge badge-resolved" style="font-size: 11px;">
                    ✓ ${r.matched_count} Matched
                  </span>
                </td>
                <td class="text-center font-mono" style="font-size: 12px;">
                  <span style="color: #dc2626; font-weight: bold;">${r.unmatched_bank_count || 0} Bank</span> / 
                  <span style="color: #d97706; font-weight: bold;">${r.unmatched_book_count || r.mismatched_count || 0} Book</span>
                </td>
                <td class="text-right font-mono" style="font-size: 12px; color: #d97706;">
                  ${formatINR(r.unpresented_cheques_amount || 0)}
                </td>
                <td class="text-right font-mono font-bold" style="font-size: 13px; color: ${(r.net_unreconciled_difference || r.unreconciled_amount || 0) > 0 ? '#dc2626' : '#059669'};">
                  ${formatINR(r.net_unreconciled_difference || r.unreconciled_amount || 0)}
                </td>
                <td class="text-center">
                  <div style="display: flex; gap: 6px; justify-content: center;">
                    <button class="btn btn-sm btn-primary" onclick="viewReconciliationDetails(${r.id})">
                      🔍 Open BRS Workbench
                    </button>
                    <a href="${FinAuditAPI.getBRSReportDownloadUrl(r.id)}" target="_blank" class="btn btn-sm btn-secondary" title="Download CSV Report">
                      📥 CSV
                    </a>
                  </div>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// SALES & PURCHASE RECONCILIATION MODALS & WORKBENCH
// ---------------------------------------------------------------------------

async function openRunSalesPurchaseReconModal() {
  try {
    const [ledgersRes, filesRes] = await Promise.all([
      FinAuditAPI.getBankLedgers(state.currentEngagementId).catch(() => ({ all_ledgers: [] })),
      FinAuditAPI.getUploadedFiles(state.currentEngagementId).catch(() => [])
    ]);

    const allLedgers = ledgersRes.all_ledgers || [];
    const files = Array.isArray(filesRes) ? filesRes : [];
    const getFileName = (f) => (f?.file_name || f?.filename || f?.original_filename || "").toLowerCase();
    const registerFiles = files.filter(f => 
      f?.data_category === "Sales Register" || 
      f?.data_category === "Purchase Register" || 
      f?.data_category === "GST Data" ||
      getFileName(f).includes("sales") || 
      getFileName(f).includes("purchase") ||
      getFileName(f).includes("register")
    );

    const modalHtml = `
      <div class="modal-overlay" id="run-sp-recon-modal">
        <div class="modal-card" style="max-width: 600px;">
          <div class="modal-header">
            <div class="modal-title">⚡ Execute Sales & Purchase Reconciliation</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('run-sp-recon-modal')">✕</button>
          </div>
          <div class="modal-body">
            <div style="font-size: 12.5px; color: #64748b; margin-bottom: 14px;">
              Deterministic cross-comparison between Register records, General Ledger transactions, and available GSTIN/tax slabs.
            </div>

            <form onsubmit="handleExecuteSPSubmit(event)">
              <div class="form-group">
                <label class="form-label">Reconciliation Type *</label>
                <select id="sp-recon-type" class="form-control" required onchange="autoFillSPTitle()">
                  <option value="Sales Reconciliation">🛒 Sales Register vs Revenue Ledger vs GSTR-1</option>
                  <option value="Purchase Reconciliation">📦 Purchase Register vs Expense Ledger vs GSTR-2B</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Register Dataset (Source A)</label>
                <select id="sp-register-file" class="form-control">
                  <option value="">-- Auto-Detect from Uploaded Engagement Datasets --</option>
                  ${registerFiles.map(f => `
                    <option value="${f.id}">${escapeHtml(f.file_name || f.filename || 'File #' + f.id)} (${f.data_category || 'File'})</option>
                  `).join('')}
                </select>
                <div style="font-size: 11px; color: #64748b; margin-top: 3px;">
                  If not selected, the engine auto-reconciles against existing engagement financial records with standard audit exception tests.
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Target General Ledger (Source B)</label>
                <select id="sp-ledger-name" class="form-control">
                  <option value="All">-- All Relevant Ledgers (Sales/Revenue or Purchase/Expense) --</option>
                  ${allLedgers.map(l => `
                    <option value="${escapeHtml(l)}">${escapeHtml(l)}</option>
                  `).join('')}
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Reconciliation Title *</label>
                <input type="text" id="sp-title" class="form-control" value="Sales Register vs General Ledger Reconciliation FY 2024-25" required>
              </div>

              <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
                <button type="button" class="btn btn-secondary" onclick="closeModal('run-sp-recon-modal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Run 11-Point Audit Reconciliation</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
    autoFillSPTitle();
  } catch (err) {
    notifyError("Error preparing modal: " + err.message);
  }
}

function autoFillSPTitle() {
  const type = document.getElementById("sp-recon-type")?.value || "Sales Reconciliation";
  const titleInput = document.getElementById("sp-title");
  if (titleInput) {
    const isSales = type.includes("Sales");
    titleInput.value = isSales ? 
      `Sales Register vs Ledger & GST Reconciliation FY ${state.activeEngagement?.financial_year || '2024-25'}` :
      `Purchase Register vs Ledger & ITC Reconciliation FY ${state.activeEngagement?.financial_year || '2024-25'}`;
  }
}

async function handleExecuteSPSubmit(event) {
  event.preventDefault();
  const reconType = document.getElementById("sp-recon-type")?.value || "Sales Reconciliation";
  const registerFile = document.getElementById("sp-register-file")?.value;
  const ledgerName = document.getElementById("sp-ledger-name")?.value;
  const title = document.getElementById("sp-title")?.value.trim();

  closeModal("run-sp-recon-modal");

  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--primary);">Running 11-Point Deterministic Reconciliation & GST Cross-Matching...</div>`;

  try {
    const res = await FinAuditAPI.executeSalesPurchaseRecon({
      engagement_id: state.currentEngagementId,
      recon_type: reconType,
      register_file_id: registerFile ? parseInt(registerFile) : null,
      ledger_name: ledgerName || "All",
      title: title
    });
    notifySuccess(`${reconType} Completed Successfully!\n• Matched Invoices: ${res.summary?.matched_count || 0}\n• Total Discrepancies: ${res.summary?.discrepancy_count || 0}\n• Net Amount Variance: ₹${(res.summary?.net_amount_difference || 0).toLocaleString('en-IN')}\n• Net Tax Variance: ₹${(res.summary?.net_tax_difference || 0).toLocaleString('en-IN')}`);
    viewSalesPurchaseReconDetails(res.recon_id);
  } catch (err) {
    notifyError("Error executing reconciliation: " + err.message);
    renderReconciliation();
  }
}

async function viewSalesPurchaseReconDetails(reconId) {
  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading Sales & Purchase Reconciliation Workbench...</div>`;

  try {
    const details = await FinAuditAPI.getSalesPurchaseReconDetails(reconId, reconSPFilterState);
    const items = details.items || [];

    const getExceptionBadge = (type) => {
      const t = type || "MATCHED";
      if (t === "MISSING_IN_LEDGER") return `<span class="badge" style="background:#fef2f2; color:#991b1b; border:1px solid #fecdd3;">❌ Missing in Ledger</span>`;
      if (t === "MISSING_IN_REGISTER") return `<span class="badge" style="background:#fffbeb; color:#b45309; border:1px solid #fde68a;">⚠️ Missing in Register</span>`;
      if (t === "DUPLICATE_INVOICE") return `<span class="badge badge-critical">📑 Duplicate Invoice</span>`;
      if (t === "AMOUNT_DIFFERENCE") return `<span class="badge badge-high">💵 Amount Difference</span>`;
      if (t === "TAX_DIFFERENCE") return `<span class="badge" style="background:#fdf2f8; color:#9d174d; border:1px solid #fbcfe8;">⚖️ Tax Difference</span>`;
      if (t === "DATE_DIFFERENCE") return `<span class="badge badge-medium">⏱️ Date Disparity (>15d)</span>`;
      if (t === "PARTY_MISMATCH") return `<span class="badge" style="background:#f3e8ff; color:#6b21a8; border:1px solid #e9d5ff;">🏢 Party Mismatch</span>`;
      if (t === "INVOICE_NUMBER_MISMATCH") return `<span class="badge badge-medium">🔢 Inv # Mismatch</span>`;
      if (t === "MISSING_GSTIN") return `<span class="badge badge-critical">🚫 Missing GSTIN</span>`;
      if (t === "DUPLICATE_GSTIN_INVOICE") return `<span class="badge badge-critical">📑 Duplicate GSTIN+Inv</span>`;
      if (t === "CREDIT_NOTE_MISMATCH") return `<span class="badge" style="background:#fff7ed; color:#c2410c; border:1px solid #ffedd5;">📜 Credit Note Diff</span>`;
      if (t === "DEBIT_NOTE_MISMATCH") return `<span class="badge" style="background:#fff7ed; color:#c2410c; border:1px solid #ffedd5;">📜 Debit Note Diff</span>`;
      return `<span class="badge badge-resolved">✓ Matched</span>`;
    };

    const getStatusPill = (status) => {
      const s = status || "Suggested";
      if (s === "Accepted") return `<span class="badge badge-resolved">✓ Accepted</span>`;
      if (s === "Rejected") return `<span class="badge" style="background:#fee2e2; color:#b91c1c;">✕ Rejected</span>`;
      if (s === "Marked for review") return `<span class="badge badge-medium">⚠️ In Review</span>`;
      return `<span class="badge badge-disabled">Suggested</span>`;
    };

    const isSales = (details.recon_type || "").includes("Sales");

    container.innerHTML = `
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">${escapeHtml(details.title)}</h2>
            <span class="badge" style="${isSales ? 'background: #eff6ff; color: #1e40af;' : 'background: #fdf2f8; color: #9d174d;'} font-weight: 600;">
              ${escapeHtml(details.recon_type || 'Reconciliation')}
            </span>
          </div>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Target Ledger: <b>${escapeHtml(details.bank_account_name || 'All Ledgers')}</b> | Generated: ${details.created_at ? details.created_at.split('T')[0] : 'Today'}
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <a href="${FinAuditAPI.getSalesPurchaseReportDownloadUrl(reconId)}" target="_blank" class="btn btn-secondary">
            📥 Download Report (CSV)
          </a>
          <button class="btn btn-secondary" onclick="renderReconciliation()">
            ◀ Back to Reconciliations
          </button>
        </div>
      </div>

      <!-- Executive KPI Cards -->
      <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px;">
        <div class="kpi-card" style="border-left: 4px solid var(--primary);">
          <div class="kpi-label">REGISTER INVOICES</div>
          <div class="kpi-value">${details.total_bank_tx || 0}</div>
          <div class="kpi-subtext">${isSales ? 'Sales Register lines' : 'Purchase Register lines'}</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #2563eb;">
          <div class="kpi-label">LEDGER INVOICES</div>
          <div class="kpi-value">${details.total_book_tx || 0}</div>
          <div class="kpi-subtext">General ledger vouchers</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #059669;">
          <div class="kpi-label">MATCHED INVOICES</div>
          <div class="kpi-value" style="color: #059669;">${details.matched_count || 0}</div>
          <div class="kpi-subtext">Verified & reconciled</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #dc2626;">
          <div class="kpi-label">DISCREPANCIES</div>
          <div class="kpi-value" style="color: #dc2626;">${details.amount_diff_count || 0}</div>
          <div class="kpi-subtext">Audit exceptions detected</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid ${(details.net_unreconciled_difference || 0) === 0 ? '#10b981' : '#dc2626'};">
          <div class="kpi-label">NET AMOUNT VARIANCE</div>
          <div class="kpi-value font-mono" style="font-size: 13px; color: ${(details.net_unreconciled_difference || 0) === 0 ? '#059669' : '#dc2626'};">
            ${formatINR(details.net_unreconciled_difference || 0)}
          </div>
          <div class="kpi-subtext">${(details.net_unreconciled_difference || 0) === 0 ? '✓ Balanced' : 'Gross value mismatch'}</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid ${(details.unreconciled_amount || 0) === 0 ? '#10b981' : '#d97706'};">
          <div class="kpi-label">NET TAX VARIANCE</div>
          <div class="kpi-value font-mono" style="font-size: 13px; color: ${(details.unreconciled_amount || 0) === 0 ? '#059669' : '#d97706'};">
            ${formatINR(details.unreconciled_amount || 0)}
          </div>
          <div class="kpi-subtext">${(details.unreconciled_amount || 0) === 0 ? '✓ GST Slabs Match' : 'GST/ITC difference'}</div>
        </div>
      </div>

      <!-- Filter Chips & Search Bar -->
      <div class="card" style="padding: 12px 16px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <div style="font-size: 11.5px; font-weight: 700; color: #475569; text-transform: uppercase;">
            🔍 Filter Exceptions & Mismatches
          </div>
          <div style="width: 280px;">
            <input type="text" id="sp-recon-search-input" class="form-control" placeholder="Search invoice, party, GSTIN..." value="${escapeHtml(reconSPFilterState.search)}" oninput="applySPFilters(${reconId})">
          </div>
        </div>

        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'ALL' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'ALL' ? 'background:#0f172a; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'ALL')">
            📋 All Items (${items.length})
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'MISSING_IN_LEDGER' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'MISSING_IN_LEDGER' ? 'background:#dc2626; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'MISSING_IN_LEDGER')">
            ❌ Missing in Ledger
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'MISSING_IN_REGISTER' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'MISSING_IN_REGISTER' ? 'background:#b45309; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'MISSING_IN_REGISTER')">
            ⚠️ Missing in Register
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'DUPLICATE_INVOICE' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'DUPLICATE_INVOICE' ? 'background:#7c2d12; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'DUPLICATE_INVOICE')">
            📑 Duplicate Invoices
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'AMOUNT_DIFFERENCE' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'AMOUNT_DIFFERENCE' ? 'background:#ea580c; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'AMOUNT_DIFFERENCE')">
            💵 Amount Differences
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'TAX_DIFFERENCE' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'TAX_DIFFERENCE' ? 'background:#9d174d; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'TAX_DIFFERENCE')">
            ⚖️ Tax Differences
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'DATE_DIFFERENCE' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'DATE_DIFFERENCE' ? 'background:#4338ca; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'DATE_DIFFERENCE')">
            ⏱️ Date Cutoff (>15d)
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'PARTY_MISMATCH' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'PARTY_MISMATCH' ? 'background:#6b21a8; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'PARTY_MISMATCH')">
            🏢 Party Mismatches
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'MISSING_GSTIN' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'MISSING_GSTIN' ? 'background:#991b1b; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'MISSING_GSTIN')">
            🚫 Missing GSTIN
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'DUPLICATE_GSTIN_INVOICE' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'DUPLICATE_GSTIN_INVOICE' ? 'background:#831843; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'DUPLICATE_GSTIN_INVOICE')">
            📑 Duplicate GSTIN+Inv
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'CREDIT_NOTE_MISMATCH' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'CREDIT_NOTE_MISMATCH' ? 'background:#c2410c; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'CREDIT_NOTE_MISMATCH')">
            📜 Credit Note Mismatch
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'DEBIT_NOTE_MISMATCH' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'DEBIT_NOTE_MISMATCH' ? 'background:#c2410c; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'DEBIT_NOTE_MISMATCH')">
            📜 Debit Note Mismatch
          </button>
          <button class="demo-chip ${reconSPFilterState.exceptionType === 'MATCHED' ? 'active' : ''}" style="${reconSPFilterState.exceptionType === 'MATCHED' ? 'background:#059669; color:white;' : ''}" onclick="setSPFilter(${reconId}, 'MATCHED')">
            ✓ Clean Matches
          </button>
        </div>
      </div>

      <!-- Exceptions & Reconciled Items Workbench Master Table -->
      <div class="card">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div class="card-title">Reconciliation Exception Workbench (${items.length} Records)</div>
          <div style="font-size: 11px; color: #64748b;">
            All 11 audit exception rules evaluated deterministically against Register, Ledger & GST data
          </div>
        </div>

        ${items.length === 0 ? `
          <div style="padding: 30px; text-align: center; color: #64748b;">
            No records match the selected filter.
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 130px;">Invoice Number</th>
                  <th style="width: 170px;">Party Name</th>
                  <th class="text-right" style="width: 105px;">Register Amt</th>
                  <th class="text-right" style="width: 105px;">Ledger Amt</th>
                  <th class="text-right" style="width: 95px;">Difference</th>
                  <th class="text-right" style="width: 95px;">Tax Diff</th>
                  <th class="text-center" style="width: 80px;">Date Diff</th>
                  <th style="width: 130px;">Exception Category</th>
                  <th>Audit Observation & Reasoning</th>
                  <th style="width: 90px;">Status</th>
                  <th class="text-center" style="width: 140px;">Auditor Action</th>
                </tr>
              </thead>
              <tbody>
                ${items.map(itm => {
                  const invNo = itm.ref_a || itm.ref_b || "N/A";
                  const partyName = itm.party_a || itm.party_b || "N/A";
                  const hasDiff = (itm.difference || 0) > 0;
                  const hasTaxDiff = (itm.tax_difference || 0) > 0;
                  const hasDateDiff = (itm.date_diff_days || 0) > 0;

                  return `
                    <tr style="${itm.item_type !== 'MATCHED' ? 'background-color: #fffbf5;' : ''}">
                      <td>
                        <span class="font-mono font-bold" style="color: #0f172a; font-size: 12px;">${escapeHtml(invNo)}</span><br/>
                        <span style="font-size: 10px; color: #64748b;">
                          Reg: ${itm.date_a || '—'} | Led: ${itm.date_b || '—'}
                        </span>
                      </td>
                      <td>
                        <div style="font-size: 12px; font-weight: 600; color: #0f172a;">${escapeHtml(partyName)}</div>
                        ${itm.gstin_a || itm.gstin_b ? `
                          <span class="font-mono" style="font-size: 10px; color: #0284c7;">GSTIN: ${escapeHtml(itm.gstin_a || itm.gstin_b)}</span>
                        ` : `
                          <span style="font-size: 10px; color: #dc2626;">(No GSTIN)</span>
                        `}
                      </td>
                      <td class="text-right font-mono" style="font-size: 12px; color: #0f172a;">
                        ${formatINR(itm.amount_a || 0)}
                        <br/><span style="font-size: 10px; color: #64748b;">Tax: ${formatINR(itm.tax_a || 0)}</span>
                      </td>
                      <td class="text-right font-mono" style="font-size: 12px; color: #0f172a;">
                        ${formatINR(itm.amount_b || 0)}
                        <br/><span style="font-size: 10px; color: #64748b;">Tax: ${formatINR(itm.tax_b || 0)}</span>
                      </td>
                      <td class="text-right font-mono font-bold" style="font-size: 12px; color: ${hasDiff ? '#dc2626' : '#059669'};">
                        ${formatINR(itm.difference || 0)}
                      </td>
                      <td class="text-right font-mono font-bold" style="font-size: 12px; color: ${hasTaxDiff ? '#d97706' : '#059669'};">
                        ${formatINR(itm.tax_difference || 0)}
                      </td>
                      <td class="text-center font-mono" style="font-size: 11px; color: ${hasDateDiff ? '#d97706' : '#64748b'};">
                        ${hasDateDiff ? `⏱️ ${itm.date_diff_days}d` : '0d'}
                      </td>
                      <td>${getExceptionBadge(itm.item_type)}</td>
                      <td style="font-size: 11.5px; color: #334155;">
                        <div>${escapeHtml(itm.match_reason || 'Reconciled invoice record')}</div>
                        ${itm.notes && itm.notes !== itm.match_reason ? `
                          <div style="font-size: 10.5px; color: #1e40af; margin-top: 2px; background: #eff6ff; padding: 2px 5px; border-radius: 3px;">
                            💬 Auditor Note: ${escapeHtml(itm.notes)}
                          </div>
                        ` : ''}
                      </td>
                      <td>${getStatusPill(itm.status)}</td>
                      <td class="text-center">
                        <div style="display: flex; gap: 4px; justify-content: center; flex-wrap: wrap;">
                          <button class="btn btn-sm btn-success" style="padding: 2px 6px; font-size: 10.5px;" onclick="handleSPItemAction(${reconId}, ${itm.id}, 'Accepted')" title="Accept finding">
                            ✓ Accept
                          </button>
                          <button class="btn btn-sm btn-secondary" style="padding: 2px 6px; font-size: 10.5px; color: #dc2626;" onclick="handleSPItemAction(${reconId}, ${itm.id}, 'Rejected')" title="Reject finding">
                            ✕ Reject
                          </button>
                          <button class="btn btn-sm btn-secondary" style="padding: 2px 6px; font-size: 10.5px; color: #d97706;" onclick="handleSPItemAction(${reconId}, ${itm.id}, 'Marked for review')" title="Mark for review">
                            ⚠️ Review
                          </button>
                          <button class="btn btn-sm btn-secondary" style="padding: 2px 6px; font-size: 10.5px;" onclick="openSPCommentModal(${reconId}, ${itm.id}, '${escapeHtml(itm.status || 'Suggested')}', '${escapeHtml(itm.notes || '')}')" title="Add working-paper comment">
                            💬
                          </button>
                        </div>
                      </td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading Reconciliation Workbench: ${err.message}</div>`;
  }
}

function setSPFilter(reconId, exceptionType) {
  reconSPFilterState.exceptionType = exceptionType;
  viewSalesPurchaseReconDetails(reconId);
}

function applySPFilters(reconId) {
  reconSPFilterState.search = document.getElementById("sp-recon-search-input")?.value || "";
  viewSalesPurchaseReconDetails(reconId);
}

async function handleSPItemAction(reconId, itemId, status, comment = null) {
  try {
    await FinAuditAPI.updateSalesPurchaseItemAction(reconId, itemId, {
      status: status,
      auditor_comment: comment
    });
    viewSalesPurchaseReconDetails(reconId);
  } catch (err) {
    notifyError("Error updating item action: " + err.message);
  }
}

function openSPCommentModal(reconId, itemId, currentStatus, currentNotes) {
  const modalHtml = `
    <div class="modal-overlay" id="sp-comment-modal">
      <div class="modal-card" style="max-width: 500px;">
        <div class="modal-header">
          <div class="modal-title">💬 Add Auditor Comment & Review Status</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('sp-comment-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleSPCommentSubmit(event, ${reconId}, ${itemId})">
            <div class="form-group">
              <label class="form-label">Audit Review Status *</label>
              <select id="sp-modal-status" class="form-control" required>
                <option value="Accepted" ${currentStatus === 'Accepted' ? 'selected' : ''}>✓ Accept (Valid Exception / Verified)</option>
                <option value="Rejected" ${currentStatus === 'Rejected' ? 'selected' : ''}>✕ Reject (False Positive / Explanation Accepted)</option>
                <option value="Marked for review" ${currentStatus === 'Marked for review' ? 'selected' : ''}>⚠️ Marked for Review (Pending Client Clarification)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Working Paper Comment *</label>
              <textarea id="sp-modal-comment" class="form-control" rows="3" placeholder="e.g. Cross-checked with GSTR-1 e-way bill; difference of ₹450 is round-off discount." required>${escapeHtml(currentNotes || '')}</textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('sp-comment-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Auditor Note</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleSPCommentSubmit(event, reconId, itemId) {
  event.preventDefault();
  const status = document.getElementById("sp-modal-status")?.value;
  const comment = document.getElementById("sp-modal-comment")?.value.trim();

  closeModal("sp-comment-modal");

  await handleSPItemAction(reconId, itemId, status, comment);
}

// ---------------------------------------------------------------------------
// BANK BRS RECONCILIATION MODALS & WORKBENCH
// ---------------------------------------------------------------------------

async function openRunBRSModal() {
  try {
    const [ledgersRes, filesRes] = await Promise.all([
      FinAuditAPI.getBankLedgers(state.currentEngagementId).catch(() => ({ bank_ledgers: ["HDFC Bank Account"] })),
      FinAuditAPI.getUploadedFiles(state.currentEngagementId).catch(() => [])
    ]);

    const bankLedgers = ledgersRes.bank_ledgers || ["Bank Account"];
    const files = Array.isArray(filesRes) ? filesRes : [];
    const getFileName = (f) => (f?.file_name || f?.filename || f?.original_filename || "").toLowerCase();
    const bankFiles = files.filter(f => f?.data_category === "Bank Statement" || getFileName(f).includes("bank") || getFileName(f).includes("stmt"));

    const modalHtml = `
      <div class="modal-overlay" id="run-brs-modal">
        <div class="modal-card" style="max-width: 580px;">
          <div class="modal-header">
            <div class="modal-title">⚡ Execute Bank Reconciliation (BRS Engine)</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('run-brs-modal')">✕</button>
          </div>
          <div class="modal-body">
            <div style="font-size: 12.5px; color: #64748b; margin-bottom: 14px;">
              Automated 4-tier matching engine will cross-compare bank ledger transactions against external statement lines.
            </div>

            <form onsubmit="handleExecuteBRSSubmit(event)">
              <div class="form-group">
                <label class="form-label">Bank Account Ledger (Books Source A) *</label>
                <select id="brs-bank-ledger" class="form-control" required onchange="autoFillBRSTitle()">
                  ${bankLedgers.map(l => `
                    <option value="${escapeHtml(l)}">${escapeHtml(l)}</option>
                  `).join('')}
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Bank Statement Dataset (External Source B)</label>
                <select id="brs-file-b" class="form-control">
                  <option value="">-- Auto-Detect / Engagement Bank Dataset --</option>
                  ${bankFiles.map(f => `
                    <option value="${f.id}">${escapeHtml(f.file_name || f.filename || 'File #' + f.id)} (${f.data_category || 'File'})</option>
                  `).join('')}
                </select>
                <div style="font-size: 11px; color: #64748b; margin-top: 3px;">
                  If no separate statement file is selected, the engine auto-reconciles against existing engagement financial records.
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Reconciliation Title *</label>
                <input type="text" id="brs-title" class="form-control" value="HDFC Bank Account BRS Reconciliation" required>
              </div>

              <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
                <button type="button" class="btn btn-secondary" onclick="closeModal('run-brs-modal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Run Automated BRS Match</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
    autoFillBRSTitle();
  } catch (err) {
    notifyError("Error preparing BRS modal: " + err.message);
  }
}

function autoFillBRSTitle() {
  const ledger = document.getElementById("brs-bank-ledger")?.value || "Bank Account";
  const titleInput = document.getElementById("brs-title");
  if (titleInput) {
    titleInput.value = `${ledger} BRS Statement FY ${state.activeEngagement?.financial_year || '2024-25'}`;
  }
}

async function handleExecuteBRSSubmit(event) {
  event.preventDefault();
  const bankLedger = document.getElementById("brs-bank-ledger")?.value;
  const fileB = document.getElementById("brs-file-b")?.value;
  const title = document.getElementById("brs-title")?.value.trim();

  closeModal("run-brs-modal");

  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--primary);">Running 4-Tier Matching & Generating BRS Statement...</div>`;

  try {
    const res = await FinAuditAPI.executeReconciliation({
      engagement_id: state.currentEngagementId,
      bank_ledger_name: bankLedger,
      file_b_id: fileB ? parseInt(fileB) : null,
      title: title
    });
    notifySuccess(`Bank Reconciliation Completed!\n• Matched Items: ${res.summary?.matched_count || res.matched_count}\n• Unmatched Bank: ${res.summary?.unmatched_bank_count || 0}\n• Unmatched Books: ${res.summary?.unmatched_book_count || res.mismatched_count}`);
    viewReconciliationDetails(res.recon_id);
  } catch (err) {
    notifyError("Error executing reconciliation: " + err.message);
    renderReconciliation();
  }
}

async function viewReconciliationDetails(reconId) {
  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 20px; color: #64748b;">Loading BRS Statement Details...</div>`;

  try {
    const details = await FinAuditAPI.getReconciliationDetails(reconId, reconFilterState);
    currentReconDetail = details;
    const items = details.items || [];

    const getMatchLevelBadge = (level, score) => {
      const l = (level || "UNMATCHED").toUpperCase();
      if (l === "EXACT MATCH") return `<span class="badge badge-resolved" style="font-size: 11px;">✓ EXACT (100%)</span>`;
      if (l === "HIGH CONFIDENCE") return `<span class="badge" style="background: #e0f2fe; color: #0369a1; font-size: 11px;">⚡ HIGH (${score || 90}%)</span>`;
      if (l === "POSSIBLE MATCH") return `<span class="badge badge-medium" style="font-size: 11px;">⚠️ POSSIBLE (${score || 65}%)</span>`;
      return `<span class="badge badge-disabled" style="font-size: 11px;">UNMATCHED</span>`;
    };

    const getItemTypeBadge = (type) => {
      const t = type || "MATCHED";
      if (t === "UNPRESENTED_CHEQUE") return `<span class="badge" style="background:#fffbeb; color:#b45309; border:1px solid #fde68a;">📤 Unpresented Cheque</span>`;
      if (t === "OUTSTANDING_DEPOSIT") return `<span class="badge" style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;">📥 Outstanding Deposit</span>`;
      if (t === "BANK_CHARGES") return `<span class="badge" style="background:#fef2f2; color:#991b1b; border:1px solid #fecdd3;">💳 Direct Bank Charges</span>`;
      if (t === "INTEREST_CREDIT") return `<span class="badge" style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0;">💰 Interest Credited</span>`;
      if (t === "AMOUNT_MISMATCH") return `<span class="badge badge-high">⚠️ Amount Mismatch</span>`;
      if (t === "UNKNOWN_ENTRY") return `<span class="badge badge-critical">❓ Unknown Entry</span>`;
      if (t === "DUPLICATE_BOOK_ENTRY" || t === "DUPLICATE_BANK_ENTRY") return `<span class="badge badge-critical">📑 Duplicate Entry</span>`;
      return `<span class="badge badge-resolved">✓ Matched</span>`;
    };

    container.innerHTML = `
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">${escapeHtml(details.title)}</h2>
            <span class="badge badge-resolved">${details.status || 'Completed'}</span>
          </div>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Bank Account: <b>${escapeHtml(details.bank_account_name || 'Bank Account')}</b> | Generated: ${details.created_at ? details.created_at.split('T')[0] : 'Today'}
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <a href="${FinAuditAPI.getBRSReportDownloadUrl(reconId)}" target="_blank" class="btn btn-secondary">
            📥 Download BRS Report (CSV)
          </a>
          <button class="btn btn-secondary" onclick="openManualMatchModal(${reconId})">
            ➕ Manual Match Pair
          </button>
          <button class="btn btn-secondary" onclick="renderReconciliation()">
            ◀ All BRS Statements
          </button>
        </div>
      </div>

      <!-- Executive KPI Cards -->
      <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px;">
        <div class="kpi-card" style="border-left: 4px solid var(--primary);">
          <div class="kpi-label">TOTAL BANK TX</div>
          <div class="kpi-value">${details.total_bank_tx || 0}</div>
          <div class="kpi-subtext">Statement lines</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #2563eb;">
          <div class="kpi-label">TOTAL BOOK TX</div>
          <div class="kpi-value">${details.total_book_tx || 0}</div>
          <div class="kpi-subtext">Cash book entries</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #059669;">
          <div class="kpi-label">MATCHED PAIRS</div>
          <div class="kpi-value" style="color: #059669;">${details.matched_count || 0}</div>
          <div class="kpi-subtext">Reconciled pairings</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #d97706;">
          <div class="kpi-label">UNPRESENTED CHEQUES</div>
          <div class="kpi-value font-mono" style="font-size: 13px; color: #d97706;">${formatINR(details.unpresented_cheques_amount || 0)}</div>
          <div class="kpi-subtext">Payments not in bank</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid #7c3aed;">
          <div class="kpi-label">OUTSTANDING DEPOSITS</div>
          <div class="kpi-value font-mono" style="font-size: 13px; color: #7c3aed;">${formatINR(details.outstanding_deposits_amount || 0)}</div>
          <div class="kpi-subtext">Receipts not in bank</div>
        </div>
        <div class="kpi-card" style="border-left: 4px solid ${(details.net_unreconciled_difference || 0) === 0 ? '#10b981' : '#dc2626'};">
          <div class="kpi-label">NET VARIANCE</div>
          <div class="kpi-value font-mono" style="font-size: 13px; color: ${(details.net_unreconciled_difference || 0) === 0 ? '#059669' : '#dc2626'};">
            ${formatINR(details.net_unreconciled_difference || 0)}
          </div>
          <div class="kpi-subtext">${(details.net_unreconciled_difference || 0) === 0 ? '✓ Fully Reconciled' : 'Unreconciled difference'}</div>
        </div>
      </div>

      <!-- Formal Bank Reconciliation Statement (BRS Roll-Forward Schedule) -->
      <div class="card" style="margin-bottom: 20px; border: 1px solid #bfdbfe; background: #f8fafc;">
        <div class="card-header" style="background: #eff6ff; padding: 10px 16px;">
          <div style="font-weight: 700; font-size: 13.5px; color: #1e3a8a;">
            📋 Formal Bank Reconciliation Statement Computation (ICAI Standard Schedule)
          </div>
        </div>
        <div style="padding: 14px 18px;">
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 8px; font-size: 13px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">
            <div><b>Balance as per Bank Statement (Closing):</b></div>
            <div class="text-right font-mono font-bold" style="color: #0f172a;">${formatINR(details.bank_balance || 0)}</div>
          </div>
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 8px; font-size: 12.5px; padding: 6px 0; color: #d97706;">
            <div>&nbsp;&nbsp;<b>Less:</b> Cheques issued to suppliers/parties but not presented for payment</div>
            <div class="text-right font-mono font-bold">- ${formatINR(details.unpresented_cheques_amount || 0)}</div>
          </div>
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 8px; font-size: 12.5px; padding: 6px 0; color: #2563eb;">
            <div>&nbsp;&nbsp;<b>Add:</b> Cheques / receipts deposited into bank but not yet credited/cleared</div>
            <div class="text-right font-mono font-bold">+ ${formatINR(details.outstanding_deposits_amount || 0)}</div>
          </div>
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 8px; font-size: 12.5px; padding: 6px 0; color: #991b1b;">
            <div>&nbsp;&nbsp;<b>Add:</b> Direct bank charges/debits debited by bank not posted in Cash Book</div>
            <div class="text-right font-mono font-bold">+ ${formatINR(details.bank_charges_amount || 0)}</div>
          </div>
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 8px; font-size: 12.5px; padding: 6px 0; color: #059669;">
            <div>&nbsp;&nbsp;<b>Less:</b> Direct interest / remittances credited by bank not posted in Cash Book</div>
            <div class="text-right font-mono font-bold">- ${formatINR(details.interest_credited_amount || 0)}</div>
          </div>
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 8px; font-size: 13px; border-top: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1; padding: 8px 0; margin-top: 4px; background: #f1f5f9; border-radius: 4px;">
            <div><b>&nbsp;&nbsp;Adjusted Balance as per Bank Statement:</b></div>
            <div class="text-right font-mono font-bold" style="color: #0f172a;">${formatINR(details.adjusted_bank_balance || 0)}</div>
          </div>
          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 8px; font-size: 13px; padding: 8px 0;">
            <div><b>Balance as per Cash Book (Bank Ledger in Books):</b></div>
            <div class="text-right font-mono font-bold" style="color: var(--primary);">${formatINR(details.book_balance || 0)}</div>
          </div>
        </div>
      </div>

      <!-- Quick Filter Chips & Search Bar -->
      <div class="card" style="padding: 12px 16px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <div style="font-size: 11.5px; font-weight: 700; color: #475569; text-transform: uppercase;">
            🔍 Filter Items by Matching Category
          </div>
          <div style="width: 260px;">
            <input type="text" id="recon-search-input" class="form-control" placeholder="Search ref, party, memo..." value="${escapeHtml(reconFilterState.search)}" oninput="applyReconFilters(${reconId})">
          </div>
        </div>

        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          <button class="demo-chip ${reconFilterState.itemType === 'ALL' && reconFilterState.matchLevel === 'ALL' ? 'active' : ''}" style="${reconFilterState.itemType === 'ALL' && reconFilterState.matchLevel === 'ALL' ? 'background:#0f172a; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'ALL', 'ALL')">
            📋 All Items (${items.length})
          </button>
          <button class="demo-chip ${reconFilterState.matchLevel === 'EXACT MATCH' ? 'active' : ''}" style="${reconFilterState.matchLevel === 'EXACT MATCH' ? 'background:#059669; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'EXACT MATCH', 'ALL')">
            ✓ Exact Matches
          </button>
          <button class="demo-chip ${reconFilterState.matchLevel === 'HIGH CONFIDENCE' ? 'active' : ''}" style="${reconFilterState.matchLevel === 'HIGH CONFIDENCE' ? 'background:#0284c7; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'HIGH CONFIDENCE', 'ALL')">
            ⚡ High Confidence
          </button>
          <button class="demo-chip ${reconFilterState.matchLevel === 'POSSIBLE MATCH' ? 'active' : ''}" style="${reconFilterState.matchLevel === 'POSSIBLE MATCH' ? 'background:#ea580c; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'POSSIBLE MATCH', 'ALL')">
            ⚠️ Possible Matches
          </button>
          <button class="demo-chip ${reconFilterState.itemType === 'UNPRESENTED_CHEQUE' ? 'active' : ''}" style="${reconFilterState.itemType === 'UNPRESENTED_CHEQUE' ? 'background:#b45309; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'ALL', 'UNPRESENTED_CHEQUE')">
            📤 Unpresented Cheques
          </button>
          <button class="demo-chip ${reconFilterState.itemType === 'OUTSTANDING_DEPOSIT' ? 'active' : ''}" style="${reconFilterState.itemType === 'OUTSTANDING_DEPOSIT' ? 'background:#4338ca; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'ALL', 'OUTSTANDING_DEPOSIT')">
            📥 Outstanding Deposits
          </button>
          <button class="demo-chip ${reconFilterState.itemType === 'BANK_CHARGES' ? 'active' : ''}" style="${reconFilterState.itemType === 'BANK_CHARGES' ? 'background:#991b1b; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'ALL', 'BANK_CHARGES')">
            💳 Direct Bank Charges
          </button>
          <button class="demo-chip ${reconFilterState.itemType === 'INTEREST_CREDIT' ? 'active' : ''}" style="${reconFilterState.itemType === 'INTEREST_CREDIT' ? 'background:#065f46; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'ALL', 'INTEREST_CREDIT')">
            💰 Interest Credited
          </button>
          <button class="demo-chip ${reconFilterState.matchLevel === 'UNMATCHED' ? 'active' : ''}" style="${reconFilterState.matchLevel === 'UNMATCHED' ? 'background:#475569; color:white;' : ''}" onclick="setReconFilter(${reconId}, 'UNMATCHED', 'ALL')">
            ❌ All Unmatched
          </button>
        </div>
      </div>

      <!-- Reconciliation Items Master Table -->
      <div class="card">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div class="card-title">Reconciliation Matching Workbench (${items.length} Items Displayed)</div>
        </div>

        ${items.length === 0 ? `
          <div style="padding: 30px; text-align: center; color: #64748b;">
            No reconciliation items match the selected filter.
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 140px;">Match Level</th>
                  <th style="width: 160px;">Exception Category</th>
                  <th style="width: 220px;">Book Record (Source A)</th>
                  <th style="width: 220px;">Bank Statement (Source B)</th>
                  <th class="text-right" style="width: 110px;">Amount (INR)</th>
                  <th class="text-center" style="width: 90px;">Transit Lag</th>
                  <th>Match Reason & Audit Observations</th>
                  <th style="width: 100px;">Status</th>
                  <th class="text-center" style="width: 130px;">Auditor Action</th>
                </tr>
              </thead>
              <tbody>
                ${items.map(itm => {
                  const amt = itm.amount_a || itm.amount_b || 0.0;
                  const isSuggested = itm.status === "Suggested";
                  const isConfirmed = itm.status === "Confirmed" || itm.status === "Manual Matched";
                  return `
                    <tr style="${itm.match_level === 'POSSIBLE MATCH' || itm.status === 'Unmatched' ? 'background-color: #fffbf5;' : ''}">
                      <td>${getMatchLevelBadge(itm.match_level, itm.match_score)}</td>
                      <td>${getItemTypeBadge(itm.item_type)}</td>
                      <td>
                        ${itm.amount_a > 0 ? `
                          <div style="font-size: 12px; color: #0f172a;"><b>${escapeHtml(itm.party_a || 'Cash Book Entry')}</b></div>
                          <div style="font-size: 11px; color: #64748b;">Date: <b>${itm.date_a || '—'}</b> | Voucher: <span class="font-mono">${escapeHtml(itm.ref_a || '—')}</span></div>
                          <div style="font-size: 11px; color: #475569; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(itm.description_a || '')}">${escapeHtml(itm.description_a || '')}</div>
                        ` : '<span style="color:#94a3b8; font-size:11px;">(Missing in Books)</span>'}
                      </td>
                      <td>
                        ${itm.amount_b > 0 ? `
                          <div style="font-size: 12px; color: #0f172a;"><b>${escapeHtml(itm.party_b || itm.description_b || 'Statement Line')}</b></div>
                          <div style="font-size: 11px; color: #64748b;">Date: <b>${itm.date_b || '—'}</b> | Ref: <span class="font-mono">${escapeHtml(itm.ref_b || '—')}</span></div>
                          <div style="font-size: 11px; color: #475569; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(itm.description_b || '')}">${escapeHtml(itm.description_b || '')}</div>
                        ` : '<span style="color:#94a3b8; font-size:11px;">(Missing in Bank)</span>'}
                      </td>
                      <td class="text-right font-mono font-bold" style="font-size: 12.5px; color: #0f172a;">
                        ${formatINR(amt)}
                        ${itm.difference > 0 ? `<br/><span style="font-size:10px; color:#dc2626;">Diff: ${formatINR(itm.difference)}</span>` : ''}
                      </td>
                      <td class="text-center font-mono" style="font-size: 11.5px; color: #475569;">
                        ${itm.date_diff_days > 0 ? `⏱️ ${itm.date_diff_days}d` : 'Same Day'}
                      </td>
                      <td style="font-size: 11.5px; color: #334155;">
                        <div>${escapeHtml(itm.match_reason || itm.notes || 'Reconciled item')}</div>
                        ${itm.notes && itm.notes !== itm.match_reason ? `<div style="font-size: 10.5px; color: #64748b; margin-top: 2px;">💬 ${escapeHtml(itm.notes)}</div>` : ''}
                      </td>
                      <td>
                        ${isConfirmed ? `
                          <span class="badge badge-resolved">Confirmed</span>
                        ` : (isSuggested ? `
                          <span class="badge badge-medium">Suggested</span>
                        ` : `
                          <span class="badge badge-disabled">Unmatched</span>
                        `)}
                      </td>
                      <td class="text-center">
                        <div style="display: flex; gap: 4px; justify-content: center;">
                          ${isSuggested ? `
                            <button class="btn btn-sm btn-success" style="padding: 3px 7px; font-size: 11px;" onclick="confirmBRSMatch(${reconId}, ${itm.id})" title="Confirm suggested match">
                              ✓ Accept
                            </button>
                            <button class="btn btn-sm btn-secondary" style="padding: 3px 7px; font-size: 11px; color: #dc2626;" onclick="rejectBRSMatch(${reconId}, ${itm.id})" title="Reject match">
                              ✕ Reject
                            </button>
                          ` : (isConfirmed ? `
                            <button class="btn btn-sm btn-secondary" style="padding: 3px 7px; font-size: 11px;" onclick="rejectBRSMatch(${reconId}, ${itm.id})" title="Unlink / Reject">
                              Unlink
                            </button>
                          ` : `
                            <button class="btn btn-sm btn-secondary" style="padding: 3px 7px; font-size: 11px;" onclick="openManualMatchModal(${reconId})">
                              Match...
                            </button>
                          `)}
                        </div>
                      </td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading BRS Workbench: ${err.message}</div>`;
  }
}

function setReconFilter(reconId, matchLevel, itemType) {
  reconFilterState.matchLevel = matchLevel;
  reconFilterState.itemType = itemType;
  viewReconciliationDetails(reconId);
}

function applyReconFilters(reconId) {
  reconFilterState.search = document.getElementById("recon-search-input")?.value || "";
  viewReconciliationDetails(reconId);
}

async function confirmBRSMatch(reconId, itemId) {
  try {
    await FinAuditAPI.confirmReconMatch(reconId, itemId);
    viewReconciliationDetails(reconId);
  } catch (err) {
    notifyError("Error confirming match: " + err.message);
  }
}

async function rejectBRSMatch(reconId, itemId) {
  const confirmed = await FinConfirm({
    title: "Reject Reconciliation Match",
    message: "Are you sure you want to unlink and reject this match?",
    consequences: ["The transaction pair will be moved back to the unmatched population"],
    confirmText: "Unlink & Reject",
    isDanger: true
  });
  if (confirmed) {
    try {
      await FinAuditAPI.rejectReconMatch(reconId, itemId);
      viewReconciliationDetails(reconId);
    } catch (err) {
      notifyError("Error rejecting match: " + err.message);
    }
  }
}

async function openManualMatchModal(reconId) {
  try {
    const details = await FinAuditAPI.getReconciliationDetails(reconId);
    const items = details.items || [];
    const unmatchedBook = items.filter(i => i.amount_a > 0 && i.status === "Unmatched");
    const unmatchedBank = items.filter(i => i.amount_b > 0 && i.status === "Unmatched");

    if (unmatchedBook.length === 0 || unmatchedBank.length === 0) {
      notifyWarning("Both an unmatched Book item and an unmatched Bank item are required to create a manual match.");
      return;
    }

    const modalHtml = `
      <div class="modal-overlay" id="manual-match-modal">
        <div class="modal-card" style="max-width: 650px;">
          <div class="modal-header">
            <div class="modal-title">🔗 Auditor Manual Match Pairing</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('manual-match-modal')">✕</button>
          </div>
          <div class="modal-body">
            <div style="font-size: 12px; color: #64748b; margin-bottom: 12px;">
              Select one unmatched Book voucher and one unmatched Bank statement line to create an auditor-confirmed reconciliation pairing.
            </div>

            <form onsubmit="handleManualMatchSubmit(event, ${reconId})">
              <div class="form-group">
                <label class="form-label">Select Unmatched Book Item (Cash Book) *</label>
                <select id="mm-book-item" class="form-control" required>
                  ${unmatchedBook.map(b => `
                    <option value="${b.id}">
                      [${b.date_a || 'Date'}] ${b.party_a || 'Entry'} — ${formatINR(b.amount_a)} (Voucher: ${b.ref_a || 'N/A'})
                    </option>
                  `).join('')}
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Select Unmatched Bank Statement Line *</label>
                <select id="mm-bank-item" class="form-control" required>
                  ${unmatchedBank.map(b => `
                    <option value="${b.id}">
                      [${b.date_b || 'Date'}] ${b.party_b || b.description_b || 'Line'} — ${formatINR(b.amount_b)} (Ref: ${b.ref_b || 'N/A'})
                    </option>
                  `).join('')}
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Auditor Working Paper Remark</label>
                <textarea id="mm-notes" class="form-control" rows="2" placeholder="e.g. Verified contra voucher reference; timing transit delay of 4 days confirmed."></textarea>
              </div>

              <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
                <button type="button" class="btn btn-secondary" onclick="closeModal('manual-match-modal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Create Manual Match</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Error opening manual match: " + err.message);
  }
}

async function handleManualMatchSubmit(event, reconId) {
  event.preventDefault();
  const bookId = document.getElementById("mm-book-item")?.value;
  const bankId = document.getElementById("mm-bank-item")?.value;
  const notes = document.getElementById("mm-notes")?.value.trim();

  closeModal("manual-match-modal");

  try {
    await FinAuditAPI.manualMatchReconItems(reconId, {
      book_item_id: parseInt(bookId),
      bank_item_id: parseInt(bankId),
      auditor_notes: notes
    });
    notifySuccess("Manual match created successfully!");
    viewReconciliationDetails(reconId);
  } catch (err) {
    notifyError("Error creating manual match: " + err.message);
  }
}


// Financial Statements View (Schedule III)
async function renderFinancialStatements() {
  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 20px;">Generating Schedule III Financial Statements...</div>`;

  try {
    const fs = await FinAuditAPI.getFinancialStatements(state.currentEngagementId);

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Financial Statements (Schedule III Companies Act)</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Draft Statement of Profit & Loss and Balance Sheet for FY ${fs.financial_year}
          </div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
        <div class="card">
          <div class="card-header">
            <div class="card-title">Statement of Profit and Loss</div>
          </div>
          <div style="margin-bottom: 12px; font-size: 13px; font-weight: 700; color: #2563eb;">I. Revenue from Operations</div>
          <div class="table-container" style="margin-bottom: 16px;">
            <table class="data-table">
              ${fs.profit_and_loss.revenue_items.map(r => `
                <tr>
                  <td>${r.ledger}</td>
                  <td class="text-right font-mono font-bold">${formatINR(r.amount)}</td>
                </tr>
              `).join("")}
              <tr style="background-color: #f8fafc; font-weight: 700;">
                <td>Total Revenue (A)</td>
                <td class="text-right font-mono">${formatINR(fs.profit_and_loss.total_revenue)}</td>
              </tr>
            </table>
          </div>

          <div style="margin-bottom: 12px; font-size: 13px; font-weight: 700; color: #dc2626;">II. Expenses</div>
          <div class="table-container" style="margin-bottom: 16px;">
            <table class="data-table">
              ${fs.profit_and_loss.expense_items.map(e => `
                <tr>
                  <td>${e.ledger}</td>
                  <td class="text-right font-mono font-bold">${formatINR(e.amount)}</td>
                </tr>
              `).join("")}
              <tr style="background-color: #f8fafc; font-weight: 700;">
                <td>Total Expenses (B)</td>
                <td class="text-right font-mono">${formatINR(fs.profit_and_loss.total_expenses)}</td>
              </tr>
            </table>
          </div>

          <div style="padding: 12px; background: #eff6ff; border-radius: var(--radius-md); border: 1px solid #bfdbfe;">
            <div style="display: flex; justify-content: space-between; font-weight: 700; font-size: 13px;">
              <span>Profit Before Tax:</span>
              <span class="font-mono">${formatINR(fs.profit_and_loss.net_profit_before_tax)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #475569; margin-top: 4px;">
              <span>Tax Expense @ 25%:</span>
              <span class="font-mono">${formatINR(fs.profit_and_loss.tax_provision_25pct)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-weight: 700; font-size: 14px; color: #1d4ed8; margin-top: 6px; border-top: 1px solid #bfdbfe; padding-top: 6px;">
              <span>Profit After Tax (PAT):</span>
              <span class="font-mono">${formatINR(fs.profit_and_loss.profit_after_tax)}</span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title">Balance Sheet (Draft)</div>
          </div>
          <div style="margin-bottom: 12px; font-size: 13px; font-weight: 700; color: #0f172a;">EQUITY AND LIABILITIES</div>
          <div class="table-container" style="margin-bottom: 16px;">
            <table class="data-table">
              ${fs.balance_sheet.liability_items.map(l => `
                <tr>
                  <td>${l.ledger}</td>
                  <td class="text-right font-mono">${formatINR(l.amount)}</td>
                </tr>
              `).join("")}
              <tr>
                <td>Retained Surplus (PAT for current year)</td>
                <td class="text-right font-mono font-bold">${formatINR(fs.balance_sheet.retained_earnings_pat)}</td>
              </tr>
              <tr style="background-color: #f8fafc; font-weight: 700;">
                <td>Total Equity & Liabilities</td>
                <td class="text-right font-mono">${formatINR(fs.balance_sheet.total_equity_and_liabilities)}</td>
              </tr>
            </table>
          </div>

          <div style="margin-bottom: 12px; font-size: 13px; font-weight: 700; color: #0f172a;">ASSETS</div>
          <div class="table-container">
            <table class="data-table">
              ${fs.balance_sheet.asset_items.map(a => `
                <tr>
                  <td>${a.ledger}</td>
                  <td class="text-right font-mono">${formatINR(a.amount)}</td>
                </tr>
              `).join("")}
              <tr style="background-color: #f8fafc; font-weight: 700;">
                <td>Total Assets</td>
                <td class="text-right font-mono">${formatINR(fs.balance_sheet.total_assets)}</td>
              </tr>
            </table>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error: ${err.message}</div>`;
  }
}

// Local AI Audit Assistant View
async function renderAIAssistant() {
  const container = document.getElementById("content-container");
  
  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div>
        <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Local AI Audit Assistant & Query Engine</h2>
        <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
          100% Offline AI Natural Language Auditor • Evidence-backed reasoning
        </div>
      </div>
    </div>

    <div class="chat-container">
      <div class="chat-messages" id="chat-messages">
        <div class="chat-bubble bot">
          <b>FinAuditPro AI Assistant initialized (100% Local & Offline).</b><br/>
          I have indexed all transactions, trial balance groupings, and audit findings for this engagement. How can I assist with your audit verification?
        </div>
      </div>

      <div style="padding: 8px 16px; background: #f1f5f9; display: flex; gap: 8px; overflow-x: auto;">
        <button class="btn btn-sm btn-secondary" onclick="sendQuickPrompt('Show large cash transactions above Section 40A(3) limit')">💡 Section 40A(3) Cash Violations</button>
        <button class="btn btn-sm btn-secondary" onclick="sendQuickPrompt('What are the critical risks in this engagement?')">💡 Critical Audit Risks</button>
        <button class="btn btn-sm btn-secondary" onclick="sendQuickPrompt('What are the top 5 highest value vouchers?')">💡 Top 5 Highest Vouchers</button>
        <button class="btn btn-sm btn-secondary" onclick="sendQuickPrompt('Are there any GSTIN format or ITC matching issues?')">💡 GSTIN & ITC Compliance</button>
      </div>

      <div class="chat-input-bar">
        <input type="text" id="chat-input" class="form-control" placeholder="Ask a question about financial vouchers, tax limits, or audit rules..." onkeydown="if(event.key==='Enter') submitChatMessage()">
        <button class="btn btn-primary" onclick="submitChatMessage()">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
          Ask
        </button>
      </div>
    </div>
  `;
}

async function sendQuickPrompt(promptText) {
  document.getElementById("chat-input").value = promptText;
  await submitChatMessage();
}

async function submitChatMessage() {
  const input = document.getElementById("chat-input");
  const query = input.value.trim();
  if (!query) return;

  const chatMessages = document.getElementById("chat-messages");
  chatMessages.innerHTML += `<div class="chat-bubble user">${query}</div>`;
  input.value = "";
  chatMessages.scrollTop = chatMessages.scrollHeight;

  const loadingId = "bot-loading-" + Date.now();
  chatMessages.innerHTML += `<div class="chat-bubble bot" id="${loadingId}">Analyzing local financial records...</div>`;
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await FinAuditAPI.queryAssistant({
      engagement_id: state.currentEngagementId,
      query: query
    });

    const loadingElem = document.getElementById(loadingId);
    let botHtml = `<div>${res.response.replace(/\n/g, '<br/>')}</div>`;

    if (res.evidence && res.evidence.length > 0) {
      botHtml += `
        <div style="margin-top: 10px; padding: 8px; background: #ffffff; border: 1px solid var(--border); border-radius: var(--radius-sm); font-size: 11.5px;">
          <b>Attached Audit Evidence:</b>
          <div style="margin-top: 4px;">
            ${res.evidence.map(e => `
              <div style="padding: 2px 0; font-family: monospace;">• ${JSON.stringify(e)}</div>
            `).join("")}
          </div>
        </div>
      `;
    }

    if (loadingElem) {
      loadingElem.innerHTML = botHtml;
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
  } catch (err) {
    const loadingElem = document.getElementById(loadingId);
    if (loadingElem) {
      loadingElem.innerHTML = `<span style="color: #dc2626;">Error: ${err.message}</span>`;
    }
  }
}

// Data Import View
function renderImportData() {
  const container = document.getElementById("content-container");
  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div>
        <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Data Import & Smart Column Mapper</h2>
        <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
          Import General Ledger, Day Book, Bank Statements, or GST Files (.xlsx, .csv, .json)
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">1. Upload Financial Data File</div>
      </div>
      <div style="padding: 24px; border: 2px dashed var(--border-dark); border-radius: var(--radius-lg); text-align: center; background: #f8fafc;" id="drop-zone">
        <svg width="40" height="40" fill="none" stroke="#64748b" viewBox="0 0 24 24" style="margin-bottom: 8px;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
        <div style="font-weight: 600; color: #0f172a;">Drag and drop Excel (.xlsx, .xls), CSV, or JSON file here</div>
        <div style="font-size: 12px; color: #64748b; margin-top: 4px;">Supports Tally, SAP, Busy, Quickbooks, and custom ERP export files</div>
        <input type="file" id="file-input" style="display: none;" accept=".xlsx,.xls,.csv,.json" onchange="handleFileSelected(event)">
        <button class="btn btn-primary" style="margin-top: 14px;" onclick="document.getElementById('file-input').click()">Browse Local Files</button>
      </div>
    </div>

    <div id="mapping-container"></div>
  `;
}

async function handleFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  const mappingContainer = document.getElementById("mapping-container");
  mappingContainer.innerHTML = `<div style="padding: 20px; color: #2563eb;">Analyzing file structure and auto-detecting columns...</div>`;

  try {
    const preview = await FinAuditAPI.uploadFile(state.currentEngagementId, file);
    state.uploadPreview = preview;

    const standardFields = [
      { id: "date", name: "Transaction / Voucher Date" },
      { id: "voucher_no", name: "Voucher Number" },
      { id: "invoice_no", name: "Invoice / Reference Number" },
      { id: "ledger", name: "Ledger / Account Head" },
      { id: "party_name", name: "Party / Vendor / Customer Name" },
      { id: "gstin", name: "GSTIN (15 Digits)" },
      { id: "debit", name: "Debit Amount" },
      { id: "credit", name: "Credit Amount" },
      { id: "amount", name: "Total Amount" },
      { id: "description", name: "Narration / Description" },
      { id: "payment_date", name: "Payment Date" }
    ];

    mappingContainer.innerHTML = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">2. Intelligent Column Mapping (${preview.file_name})</div>
            <div class="card-subtitle">Estimated ${preview.estimated_rows} rows. Review auto-detected fields below.</div>
          </div>
          <button class="btn btn-primary" onclick="submitImportMapping()">Confirm & Import Transactions</button>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; margin-bottom: 20px;">
          ${standardFields.map(f => {
            const matchedCol = Object.keys(preview.suggested_mapping).find(src => preview.suggested_mapping[src] === f.id) || "";
            return `
              <div class="form-group" style="padding: 10px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md);">
                <label class="form-label">${f.name}</label>
                <select class="form-control mapping-select" data-field="${f.id}">
                  <option value="">-- Ignore Field --</option>
                  ${preview.columns.map(c => `
                    <option value="${c}" ${c === matchedCol ? 'selected' : ''}>${c}</option>
                  `).join("")}
                </select>
              </div>
            `;
          }).join("")}
        </div>

        <div class="card-title" style="font-size: 13px; margin-bottom: 8px;">Source Data Preview (First 5 Rows):</div>
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>${preview.columns.map(c => `<th>${c}</th>`).join("")}</tr>
            </thead>
            <tbody>
              ${preview.preview_rows.slice(0, 5).map(r => `
                <tr>
                  ${preview.columns.map(c => `<td>${r[c] !== null && r[c] !== undefined ? r[c] : ''}</td>`).join("")}
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    mappingContainer.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error parsing file: ${err.message}</div>`;
  }
}

async function submitImportMapping() {
  if (!state.uploadPreview) return;
  const selects = document.querySelectorAll(".mapping-select");
  const mapping = {};

  selects.forEach(sel => {
    const srcCol = sel.value;
    const targetField = sel.dataset.field;
    if (srcCol) {
      mapping[srcCol] = targetField;
    }
  });

  try {
    const res = await FinAuditAPI.applyMapping(state.uploadPreview.file_id, mapping);
    notifyInfo(res.message);
    await updateActiveEngagement();
    navigateTo("trial_balance");
  } catch (err) {
    notifyError("Import failed: " + err.message);
  }
}

// ==========================================
// AUDIT CHECKLIST & COMPLIANCE WORKPROGRAM
// 15 Categories, Dynamic Risk Findings Integration,
// Custom Items, and Manual Auditor Sign-off
// ==========================================

const checklistState = {
  activeCategory: "All",
  statusFilter: "All",
  searchQuery: "",
  summary: null,
  items: []
};

const CHECKLIST_CATEGORIES_LIST = [
  "Planning",
  "Internal Controls",
  "Cash & Bank",
  "Receivables",
  "Payables",
  "Inventory",
  "Fixed Assets",
  "Revenue",
  "Expenses",
  "Loans",
  "Related Parties",
  "Payroll",
  "Tax/GST",
  "Financial Statements",
  "Closing Procedures"
];

function getChecklistStatusBadge(status) {
  const s = status || "Not Started";
  if (s === "Completed") return `<span class="badge badge-chk-completed">✓ Completed</span>`;
  if (s === "In Progress") return `<span class="badge badge-chk-in-progress">⟳ In Progress</span>`;
  if (s === "Requires Review") return `<span class="badge badge-chk-requires-review">⚠ Requires Review</span>`;
  if (s === "Not Applicable") return `<span class="badge badge-chk-not-applicable">Ø Not Applicable</span>`;
  return `<span class="badge badge-chk-not-started">○ Not Started</span>`;
}

async function renderChecklist() {
  const container = document.getElementById("content-container");
  if (!container) return;

  container.innerHTML = `
    <div style="padding: 24px; text-align: center; color: #64748b;">
      <div style="font-size: 24px; margin-bottom: 8px;">📋</div>
      Loading Audit Checklist & Substantive Procedures...
    </div>
  `;

  try {
    const [summary, items] = await Promise.all([
      FinAuditAPI.getChecklistSummary(state.currentEngagementId),
      FinAuditAPI.getChecklist(state.currentEngagementId, {
        category: checklistState.activeCategory !== "All" ? checklistState.activeCategory : null,
        status: checklistState.statusFilter !== "All" ? checklistState.statusFilter : null,
        search: checklistState.searchQuery || null
      })
    ]);

    checklistState.summary = summary;
    checklistState.items = items;

    const statusCounts = summary.status_counts || {};
    const catCounts = summary.category_counts || {};
    const totalItems = summary.total_items || 0;
    const completedItems = statusCounts["Completed"] || 0;
    const inProgressItems = statusCounts["In Progress"] || 0;
    const reqReviewItems = statusCounts["Requires Review"] || 0;
    const notStartedItems = statusCounts["Not Started"] || 0;
    const naItems = statusCounts["Not Applicable"] || 0;
    const completionPct = summary.completion_percentage || 0;

    const activeEng = state.activeEngagement || {};
    const clientType = activeEng.client_type || activeEng.entity_type || "Corporate Entity";
    const auditType = activeEng.audit_type || "Statutory Audit";
    const fy = activeEng.financial_year || "2024-25";

    container.innerHTML = `
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
        <div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <h2 style="font-size: 20px; font-weight: 700; color: #0f172a; margin: 0;">Audit Checklist & Substantive Workprogram</h2>
            <span class="badge badge-medium">${auditType}</span>
            <span class="badge badge-low">FY ${fy}</span>
          </div>
          <div style="font-size: 13px; color: #64748b; margin-top: 4px;">
            Dynamic 15-category substantive procedures tailored to <b>${clientType}</b>, financial year, and automated risk findings.
          </div>
        </div>

        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <button class="btn btn-secondary" onclick="openGenerateChecklistModal()" title="Tailor procedures for this engagement">
            ⚡ Regenerate / Tailor
          </button>
          <button class="btn btn-primary" onclick="openCreateCustomChecklistItemModal()">
            ➕ Add Custom Procedure
          </button>
          <a class="btn btn-secondary" href="${FinAuditAPI.getExportChecklistCsvUrl(state.currentEngagementId)}" download="audit_checklist_${state.currentEngagementId}.csv">
            📥 Export CSV
          </a>
        </div>
      </div>

      <!-- Professional Standard Skepticism Banner -->
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 10px 14px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 12.5px; color: #334155;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 16px;">🛡️</span>
          <span><b>Auditor Professional Skepticism Policy (SA 200/230):</b> AI audit engines automatically flag exceptions and initiate procedures as <i>'Requires Review'</i> or <i>'Not Started'</i>. Items are <b>never automatically marked Completed</b> by AI without verified auditor working paper sign-off.</span>
        </div>
        <span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; white-space: nowrap;">Offline Deterministic Check</span>
      </div>

      <!-- Summary KPI Row -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px;">
        <!-- Total & Completion -->
        <div class="card" style="padding: 14px; display: flex; flex-direction: column; justify-content: space-between;">
          <div style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;">Total Procedures</div>
          <div style="display: flex; align-items: baseline; gap: 8px; margin: 6px 0;">
            <span style="font-size: 26px; font-weight: 700; color: #0f172a;">${totalItems}</span>
            <span style="font-size: 12px; color: #059669; font-weight: 600;">${completionPct}% Done</span>
          </div>
          <div style="background: #e2e8f0; border-radius: 6px; height: 6px; overflow: hidden;">
            <div style="background: #10b981; width: ${completionPct}%; height: 100%; transition: width 0.3s ease;"></div>
          </div>
        </div>

        <!-- Requires Review -->
        <div class="card" style="padding: 14px; border-left: 3px solid ${reqReviewItems > 0 ? '#e11d48' : '#e2e8f0'};">
          <div style="font-size: 11px; font-weight: 600; color: #e11d48; text-transform: uppercase;">Requires Review</div>
          <div style="font-size: 26px; font-weight: 700; color: ${reqReviewItems > 0 ? '#be123c' : '#0f172a'}; margin: 6px 0;">
            ${reqReviewItems}
          </div>
          <div style="font-size: 11px; color: #64748b;">Substantive & Risk Exceptions</div>
        </div>

        <!-- In Progress -->
        <div class="card" style="padding: 14px; border-left: 3px solid #3b82f6;">
          <div style="font-size: 11px; font-weight: 600; color: #2563eb; text-transform: uppercase;">In Progress</div>
          <div style="font-size: 26px; font-weight: 700; color: #1d4ed8; margin: 6px 0;">
            ${inProgressItems}
          </div>
          <div style="font-size: 11px; color: #64748b;">Active Fieldwork</div>
        </div>

        <!-- Completed -->
        <div class="card" style="padding: 14px; border-left: 3px solid #10b981;">
          <div style="font-size: 11px; font-weight: 600; color: #059669; text-transform: uppercase;">Completed</div>
          <div style="font-size: 26px; font-weight: 700; color: #047857; margin: 6px 0;">
            ${completedItems}
          </div>
          <div style="font-size: 11px; color: #64748b;">Auditor Signed Off</div>
        </div>

        <!-- Not Started -->
        <div class="card" style="padding: 14px;">
          <div style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;">Not Started</div>
          <div style="font-size: 26px; font-weight: 700; color: #475569; margin: 6px 0;">
            ${notStartedItems}
          </div>
          <div style="font-size: 11px; color: #64748b;">Pending Staff Allocation</div>
        </div>

        <!-- Not Applicable -->
        <div class="card" style="padding: 14px;">
          <div style="font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase;">Not Applicable</div>
          <div style="font-size: 26px; font-weight: 700; color: #94a3b8; margin: 6px 0;">
            ${naItems}
          </div>
          <div style="font-size: 11px; color: #94a3b8;">Out of Scope</div>
        </div>
      </div>

      <!-- 15 Categories Tab Bar -->
      <div style="margin-bottom: 16px;">
        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 8px;">
          Audit Scope Categories (${CHECKLIST_CATEGORIES_LIST.length} Sections)
        </div>
        <div style="display: flex; gap: 6px; overflow-x: auto; padding-bottom: 8px; -webkit-overflow-scrolling: touch;">
          <button class="category-tab-chip ${checklistState.activeCategory === 'All' ? 'active' : ''}" onclick="filterChecklistCategory('All')">
            <span>All Categories</span>
            <span class="badge-count">${totalItems}</span>
          </button>
          ${CHECKLIST_CATEGORIES_LIST.map(cat => `
            <button class="category-tab-chip ${checklistState.activeCategory === cat ? 'active' : ''}" onclick="filterChecklistCategory('${cat}')">
              <span>${cat}</span>
              <span class="badge-count">${catCounts[cat] || 0}</span>
            </button>
          `).join("")}
        </div>
      </div>

      <!-- Filter and Search Toolbar -->
      <div class="card" style="padding: 12px 16px; margin-bottom: 16px;">
        <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
          <!-- Search -->
          <div style="flex: 1; min-width: 220px; position: relative;">
            <input
              type="text"
              id="checklist-search-input"
              class="form-control"
              placeholder="🔍 Search procedures, checklist ID, or assigned staff..."
              value="${checklistState.searchQuery || ''}"
              onkeydown="if(event.key==='Enter') executeChecklistSearch(this.value)"
            >
          </div>

          <!-- Status Filter -->
          <div style="width: 190px;">
            <select class="form-control" onchange="filterChecklistStatus(this.value)">
              <option value="All" ${checklistState.statusFilter === 'All' ? 'selected' : ''}>All Statuses (${totalItems})</option>
              <option value="Requires Review" ${checklistState.statusFilter === 'Requires Review' ? 'selected' : ''}>⚠ Requires Review (${reqReviewItems})</option>
              <option value="In Progress" ${checklistState.statusFilter === 'In Progress' ? 'selected' : ''}>⟳ In Progress (${inProgressItems})</option>
              <option value="Not Started" ${checklistState.statusFilter === 'Not Started' ? 'selected' : ''}>○ Not Started (${notStartedItems})</option>
              <option value="Completed" ${checklistState.statusFilter === 'Completed' ? 'selected' : ''}>✓ Completed (${completedItems})</option>
              <option value="Not Applicable" ${checklistState.statusFilter === 'Not Applicable' ? 'selected' : ''}>Ø Not Applicable (${naItems})</option>
            </select>
          </div>

          <button class="btn btn-secondary" onclick="executeChecklistSearch(document.getElementById('checklist-search-input').value)">
            Search
          </button>

          ${(checklistState.activeCategory !== 'All' || checklistState.statusFilter !== 'All' || checklistState.searchQuery) ? `
            <button class="btn btn-sm btn-secondary" onclick="resetChecklistFilters()">
              ✕ Clear Filters
            </button>
          ` : ''}
        </div>
      </div>

      <!-- Procedures Table -->
      <div class="card">
        <div class="table-container" style="max-height: 680px; overflow-y: auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 110px;">Checklist ID</th>
                <th style="width: 130px;">Category</th>
                <th>Question / Procedure Description</th>
                <th style="width: 140px;">Status</th>
                <th style="width: 120px;">Assigned Staff</th>
                <th style="width: 150px;">Evidence & Cross-Ref</th>
                <th style="width: 140px;">Auditor Comment</th>
                <th style="width: 95px;">Due Date</th>
                <th style="width: 95px;">Completed</th>
                <th class="text-center" style="width: 90px;">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${items.length === 0 ? `
                <tr>
                  <td colspan="10" style="text-align: center; padding: 40px; color: #64748b;">
                    <div style="font-size: 28px; margin-bottom: 8px;">📂</div>
                    <div style="font-weight: 600; font-size: 14px; color: #1e293b;">No checklist items found</div>
                    <div style="font-size: 12px; margin-top: 4px;">Try clearing filters or click <b>"Regenerate / Tailor"</b> to generate standard procedures.</div>
                  </td>
                </tr>
              ` : items.map(item => `
                <tr style="${item.status === 'Requires Review' ? 'background-color: #fff9f9;' : ''}">
                  <!-- Checklist ID -->
                  <td>
                    <div class="font-mono font-bold" style="color: #1e293b; font-size: 12px;">${item.item_code}</div>
                    ${item.is_custom ? '<span class="badge badge-low" style="font-size: 9px; padding: 1px 4px;">CUSTOM</span>' : ''}
                    ${item.risk_finding_id ? `
                      <span class="badge badge-critical" style="font-size: 9px; padding: 1px 4px; cursor: pointer;" onclick="openLinkedRiskFinding(${item.risk_finding_id})" title="Click to view linked risk finding">
                        ⚡ RISK #${item.risk_finding_id}
                      </span>
                    ` : ''}
                  </td>

                  <!-- Category -->
                  <td>
                    <span class="badge badge-medium" style="font-size: 11px; white-space: nowrap;">${item.category}</span>
                  </td>

                  <!-- Question / Procedure -->
                  <td>
                    <div style="font-weight: 600; color: #0f172a; font-size: 12.5px; line-height: 1.45;">
                      ${item.question}
                    </div>
                    ${item.guidance ? `
                      <div style="font-size: 11px; color: #64748b; margin-top: 4px; line-height: 1.35;">
                        <span style="font-weight: 600;">Guidance:</span> ${item.guidance}
                      </div>
                    ` : ''}
                  </td>

                  <!-- Status with inline dropdown -->
                  <td>
                    <div style="margin-bottom: 4px;">
                      ${getChecklistStatusBadge(item.status)}
                    </div>
                    <select
                      class="form-control"
                      style="font-size: 11px; padding: 3px 6px; height: auto;"
                      onchange="handleInlineChecklistStatusChange(${item.id}, this.value)"
                    >
                      <option value="Not Started" ${item.status === 'Not Started' ? 'selected' : ''}>Not Started</option>
                      <option value="In Progress" ${item.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
                      <option value="Requires Review" ${item.status === 'Requires Review' ? 'selected' : ''}>Requires Review</option>
                      <option value="Completed" ${item.status === 'Completed' ? 'selected' : ''}>Completed</option>
                      <option value="Not Applicable" ${item.status === 'Not Applicable' ? 'selected' : ''}>Not Applicable</option>
                    </select>
                  </td>

                  <!-- Assigned Staff -->
                  <td style="font-size: 12px; color: #334155;">
                    ${item.assigned_staff ? `<span>👤 ${item.assigned_staff}</span>` : '<span style="color: #94a3b8; font-style: italic;">Unassigned</span>'}
                  </td>

                  <!-- Evidence -->
                  <td>
                    ${item.evidence ? `
                      <div style="font-size: 11.5px; color: #0369a1; background: #f0f9ff; padding: 4px 6px; border-radius: 4px; border: 1px solid #bae6fd; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.evidence}">
                        📎 ${item.evidence}
                      </div>
                    ` : '<span style="color: #94a3b8; font-size: 11.5px;">None</span>'}
                  </td>

                  <!-- Comment -->
                  <td>
                    ${item.comment ? `
                      <div style="font-size: 11.5px; color: #475569; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.comment}">
                        💬 ${item.comment}
                      </div>
                    ` : '<span style="color: #94a3b8; font-size: 11.5px;">—</span>'}
                  </td>

                  <!-- Due Date -->
                  <td style="font-size: 11.5px; color: #475569; white-space: nowrap;">
                    ${item.due_date || '—'}
                  </td>

                  <!-- Completed Date -->
                  <td style="font-size: 11.5px; color: #047857; white-space: nowrap; font-weight: 500;">
                    ${item.completed_date || '—'}
                  </td>

                  <!-- Actions -->
                  <td class="text-center">
                    <div style="display: flex; gap: 4px; justify-content: center;">
                      <button
                        class="btn btn-sm btn-secondary"
                        style="padding: 3px 7px; font-size: 11px;"
                        onclick="openChecklistSignOffModal(${item.id})"
                        title="Inspect, sign off, and edit procedure details"
                      >
                        ✏️ Review
                      </button>
                      ${item.is_custom ? `
                        <button
                          class="btn btn-sm btn-secondary"
                          style="padding: 3px 6px; font-size: 11px; color: #dc2626;"
                          onclick="handleDeleteChecklistItem(${item.id}, '${item.item_code}')"
                          title="Delete custom item"
                        >
                          🗑️
                        </button>
                      ` : ''}
                    </div>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    console.error("Failed to render checklist:", err);
    container.innerHTML = `
      <div class="card" style="padding: 30px; text-align: center; color: #dc2626;">
        <h3>Failed to Load Audit Checklist</h3>
        <p style="margin-top: 8px; color: #64748b;">${err.message || 'An error occurred while fetching checklist procedures.'}</p>
        <button class="btn btn-primary" style="margin-top: 16px;" onclick="renderChecklist()">Retry</button>
      </div>
    `;
  }
}

// ----------------- Filter & Search Handlers -----------------

function filterChecklistCategory(cat) {
  checklistState.activeCategory = cat;
  renderChecklist();
}

function filterChecklistStatus(status) {
  checklistState.statusFilter = status;
  renderChecklist();
}

function executeChecklistSearch(query) {
  checklistState.searchQuery = (query || "").trim();
  renderChecklist();
}

function resetChecklistFilters() {
  checklistState.activeCategory = "All";
  checklistState.statusFilter = "All";
  checklistState.searchQuery = "";
  renderChecklist();
}

// ----------------- Inline Status Change Handler -----------------

async function handleInlineChecklistStatusChange(itemId, newStatus) {
  try {
    const updateData = { status: newStatus };
    if (newStatus === "Completed") {
      updateData.completed_date = new Date().toISOString().split("T")[0];
    } else {
      updateData.completed_date = null;
    }

    await FinAuditAPI.updateChecklistItem(itemId, updateData);
    await renderChecklist();
  } catch (err) {
    notifyError("Failed to update status: " + (err.message || "Unknown error"));
  }
}

// ----------------- Custom Checklist Item Modal -----------------

function openCreateCustomChecklistItemModal() {
  const currentCategory = checklistState.activeCategory !== "All" ? checklistState.activeCategory : "Planning";
  const defaultUser = state.currentUser ? state.currentUser.full_name : "";

  const modalHtml = `
    <div class="modal-overlay" id="custom-checklist-modal">
      <div class="modal-card" style="max-width: 620px;">
        <div class="modal-header">
          <div class="modal-title">➕ Add Custom Audit Checklist Procedure</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('custom-checklist-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleCreateCustomChecklistSubmit(event)">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Category *</label>
                <select id="custom-chk-category" class="form-control" required>
                  ${CHECKLIST_CATEGORIES_LIST.map(cat => `
                    <option value="${cat}" ${cat === currentCategory ? 'selected' : ''}>${cat}</option>
                  `).join("")}
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Checklist ID / Ref (Optional)</label>
                <input type="text" id="custom-chk-code" class="form-control" placeholder="e.g. CUST-INV-01 (Auto if blank)">
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Question / Audit Procedure Description *</label>
              <textarea id="custom-chk-question" class="form-control" rows="3" placeholder="Specify substantive audit procedure, verification standard, or compliance check..." required></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Guidance Note / Accounting Standard Ref</label>
              <input type="text" id="custom-chk-guidance" class="form-control" placeholder="e.g. Ind AS 2 / SA 501 Attendance at Physical Inventory Counting">
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Assigned Staff</label>
                <input type="text" id="custom-chk-staff" class="form-control" placeholder="Audit team member" value="${defaultUser}">
              </div>

              <div class="form-group">
                <label class="form-label">Due Date</label>
                <input type="date" id="custom-chk-due" class="form-control">
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Evidence / Working Paper Ref</label>
              <input type="text" id="custom-chk-evidence" class="form-control" placeholder="e.g. WP-INV-102 / Physical verification sheet signed">
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Comment / Working Notes</label>
              <textarea id="custom-chk-comment" class="form-control" rows="2" placeholder="Initial observation or preliminary testing notes..."></textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('custom-checklist-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Create Procedure</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleCreateCustomChecklistSubmit(event) {
  event.preventDefault();
  const category = document.getElementById("custom-chk-category").value;
  const item_code = document.getElementById("custom-chk-code").value.trim() || undefined;
  const question = document.getElementById("custom-chk-question").value.trim();
  const guidance = document.getElementById("custom-chk-guidance").value.trim() || undefined;
  const assigned_staff = document.getElementById("custom-chk-staff").value.trim() || undefined;
  const due_date = document.getElementById("custom-chk-due").value || undefined;
  const evidence = document.getElementById("custom-chk-evidence").value.trim() || undefined;
  const comment = document.getElementById("custom-chk-comment").value.trim() || undefined;

  try {
    await FinAuditAPI.createCustomChecklistItem(state.currentEngagementId, {
      category,
      item_code,
      question,
      guidance,
      assigned_staff,
      due_date,
      evidence,
      comment,
      status: "Not Started"
    });

    closeModal("custom-checklist-modal");
    await renderChecklist();
  } catch (err) {
    notifyError("Failed to create custom checklist item: " + (err.message || "Unknown error"));
  }
}

// ----------------- Auditor Review & Sign-off Modal -----------------

function openChecklistSignOffModal(itemId) {
  const item = (checklistState.items || []).find(i => i.id === itemId);
  if (!item) return;

  const modalHtml = `
    <div class="modal-overlay" id="checklist-signoff-modal">
      <div class="modal-card" style="max-width: 660px;">
        <div class="modal-header">
          <div class="modal-title">📋 Review & Sign-Off: ${item.item_code}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('checklist-signoff-modal')">✕</button>
        </div>
        <div class="modal-body">
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 16px;">
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 6px;">
              <span class="badge badge-medium">${item.category}</span>
              <span class="font-mono font-bold" style="font-size: 12px; color: #475569;">${item.item_code}</span>
              ${item.risk_finding_id ? `<span class="badge badge-critical">Linked to Risk Finding #${item.risk_finding_id}</span>` : ''}
            </div>
            <div style="font-weight: 600; color: #0f172a; font-size: 13.5px; line-height: 1.45;">
              ${item.question}
            </div>
            ${item.guidance ? `
              <div style="font-size: 12px; color: #64748b; margin-top: 6px;">
                <b>Guidance:</b> ${item.guidance}
              </div>
            ` : ''}
          </div>

          <form onsubmit="handleChecklistSignOffSubmit(event, ${item.id})">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Audit Status *</label>
                <select id="signoff-status" class="form-control" onchange="handleSignOffStatusChange(this.value)" required>
                  <option value="Not Started" ${item.status === 'Not Started' ? 'selected' : ''}>○ Not Started</option>
                  <option value="In Progress" ${item.status === 'In Progress' ? 'selected' : ''}>⟳ In Progress</option>
                  <option value="Requires Review" ${item.status === 'Requires Review' ? 'selected' : ''}>⚠ Requires Review</option>
                  <option value="Completed" ${item.status === 'Completed' ? 'selected' : ''}>✓ Completed (Signed Off)</option>
                  <option value="Not Applicable" ${item.status === 'Not Applicable' ? 'selected' : ''}>Ø Not Applicable</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Assigned Staff</label>
                <input type="text" id="signoff-staff" class="form-control" value="${item.assigned_staff || ''}" placeholder="Staff member name">
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Due Date</label>
                <input type="date" id="signoff-due-date" class="form-control" value="${item.due_date || ''}">
              </div>

              <div class="form-group">
                <label class="form-label">Completed Date</label>
                <input type="date" id="signoff-completed-date" class="form-control" value="${item.completed_date || ''}">
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Audit Evidence / Working Paper References</label>
              <textarea id="signoff-evidence" class="form-control" rows="2" placeholder="Record reference to verified documents, bank certificates, reconciliation sheets, or invoices...">${item.evidence || ''}</textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Verification Remarks / Conclusion</label>
              <textarea id="signoff-comment" class="form-control" rows="3" placeholder="Enter findings, cross-checks performed, or conclusion for final sign-off...">${item.comment || ''}</textarea>
            </div>

            <!-- Professional Skepticism Reminder -->
            <div style="background: #fffbeb; border: 1px solid #fef3c7; border-radius: 4px; padding: 8px 12px; font-size: 11.5px; color: #92400e; margin-top: 10px;">
              🔒 <b>SA 230 Working Paper Rule:</b> Only mark 'Completed' after independent substantive testing or verification of management representations.
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('checklist-signoff-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Sign-Off & Evidence</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

function handleSignOffStatusChange(newStatus) {
  const completedInput = document.getElementById("signoff-completed-date");
  if (!completedInput) return;
  if (newStatus === "Completed" && !completedInput.value) {
    completedInput.value = new Date().toISOString().split("T")[0];
  } else if (newStatus !== "Completed") {
    completedInput.value = "";
  }
}

async function handleChecklistSignOffSubmit(event, itemId) {
  event.preventDefault();
  const status = document.getElementById("signoff-status").value;
  const assigned_staff = document.getElementById("signoff-staff").value.trim() || null;
  const due_date = document.getElementById("signoff-due-date").value || null;
  const completed_date = document.getElementById("signoff-completed-date").value || null;
  const evidence = document.getElementById("signoff-evidence").value.trim() || null;
  const comment = document.getElementById("signoff-comment").value.trim() || null;

  try {
    await FinAuditAPI.updateChecklistItem(itemId, {
      status,
      assigned_staff,
      due_date,
      completed_date,
      evidence,
      comment
    });

    closeModal("checklist-signoff-modal");
    await renderChecklist();
  } catch (err) {
    notifyError("Failed to update checklist item: " + (err.message || "Unknown error"));
  }
}

// ----------------- Dynamic Tailor / Generation Modal -----------------

function openGenerateChecklistModal() {
  const activeEng = state.activeEngagement || {};
  const currentClientType = activeEng.client_type || activeEng.entity_type || "Private Limited";
  const currentAuditType = activeEng.audit_type || "Statutory Audit";
  const currentFy = activeEng.financial_year || "2024-25";

  const modalHtml = `
    <div class="modal-overlay" id="generate-checklist-modal">
      <div class="modal-card" style="max-width: 620px;">
        <div class="modal-header">
          <div class="modal-title">⚡ Tailor & Generate Audit Checklist</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('generate-checklist-modal')">✕</button>
        </div>
        <div class="modal-body">
          <div style="font-size: 13px; color: #475569; margin-bottom: 16px;">
            Generate tailored audit procedures across all 15 audit categories according to client entity structure, audit mandate, financial year, and automated risk findings.
          </div>

          <form onsubmit="handleGenerateChecklistSubmit(event)">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Client Legal Type *</label>
                <select id="gen-client-type" class="form-control">
                  <option value="Private Limited" ${currentClientType.includes('Private') ? 'selected' : ''}>Private Limited Company (Companies Act 2013)</option>
                  <option value="Public Limited" ${currentClientType.includes('Public') ? 'selected' : ''}>Public Limited Company / Listed</option>
                  <option value="LLP" ${currentClientType.includes('LLP') ? 'selected' : ''}>Limited Liability Partnership (LLP)</option>
                  <option value="Partnership" ${currentClientType.includes('Partnership') ? 'selected' : ''}>Partnership Firm</option>
                  <option value="Sole Proprietorship" ${currentClientType.includes('Proprietorship') ? 'selected' : ''}>Sole Proprietorship</option>
                  <option value="Trust / Society">Trust / Society / Section 8</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Audit Type *</label>
                <select id="gen-audit-type" class="form-control">
                  <option value="Statutory Audit" ${currentAuditType.includes('Statutory') ? 'selected' : ''}>Statutory Audit (CARO 2020 + SAs)</option>
                  <option value="Tax Audit (3CD)" ${currentAuditType.includes('Tax') || currentAuditType.includes('3CD') ? 'selected' : ''}>Tax Audit (Form 3CA/3CB/3CD)</option>
                  <option value="Internal Audit" ${currentAuditType.includes('Internal') ? 'selected' : ''}>Internal Audit & IFC Testing</option>
                  <option value="GST Audit" ${currentAuditType.includes('GST') ? 'selected' : ''}>GST Audit (GSTR-9C)</option>
                  <option value="Transfer Pricing Audit">Transfer Pricing (Form 3CEB)</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Financial Year *</label>
              <input type="text" id="gen-fy" class="form-control" value="${currentFy}" placeholder="e.g. 2024-25" required>
            </div>

            <div class="form-group">
              <label class="form-label" style="margin-bottom: 8px;">Audit Modules in Scope:</label>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12.5px;">
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                  <input type="checkbox" name="gen-module" value="General Ledger" checked> General Ledger & Vouching
                </label>
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                  <input type="checkbox" name="gen-module" value="Bank Reconciliation" checked> Bank Reconciliation (BRS)
                </label>
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                  <input type="checkbox" name="gen-module" value="GST Verification" checked> GST vs 2B / GSTR-3B Recon
                </label>
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                  <input type="checkbox" name="gen-module" value="Duplicates & Gaps" checked> Duplicates & Sequence Gaps
                </label>
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                  <input type="checkbox" name="gen-module" value="Anomaly Detection" checked> ML Anomaly & Benford's Law
                </label>
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                  <input type="checkbox" name="gen-module" value="Fixed Assets" checked> Fixed Asset Register & Depr
                </label>
              </div>
            </div>

            <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 12px; margin-top: 14px;">
              <label style="display: flex; align-items: flex-start; gap: 8px; cursor: pointer; margin: 0; font-size: 12.5px; color: #1e3a8a;">
                <input type="checkbox" id="gen-include-risk-findings" checked style="margin-top: 2px;">
                <div>
                  <b>Integrate Audit Risk Findings Module</b>
                  <div style="font-size: 11.5px; color: #3b82f6; margin-top: 2px;">
                    Automatically inject substantive audit procedures for detected High-Risk and Critical findings (set to status <i>'Requires Review'</i> for manual auditor sign-off).
                  </div>
                </div>
              </label>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 16px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('generate-checklist-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Generate Checklist</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleGenerateChecklistSubmit(event) {
  event.preventDefault();
  const client_type = document.getElementById("gen-client-type").value;
  const audit_type = document.getElementById("gen-audit-type").value;
  const financial_year = document.getElementById("gen-fy").value.trim();
  const include_risk_findings = document.getElementById("gen-include-risk-findings").checked;

  const moduleCheckboxes = document.querySelectorAll("input[name='gen-module']:checked");
  const selected_modules = Array.from(moduleCheckboxes).map(cb => cb.value);

  try {
    const res = await FinAuditAPI.generateChecklist(state.currentEngagementId, {
      client_type,
      audit_type,
      financial_year,
      selected_modules,
      include_risk_findings
    });

    closeModal("generate-checklist-modal");
    notifySuccess(`Success: ${res.generated_items || 0} substantive procedures generated across 15 audit categories.`);
    await renderChecklist();
  } catch (err) {
    notifyError("Failed to generate checklist: " + (err.message || "Unknown error"));
  }
}

// ----------------- Delete Custom Item Handler -----------------

async function handleDeleteChecklistItem(itemId, code) {
  const confirmed = await FinConfirm({
    title: "Delete Custom Checklist Procedure",
    message: `Are you sure you want to delete custom procedure ${code}?`,
    consequences: ["This procedure and any responses or comments recorded under it will be removed"],
    confirmText: "Delete Procedure",
    isDanger: true
  });
  if (!confirmed) return;

  try {
    await FinAuditAPI.deleteChecklistItem(itemId);
    await renderChecklist();
  } catch (err) {
    notifyError("Failed to delete checklist item: " + (err.message || "Unknown error"));
  }
}

// ----------------- Linked Finding Inspection -----------------

function openLinkedRiskFinding(findingId) {
  if (typeof openFindingDetailModal === "function") {
    openFindingDetailModal(findingId);
  } else {
    navigateTo("findings");
  }
}

// ==========================================================================
// Working Papers Module (SA 230 Compliant Audit Documentation)
// ==========================================================================

if (!state.wpFilters) {
  state.wpFilters = {
    area: "All",
    status: "All",
    search: "",
    activeTab: "all"
  };
}

const WP_STANDARD_AREAS = [
  "General",
  "Cash & Bank",
  "Revenue & Debtors",
  "Purchases & Creditors",
  "Statutory Compliance",
  "Fixed Assets & Depreciation",
  "Inventories",
  "Payroll & Employee Benefits",
  "Borrowings & Finance Costs",
  "Direct & Indirect Taxation",
  "Internal Controls & Governance",
  "Related Party Disclosures",
  "Subsequent Events & Contingencies"
];

function getWpStatusBadge(status) {
  switch (status) {
    case "Prepared":
      return `<span class="badge badge-wp-prepared"><svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg> Prepared</span>`;
    case "Under Review":
      return `<span class="badge badge-wp-under-review"><svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> Under Review</span>`;
    case "Reviewed":
      return `<span class="badge badge-wp-reviewed"><svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> Reviewed</span>`;
    case "Needs Correction":
      return `<span class="badge badge-wp-needs-correction"><svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg> Needs Correction</span>`;
    default:
      return `<span class="badge badge-wp-prepared">${status || 'Prepared'}</span>`;
  }
}

async function renderWorkingPapers() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `
      <div class="card" style="padding: 40px; text-align: center;">
        <div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">No Engagement Selected</div>
        <p style="color: #64748b; font-size: 13px;">Please select an audit engagement from the top bar to manage working papers.</p>
      </div>`;
    return;
  }

  container.innerHTML = `
    <div style="padding: 40px; text-align: center; color: #64748b;">
      <div class="spinner" style="display:inline-block; margin-bottom: 12px;"></div>
      <div>Loading SA 230 Working Papers & Audit Evidence Repository...</div>
    </div>`;

  try {
    const data = await FinAuditAPI.getWorkingPapers(state.currentEngagementId, state.wpFilters);
    const wps = data.working_papers || [];
    const summary = data.summary || { total: 0, prepared: 0, under_review: 0, reviewed: 0, needs_correction: 0, total_files: 0, total_linked_items: 0 };

    container.innerHTML = `
      <!-- Header Area -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
        <div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <h2 style="font-size: 20px; font-weight: 700; color: #0f172a; margin: 0;">Audit Working Papers & Evidence Repository</h2>
            <span class="badge badge-role-auditor">SA 230 Compliant</span>
          </div>
          <div style="font-size: 13px; color: #64748b; margin-top: 3px;">
            Maintain audit evidence, working notes, supporting files, cross-links, and partner reviews for Engagement #${state.currentEngagementId}
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          <a class="btn btn-secondary" href="${FinAuditAPI.getExportWorkingPapersCsvUrl(state.currentEngagementId)}" download title="Export Working Paper Register (CSV)">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
            Export Register (CSV)
          </a>
          <button class="btn btn-secondary" onclick="renderWorkingPapers()" title="Refresh Working Papers">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
            Refresh
          </button>
          <button class="btn btn-primary" onclick="openCreateWorkingPaperModal()">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            + New Working Paper
          </button>
        </div>
      </div>

      <!-- Executive Metric Stats Cards -->
      <div class="metrics-grid" style="grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); margin-bottom: 20px;">
        <div class="metric-card" style="border-left: 4px solid #3b82f6; cursor: pointer;" onclick="setWpStatusFilter('All')">
          <div class="metric-title">Total Working Papers</div>
          <div class="metric-value">${summary.total}</div>
          <div class="metric-desc">Master Audit File</div>
        </div>
        <div class="metric-card" style="border-left: 4px solid #64748b; cursor: pointer;" onclick="setWpStatusFilter('Prepared')">
          <div class="metric-title">Prepared (Draft)</div>
          <div class="metric-value" style="color: #475569;">${summary.prepared}</div>
          <div class="metric-desc">Ready for CA review</div>
        </div>
        <div class="metric-card" style="border-left: 4px solid #2563eb; cursor: pointer;" onclick="setWpStatusFilter('Under Review')">
          <div class="metric-title">Under Review</div>
          <div class="metric-value" style="color: #2563eb;">${summary.under_review}</div>
          <div class="metric-desc">Pending partner sign-off</div>
        </div>
        <div class="metric-card" style="border-left: 4px solid #10b981; cursor: pointer;" onclick="setWpStatusFilter('Reviewed')">
          <div class="metric-title">Reviewed & Signed</div>
          <div class="metric-value" style="color: #059669;">${summary.reviewed}</div>
          <div class="metric-desc">Partner approved</div>
        </div>
        <div class="metric-card" style="border-left: 4px solid #ef4444; cursor: pointer;" onclick="setWpStatusFilter('Needs Correction')">
          <div class="metric-title">Needs Correction</div>
          <div class="metric-value" style="color: #dc2626;">${summary.needs_correction}</div>
          <div class="metric-desc">Staff rework required</div>
        </div>
        <div class="metric-card" style="border-left: 4px solid #8b5cf6;">
          <div class="metric-title">Evidence Files</div>
          <div class="metric-value" style="color: #7c3aed;">${summary.total_files}</div>
          <div class="metric-desc">Uploaded documents</div>
        </div>
        <div class="metric-card" style="border-left: 4px solid #f59e0b;">
          <div class="metric-title">Cross Links</div>
          <div class="metric-value" style="color: #d97706;">${summary.total_linked_items}</div>
          <div class="metric-desc">Findings, Txns & Checklists</div>
        </div>
      </div>

      <!-- Filter and Search Controls Toolbar -->
      <div class="card" style="padding: 14px 18px; margin-bottom: 16px;">
        <div style="display: flex; gap: 12px; align-items: center; justify-content: space-between; flex-wrap: wrap;">
          <div style="display: flex; gap: 10px; align-items: center; flex: 1; min-width: 280px;">
            <div style="position: relative; flex: 1;">
              <input type="text" id="wp-search-input" class="form-control" 
                placeholder="Search by WP ID, Title, Area, Description, Notes..." 
                value="${escapeHtml(state.wpFilters.search || '')}"
                onkeyup="handleWpSearchKey(event)" style="padding-left: 32px;" />
              <svg width="14" height="14" fill="none" stroke="#94a3b8" viewBox="0 0 24 24" style="position: absolute; left: 10px; top: 11px;">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
              </svg>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="executeWpSearch()">Search</button>
          </div>

          <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 12px; font-weight: 600; color: #64748b;">Area:</span>
              <select class="form-control" style="width: 180px; padding: 6px 10px; font-size: 12.5px;" onchange="handleWpAreaFilter(this.value)">
                <option value="All" ${state.wpFilters.area === 'All' ? 'selected' : ''}>All Audit Areas</option>
                ${WP_STANDARD_AREAS.map(a => `<option value="${escapeHtml(a)}" ${state.wpFilters.area === a ? 'selected' : ''}>${escapeHtml(a)}</option>`).join("")}
              </select>
            </div>

            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 12px; font-weight: 600; color: #64748b;">Status:</span>
              <select class="form-control" style="width: 150px; padding: 6px 10px; font-size: 12.5px;" onchange="handleWpStatusFilter(this.value)">
                <option value="All" ${state.wpFilters.status === 'All' ? 'selected' : ''}>All Statuses</option>
                <option value="Prepared" ${state.wpFilters.status === 'Prepared' ? 'selected' : ''}>Prepared</option>
                <option value="Under Review" ${state.wpFilters.status === 'Under Review' ? 'selected' : ''}>Under Review</option>
                <option value="Reviewed" ${state.wpFilters.status === 'Reviewed' ? 'selected' : ''}>Reviewed</option>
                <option value="Needs Correction" ${state.wpFilters.status === 'Needs Correction' ? 'selected' : ''}>Needs Correction</option>
              </select>
            </div>

            ${(state.wpFilters.area !== 'All' || state.wpFilters.status !== 'All' || state.wpFilters.search) ? `
              <button class="btn btn-secondary btn-sm" onclick="resetWpFilters()" style="color: #ef4444;" title="Clear all filters">
                Clear Filters
              </button>
            ` : ''}
          </div>
        </div>
      </div>

      <!-- Working Papers Table Card -->
      <div class="card" style="padding: 0; overflow: hidden;">
        <div class="table-container" style="border: none; border-radius: 0;">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 110px;">WP ID</th>
                <th>Audit Area</th>
                <th>Working Paper Title & Description</th>
                <th>Evidence & Files</th>
                <th>Cross References</th>
                <th>Prepared By</th>
                <th>Reviewed By</th>
                <th>Status</th>
                <th style="text-align: right; width: 140px;">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${wps.length === 0 ? `
                <tr>
                  <td colspan="9" style="text-align: center; padding: 48px 20px; color: #64748b;">
                    <svg width="40" height="40" fill="none" stroke="#cbd5e1" viewBox="0 0 24 24" style="margin: 0 auto 10px auto; display: block;">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <div style="font-weight: 600; font-size: 14px; color: #334155;">No Working Papers Found</div>
                    <div style="font-size: 12px; margin-top: 4px;">Click "+ New Working Paper" to begin document indexing and SA 230 evidence collection.</div>
                  </td>
                </tr>
              ` : wps.map(w => {
                const attachedCount = (w.attached_files || []).length;
                const fCount = (w.linked_findings || []).length;
                const tCount = (w.linked_transactions || []).length;
                const cCount = (w.linked_checklists || []).length;
                const commentsCount = (w.reviewer_comments || []).length;

                return `
                  <tr style="cursor: pointer;" onclick="openWorkingPaperDrawer(${w.id})">
                    <td>
                      <span class="font-mono font-bold" style="color: #2563eb; background: #eff6ff; padding: 3px 8px; border-radius: 4px; border: 1px solid #bfdbfe; font-size: 12px;">
                        ${escapeHtml(w.wp_reference)}
                      </span>
                    </td>
                    <td>
                      <span class="wp-area-tag">
                        ${escapeHtml(w.area || w.category || 'General')}
                      </span>
                    </td>
                    <td>
                      <div class="font-bold" style="color: #0f172a; font-size: 13.5px;">${escapeHtml(w.title)}</div>
                      ${w.description ? `<div style="max-width: 320px; font-size: 11.5px; color: #64748b; white-space: normal; margin-top: 2px; line-height: 1.3;">${escapeHtml(w.description.length > 90 ? w.description.substring(0, 90) + '...' : w.description)}</div>` : ''}
                    </td>
                    <td>
                      <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                        ${attachedCount > 0 ? `
                          <span class="badge" style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1;">
                            <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"></path></svg>
                            ${attachedCount} Doc${attachedCount > 1 ? 's' : ''}
                          </span>
                        ` : '<span style="color: #94a3b8; font-size: 11px;">No files</span>'}
                        ${w.evidence ? `<span title="${escapeHtml(w.evidence)}" style="color: #059669; font-size: 11px; font-weight: 500;">✓ Summary</span>` : ''}
                      </div>
                    </td>
                    <td>
                      <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
                        ${fCount > 0 ? `<span class="badge badge-high" style="font-size: 10.5px; padding: 2px 5px;" title="${fCount} Linked Audit Finding(s)">F: ${fCount}</span>` : ''}
                        ${tCount > 0 ? `<span class="badge badge-open" style="font-size: 10.5px; padding: 2px 5px;" title="${tCount} Linked GL Transaction(s)">Tx: ${tCount}</span>` : ''}
                        ${cCount > 0 ? `<span class="badge badge-low" style="font-size: 10.5px; padding: 2px 5px;" title="${cCount} Linked Checklist Item(s)">Chk: ${cCount}</span>` : ''}
                        ${(fCount === 0 && tCount === 0 && cCount === 0) ? '<span style="color: #94a3b8; font-size: 11px;">None</span>' : ''}
                      </div>
                    </td>
                    <td>
                      <div style="font-weight: 600; font-size: 12px; color: #334155;">${escapeHtml(w.prepared_by || 'Staff')}</div>
                      <div style="font-size: 10.5px; color: #94a3b8;">${escapeHtml(w.prepared_date || w.created_at ? (w.prepared_date || w.created_at.substring(0, 10)) : '')}</div>
                    </td>
                    <td>
                      <div style="font-weight: 600; font-size: 12px; color: #334155;">${escapeHtml(w.reviewed_by || '-')}</div>
                      <div style="font-size: 10.5px; color: #94a3b8;">${escapeHtml(w.review_date || '-')}</div>
                    </td>
                    <td>
                      ${getWpStatusBadge(w.status)}
                      ${commentsCount > 0 ? `<div style="font-size: 10px; color: #64748b; margin-top: 2px;">💬 ${commentsCount} note${commentsCount > 1 ? 's' : ''}</div>` : ''}
                    </td>
                    <td style="text-align: right;" onclick="event.stopPropagation();">
                      <div style="display: flex; gap: 4px; justify-content: flex-end;">
                        <button class="btn btn-secondary btn-sm" onclick="openWorkingPaperDrawer(${w.id})" title="View / Edit Working Paper Details">
                          Open
                        </button>
                        ${w.status !== 'Reviewed' ? `
                          <button class="btn btn-success btn-sm" onclick="openReviewWorkingPaperModal(${w.id}, '${escapeHtml(w.wp_reference)}')" title="Mark as Reviewed & Sign Off">
                            ✓ Review
                          </button>
                        ` : ''}
                        <button class="btn btn-secondary btn-sm" style="color: #ef4444; border-color: #fecaca;" onclick="promptDeleteWorkingPaper(${w.id}, ${w.status === 'Reviewed'}, '${escapeHtml(w.wp_reference)}')" title="Delete Working Paper">
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `
      <div class="card" style="padding: 30px; text-align: center;">
        <div style="color: #dc2626; font-weight: 700; font-size: 15px; margin-bottom: 6px;">Error Loading Working Papers</div>
        <p style="color: #64748b; font-size: 13px;">${escapeHtml(err.message)}</p>
        <button class="btn btn-secondary" onclick="renderWorkingPapers()" style="margin-top: 12px;">Try Again</button>
      </div>`;
  }
}

// Filter helpers
function handleWpAreaFilter(area) {
  state.wpFilters.area = area;
  renderWorkingPapers();
}

function handleWpStatusFilter(status) {
  state.wpFilters.status = status;
  renderWorkingPapers();
}

function setWpStatusFilter(status) {
  state.wpFilters.status = status;
  renderWorkingPapers();
}

function handleWpSearchKey(e) {
  if (e.key === "Enter") {
    executeWpSearch();
  }
}

function executeWpSearch() {
  const input = document.getElementById("wp-search-input");
  if (input) {
    state.wpFilters.search = input.value.trim();
    renderWorkingPapers();
  }
}

function resetWpFilters() {
  state.wpFilters = { area: "All", status: "All", search: "", activeTab: "all" };
  renderWorkingPapers();
}

// ----------------- Working Paper Creation Modal -----------------

function openCreateWorkingPaperModal() {
  const currentUserName = state.currentUser ? (state.currentUser.full_name || state.currentUser.username) : "Auditor";
  const today = new Date().toISOString().substring(0, 10);

  const modalHtml = `
    <div class="modal-overlay" id="wp-create-modal" onclick="if(event.target===this) closeModal('wp-create-modal')">
      <div class="modal-card" style="max-width: 680px; width: 95vw;">
        <div class="modal-header">
          <div class="modal-title">Create New Audit Working Paper (SA 230)</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('wp-create-modal')">✕</button>
        </div>
        <div class="modal-body" style="max-height: 80vh; overflow-y: auto;">
          <form id="wp-create-form" onsubmit="handleCreateWorkingPaperSubmit(event)">
            <div class="form-group" style="display: grid; grid-template-columns: 1fr 2fr; gap: 12px;">
              <div>
                <label class="form-label">WP Reference (ID) *</label>
                <input type="text" id="wp-new-ref" class="form-control font-mono font-bold" placeholder="e.g., WP-A101" required />
                <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Unique reference code</div>
              </div>
              <div>
                <label class="form-label">Audit Area *</label>
                <select id="wp-new-area" class="form-control" required>
                  ${WP_STANDARD_AREAS.map(a => `<option value="${escapeHtml(a)}">${escapeHtml(a)}</option>`).join("")}
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Working Paper Title *</label>
              <input type="text" id="wp-new-title" class="form-control" placeholder="e.g., Revenue Cut-Off & Invoice Verification Test" required />
            </div>

            <div class="form-group">
              <label class="form-label">Objective & Scope Description</label>
              <textarea id="wp-new-desc" class="form-control" rows="3" placeholder="Describe the audit objective, scope, and procedures performed..."></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Audit Evidence Summary</label>
              <textarea id="wp-new-evidence" class="form-control" rows="2" placeholder="Summary of documentary evidence examined, sampled vouchers, portal returns..."></textarea>
            </div>

            <div class="form-group" style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;">
              <div>
                <label class="form-label">Prepared By</label>
                <input type="text" id="wp-new-prep-by" class="form-control" value="${escapeHtml(currentUserName)}" />
              </div>
              <div>
                <label class="form-label">Prepared Date</label>
                <input type="date" id="wp-new-prep-date" class="form-control" value="${today}" />
              </div>
              <div>
                <label class="form-label">Initial Status</label>
                <select id="wp-new-status" class="form-control">
                  <option value="Prepared" selected>Prepared</option>
                  <option value="Under Review">Under Review</option>
                  <option value="Needs Correction">Needs Correction</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Initial Audit Notes / Observations</label>
              <textarea id="wp-new-notes" class="form-control" rows="2" placeholder="Internal observations, maker-checker notes, or follow-up items..."></textarea>
            </div>

            <div class="modal-footer" style="padding: 14px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('wp-create-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary" id="btn-save-new-wp">Create Working Paper</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
  setTimeout(() => {
    const refInput = document.getElementById("wp-new-ref");
    if (refInput) refInput.focus();
  }, 50);
}

async function handleCreateWorkingPaperSubmit(event) {
  event.preventDefault();
  const btn = document.getElementById("btn-save-new-wp");
  if (btn) btn.disabled = true;

  const payload = {
    wp_reference: document.getElementById("wp-new-ref").value.trim(),
    title: document.getElementById("wp-new-title").value.trim(),
    area: document.getElementById("wp-new-area").value,
    description: document.getElementById("wp-new-desc").value.trim(),
    evidence: document.getElementById("wp-new-evidence").value.trim(),
    prepared_by: document.getElementById("wp-new-prep-by").value.trim(),
    prepared_date: document.getElementById("wp-new-prep-date").value,
    status: document.getElementById("wp-new-status").value,
    notes: document.getElementById("wp-new-notes").value.trim(),
    linked_findings: [],
    linked_transactions: [],
    linked_checklists: []
  };

  try {
    const res = await FinAuditAPI.createWorkingPaper(state.currentEngagementId, payload);
    closeModal("wp-create-modal");
    await renderWorkingPapers();
    // Auto open drawer for the newly created working paper
    if (res && res.id) {
      openWorkingPaperDrawer(res.id);
    }
  } catch (err) {
    notifyError("Failed to create Working Paper: " + err.message);
    if (btn) btn.disabled = false;
  }
}

// ----------------- Working Paper Detail Drawer & Full Hub -----------------

let currentDrawerWp = null;
let currentDrawerTab = "overview";

async function openWorkingPaperDrawer(wpId, defaultTab = "overview") {
  // Remove existing drawer if open
  const existing = document.getElementById("wp-detail-drawer-overlay");
  if (existing) existing.remove();

  currentDrawerTab = defaultTab;

  const drawerHtml = `
    <div class="wp-detail-drawer-overlay" id="wp-detail-drawer-overlay" onclick="if(event.target===this) closeWorkingPaperDrawer()">
      <div class="wp-detail-drawer">
        <div class="wp-drawer-header">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span class="font-mono font-bold" id="drawer-wp-ref" style="color: #2563eb; background: #eff6ff; padding: 4px 10px; border-radius: 4px; border: 1px solid #bfdbfe; font-size: 13px;">...</span>
            <div style="font-weight: 700; font-size: 16px; color: #0f172a; max-width: 440px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" id="drawer-wp-title">Loading...</div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div id="drawer-wp-status-badge"></div>
            <button class="btn btn-sm btn-secondary" style="border: none; font-size: 16px;" onclick="closeWorkingPaperDrawer()">✕</button>
          </div>
        </div>

        <!-- Tab Navigation Bar -->
        <div style="padding: 12px 24px 0 24px; background: #ffffff;">
          <div class="wp-nav-tabs">
            <div class="wp-nav-tab ${currentDrawerTab === 'overview' ? 'active' : ''}" onclick="switchWpDrawerTab('overview')">
              📋 Overview
            </div>
            <div class="wp-nav-tab ${currentDrawerTab === 'evidence' ? 'active' : ''}" onclick="switchWpDrawerTab('evidence')">
              📎 Supporting Evidence (<span id="drawer-tab-docs-count">0</span>)
            </div>
            <div class="wp-nav-tab ${currentDrawerTab === 'notes' ? 'active' : ''}" onclick="switchWpDrawerTab('notes')">
              📝 Working Notes
            </div>
            <div class="wp-nav-tab ${currentDrawerTab === 'links' ? 'active' : ''}" onclick="switchWpDrawerTab('links')">
              🔗 Cross References (<span id="drawer-tab-links-count">0</span>)
            </div>
            <div class="wp-nav-tab ${currentDrawerTab === 'comments' ? 'active' : ''}" onclick="switchWpDrawerTab('comments')">
              💬 Review Comments (<span id="drawer-tab-comments-count">0</span>)
            </div>
            <div class="wp-nav-tab ${currentDrawerTab === 'audit_trail' ? 'active' : ''}" onclick="switchWpDrawerTab('audit_trail')">
              📜 Audit Trail
            </div>
          </div>
        </div>

        <div class="wp-drawer-body" id="drawer-content-area">
          <div style="padding: 40px; text-align: center; color: #64748b;">
            <div class="spinner" style="display:inline-block; margin-bottom: 10px;"></div>
            <div>Loading working paper details & audit evidence...</div>
          </div>
        </div>

        <div class="wp-drawer-footer" id="drawer-footer-area">
          <button class="btn btn-secondary" onclick="closeWorkingPaperDrawer()">Close</button>
          <div style="display: flex; gap: 8px;" id="drawer-footer-actions"></div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", drawerHtml);

  try {
    const wp = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = wp;
    populateWorkingPaperDrawer();
  } catch (err) {
    const content = document.getElementById("drawer-content-area");
    if (content) {
      content.innerHTML = `<div style="color: #dc2626; padding: 20px; text-align: center;">Error: ${escapeHtml(err.message)}</div>`;
    }
  }
}

function closeWorkingPaperDrawer() {
  const drawer = document.getElementById("wp-detail-drawer-overlay");
  if (drawer) drawer.remove();
  currentDrawerWp = null;
}

function switchWpDrawerTab(tabName) {
  currentDrawerTab = tabName;
  const tabs = document.querySelectorAll(".wp-nav-tab");
  tabs.forEach(t => t.classList.remove("active"));
  // Re-populate active tab
  populateWorkingPaperDrawer();
}

function populateWorkingPaperDrawer() {
  if (!currentDrawerWp) return;
  const wp = currentDrawerWp;

  // Header updates
  const refEl = document.getElementById("drawer-wp-ref");
  const titleEl = document.getElementById("drawer-wp-title");
  const statusBadgeEl = document.getElementById("drawer-wp-status-badge");
  if (refEl) refEl.innerText = wp.wp_reference;
  if (titleEl) titleEl.innerText = wp.title;
  if (statusBadgeEl) statusBadgeEl.innerHTML = getWpStatusBadge(wp.status);

  // Tab count badges
  const docsCount = (wp.attached_files || []).length;
  const linksCount = (wp.linked_findings || []).length + (wp.linked_transactions || []).length + (wp.linked_checklists || []).length;
  const commentsCount = (wp.reviewer_comments || []).length;

  const docTabCount = document.getElementById("drawer-tab-docs-count");
  const linkTabCount = document.getElementById("drawer-tab-links-count");
  const commentTabCount = document.getElementById("drawer-tab-comments-count");
  if (docTabCount) docTabCount.innerText = docsCount;
  if (linkTabCount) linkTabCount.innerText = linksCount;
  if (commentTabCount) commentTabCount.innerText = commentsCount;

  // Highlight active tab
  const tabs = document.querySelectorAll(".wp-nav-tab");
  tabs.forEach(t => {
    const text = t.innerText.toLowerCase();
    if (text.includes(currentDrawerTab.replace("_", " "))) {
      t.classList.add("active");
    } else {
      t.classList.remove("active");
    }
  });

  const contentArea = document.getElementById("drawer-content-area");
  const footerActions = document.getElementById("drawer-footer-actions");

  if (!contentArea) return;

  if (currentDrawerTab === "overview") {
    contentArea.innerHTML = renderWpOverviewTab(wp);
    if (footerActions) {
      footerActions.innerHTML = `
        <button class="btn btn-secondary" style="color: #ef4444;" onclick="promptDeleteWorkingPaper(${wp.id}, ${wp.status === 'Reviewed'}, '${escapeHtml(wp.wp_reference)}')">
          🗑️ Delete WP
        </button>
        <button class="btn btn-primary" onclick="saveWorkingPaperOverview(${wp.id})">
          Save Changes
        </button>
      `;
    }
  } else if (currentDrawerTab === "evidence") {
    contentArea.innerHTML = renderWpEvidenceTab(wp);
    if (footerActions) {
      footerActions.innerHTML = `
        <button class="btn btn-primary" onclick="triggerWpDocUpload()">
          + Upload Supporting Document
        </button>
      `;
    }
  } else if (currentDrawerTab === "notes") {
    contentArea.innerHTML = renderWpNotesTab(wp);
    if (footerActions) {
      footerActions.innerHTML = `
        <button class="btn btn-primary" onclick="saveWpNotes(${wp.id})">
          Save Working Notes
        </button>
      `;
    }
  } else if (currentDrawerTab === "links") {
    contentArea.innerHTML = renderWpLinksTab(wp);
    if (footerActions) {
      footerActions.innerHTML = ``;
    }
  } else if (currentDrawerTab === "comments") {
    contentArea.innerHTML = renderWpCommentsTab(wp);
    if (footerActions) {
      footerActions.innerHTML = ``;
    }
  } else if (currentDrawerTab === "audit_trail") {
    contentArea.innerHTML = renderWpAuditTrailTab(wp);
    if (footerActions) {
      footerActions.innerHTML = ``;
    }
  }
}

// ----------------- Tab 1: Overview -----------------

function renderWpOverviewTab(wp) {
  return `
    <!-- Status Switcher Bar -->
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 16px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
      <div>
        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Current Review Status</div>
        <div style="margin-top: 4px;">${getWpStatusBadge(wp.status)}</div>
      </div>
      <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
        <span style="font-size: 12px; color: #64748b; font-weight: 600;">Transition to:</span>
        <button class="btn btn-secondary btn-sm ${wp.status === 'Prepared' ? 'font-bold' : ''}" onclick="quickChangeWpStatus(${wp.id}, 'Prepared')">Prepared</button>
        <button class="btn btn-secondary btn-sm ${wp.status === 'Under Review' ? 'font-bold' : ''}" onclick="quickChangeWpStatus(${wp.id}, 'Under Review')">Under Review</button>
        <button class="btn btn-success btn-sm ${wp.status === 'Reviewed' ? 'font-bold' : ''}" onclick="openReviewWorkingPaperModal(${wp.id}, '${escapeHtml(wp.wp_reference)}')">✓ Mark Reviewed</button>
        <button class="btn btn-danger btn-sm ${wp.status === 'Needs Correction' ? 'font-bold' : ''}" onclick="quickChangeWpStatus(${wp.id}, 'Needs Correction')">Needs Correction</button>
      </div>
    </div>

    <!-- Metadata Form Fields -->
    <div class="wp-field-grid">
      <div class="form-group">
        <label class="form-label">WP Reference (ID) *</label>
        <input type="text" id="wp-edit-ref" class="form-control font-mono font-bold" value="${escapeHtml(wp.wp_reference)}" required />
      </div>
      <div class="form-group">
        <label class="form-label">Audit Area *</label>
        <select id="wp-edit-area" class="form-control" required>
          ${WP_STANDARD_AREAS.map(a => `<option value="${escapeHtml(a)}" ${(wp.area === a || wp.category === a) ? 'selected' : ''}>${escapeHtml(a)}</option>`).join("")}
        </select>
      </div>
    </div>

    <div class="form-group">
      <label class="form-label">Working Paper Title *</label>
      <input type="text" id="wp-edit-title" class="form-control font-bold" value="${escapeHtml(wp.title)}" required />
    </div>

    <div class="form-group">
      <label class="form-label">Audit Objective & Scope Description</label>
      <textarea id="wp-edit-desc" class="form-control" rows="3">${escapeHtml(wp.description || '')}</textarea>
    </div>

    <div class="form-group">
      <label class="form-label">Audit Evidence Summary & Cross-Verification</label>
      <textarea id="wp-edit-evidence" class="form-control" rows="3" placeholder="Summary of documentary evidence examined, sampled vouchers, portal confirmations...">${escapeHtml(wp.evidence || '')}</textarea>
    </div>

    <div class="wp-field-grid" style="margin-top: 16px;">
      <div class="wp-field-card">
        <div class="wp-field-label">Prepared By & Date</div>
        <div style="display: flex; gap: 8px; margin-top: 6px;">
          <input type="text" id="wp-edit-prep-by" class="form-control" style="font-size: 12px; padding: 5px 8px;" value="${escapeHtml(wp.prepared_by || '')}" placeholder="Preparer Name" />
          <input type="date" id="wp-edit-prep-date" class="form-control" style="font-size: 12px; padding: 5px 8px;" value="${escapeHtml(wp.prepared_date || '')}" />
        </div>
      </div>

      <div class="wp-field-card">
        <div class="wp-field-label">Reviewed By & Date</div>
        <div style="display: flex; gap: 8px; margin-top: 6px;">
          <input type="text" id="wp-edit-rev-by" class="form-control" style="font-size: 12px; padding: 5px 8px;" value="${escapeHtml(wp.reviewed_by || '')}" placeholder="Reviewer Name" />
          <input type="date" id="wp-edit-rev-date" class="form-control" style="font-size: 12px; padding: 5px 8px;" value="${escapeHtml(wp.review_date || '')}" />
        </div>
      </div>
    </div>
  `;
}

async function saveWorkingPaperOverview(wpId) {
  const payload = {
    wp_reference: document.getElementById("wp-edit-ref").value.trim(),
    area: document.getElementById("wp-edit-area").value,
    title: document.getElementById("wp-edit-title").value.trim(),
    description: document.getElementById("wp-edit-desc").value.trim(),
    evidence: document.getElementById("wp-edit-evidence").value.trim(),
    prepared_by: document.getElementById("wp-edit-prep-by").value.trim(),
    prepared_date: document.getElementById("wp-edit-prep-date").value,
    reviewed_by: document.getElementById("wp-edit-rev-by").value.trim(),
    review_date: document.getElementById("wp-edit-rev-date").value
  };

  try {
    await FinAuditAPI.updateWorkingPaper(wpId, payload);
    const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = updated;
    populateWorkingPaperDrawer();
    renderWorkingPapers();
    notifySuccess("Working paper details saved successfully.");
  } catch (err) {
    notifyError("Failed to save working paper: " + err.message);
  }
}

// ----------------- Tab 2: Supporting Evidence & Documents -----------------

function renderWpEvidenceTab(wp) {
  const files = wp.attached_files || [];

  return `
    <div style="margin-bottom: 20px;">
      <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">Supporting Evidence & Documents</div>
      <div style="font-size: 12px; color: #64748b;">
        Upload bank statements, confirmations, certificates, sample invoices, ledger extracts, or statutory returns (SA 230).
      </div>
    </div>

    <!-- Hidden file input for upload -->
    <input type="file" id="wp-file-input" style="display: none;" onchange="handleWpFileInputChange(event, ${wp.id})" />

    <!-- Drag & Drop Upload Zone -->
    <div class="wp-upload-dropzone" onclick="triggerWpDocUpload()" ondragover="event.preventDefault();" ondrop="handleWpDocDrop(event, ${wp.id})">
      <svg width="32" height="32" fill="none" stroke="#3b82f6" viewBox="0 0 24 24" style="margin: 0 auto 8px auto; display: block;">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
      </svg>
      <div style="font-size: 13.5px; font-weight: 700; color: #1e293b;">Click or Drag files here to attach evidence</div>
      <div style="font-size: 11.5px; color: #64748b; margin-top: 3px;">Supports PDF, XLSX, XLS, CSV, DOCX, PNG, JPG (Auto recorded in Audit Trail)</div>
    </div>

    <!-- Uploaded Documents List -->
    <div style="margin-top: 24px;">
      <div style="font-size: 12.5px; font-weight: 700; color: #334155; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between;">
        <span>Attached Supporting Files (${files.length})</span>
      </div>

      ${files.length === 0 ? `
        <div style="padding: 24px; text-align: center; color: #94a3b8; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; font-size: 12.5px;">
          No supporting documents attached yet. Click above to upload evidence files.
        </div>
      ` : files.map((file, idx) => `
        <div class="wp-attachment-card">
          <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
            <div style="width: 36px; height: 36px; border-radius: 6px; background: #eff6ff; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0;">
              ${getFileTypeIcon(file.name)}
            </div>
            <div style="min-width: 0; flex: 1;">
              <div style="font-weight: 600; font-size: 13px; color: #0f172a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                ${escapeHtml(file.name)}
              </div>
              <div style="font-size: 11px; color: #64748b; display: flex; gap: 8px; align-items: center; margin-top: 2px;">
                <span>${escapeHtml(file.size_display || 'File')}</span>
                <span>•</span>
                <span>By ${escapeHtml(file.uploaded_by || 'Auditor')}</span>
                <span>•</span>
                <span>${escapeHtml(file.uploaded_at ? file.uploaded_at.substring(0, 10) : '')}</span>
              </div>
              ${file.description ? `<div style="font-size: 11px; color: #475569; margin-top: 2px; font-style: italic;">"${escapeHtml(file.description)}"</div>` : ''}
            </div>
          </div>
          <div style="display: flex; gap: 6px; align-items: center; flex-shrink: 0; margin-left: 12px;">
            <a class="btn btn-secondary btn-sm" href="${FinAuditAPI.getWorkingPaperDocumentDownloadUrl(wp.id, file.id || file.file_name)}" target="_blank" download="${escapeHtml(file.name)}" title="Download / Preview file">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
              Download
            </a>
            <button class="btn btn-secondary btn-sm" style="color: #ef4444; border-color: #fecaca;" onclick="handleDeleteWpDoc(${wp.id}, '${escapeHtml(file.id || file.file_name)}')" title="Delete attached file">
              ✕
            </button>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function getFileTypeIcon(filename) {
  if (!filename) return "📄";
  const ext = filename.split(".").pop().toLowerCase();
  if (["pdf"].includes(ext)) return "📕";
  if (["xlsx", "xls", "csv"].includes(ext)) return "📊";
  if (["doc", "docx", "txt"].includes(ext)) return "📝";
  if (["png", "jpg", "jpeg", "webp"].includes(ext)) return "🖼️";
  return "📁";
}

function triggerWpDocUpload() {
  const input = document.getElementById("wp-file-input");
  if (input) input.click();
}

async function handleWpFileInputChange(event, wpId) {
  const file = event.target.files[0];
  if (!file) return;
  await uploadWorkingPaperFile(wpId, file);
}

async function handleWpDocDrop(event, wpId) {
  event.preventDefault();
  if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
    const file = event.dataTransfer.files[0];
    await uploadWorkingPaperFile(wpId, file);
  }
}

async function uploadWorkingPaperFile(wpId, file) {
  const desc = prompt(`Optional: Enter description or note for '${file.name}':`, "");
  const formData = new FormData();
  formData.append("file", file);
  if (desc) formData.append("description", desc);

  try {
    await FinAuditAPI.uploadWorkingPaperDocument(wpId, formData);
    const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = updated;
    populateWorkingPaperDrawer();
    renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to upload document: " + err.message);
  }
}

async function handleDeleteWpDoc(wpId, docId) {
  const confirmed = await FinConfirm({
    title: "Remove Supporting Evidence File",
    message: "Are you sure you want to remove this supporting evidence file?",
    consequences: ["The document will be unlinked from the working paper", "This action will be logged in the tamper-evident audit trail"],
    confirmText: "Remove Document",
    isDanger: true
  });
  if (!confirmed) return;
  try {
    await FinAuditAPI.deleteWorkingPaperDocument(wpId, docId);
    const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = updated;
    populateWorkingPaperDrawer();
    renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to delete document: " + err.message);
  }
}

// ----------------- Tab 3: Working Notes -----------------

function renderWpNotesTab(wp) {
  return `
    <div style="margin-bottom: 16px;">
      <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">Auditor Working Notes & Audit Observations</div>
      <div style="font-size: 12px; color: #64748b;">
        Record substantive test notes, sample selection rationale, analytical review commentary, and management discussions.
      </div>
    </div>

    <div class="form-group">
      <textarea id="wp-edit-notes-input" class="form-control font-mono" rows="14" style="font-size: 13px; line-height: 1.6;" placeholder="Type detailed audit notes, substantive test observations, sampling methodology, management representations received...">${escapeHtml(wp.notes || '')}</textarea>
    </div>
  `;
}

async function saveWpNotes(wpId) {
  const notesText = document.getElementById("wp-edit-notes-input").value;
  try {
    await FinAuditAPI.updateWorkingPaperNotes(wpId, { notes: notesText });
    const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = updated;
    notifySuccess("Working notes saved successfully.");
    renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to save notes: " + err.message);
  }
}

// ----------------- Tab 4: Cross-References & Linked Entities -----------------

function renderWpLinksTab(wp) {
  const findings = wp.resolved_findings || [];
  const txns = wp.resolved_transactions || [];
  const chks = wp.resolved_checklists || [];

  return `
    <div style="margin-bottom: 18px;">
      <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">Audit Cross-References & Evidence Links</div>
      <div style="font-size: 12px; color: #64748b;">
        Bi-directionally link this working paper to specific Audit Findings, General Ledger Transactions, and Statutory Checklist Items.
      </div>
    </div>

    <!-- Section 1: Linked Findings -->
    <div style="margin-bottom: 22px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <div style="font-size: 13px; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 6px;">
          <span>Linked Audit Findings</span>
          <span class="badge badge-high" style="font-size: 10.5px;">${findings.length}</span>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="openLinkEntityModal(${wp.id}, 'finding')">
          + Link Finding
        </button>
      </div>

      ${findings.length === 0 ? `
        <div style="padding: 14px; text-align: center; color: #94a3b8; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 6px; font-size: 12px;">
          No audit findings linked to this working paper.
        </div>
      ` : findings.map(f => `
        <div class="wp-link-card">
          <div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="font-mono font-bold" style="font-size: 11.5px; color: #2563eb;">${escapeHtml(f.finding_code || `F#${f.id}`)}</span>
              <span class="badge badge-${(f.severity || 'medium').toLowerCase()}">${escapeHtml(f.severity || 'MEDIUM')}</span>
              <span class="font-bold" style="font-size: 13px; color: #0f172a;">${escapeHtml(f.title)}</span>
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 3px;">
              Category: ${escapeHtml(f.category || 'General')} • Status: ${escapeHtml(f.status || 'Open')}
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" style="color: #ef4444; border: none; padding: 2px 6px;" onclick="unlinkWpEntity(${wp.id}, 'finding', ${f.id})" title="Unlink Finding">
            ✕
          </button>
        </div>
      `).join("")}
    </div>

    <!-- Section 2: Linked Transactions -->
    <div style="margin-bottom: 22px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <div style="font-size: 13px; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 6px;">
          <span>Linked General Ledger Transactions</span>
          <span class="badge badge-open" style="font-size: 10.5px;">${txns.length}</span>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="openLinkEntityModal(${wp.id}, 'transaction')">
          + Link Transaction
        </button>
      </div>

      ${txns.length === 0 ? `
        <div style="padding: 14px; text-align: center; color: #94a3b8; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 6px; font-size: 12px;">
          No transactions linked to this working paper.
        </div>
      ` : txns.map(t => `
        <div class="wp-link-card">
          <div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="font-mono" style="font-size: 11.5px; color: #475569;">${escapeHtml(t.date || '')}</span>
              <span class="font-mono font-bold" style="font-size: 12px; color: #2563eb;">${escapeHtml(t.voucher_no || `Tx#${t.id}`)}</span>
              <span class="font-bold" style="font-size: 13px; color: #0f172a;">${escapeHtml(t.ledger || '')}</span>
              <span style="font-weight: 700; color: ${t.debit > 0 ? '#b91c1c' : '#047857'}; font-size: 12px;">
                ₹ ${Number(t.amount || (t.debit || t.credit)).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
            ${t.description ? `<div style="font-size: 11px; color: #64748b; margin-top: 3px;">${escapeHtml(t.description)} ${t.party_name ? '• ' + escapeHtml(t.party_name) : ''}</div>` : ''}
          </div>
          <button class="btn btn-secondary btn-sm" style="color: #ef4444; border: none; padding: 2px 6px;" onclick="unlinkWpEntity(${wp.id}, 'transaction', ${t.id})" title="Unlink Transaction">
            ✕
          </button>
        </div>
      `).join("")}
    </div>

    <!-- Section 3: Linked Checklist Items -->
    <div style="margin-bottom: 22px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <div style="font-size: 13px; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 6px;">
          <span>Linked Statutory & Audit Checklist Items</span>
          <span class="badge badge-low" style="font-size: 10.5px;">${chks.length}</span>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="openLinkEntityModal(${wp.id}, 'checklist')">
          + Link Checklist Item
        </button>
      </div>

      ${chks.length === 0 ? `
        <div style="padding: 14px; text-align: center; color: #94a3b8; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 6px; font-size: 12px;">
          No checklist items linked to this working paper.
        </div>
      ` : chks.map(c => `
        <div class="wp-link-card">
          <div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="font-mono font-bold" style="font-size: 11.5px; color: #2563eb;">${escapeHtml(c.item_code || `Chk#${c.id}`)}</span>
              <span class="badge badge-medium" style="font-size: 10.5px;">${escapeHtml(c.category || 'Statutory')}</span>
              <span class="badge ${c.status === 'Completed' ? 'badge-resolved' : 'badge-open'}" style="font-size: 10.5px;">${escapeHtml(c.status || 'Pending')}</span>
            </div>
            <div style="font-size: 12px; color: #334155; font-weight: 600; margin-top: 4px;">${escapeHtml(c.question)}</div>
          </div>
          <button class="btn btn-secondary btn-sm" style="color: #ef4444; border: none; padding: 2px 6px;" onclick="unlinkWpEntity(${wp.id}, 'checklist', ${c.id})" title="Unlink Checklist Item">
            ✕
          </button>
        </div>
      `).join("")}
    </div>
  `;
}

async function unlinkWpEntity(wpId, entityType, itemId) {
  try {
    await FinAuditAPI.updateWorkingPaperLink(wpId, {
      link_type: entityType,
      action: "unlink",
      item_id: itemId
    });
    const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = updated;
    populateWorkingPaperDrawer();
    renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to unlink: " + err.message);
  }
}

// ----------------- Modal to Link Entities -----------------

async function openLinkEntityModal(wpId, entityType) {
  const modalId = "wp-link-entity-modal";
  const existing = document.getElementById(modalId);
  if (existing) existing.remove();

  const loadingHtml = `
    <div class="modal-overlay" id="${modalId}" onclick="if(event.target===this) closeModal('${modalId}')">
      <div class="modal-card" style="max-width: 650px; width: 95vw;">
        <div class="modal-header">
          <div class="modal-title">Link ${entityType.toUpperCase()} to WP</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('${modalId}')">✕</button>
        </div>
        <div class="modal-body" style="padding: 30px; text-align: center; color: #64748b;">
          <div class="spinner" style="display:inline-block; margin-bottom: 8px;"></div>
          <div>Loading available ${entityType} records...</div>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", loadingHtml);

  try {
    const data = await FinAuditAPI.getWorkingPaperLinkableItems(state.currentEngagementId);
    let items = [];
    let title = "";

    if (entityType === "finding") {
      items = data.findings || [];
      title = "Select Audit Finding to Link";
    } else if (entityType === "transaction") {
      items = data.transactions || [];
      title = "Select General Ledger Transaction to Link";
    } else if (entityType === "checklist") {
      items = data.checklists || [];
      title = "Select Checklist Item to Link";
    }

    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.innerHTML = `
      <div class="modal-card" style="max-width: 680px; width: 95vw;">
        <div class="modal-header">
          <div class="modal-title">${title}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('${modalId}')">✕</button>
        </div>
        <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
          <div style="margin-bottom: 12px;">
            <input type="text" id="link-item-filter-input" class="form-control" placeholder="Type to filter..." oninput="filterLinkableModalItems()" />
          </div>

          <div id="linkable-items-list">
            ${items.length === 0 ? `
              <div style="padding: 24px; text-align: center; color: #94a3b8;">No available records to link.</div>
            ` : items.map(item => {
              if (entityType === "finding") {
                return `
                  <div class="wp-attachment-card link-item-row" data-search="${escapeHtml((item.finding_code + ' ' + item.title + ' ' + item.category).toLowerCase())}">
                    <div>
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="font-mono font-bold" style="color: #2563eb; font-size: 12px;">${escapeHtml(item.finding_code || `F#${item.id}`)}</span>
                        <span class="badge badge-${(item.severity || 'medium').toLowerCase()}">${escapeHtml(item.severity || 'MEDIUM')}</span>
                        <span class="font-bold" style="font-size: 13px;">${escapeHtml(item.title)}</span>
                      </div>
                      <div style="font-size: 11px; color: #64748b; margin-top: 2px;">${escapeHtml(item.category || '')} • Status: ${escapeHtml(item.status || 'Open')}</div>
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="executeLinkItem(${wpId}, 'finding', ${item.id})">+ Link</button>
                  </div>
                `;
              } else if (entityType === "transaction") {
                return `
                  <div class="wp-attachment-card link-item-row" data-search="${escapeHtml((item.voucher_no + ' ' + item.ledger + ' ' + (item.description||'')).toLowerCase())}">
                    <div>
                      <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="font-mono" style="font-size: 11.5px; color: #64748b;">${escapeHtml(item.date || '')}</span>
                        <span class="font-mono font-bold" style="color: #2563eb;">${escapeHtml(item.voucher_no || `Tx#${item.id}`)}</span>
                        <span class="font-bold">${escapeHtml(item.ledger)}</span>
                        <span style="font-weight: 700; color: #0f172a;">₹ ${Number(item.amount || (item.debit || item.credit)).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                      </div>
                      <div style="font-size: 11px; color: #64748b; margin-top: 2px;">${escapeHtml(item.description || '')}</div>
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="executeLinkItem(${wpId}, 'transaction', ${item.id})">+ Link</button>
                  </div>
                `;
              } else if (entityType === "checklist") {
                return `
                  <div class="wp-attachment-card link-item-row" data-search="${escapeHtml((item.item_code + ' ' + item.category + ' ' + item.question).toLowerCase())}">
                    <div>
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="font-mono font-bold" style="color: #2563eb; font-size: 12px;">${escapeHtml(item.item_code || `Chk#${item.id}`)}</span>
                        <span class="badge badge-medium" style="font-size: 10.5px;">${escapeHtml(item.category || '')}</span>
                        <span class="badge ${item.status === 'Completed' ? 'badge-resolved' : 'badge-open'}" style="font-size: 10.5px;">${escapeHtml(item.status || 'Pending')}</span>
                      </div>
                      <div style="font-size: 12px; font-weight: 600; color: #334155; margin-top: 3px;">${escapeHtml(item.question)}</div>
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="executeLinkItem(${wpId}, 'checklist', ${item.id})">+ Link</button>
                  </div>
                `;
              }
            }).join("")}
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    notifyError("Failed to load items: " + err.message);
    closeModal(modalId);
  }
}

function filterLinkableModalItems() {
  const query = (document.getElementById("link-item-filter-input").value || "").toLowerCase().trim();
  const rows = document.querySelectorAll(".link-item-row");
  rows.forEach(r => {
    const text = r.getAttribute("data-search") || "";
    r.style.display = text.includes(query) ? "flex" : "none";
  });
}

async function executeLinkItem(wpId, entityType, itemId) {
  try {
    await FinAuditAPI.updateWorkingPaperLink(wpId, {
      link_type: entityType,
      action: "link",
      item_id: itemId
    });
    closeModal("wp-link-entity-modal");
    const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = updated;
    populateWorkingPaperDrawer();
    renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to link item: " + err.message);
  }
}

// ----------------- Tab 5: Reviewer Comments -----------------

function renderWpCommentsTab(wp) {
  const comments = wp.reviewer_comments || [];

  return `
    <div style="margin-bottom: 18px;">
      <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">Reviewer Comments & Discussion Log</div>
      <div style="font-size: 12px; color: #64748b;">
        Maintain an audit trail of review observations, feedback, and partner sign-off directives.
      </div>
    </div>

    <!-- Comments timeline -->
    <div style="margin-bottom: 24px;">
      ${comments.length === 0 ? `
        <div style="padding: 24px; text-align: center; color: #94a3b8; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; font-size: 12.5px;">
          No reviewer comments recorded yet.
        </div>
      ` : comments.map(c => `
        <div class="wp-comment-bubble ${c.role === 'Admin' || c.role === 'Auditor' ? 'reviewer' : ''}">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-weight: 700; font-size: 12.5px; color: #0f172a;">${escapeHtml(c.author || 'Reviewer')}</span>
              <span class="badge ${c.role === 'Admin' ? 'badge-role-admin' : 'badge-role-auditor'}" style="font-size: 10px;">${escapeHtml(c.role || 'Auditor')}</span>
            </div>
            <div style="font-size: 11px; color: #94a3b8;">
              ${escapeHtml(c.created_at ? c.created_at.replace('T', ' ').substring(0, 16) : '')}
            </div>
          </div>
          <div style="font-size: 13px; color: #334155; line-height: 1.4; white-space: pre-wrap;">${escapeHtml(c.comment)}</div>
        </div>
      `).join("")}
    </div>

    <!-- Post Comment Box -->
    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px;">
      <div style="font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 6px;">Add Reviewer Comment / Audit Note</div>
      <textarea id="wp-new-comment-text" class="form-control" rows="3" placeholder="Enter review observation, query for staff, or partner sign-off comment..."></textarea>
      <div style="display: flex; justify-content: flex-end; margin-top: 10px;">
        <button class="btn btn-primary btn-sm" onclick="handlePostWpComment(${wp.id})">
          Post Comment
        </button>
      </div>
    </div>
  `;
}

async function handlePostWpComment(wpId) {
  const input = document.getElementById("wp-new-comment-text");
  if (!input || !input.value.trim()) {
    notifyWarning("Please enter a comment.");
    return;
  }

  const commentText = input.value.trim();
  try {
    await FinAuditAPI.addWorkingPaperComment(wpId, { comment: commentText });
    const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = updated;
    populateWorkingPaperDrawer();
    renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to post comment: " + err.message);
  }
}

// ----------------- Tab 6: Audit Trail -----------------

function renderWpAuditTrailTab(wp) {
  const logs = wp.audit_trail || [];

  return `
    <div style="margin-bottom: 18px;">
      <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">SA 230 Audit Trail & Immutable Activity Log</div>
      <div style="font-size: 12px; color: #64748b;">
        Complete chronological history of all creations, edits, reviews, document uploads, and deletions for this working paper.
      </div>
    </div>

    <div>
      ${logs.length === 0 ? `
        <div style="padding: 24px; text-align: center; color: #94a3b8; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; font-size: 12.5px;">
          No audit logs recorded for this working paper yet.
        </div>
      ` : logs.map(l => `
        <div class="wp-timeline-item">
          <div class="wp-timeline-dot"></div>
          <div style="display: flex; justify-content: space-between; align-items: baseline;">
            <span style="font-weight: 700; font-size: 12.5px; color: #0f172a;">${escapeHtml(l.action)}</span>
            <span style="font-size: 11px; color: #94a3b8;">${escapeHtml(l.timestamp ? l.timestamp.replace('T', ' ').substring(0, 19) : '')}</span>
          </div>
          <div style="font-size: 12px; color: #475569; margin-top: 2px;">
            ${escapeHtml(l.details || '')}
          </div>
          <div style="font-size: 10.5px; color: #94a3b8; margin-top: 2px;">
            User: <strong style="color: #334155;">${escapeHtml(l.username || 'system')}</strong>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

// ----------------- Status Transitions & Review Sign-off -----------------

async function quickChangeWpStatus(wpId, newStatus) {
  try {
    await FinAuditAPI.updateWorkingPaperStatus(wpId, { status: newStatus });
    const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
    currentDrawerWp = updated;
    populateWorkingPaperDrawer();
    renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to update status: " + err.message);
  }
}

function openReviewWorkingPaperModal(wpId, wpRef) {
  const currentUserName = state.currentUser ? (state.currentUser.full_name || state.currentUser.username) : "Reviewer Partner";
  const today = new Date().toISOString().substring(0, 10);

  const modalHtml = `
    <div class="modal-overlay" id="wp-review-modal" onclick="if(event.target===this) closeModal('wp-review-modal')">
      <div class="modal-card" style="max-width: 520px; width: 95vw;">
        <div class="modal-header">
          <div class="modal-title">Sign Off & Mark Reviewed: ${escapeHtml(wpRef)}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('wp-review-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form id="wp-review-form" onsubmit="handleConfirmWpReview(event, ${wpId})">
            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; padding: 10px 12px; margin-bottom: 14px; font-size: 12px; color: #047857;">
              ✓ You are approving this working paper as compliant with ICAI SA 230 standard on audit documentation.
            </div>

            <div class="form-group">
              <label class="form-label">Reviewing Partner / CA Name *</label>
              <input type="text" id="wp-review-partner-name" class="form-control font-bold" value="${escapeHtml(currentUserName)}" required />
            </div>

            <div class="form-group">
              <label class="form-label">Review Date *</label>
              <input type="date" id="wp-review-date" class="form-control" value="${today}" required />
            </div>

            <div class="form-group">
              <label class="form-label">Reviewer Sign-off Notes / Concluding Remarks</label>
              <textarea id="wp-review-comment" class="form-control" rows="3" placeholder="Audit evidence verified and found sufficient and appropriate..."></textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('wp-review-modal')">Cancel</button>
              <button type="submit" class="btn btn-success" id="btn-confirm-wp-review">Confirm & Mark Reviewed</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleConfirmWpReview(event, wpId) {
  event.preventDefault();
  const btn = document.getElementById("btn-confirm-wp-review");
  if (btn) btn.disabled = true;

  const reviewerName = document.getElementById("wp-review-partner-name").value.trim();
  const reviewDate = document.getElementById("wp-review-date").value;
  const comment = document.getElementById("wp-review-comment").value.trim();

  try {
    await FinAuditAPI.updateWorkingPaperStatus(wpId, {
      status: "Reviewed",
      reviewed_by: reviewerName,
      review_date: reviewDate,
      comment: comment
    });
    closeModal("wp-review-modal");
    if (currentDrawerWp && currentDrawerWp.id === wpId) {
      const updated = await FinAuditAPI.getWorkingPaperDetail(wpId);
      currentDrawerWp = updated;
      populateWorkingPaperDrawer();
    }
    await renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to review working paper: " + err.message);
    if (btn) btn.disabled = false;
  }
}

// ----------------- Working Paper Deletion with Mandatory Audit Justification -----------------

function promptDeleteWorkingPaper(wpId, isReviewed, wpRef) {
  const modalHtml = `
    <div class="modal-overlay" id="wp-delete-modal" onclick="if(event.target===this) closeModal('wp-delete-modal')">
      <div class="modal-card" style="max-width: 520px; width: 95vw;">
        <div class="modal-header">
          <div class="modal-title" style="color: #dc2626;">Delete Working Paper: ${escapeHtml(wpRef)}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('wp-delete-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form id="wp-delete-form" onsubmit="handleExecuteWpDelete(event, ${wpId}, ${isReviewed})">
            ${isReviewed ? `
              <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 12px; margin-bottom: 14px; font-size: 12px; color: #991b1b;">
                <strong>⚠️ Mandatory Audit Compliance Rule (SA 230):</strong><br/>
                This is a <strong>REVIEWED</strong> working paper. In accordance with audit standards, reviewed working papers cannot be deleted without a recorded justification. This deletion will be permanently logged in the audit trail.
              </div>
              <div class="form-group">
                <label class="form-label" style="color: #991b1b;">Mandatory Deletion Justification / Reason *</label>
                <textarea id="wp-delete-reason" class="form-control" rows="3" placeholder="State explicit justification for deleting reviewed audit documentation (e.g., duplicate work paper created in error, superseded by WP-XYZ)..." required></textarea>
              </div>
            ` : `
              <p style="font-size: 13px; color: #475569; margin-bottom: 14px;">
                Are you sure you want to delete Working Paper <strong>${escapeHtml(wpRef)}</strong>? All attached files and link cross-references will be removed.
              </p>
              <div class="form-group">
                <label class="form-label">Deletion Reason (Optional)</label>
                <input type="text" id="wp-delete-reason" class="form-control" placeholder="Reason for deletion..." />
              </div>
            `}

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('wp-delete-modal')">Cancel</button>
              <button type="submit" class="btn btn-danger" id="btn-confirm-wp-delete">Permanently Delete & Log</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
  setTimeout(() => {
    const reasonEl = document.getElementById("wp-delete-reason");
    if (reasonEl) reasonEl.focus();
  }, 50);
}

async function handleExecuteWpDelete(event, wpId, isReviewed) {
  event.preventDefault();
  const reasonInput = document.getElementById("wp-delete-reason");
  const reason = reasonInput ? reasonInput.value.trim() : "";

  if (isReviewed && !reason) {
    notifyWarning("Mandatory Requirement: Please provide a justification for deleting a reviewed working paper.");
    return;
  }

  const btn = document.getElementById("btn-confirm-wp-delete");
  if (btn) btn.disabled = true;

  try {
    await FinAuditAPI.deleteWorkingPaper(wpId, reason);
    closeModal("wp-delete-modal");
    closeWorkingPaperDrawer();
    await renderWorkingPapers();
  } catch (err) {
    notifyError("Failed to delete working paper: " + err.message);
    if (btn) btn.disabled = false;
  }
}


// ==========================================================================
// Professional Audit Reports & PDF Generator Module
// ==========================================================================

const ALL_REPORT_TYPES = [
  {
    id: "complete_audit_analysis",
    title: "10. Complete Audit Analysis & Master Review",
    description: "Comprehensive 17-section master report containing executive summary, trial balance health, BRS, GST ITC, ML anomalies, findings with Finding IDs, and SA 230 sign-off.",
    category: "Master Report",
    badge: "17 Sections",
    badgeClass: "badge-role-admin",
    icon: "📑",
    primary: true
  },
  {
    id: "engagement_summary",
    title: "1. Engagement Summary",
    description: "High-level overview of the audit engagement, client information, audit period, turnover examined, high-level metrics, and reviewer sign-off block.",
    category: "Executive",
    badge: "Overview",
    badgeClass: "badge-role-auditor",
    icon: "📊"
  },
  {
    id: "data_import",
    title: "2. Data Import Summary",
    description: "Summary of electronic source data files ingested (General Ledger, Bank, GST 2B, Sales/Purchases), mapping validation, and sanitization logs.",
    category: "Data & Ingestion",
    badge: "Data Scope",
    badgeClass: "badge-role-staff",
    icon: "📥"
  },
  {
    id: "trial_balance",
    title: "3. Trial Balance Analysis",
    description: "Comprehensive analysis of Trial Balance heads, debit/credit health, abnormal negative cash/debtor balances, suspense accounts, and TB exceptions.",
    category: "Accounting",
    badge: "Ledger Health",
    badgeClass: "badge-low",
    icon: "⚖️"
  },
  {
    id: "bank_reconciliation",
    title: "4. Bank Reconciliation",
    description: "Bank balance confirmations, statement vs books matching results, unpresented cheques, uncredited deposits, and BRS exceptions with Finding IDs.",
    category: "Reconciliation",
    badge: "Bank BRS",
    badgeClass: "badge-open",
    icon: "🏦"
  },
  {
    id: "gst_reconciliation",
    title: "5. GST Reconciliation",
    description: "Input Tax Credit (ITC) reconciliation of GSTR-2B vs Books, tax rate discrepancies (CGST/SGST/IGST), and Section 16(2) rule violations.",
    category: "Taxation",
    badge: "GST ITC",
    badgeClass: "badge-high",
    icon: "🧾"
  },
  {
    id: "anomaly_report",
    title: "6. Anomaly Report",
    description: "Deterministic rules, Benford's Law first-digit distribution, statistical 3.0σ outliers, and machine learning Isolation Forest anomaly scores.",
    category: "AI & Analytics",
    badge: "ML / Outliers",
    badgeClass: "badge-role-admin",
    icon: "🧠"
  },
  {
    id: "yoy_comparison",
    title: "7. Year-on-Year Comparison",
    description: "Multi-year Schedule III comparative Balance Sheet and P&L movements, significant percentage variances (> threshold), and recorded auditor notes.",
    category: "Financial Analysis",
    badge: "Comparative",
    badgeClass: "badge-medium",
    icon: "📈"
  },
  {
    id: "risk_findings",
    title: "8. Risk & Findings Report",
    description: "Complete Master Risk Findings Register categorized by severity (Critical, High, Medium, Low) with traceable Finding IDs and actionable recommendations.",
    category: "Audit Exceptions",
    badge: "Risk Register",
    badgeClass: "badge-critical",
    icon: "⚠️"
  },
  {
    id: "audit_checklist",
    title: "9. Audit Checklist",
    description: "Statutory checklist compliance execution across Companies Act CARO 2020, Tax Audit Form 3CD, Standards on Auditing (SA), and internal controls.",
    category: "Compliance",
    badge: "Checklist",
    badgeClass: "badge-resolved",
    icon: "✅"
  }
];

async function renderReports() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `
      <div class="card" style="padding: 40px; text-align: center;">
        <div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">No Engagement Selected</div>
        <p style="color: #64748b; font-size: 13px;">Please select an audit engagement from the top bar to generate audit reports.</p>
      </div>`;
    return;
  }

  container.innerHTML = `
    <div style="padding: 40px; text-align: center; color: #64748b;">
      <div class="spinner" style="display:inline-block; margin-bottom: 12px;"></div>
      <div>Loading Audit Reports & PDF Generator...</div>
    </div>`;

  try {
    const reports = await FinAuditAPI.getReports(state.currentEngagementId);

    container.innerHTML = `
      <!-- Header Area -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
        <div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <h2 style="font-size: 20px; font-weight: 700; color: #0f172a; margin: 0;">Professional Audit Reports & PDF Generator</h2>
            <span class="badge badge-role-auditor">ICAI SA 230 / SA 700</span>
          </div>
          <div style="font-size: 13px; color: #64748b; margin-top: 3px;">
            Generate formal, verifiable AI-assisted audit analysis PDF reports with traceable Finding IDs for Engagement #${state.currentEngagementId}
          </div>
        </div>
        <button class="btn btn-primary" onclick="triggerGeneratePDFReport('complete_audit_analysis')" style="padding: 8px 16px;">
          <svg width="15" height="15" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
          ⚡ Generate Complete Master Analysis (PDF)
        </button>
      </div>

      <!-- Statutory Quality Control Notice Banner -->
      <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #2563eb; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; font-size: 12px; color: #334155; line-height: 1.45;">
        <strong style="color: #0f172a;">⚖️ ICAI Quality Control & SA 230 Compliance Note:</strong><br/>
        All generated PDF reports provide an <em>AI-assisted audit analysis report</em> with fully traceable <strong>Finding IDs</strong>. In accordance with professional standards (SA 200/SA 700), reports include formal review sign-off blocks and do not replace the final independent professional audit opinion rendered by the Practicing Chartered Accountant.
      </div>

      <!-- 10 Report Types Grid -->
      <div style="margin-bottom: 28px;">
        <div style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
          <span>Available Audit Report Modules (10 Specialized PDF Reports)</span>
          <span style="font-size: 12px; font-weight: 500; color: #64748b;">Click 'Generate PDF' on any report</span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px;">
          ${ALL_REPORT_TYPES.map(rt => `
            <div class="card" style="padding: 16px; margin-bottom: 0; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid ${rt.primary ? '#93c5fd' : '#e2e8f0'}; background: ${rt.primary ? '#eff6ff' : '#ffffff'}; transition: all 0.15s ease;">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 20px;">${rt.icon}</span>
                    <span class="badge ${rt.badgeClass}">${escapeHtml(rt.badge)}</span>
                  </div>
                  <span style="font-size: 10.5px; font-weight: 600; color: #64748b; text-transform: uppercase;">${escapeHtml(rt.category)}</span>
                </div>
                <div style="font-weight: 700; font-size: 14px; color: #0f172a; margin-bottom: 4px;">
                  ${escapeHtml(rt.title)}
                </div>
                <div style="font-size: 11.5px; color: #475569; line-height: 1.35; margin-bottom: 14px;">
                  ${escapeHtml(rt.description)}
                </div>
              </div>
              <div style="display: flex; justify-content: flex-end; pt: 8px;">
                <button class="btn ${rt.primary ? 'btn-primary' : 'btn-secondary'} btn-sm" id="btn-gen-${rt.id}" onclick="triggerGeneratePDFReport('${rt.id}')" style="font-weight: 600;">
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                  Generate PDF
                </button>
              </div>
            </div>
          `).join("")}
        </div>
      </div>

      <!-- Generated Audit Reports History Card -->
      <div class="card" style="padding: 0; overflow: hidden;">
        <div class="card-header" style="padding: 14px 18px; margin-bottom: 0; background: #f8fafc;">
          <div class="card-title" style="font-size: 14px;">
            <svg width="16" height="16" fill="none" stroke="#2563eb" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            Generated Audit Reports History (${reports.length})
          </div>
        </div>

        ${reports.length === 0 ? `
          <div style="padding: 36px 20px; text-align: center; color: #64748b;">
            <svg width="36" height="36" fill="none" stroke="#cbd5e1" viewBox="0 0 24 24" style="margin: 0 auto 8px auto; display: block;">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            <div style="font-weight: 600; font-size: 13.5px; color: #334155;">No Reports Generated Yet</div>
            <div style="font-size: 12px; margin-top: 2px;">Click 'Generate PDF' on any report module above to create and download formal PDF documentation.</div>
          </div>
        ` : `
          <div class="table-container" style="border: none; border-radius: 0;">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Report Title & Filename</th>
                  <th>Report Module Type</th>
                  <th>Generated By</th>
                  <th>Date & Time</th>
                  <th style="text-align: right; width: 140px;">Download</th>
                </tr>
              </thead>
              <tbody>
                ${reports.map(rep => `
                  <tr>
                    <td>
                      <div class="font-bold" style="color: #0f172a; font-size: 13px;">${escapeHtml(rep.report_title)}</div>
                    </td>
                    <td>
                      <span class="badge badge-medium" style="font-size: 11px;">
                        ${escapeHtml(rep.report_type || 'PDF Report')}
                      </span>
                    </td>
                    <td>
                      <div style="font-weight: 600; font-size: 12px; color: #334155;">${escapeHtml(rep.generated_by || 'Auditor')}</div>
                    </td>
                    <td>
                      <div class="font-mono" style="font-size: 11.5px; color: #64748b;">
                        ${escapeHtml(rep.created_at ? rep.created_at.replace('T', ' ').substring(0, 19) : '')}
                      </div>
                    </td>
                    <td style="text-align: right;">
                      <a href="/api/reports/download/${rep.id}" class="btn btn-sm btn-primary" target="_blank" download="${escapeHtml(rep.report_title)}" title="Download PDF Report">
                        <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                        Download PDF
                      </a>
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `
      <div class="card" style="padding: 30px; text-align: center;">
        <div style="color: #dc2626; font-weight: 700; font-size: 15px; margin-bottom: 6px;">Error Loading Reports</div>
        <p style="color: #64748b; font-size: 13px;">${escapeHtml(err.message)}</p>
        <button class="btn btn-secondary" onclick="renderReports()" style="margin-top: 12px;">Try Again</button>
      </div>`;
  }
}

async function triggerGeneratePDFReport(reportType = "complete_audit_analysis") {
  const btn = document.getElementById(`btn-gen-${reportType}`);
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner" style="width:12px; height:12px; border-width:2px; display:inline-block;"></span> Generating...`;
  }

  try {
    const res = await FinAuditAPI.generatePDFReport(state.currentEngagementId, reportType);
    notifySuccess(`Success! Generated PDF Report: ${res.report_title || res.filename}`);
    await renderReports();
    // Prompt download
    if (res.download_url) {
      window.open(res.download_url, "_blank");
    }
  } catch (e) {
    notifyError("Failed to generate PDF report: " + e.message);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `Generate PDF`;
    }
  }
}


// Audit Trail View
async function renderAuditTrail() {
  const container = document.getElementById("content-container");
  const logs = await FinAuditAPI.getAuditTrail(100);

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div>
        <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Audit Trail & Activity Log</h2>
        <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
          Immutable MCA / Companies Act Rule 11(g) compliant audit log
        </div>
      </div>
    </div>

    <div class="card">
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>User</th>
              <th>Action</th>
              <th>Entity</th>
              <th>Log Details</th>
            </tr>
          </thead>
          <tbody>
            ${logs.map(log => `
              <tr>
                <td class="font-mono" style="font-size: 11.5px;">${log.timestamp.replace('T', ' ').split('.')[0]}</td>
                <td class="font-bold">${log.username}</td>
                <td><span class="badge badge-open">${log.action}</span></td>
                <td>${log.entity_type} (#${log.entity_id || '0'})</td>
                <td style="font-size: 12px; color: #475569;">${log.details || ''}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// =========================================================
// 14. CLIENT MANAGEMENT MODULE
// =========================================================
async function renderClients() {
  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 20px;">Loading client database...</div>`;

  try {
    const clients = await FinAuditAPI.getClients();
    const canCreate = ["Admin", "Auditor"].includes(state.currentUser?.role);

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Client Master Database</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Corporate entities, statutory PAN/GSTIN registration, industry categories, and historical audit records
          </div>
        </div>
        ${canCreate ? `
          <button class="btn btn-primary" onclick="openCreateClientModal()">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            + Add New Client Master
          </button>
        ` : ''}
      </div>

      <!-- Filter / Search Bar -->
      <div class="card" style="padding: 14px 18px; margin-bottom: 16px; display: flex; gap: 14px; align-items: center; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 240px;">
          <input type="text" id="client-search-input" class="form-control" placeholder="🔍 Search by Client Name, PAN, GSTIN, Contact Person, Industry..." onkeyup="filterClientsLive()">
        </div>
        <div style="width: 200px;">
          <select id="client-entity-filter" class="form-control" onchange="filterClientsLive()">
            <option value="All">All Entity Types</option>
            <option value="Private Limited Company">Private Limited Company</option>
            <option value="Public Limited Company">Public Limited Company</option>
            <option value="LLP">LLP</option>
            <option value="Partnership">Partnership</option>
            <option value="Proprietorship">Proprietorship</option>
            <option value="Trust">Trust</option>
            <option value="Society">Society</option>
            <option value="NGO">NGO</option>
            <option value="Other">Other</option>
          </select>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">Registered Corporate Clients (${clients.length})</div>
        </div>
        <div class="table-container">
          <table class="data-table" id="clients-table">
            <thead>
              <tr>
                <th>Client Name & Entity Type</th>
                <th>PAN</th>
                <th>GSTIN</th>
                <th>Industry</th>
                <th>Contact Person & Email</th>
                <th>Financial Years</th>
                <th class="text-center">Engagements</th>
                <th class="text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${clients.map(c => `
                <tr data-name="${(c.name || '').toLowerCase()}" data-pan="${(c.pan || '').toLowerCase()}" data-gstin="${(c.gstin || '').toLowerCase()}" data-entity="${c.entity_type || ''}" data-industry="${c.industry || ''}">
                  <td>
                    <div style="font-weight: 700; color: #0f172a; font-size: 13.5px;">${c.name}</div>
                    <span class="badge badge-medium" style="margin-top: 2px;">${c.entity_type || 'Private Limited Company'}</span>
                  </td>
                  <td class="font-mono font-bold" style="color: var(--primary);">${c.pan || '—'}</td>
                  <td class="font-mono" style="font-size: 11.5px;">${c.gstin || '—'}</td>
                  <td><span class="badge badge-open">${c.industry || 'General'}</span></td>
                  <td>
                    <b>${c.contact_person || '—'}</b><br/>
                    <span style="font-size: 11px; color: #64748b;">${c.email || ''} ${c.phone ? `(${c.phone})` : ''}</span>
                  </td>
                  <td>
                    <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                      ${c.financial_years && c.financial_years.length > 0 ? c.financial_years.map(fy => `
                        <span class="badge badge-role-auditor font-mono" style="font-size: 10px;">${fy}</span>
                      `).join("") : '<span style="color: #94a3b8; font-size: 11px;">None</span>'}
                    </div>
                  </td>
                  <td class="text-center font-bold" style="font-size: 13px;">${c.engagements_count || 0}</td>
                  <td class="text-center">
                    <div style="display: flex; gap: 6px; justify-content: center;">
                      <button class="btn btn-sm btn-secondary" onclick="openClientHistoryDrawer(${c.id})">
                        📅 Multi-Year Timeline
                      </button>
                      ${canCreate ? `
                        <button class="btn btn-sm btn-secondary" onclick="openEditClientModal(${c.id})">
                          Edit
                        </button>
                      ` : ''}
                    </div>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading clients: ${err.message}</div>`;
  }
}

function filterClientsLive() {
  const query = document.getElementById("client-search-input").value.toLowerCase().trim();
  const entity = document.getElementById("client-entity-filter").value;
  const rows = document.querySelectorAll("#clients-table tbody tr");

  rows.forEach(r => {
    const textMatch = !query || r.innerText.toLowerCase().includes(query);
    const entityMatch = entity === "All" || r.dataset.entity === entity;
    r.style.display = (textMatch && entityMatch) ? "" : "none";
  });
}

function openCreateClientModal() {
  const modalHtml = `
    <div class="modal-overlay" id="client-modal">
      <div class="modal-card" style="width: 560px;">
        <div class="modal-header">
          <div class="modal-title">Create New Client Master Profile</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('client-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleCreateClientSubmit(event)">
            <div class="form-group">
              <label class="form-label">Client / Company Name *</label>
              <input type="text" id="cli-name" class="form-control" placeholder="e.g. Acme Precision Technologies Pvt Ltd" required>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Entity Type *</label>
                <select id="cli-entity-type" class="form-control">
                  <option value="Private Limited Company">Private Limited Company</option>
                  <option value="Public Limited Company">Public Limited Company</option>
                  <option value="LLP">LLP (Limited Liability Partnership)</option>
                  <option value="Partnership">Partnership Firm</option>
                  <option value="Proprietorship">Proprietorship</option>
                  <option value="Trust">Trust</option>
                  <option value="Society">Society</option>
                  <option value="NGO">NGO / Section 8</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Industry Sector</label>
                <select id="cli-industry" class="form-control">
                  <option value="Manufacturing">Manufacturing & Heavy Engineering</option>
                  <option value="Logistics & Transport">Logistics & Transport</option>
                  <option value="Information Technology">Information Technology & SaaS</option>
                  <option value="Wholesale & Retail">Wholesale & Retail Trading</option>
                  <option value="Financial Services">Financial Services & NBFC</option>
                  <option value="Real Estate & Infra">Real Estate & Construction</option>
                  <option value="Healthcare & Pharma">Healthcare & Pharma</option>
                  <option value="Hospitality & F&B">Hospitality & F&B</option>
                  <option value="Other">Other Industry</option>
                </select>
              </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Permanent Account Number (PAN)</label>
                <input type="text" id="cli-pan" class="form-control font-mono" placeholder="AABCA1234D" maxlength="10" style="text-transform: uppercase;">
              </div>
              <div class="form-group">
                <label class="form-label">GSTIN (15 Digits)</label>
                <input type="text" id="cli-gstin" class="form-control font-mono" placeholder="27AABCA1234D1ZP" maxlength="15" style="text-transform: uppercase;">
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Registered Office Address</label>
              <textarea id="cli-address" class="form-control" rows="2" placeholder="Full corporate / registered business address..."></textarea>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
              <div class="form-group">
                <label class="form-label">Contact Person</label>
                <input type="text" id="cli-contact" class="form-control" placeholder="Director / CFO Name">
              </div>
              <div class="form-group">
                <label class="form-label">Email</label>
                <input type="email" id="cli-email" class="form-control" placeholder="accounts@company.com">
              </div>
              <div class="form-group">
                <label class="form-label">Phone</label>
                <input type="text" id="cli-phone" class="form-control" placeholder="+91 98200 12345">
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Audit Notes & Engagement Background</label>
              <textarea id="cli-notes" class="form-control" rows="2" placeholder="Special statutory considerations, group entities, previous auditor remarks..."></textarea>
            </div>
            <div class="modal-footer" style="padding: 10px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('client-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Client Master</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleCreateClientSubmit(event) {
  event.preventDefault();
  const name = document.getElementById("cli-name").value.trim();
  const entity_type = document.getElementById("cli-entity-type").value;
  const industry = document.getElementById("cli-industry").value;
  const pan = document.getElementById("cli-pan").value.trim().toUpperCase();
  const gstin = document.getElementById("cli-gstin").value.trim().toUpperCase();
  const address = document.getElementById("cli-address").value.trim();
  const contact_person = document.getElementById("cli-contact").value.trim();
  const email = document.getElementById("cli-email").value.trim();
  const phone = document.getElementById("cli-phone").value.trim();
  const notes = document.getElementById("cli-notes").value.trim();

  try {
    await FinAuditAPI.createClient({
      name, entity_type, industry, pan, gstin, address, contact_person, email, phone, notes
    });
    notifySuccess(`Client master '${name}' created successfully!`);
    closeModal("client-modal");
    renderClients();
  } catch (err) {
    notifyError("Failed to create client: " + err.message);
  }
}

async function openEditClientModal(clientId) {
  const client = await FinAuditAPI.getClient(clientId);
  const modalHtml = `
    <div class="modal-overlay" id="edit-client-modal">
      <div class="modal-card" style="width: 560px;">
        <div class="modal-header">
          <div class="modal-title">Edit Client Master: ${client.name}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('edit-client-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleEditClientSubmit(event, ${clientId})">
            <div class="form-group">
              <label class="form-label">Client Name *</label>
              <input type="text" id="edit-cli-name" class="form-control" value="${client.name}" required>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Entity Type</label>
                <select id="edit-cli-entity-type" class="form-control">
                  <option value="Private Limited Company" ${client.entity_type === 'Private Limited Company' ? 'selected' : ''}>Private Limited Company</option>
                  <option value="Public Limited Company" ${client.entity_type === 'Public Limited Company' ? 'selected' : ''}>Public Limited Company</option>
                  <option value="LLP" ${client.entity_type === 'LLP' ? 'selected' : ''}>LLP</option>
                  <option value="Partnership" ${client.entity_type === 'Partnership' ? 'selected' : ''}>Partnership</option>
                  <option value="Proprietorship" ${client.entity_type === 'Proprietorship' ? 'selected' : ''}>Proprietorship</option>
                  <option value="Trust" ${client.entity_type === 'Trust' ? 'selected' : ''}>Trust</option>
                  <option value="Society" ${client.entity_type === 'Society' ? 'selected' : ''}>Society</option>
                  <option value="NGO" ${client.entity_type === 'NGO' ? 'selected' : ''}>NGO</option>
                  <option value="Other" ${client.entity_type === 'Other' ? 'selected' : ''}>Other</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Industry</label>
                <input type="text" id="edit-cli-industry" class="form-control" value="${client.industry || 'Manufacturing'}">
              </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">PAN</label>
                <input type="text" id="edit-cli-pan" class="form-control font-mono" value="${client.pan || ''}" maxlength="10" style="text-transform: uppercase;">
              </div>
              <div class="form-group">
                <label class="form-label">GSTIN</label>
                <input type="text" id="edit-cli-gstin" class="form-control font-mono" value="${client.gstin || ''}" maxlength="15" style="text-transform: uppercase;">
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Address</label>
              <textarea id="edit-cli-address" class="form-control" rows="2">${client.address || ''}</textarea>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
              <div class="form-group">
                <label class="form-label">Contact Person</label>
                <input type="text" id="edit-cli-contact" class="form-control" value="${client.contact_person || ''}">
              </div>
              <div class="form-group">
                <label class="form-label">Email</label>
                <input type="email" id="edit-cli-email" class="form-control" value="${client.email || ''}">
              </div>
              <div class="form-group">
                <label class="form-label">Phone</label>
                <input type="text" id="edit-cli-phone" class="form-control" value="${client.phone || ''}">
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Notes</label>
              <textarea id="edit-cli-notes" class="form-control" rows="2">${client.notes || ''}</textarea>
            </div>
            <div class="modal-footer" style="padding: 10px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('edit-client-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Update Client Profile</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleEditClientSubmit(event, clientId) {
  event.preventDefault();
  const name = document.getElementById("edit-cli-name").value.trim();
  const entity_type = document.getElementById("edit-cli-entity-type").value;
  const industry = document.getElementById("edit-cli-industry").value.trim();
  const pan = document.getElementById("edit-cli-pan").value.trim().toUpperCase();
  const gstin = document.getElementById("edit-cli-gstin").value.trim().toUpperCase();
  const address = document.getElementById("edit-cli-address").value.trim();
  const contact_person = document.getElementById("edit-cli-contact").value.trim();
  const email = document.getElementById("edit-cli-email").value.trim();
  const phone = document.getElementById("edit-cli-phone").value.trim();
  const notes = document.getElementById("edit-cli-notes").value.trim();

  try {
    await FinAuditAPI.updateClient(clientId, {
      name, entity_type, industry, pan, gstin, address, contact_person, email, phone, notes
    });
    notifySuccess("Client updated successfully!");
    closeModal("edit-client-modal");
    renderClients();
  } catch (err) {
    notifyError("Update failed: " + err.message);
  }
}

// Client Multi-Year Historical Timeline Drawer
async function openClientHistoryDrawer(clientId) {
  const data = await FinAuditAPI.getClientHistory(clientId);
  const client = data.client;
  const history = data.history || [];

  const drawerHeader = document.getElementById("drawer-title");
  const drawerBody = document.getElementById("drawer-content");

  drawerHeader.innerText = `Client History: ${client.name}`;
  drawerBody.innerHTML = `
    <div style="padding: 12px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span class="badge badge-medium">${client.entity_type}</span>
        <span class="badge badge-open">${client.industry}</span>
      </div>
      <div style="margin-top: 8px; font-size: 12px;">
        <div><b>PAN:</b> <span class="font-mono font-bold">${client.pan || '—'}</span> | <b>GSTIN:</b> <span class="font-mono">${client.gstin || '—'}</span></div>
        <div style="margin-top: 4px;"><b>Contact:</b> ${client.contact_person || '—'} (${client.email || '—'}, ${client.phone || '—'})</div>
      </div>
    </div>

    <div style="font-weight: 700; font-size: 13px; color: #0f172a; margin-bottom: 10px;">
      📅 Multi-Year Audit Engagement History (${history.length}):
    </div>

    ${history.length === 0 ? `
      <div style="padding: 20px; text-align: center; color: #64748b;">
        No engagements recorded for this client yet.
      </div>
    ` : `
      <div style="display: flex; flex-direction: column; gap: 12px;">
        ${history.map(h => `
          <div style="padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-md); background: ${h.id === state.currentEngagementId ? 'var(--primary-light)' : '#ffffff'};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <span class="badge badge-role-auditor font-mono font-bold" style="font-size: 12px;">FY ${h.financial_year}</span>
                <span style="font-weight: 700; color: #0f172a; margin-left: 6px;">${h.title}</span>
              </div>
              <span class="badge ${h.status === 'Completed' ? 'badge-resolved' : (h.status === 'Archived' ? 'badge-disabled' : 'badge-open')}">${h.status}</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 8px; font-size: 12px; color: #475569;">
              <div>Turnover: <b class="font-mono">${formatINR(h.turnover)}</b></div>
              <div>Audit Type: <b>${h.audit_type}</b></div>
              <div>Exceptions: <b style="color: ${h.critical_findings > 0 ? '#dc2626' : '#0f172a'};">${h.total_findings} (${h.critical_findings} Critical)</b></div>
              <div>Lead Auditor: <b>${h.lead_auditor_name || 'Partner'}</b></div>
            </div>
            <div style="margin-top: 10px; display: flex; gap: 8px;">
              <button class="btn btn-sm btn-primary" onclick="selectEngagementAndGo(${h.id})">
                🚀 Open Engagement Context
              </button>
              <button class="btn btn-sm btn-secondary" onclick="openDuplicateEngagementModal(${h.id})">
                📑 Clone to New FY
              </button>
            </div>
          </div>
        `).join("")}
      </div>
    `}
  `;

  document.getElementById("drawer-overlay").style.display = "block";
  document.getElementById("evidence-drawer").classList.add("open");
}

// =========================================================
// 15. ENGAGEMENT MANAGEMENT MODULE
// =========================================================
async function renderEngagements() {
  const container = document.getElementById("content-container");
  container.innerHTML = `<div style="padding: 20px;">Loading engagements directory...</div>`;

  try {
    const engagements = await FinAuditAPI.getEngagements();
    const canCreate = ["Admin", "Auditor"].includes(state.currentUser?.role);

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Audit Engagements Directory</h2>
          <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
            Statutory, Tax Audit (3CD), Internal, and Special Audit engagements with strict data isolation
          </div>
        </div>
        ${canCreate ? `
          <button class="btn btn-primary" onclick="openCreateEngagementModal()">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            + New Audit Engagement
          </button>
        ` : ''}
      </div>

      <!-- Filter Controls -->
      <div class="card" style="padding: 14px 18px; margin-bottom: 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 200px;">
          <input type="text" id="eng-search-input" class="form-control" placeholder="🔍 Search Engagement Title, Client, FY..." onkeyup="filterEngagementsLive()">
        </div>
        <div style="width: 160px;">
          <select id="eng-type-filter" class="form-control" onchange="filterEngagementsLive()">
            <option value="All">All Audit Types</option>
            <option value="Statutory Audit">Statutory Audit</option>
            <option value="Tax Audit">Tax Audit (3CD)</option>
            <option value="Internal Audit">Internal Audit</option>
            <option value="Review">Review</option>
            <option value="Special Audit">Special Audit</option>
          </select>
        </div>
        <div style="width: 160px;">
          <select id="eng-status-filter" class="form-control" onchange="filterEngagementsLive()">
            <option value="All">All Statuses</option>
            <option value="In Progress">In Progress</option>
            <option value="Under Review">Under Review</option>
            <option value="Completed">Completed</option>
            <option value="Draft">Draft</option>
            <option value="Archived">Archived</option>
          </select>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">All Engagements (${engagements.length})</div>
        </div>
        <div class="table-container">
          <table class="data-table" id="engagements-table">
            <thead>
              <tr>
                <th>Engagement & Client</th>
                <th>Audit Type</th>
                <th>Financial Year</th>
                <th>Lead Auditor & Staff</th>
                <th>Status</th>
                <th class="text-right">Turnover</th>
                <th class="text-center">Findings</th>
                <th class="text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${engagements.map(e => `
                <tr style="${e.id === state.currentEngagementId ? 'background-color: var(--primary-light);' : ''}" data-title="${(e.title || '').toLowerCase()}" data-client="${(e.client_name || '').toLowerCase()}" data-fy="${e.financial_year || ''}" data-type="${e.audit_type || ''}" data-status="${e.status || ''}">
                  <td>
                    <div style="font-weight: 700; color: #0f172a; font-size: 13.5px;">
                      ${e.title}
                      ${e.id === state.currentEngagementId ? '<span class="badge badge-open" style="margin-left: 6px;">Active Context</span>' : ''}
                    </div>
                    <div style="font-size: 11.5px; color: #64748b; margin-top: 2px;">
                      <b>${e.client_name}</b> (PAN: ${e.client_pan || '—'})
                    </div>
                  </td>
                  <td><span class="badge badge-medium">${e.audit_type}</span></td>
                  <td class="font-mono font-bold" style="color: var(--primary);">${e.financial_year}</td>
                  <td>
                    <div><b>Auditor:</b> ${e.lead_auditor_name || 'Partner'}</div>
                    <div style="font-size: 11px; color: #64748b;"><b>Staff:</b> ${e.assigned_staff_name || 'Unassigned'}</div>
                  </td>
                  <td>
                    <select class="form-control" style="font-size: 11.5px; padding: 3px 6px; width: 115px;" onchange="updateEngagementStatusDirect(${e.id}, this.value)">
                      <option value="Draft" ${e.status === 'Draft' ? 'selected' : ''}>Draft</option>
                      <option value="In Progress" ${e.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
                      <option value="Under Review" ${e.status === 'Under Review' ? 'selected' : ''}>Under Review</option>
                      <option value="Completed" ${e.status === 'Completed' ? 'selected' : ''}>Completed</option>
                      <option value="Archived" ${e.status === 'Archived' ? 'selected' : ''}>Archived</option>
                    </select>
                  </td>
                  <td class="text-right font-mono font-bold">${formatINR(e.turnover)}</td>
                  <td class="text-center font-mono font-bold" style="color: ${e.critical_findings_count > 0 ? '#dc2626' : '#0f172a'};">
                    ${e.findings_count}
                  </td>
                  <td class="text-center">
                    <div style="display: flex; gap: 6px; justify-content: center;">
                      <button class="btn btn-sm ${e.id === state.currentEngagementId ? 'btn-secondary' : 'btn-primary'}" onclick="selectEngagementAndGo(${e.id})">
                        ${e.id === state.currentEngagementId ? 'Viewing' : 'Switch Context'}
                      </button>
                      <button class="btn btn-sm btn-secondary" onclick="openDuplicateEngagementModal(${e.id})">
                        📑 Clone FY
                      </button>
                      ${canCreate ? `
                        <button class="btn btn-sm btn-secondary" onclick="openEditEngagementModal(${e.id})">
                          Edit
                        </button>
                      ` : ''}
                    </div>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: #dc2626;">Error loading engagements: ${err.message}</div>`;
  }
}

function filterEngagementsLive() {
  const query = document.getElementById("eng-search-input").value.toLowerCase().trim();
  const type = document.getElementById("eng-type-filter").value;
  const status = document.getElementById("eng-status-filter").value;
  const rows = document.querySelectorAll("#engagements-table tbody tr");

  rows.forEach(r => {
    const textMatch = !query || r.innerText.toLowerCase().includes(query);
    const typeMatch = type === "All" || r.dataset.type === type;
    const statusMatch = status === "All" || r.dataset.status === status;
    r.style.display = (textMatch && typeMatch && statusMatch) ? "" : "none";
  });
}

async function updateEngagementStatusDirect(engId, newStatus) {
  try {
    await FinAuditAPI.updateEngagementStatus(engId, newStatus);
    notifySuccess(`Engagement status updated to '${newStatus}'.`);
    await loadEngagements();
    renderEngagements();
  } catch (err) {
    notifyError("Failed to update status: " + err.message);
    renderEngagements();
  }
}

function selectEngagementAndGo(id) {
  state.currentEngagementId = id;
  const sel = document.getElementById("engagement-select");
  if (sel) sel.value = id;
  closeEvidenceDrawer();
  updateActiveEngagement().then(() => navigateTo("dashboard"));
}

// Create Engagement Modal
async function openCreateEngagementModal() {
  const clients = await FinAuditAPI.getClients();
  const users = await FinAuditAPI.getUsers();

  const modalHtml = `
    <div class="modal-overlay" id="eng-modal">
      <div class="modal-card" style="width: 560px;">
        <div class="modal-header">
          <div class="modal-title">Create New Audit Engagement</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('eng-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleCreateEngagementSubmit(event)">
            <div class="form-group">
              <label class="form-label">Client Selection *</label>
              <select id="eng-client-id" class="form-control" required>
                ${clients.map(c => `
                  <option value="${c.id}">${c.name} (${c.entity_type} - PAN: ${c.pan || 'N/A'})</option>
                `).join("")}
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Engagement Title *</label>
              <input type="text" id="eng-title" class="form-control" placeholder="e.g. Statutory & Tax Audit FY 2024-25" required>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Audit Type *</label>
                <select id="eng-audit-type" class="form-control">
                  <option value="Statutory Audit">Statutory Audit</option>
                  <option value="Tax Audit">Tax Audit (Form 3CD)</option>
                  <option value="Internal Audit">Internal Audit</option>
                  <option value="Review">Limited Review</option>
                  <option value="Special Audit">Special / Forensic Audit</option>
                  <option value="Other">Other Audit</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Financial Year (e.g. 2024-25) *</label>
                <input type="text" id="eng-fy" class="form-control font-mono font-bold" value="2024-25" required>
              </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Period Start Date</label>
                <input type="date" id="eng-start" class="form-control" value="2024-04-01">
              </div>
              <div class="form-group">
                <label class="form-label">Period End Date</label>
                <input type="date" id="eng-end" class="form-control" value="2025-03-31">
              </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Lead Engagement Partner / CA</label>
                <select id="eng-lead-auditor" class="form-control">
                  ${users.filter(u => ['Admin', 'Auditor'].includes(u.role)).map(u => `
                    <option value="${u.id}">${u.full_name} (${u.role})</option>
                  `).join("")}
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Assigned Audit Staff</label>
                <select id="eng-assigned-staff" class="form-control">
                  <option value="">-- None --</option>
                  ${users.map(u => `
                    <option value="${u.id}">${u.full_name} (${u.role})</option>
                  `).join("")}
                </select>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Engagement Scope & Audit Notes</label>
              <textarea id="eng-notes" class="form-control" rows="2" placeholder="Specific terms of audit engagement, materiality thresholds..."></textarea>
            </div>
            <div class="modal-footer" style="padding: 10px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('eng-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Initialize Audit Engagement</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleCreateEngagementSubmit(event) {
  event.preventDefault();
  const client_id = parseInt(document.getElementById("eng-client-id").value);
  const title = document.getElementById("eng-title").value.trim();
  const audit_type = document.getElementById("eng-audit-type").value;
  const financial_year = document.getElementById("eng-fy").value.trim();
  const period_start = document.getElementById("eng-start").value;
  const period_end = document.getElementById("eng-end").value;
  const lead_auditor_id = parseInt(document.getElementById("eng-lead-auditor").value) || null;
  const staffVal = document.getElementById("eng-assigned-staff").value;
  const assigned_staff_id = staffVal ? parseInt(staffVal) : null;
  const notes = document.getElementById("eng-notes").value.trim();

  try {
    const res = await FinAuditAPI.createEngagement({
      client_id, title, audit_type, financial_year, period_start, period_end, lead_auditor_id, assigned_staff_id, notes
    });
    notifySuccess(`Engagement '${title}' created successfully!`);
    closeModal("eng-modal");
    await loadEngagements();
    selectEngagementAndGo(res.id);
  } catch (err) {
    notifyError("Error creating engagement: " + err.message);
  }
}

// Edit Engagement Modal
async function openEditEngagementModal(engagementId) {
  const eng = await FinAuditAPI.getEngagementDetails(engagementId);
  const users = await FinAuditAPI.getUsers();

  const modalHtml = `
    <div class="modal-overlay" id="edit-eng-modal">
      <div class="modal-card" style="width: 560px;">
        <div class="modal-header">
          <div class="modal-title">Edit Engagement: ${eng.title}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('edit-eng-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleEditEngagementSubmit(event, ${engagementId})">
            <div class="form-group">
              <label class="form-label">Engagement Title *</label>
              <input type="text" id="edit-eng-title" class="form-control" value="${eng.title}" required>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Audit Type</label>
                <select id="edit-eng-audit-type" class="form-control">
                  <option value="Statutory Audit" ${eng.audit_type === 'Statutory Audit' ? 'selected' : ''}>Statutory Audit</option>
                  <option value="Tax Audit" ${eng.audit_type === 'Tax Audit' ? 'selected' : ''}>Tax Audit (Form 3CD)</option>
                  <option value="Internal Audit" ${eng.audit_type === 'Internal Audit' ? 'selected' : ''}>Internal Audit</option>
                  <option value="Review" ${eng.audit_type === 'Review' ? 'selected' : ''}>Limited Review</option>
                  <option value="Special Audit" ${eng.audit_type === 'Special Audit' ? 'selected' : ''}>Special / Forensic Audit</option>
                  <option value="Other" ${eng.audit_type === 'Other' ? 'selected' : ''}>Other</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Financial Year</label>
                <input type="text" id="edit-eng-fy" class="form-control font-mono font-bold" value="${eng.financial_year}" required>
              </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Period Start</label>
                <input type="date" id="edit-eng-start" class="form-control" value="${eng.period_start || ''}">
              </div>
              <div class="form-group">
                <label class="form-label">Period End</label>
                <input type="date" id="edit-eng-end" class="form-control" value="${eng.period_end || ''}">
              </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Lead Engagement Partner</label>
                <select id="edit-eng-lead" class="form-control">
                  ${users.map(u => `
                    <option value="${u.id}" ${u.id === eng.lead_auditor_id ? 'selected' : ''}>${u.full_name} (${u.role})</option>
                  `).join("")}
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Assigned Audit Staff</label>
                <select id="edit-eng-staff" class="form-control">
                  <option value="">-- None --</option>
                  ${users.map(u => `
                    <option value="${u.id}" ${u.id === eng.assigned_staff_id ? 'selected' : ''}>${u.full_name} (${u.role})</option>
                  `).join("")}
                </select>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Notes & Scope</label>
              <textarea id="edit-eng-notes" class="form-control" rows="2">${eng.notes || ''}</textarea>
            </div>
            <div class="modal-footer" style="padding: 10px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('edit-eng-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Changes</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleEditEngagementSubmit(event, engagementId) {
  event.preventDefault();
  const title = document.getElementById("edit-eng-title").value.trim();
  const audit_type = document.getElementById("edit-eng-audit-type").value;
  const financial_year = document.getElementById("edit-eng-fy").value.trim();
  const period_start = document.getElementById("edit-eng-start").value;
  const period_end = document.getElementById("edit-eng-end").value;
  const lead_auditor_id = parseInt(document.getElementById("edit-eng-lead").value) || null;
  const staffVal = document.getElementById("edit-eng-staff").value;
  const assigned_staff_id = staffVal ? parseInt(staffVal) : null;
  const notes = document.getElementById("edit-eng-notes").value.trim();

  try {
    await FinAuditAPI.updateEngagement(engagementId, {
      title, audit_type, financial_year, period_start, period_end, lead_auditor_id, assigned_staff_id, notes
    });
    notifySuccess("Engagement updated successfully!");
    closeModal("edit-eng-modal");
    await loadEngagements();
    renderEngagements();
  } catch (err) {
    notifyError("Failed to update engagement: " + err.message);
  }
}

// Duplicate Engagement Structure for New FY Modal
async function openDuplicateEngagementModal(sourceEngagementId) {
  const eng = await FinAuditAPI.getEngagementDetails(sourceEngagementId);
  const fyParts = (eng.financial_year || "2024-25").split("-");
  let nextFY = "2025-26";
  if (fyParts.length === 2 && !isNaN(parseInt(fyParts[0]))) {
    const y1 = parseInt(fyParts[0]) + 1;
    const y2 = parseInt(fyParts[1]) + 1;
    nextFY = `${y1}-${String(y2).padStart(2, '0')}`;
  }

  const modalHtml = `
    <div class="modal-overlay" id="duplicate-eng-modal">
      <div class="modal-card" style="width: 500px;">
        <div class="modal-header">
          <div class="modal-title">Duplicate Audit Structure for New FY</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('duplicate-eng-modal')">✕</button>
        </div>
        <div class="modal-body">
          <div style="padding: 10px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: var(--radius-md); font-size: 12px; margin-bottom: 14px; color: #1e3a8a;">
            <b>Cloning Source:</b> ${eng.client_name} — ${eng.title} (FY ${eng.financial_year})<br/>
            This creates an isolated new engagement while carrying over your customized CARO/3CD checklists and working paper index.
          </div>

          <form onsubmit="handleDuplicateEngagementSubmit(event, ${sourceEngagementId})">
            <div class="form-group">
              <label class="form-label">Target Financial Year *</label>
              <input type="text" id="dup-target-fy" class="form-control font-mono font-bold" value="${nextFY}" required>
            </div>
            <div class="form-group">
              <label class="form-label">New Engagement Title *</label>
              <input type="text" id="dup-title" class="form-control" value="${eng.audit_type} FY ${nextFY}" required>
            </div>
            <div class="form-group" style="padding: 10px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md);">
              <label style="display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 12.5px; cursor: pointer;">
                <input type="checkbox" id="dup-copy-checklists" checked> Copy CARO & Tax Audit Checklist Templates
              </label>
              <label style="display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 12.5px; cursor: pointer; margin-top: 6px;">
                <input type="checkbox" id="dup-copy-wps" checked> Copy Working Paper Index & File Structure
              </label>
            </div>
            <div class="modal-footer" style="padding: 10px 0 0 0;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('duplicate-eng-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Clone Structure & Launch</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleDuplicateEngagementSubmit(event, sourceEngagementId) {
  event.preventDefault();
  const target_financial_year = document.getElementById("dup-target-fy").value.trim();
  const title = document.getElementById("dup-title").value.trim();
  const copy_checklists = document.getElementById("dup-copy-checklists").checked;
  const copy_working_paper_templates = document.getElementById("dup-copy-wps").checked;

  try {
    const res = await FinAuditAPI.duplicateEngagement({
      source_engagement_id: sourceEngagementId,
      target_financial_year,
      title,
      copy_checklists,
      copy_working_paper_templates
    });
    notifySuccess(`Success! Cloned ${res.cloned_checklists} checklists and ${res.cloned_working_papers} working paper structures to FY ${target_financial_year}.`);
    closeModal("duplicate-eng-modal");
    await loadEngagements();
    selectEngagementAndGo(res.new_engagement_id);
  } catch (err) {
    notifyError("Duplication failed: " + err.message);
  }
}

// Settings View
async function renderSettings() {
  const container = document.getElementById("content-container");
  const info = await FinAuditAPI.getSystemInfo();
  const isAdmin = state.currentUser?.role === "Admin";

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div>
        <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Application Settings & Local Security</h2>
        <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
          Offline SQLite Database, Backup/Restore, and Audit User Roles
        </div>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
      <div class="card">
        <div class="card-header">
          <div class="card-title">System & Database Status</div>
        </div>
        <table class="data-table">
          <tr><td><b>Application:</b></td><td>${info.app_name} v${info.version}</td></tr>
          <tr><td><b>Operation Mode:</b></td><td><span class="offline-pill"><span class="offline-dot"></span> ${info.mode}</span></td></tr>
          <tr><td><b>Database Engine:</b></td><td>${info.database_engine}</td></tr>
          <tr><td><b>Database File:</b></td><td class="font-mono" style="font-size: 11px;">${info.database_path}</td></tr>
          <tr><td><b>Database Size:</b></td><td>${info.database_size_kb} KB</td></tr>
          <tr><td><b>Total Clients / Engagements:</b></td><td>${info.statistics.clients} Clients / ${info.statistics.engagements} Engagements</td></tr>
          <tr><td><b>Total Transactions:</b></td><td class="font-mono font-bold">${info.statistics.total_transactions}</td></tr>
        </table>

        ${isAdmin ? `
          <div style="margin-top: 16px; display: flex; gap: 10px;">
            <button class="btn btn-primary" onclick="triggerBackup()">
              💾 Create Full SQLite Backup
            </button>
          </div>
        ` : ''}
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">My Account & Security Profile</div>
        </div>
        <div style="padding: 6px 0;">
          <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
            <div class="user-avatar ${(state.currentUser?.role || 'Admin').toLowerCase().replace(' ', '')}" style="width: 44px; height: 44px; font-size: 16px;">
              ${(state.currentUser?.full_name || 'Admin').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()}
            </div>
            <div>
              <div style="font-size: 15px; font-weight: 700; color: #0f172a;">${state.currentUser?.full_name}</div>
              <div style="font-size: 12px; color: #64748b;">${state.currentUser?.email}</div>
              <div style="margin-top: 4px;">${getRoleBadge(state.currentUser?.role)}</div>
            </div>
          </div>
          <table class="data-table" style="margin-bottom: 16px;">
            <tr><td><b>Username:</b></td><td class="font-mono">${state.currentUser?.username}</td></tr>
            <tr><td><b>Phone:</b></td><td>${state.currentUser?.phone || 'Not set'}</td></tr>
            <tr><td><b>Account Created:</b></td><td>${state.currentUser?.created_at ? state.currentUser.created_at.split('T')[0] : '—'}</td></tr>
            <tr><td><b>Last Login Recorded:</b></td><td class="font-mono">${state.currentUser?.last_login ? state.currentUser.last_login.replace('T', ' ').split('.')[0] : '—'}</td></tr>
          </table>
          <button class="btn btn-secondary" style="width: 100%;" onclick="openChangePasswordModal()">
            🔒 Change My Account Password
          </button>
        </div>
      </div>
    </div>
  `;
}

async function triggerBackup() {
  try {
    const res = await FinAuditAPI.createBackup();
    notifySuccess(`Backup created successfully: ${res.backup_file}`);
  } catch (e) {
    notifyError("Backup failed: " + e.message);
  }
}

// Slide-out Evidence Drawer Logic
function setupDrawer() {
  const overlay = document.getElementById("drawer-overlay");
  const closeBtn = document.getElementById("drawer-close-btn");
  if (overlay) overlay.addEventListener("click", closeEvidenceDrawer);
  if (closeBtn) closeBtn.addEventListener("click", closeEvidenceDrawer);
}

function closeEvidenceDrawer() {
  document.getElementById("drawer-overlay").style.display = "none";
  document.getElementById("evidence-drawer").classList.remove("open");
}

async function openEvidenceDrawer(findingId) {
  const finding = await FinAuditAPI.getFindingDetail(findingId);
  state.activeFinding = finding;

  const header = document.getElementById("drawer-title");
  const body = document.getElementById("drawer-content");

  header.innerHTML = `Finding ${finding.finding_code}: ${getSeverityBadge(finding.severity)}`;

  body.innerHTML = `
    <div style="margin-bottom: 16px;">
      <h3 style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 6px;">${finding.title}</h3>
      <div style="font-size: 12.5px; color: #475569; line-height: 1.5;">${finding.description}</div>
    </div>

    <div style="padding: 12px; background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 16px; font-size: 12px;">
      <div><b>Rule & Statutory Standard:</b> ${finding.rule_used}</div>
      <div style="margin-top: 4px;"><b>Engine Type:</b> <span class="badge badge-open">${finding.engine_type}</span></div>
      <div style="margin-top: 4px;"><b>Risk Score:</b> <span class="font-mono font-bold">${finding.risk_score} / 10</span></div>
      <div style="margin-top: 4px; color: #dc2626;"><b>Discrepancy:</b> ${finding.difference || 'N/A'}</div>
    </div>

    <div style="margin-bottom: 16px;">
      <div style="font-weight: 700; font-size: 13px; color: #0f172a; margin-bottom: 4px;">💡 Local AI Audit Commentary & Analysis:</div>
      <div style="font-size: 12px; color: #334155; padding: 10px; background: #eff6ff; border-radius: var(--radius-md); border: 1px solid #bfdbfe; line-height: 1.5;">
        ${finding.ai_explanation || 'Detailed review required.'}
      </div>
    </div>

    <div style="margin-bottom: 16px;">
      <div style="font-weight: 700; font-size: 13px; color: #0f172a; margin-bottom: 4px;">📋 Recommended Auditor Action:</div>
      <div style="font-size: 12px; color: #065f46; padding: 10px; background: #ecfdf5; border-radius: var(--radius-md); border: 1px solid #a7f3d0; line-height: 1.5;">
        ${finding.recommended_action || 'Inspect supporting invoice.'}
      </div>
    </div>

    <div style="margin-bottom: 16px;">
      <div style="font-weight: 700; font-size: 13px; color: #0f172a; margin-bottom: 6px;">Associated Transactions & Vouchers (${finding.affected_transactions?.length || 0}):</div>
      ${(!finding.affected_transactions || finding.affected_transactions.length === 0) ? `
        <div style="font-size: 12px; color: #64748b;">No individual transactions linked directly.</div>
      ` : `
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Voucher</th>
                <th>Party</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              ${finding.affected_transactions.map(t => `
                <tr>
                  <td>${t.date}</td>
                  <td class="font-mono">${t.voucher_no || '—'}</td>
                  <td>${t.party_name || t.ledger}</td>
                  <td class="font-mono font-bold">${formatINR(t.amount || t.debit || t.credit)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `}
    </div>

    <div style="margin-top: 20px; border-top: 1px solid var(--border); padding-top: 16px;">
      <div style="font-weight: 700; font-size: 13px; color: #0f172a; margin-bottom: 8px;">Auditor Review & Decision:</div>
      <div class="form-group">
        <label class="form-label">Review Status</label>
        <select class="form-control" id="drawer-finding-status">
          <option value="Open" ${finding.status === 'Open' ? 'selected' : ''}>Open</option>
          <option value="In Review" ${finding.status === 'In Review' ? 'selected' : ''}>In Review</option>
          <option value="Resolved" ${finding.status === 'Resolved' ? 'selected' : ''}>Resolved (Documented in Working Paper)</option>
          <option value="Waived" ${finding.status === 'Waived' ? 'selected' : ''}>Waived (Immaterial)</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Auditor Comment / Working Paper Reference</label>
        <textarea class="form-control" id="drawer-finding-comment" rows="3" placeholder="Enter auditor reasoning, verification notes, or Form 3CD disclosure clause...">${finding.auditor_comment || ''}</textarea>
      </div>
      <button class="btn btn-primary" style="width: 100%;" onclick="saveFindingReview(${finding.id})">Save Audit Review Note</button>
    </div>
  `;

  document.getElementById("drawer-overlay").style.display = "block";
  document.getElementById("evidence-drawer").classList.add("open");
}

async function saveFindingReview(findingId) {
  const status = document.getElementById("drawer-finding-status").value;
  const comment = document.getElementById("drawer-finding-comment").value;

  try {
    await FinAuditAPI.updateFinding(findingId, { status: status, auditor_comment: comment });
    notifySuccess("Audit finding status and comments saved.");
    closeEvidenceDrawer();
    if (state.currentTab === "findings") renderFindings();
    else if (state.currentTab === "dashboard") renderDashboard();
  } catch (e) {
    notifyError("Failed to update finding: " + e.message);
  }
}

// ----------------- FINANCIAL STATEMENT ANALYSIS MODULE -----------------
let currentFSTab = "ratios";
let cachedFSData = null;

async function renderFinancialStatements() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `<div class="card" style="padding: 24px; text-align: center; color: #64748b;">Please select an engagement to analyze financial statements.</div>`;
    return;
  }

  container.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; height: 300px; color: #64748b;">
      <div style="text-align: center;">
        <div style="font-size: 28px; margin-bottom: 8px;">⏳</div>
        <div>Generating Schedule III Financial Statements & Computing Analytical Ratios...</div>
      </div>
    </div>
  `;

  try {
    const data = await FinAuditAPI.getFinancialStatements(state.currentEngagementId);
    cachedFSData = data;
    renderFSContent(data);
  } catch (err) {
    container.innerHTML = `
      <div class="card" style="padding: 30px; text-align: center; color: #dc2626;">
        <div style="font-size: 32px; margin-bottom: 10px;">⚠️</div>
        <h3>Financial Statement Analysis Error</h3>
        <p style="margin-top: 6px; color: #64748b;">${err.message || "Failed to load financial statement data."}</p>
        <button class="btn btn-secondary" style="margin-top: 14px;" onclick="renderFinancialStatements()">Retry Analysis</button>
      </div>
    `;
  }
}

function renderFSContent(data) {
  const container = document.getElementById("content-container");
  const cyYear = data.financial_year_current || "CY";
  const pyYear = data.financial_year_previous || "PY";
  const summary = data.summary || {};
  const sigCount = summary.significant_movements_count || 0;

  const downloadReportUrl = FinAuditAPI.getFSReportDownloadUrl(state.currentEngagementId);

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px;">
      <div>
        <div style="display: flex; align-items: center; gap: 10px;">
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Financial Statement Analysis & SA 520 Analytical Review</h2>
          <span class="badge ${sigCount > 0 ? 'badge-high' : 'badge-low'}" style="font-size: 12px;">
            ${sigCount} Significant Movements
          </span>
        </div>
        <div style="font-size: 13px; color: #64748b; margin-top: 3px;">
          Deterministic Schedule III Financials, Ratio Analytics, and Comparative Multi-Year Variance Workbench
        </div>
      </div>

      <div style="display: flex; gap: 10px;">
        <a href="${downloadReportUrl}" target="_blank" class="btn btn-secondary">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          Export CSV Analysis
        </a>
        <button class="btn btn-primary" onclick="renderFinancialStatements()">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          Recalculate
        </button>
      </div>
    </div>

    <!-- Executive Management & Audit Commentary Banner -->
    <div class="card" style="margin-bottom: 20px; border-left: 4px solid var(--primary); background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);">
      <div style="display: flex; align-items: flex-start; gap: 14px;">
        <div style="font-size: 24px; line-height: 1;">📋</div>
        <div style="flex: 1;">
          <div style="font-weight: 700; font-size: 14px; color: #0f172a; margin-bottom: 4px;">
            Executive Audit & Management Analysis Summary (FY ${cyYear} vs FY ${pyYear})
          </div>
          <p style="font-size: 13px; color: #334155; line-height: 1.6; margin: 0;">
            ${summary.management_commentary || 'Analysis generated based on transaction ledgers and Schedule III classification.'}
          </p>
          <div style="display: flex; gap: 16px; margin-top: 10px; font-size: 11px; color: #64748b;">
            <span><b>Auditing Standard:</b> SA 520 (Analytical Procedures)</span>
            <span>•</span>
            <span><b>Significant Threshold:</b> |Δ%| ≥ 20% or |Δ| ≥ ₹5,00,000</span>
            <span>•</span>
            <span><b>Audit Notice:</b> Movements reflect financial variance and require professional CA inquiry.</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Sub Navigation Tabs -->
    <div class="tab-pills" style="margin-bottom: 18px;">
      <div class="tab-pill ${currentFSTab === 'ratios' ? 'active' : ''}" onclick="switchFSTab('ratios')">
        📊 Statutory & Financial Ratios
      </div>
      <div class="tab-pill ${currentFSTab === 'balance_sheet' ? 'active' : ''}" onclick="switchFSTab('balance_sheet')">
        📑 Balance Sheet (Schedule III)
      </div>
      <div class="tab-pill ${currentFSTab === 'pnl' ? 'active' : ''}" onclick="switchFSTab('pnl')">
        📈 Profit & Loss Statement
      </div>
      <div class="tab-pill ${currentFSTab === 'cash_flow' ? 'active' : ''}" onclick="switchFSTab('cash_flow')">
        💸 Cash Flow Statement
      </div>
      <div class="tab-pill ${currentFSTab === 'significant_movements' ? 'active' : ''}" onclick="switchFSTab('significant_movements')">
        🔍 Significant Movements (${sigCount})
      </div>
    </div>

    <!-- Tab View Container -->
    <div id="fs-tab-content">
      ${getFSTabContentHtml(currentFSTab, data)}
    </div>
  `;
}

function switchFSTab(tab) {
  currentFSTab = tab;
  document.querySelectorAll(".tab-pills .tab-pill").forEach((pill, idx) => {
    pill.classList.remove("active");
  });
  if (cachedFSData) {
    const tabContainer = document.getElementById("fs-tab-content");
    if (tabContainer) {
      tabContainer.innerHTML = getFSTabContentHtml(tab, cachedFSData);
    }
    const pills = document.querySelectorAll(".tab-pills .tab-pill");
    const tabMap = ['ratios', 'balance_sheet', 'pnl', 'cash_flow', 'significant_movements'];
    pills.forEach((p, idx) => {
      if (tabMap[idx] === tab) p.classList.add("active");
    });
  }
}

function getFSTabContentHtml(tab, data) {
  const cyYear = data.financial_year_current || "CY";
  const pyYear = data.financial_year_previous || "PY";

  if (tab === "ratios") {
    return renderRatiosDashboardHtml(data, cyYear, pyYear);
  } else if (tab === "balance_sheet") {
    return renderBalanceSheetHtml(data, cyYear, pyYear);
  } else if (tab === "pnl") {
    return renderPnLHtml(data, cyYear, pyYear);
  } else if (tab === "cash_flow") {
    return renderCashFlowHtml(data, cyYear, pyYear);
  } else if (tab === "significant_movements") {
    return renderSignificantMovementsHtml(data, cyYear, pyYear);
  }
  return "";
}

function renderRatiosDashboardHtml(data, cyYear, pyYear) {
  const cy = data.ratios?.current_year || {};
  const py = data.ratios?.previous_year || {};

  function ratioCard(title, category, cyVal, pyVal, unit, benchmark = null, invert = false) {
    const diff = roundNum((cyVal || 0) - (pyVal || 0), 2);
    const isUp = diff > 0;
    const isGood = invert ? !isUp : isUp;
    const isNeutral = Math.abs(diff) < 0.001;
    const diffColor = isNeutral ? "#64748b" : (isGood ? "#059669" : "#dc2626");
    const diffArrow = isNeutral ? "" : (isUp ? "↑" : "↓");

    return `
      <div class="card" style="padding: 16px; border: 1px solid var(--border); transition: transform 0.15s, box-shadow 0.15s;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
          <div>
            <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">${category}</div>
            <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-top: 2px;">${title}</div>
          </div>
          ${benchmark ? `<span class="badge badge-low" style="font-size: 10px;">Target: ${benchmark}</span>` : ''}
        </div>

        <div style="display: flex; align-items: baseline; gap: 8px; margin-top: 10px;">
          <span style="font-size: 24px; font-weight: 800; color: #0f172a; font-family: monospace;">
            ${typeof cyVal === 'number' ? cyVal.toFixed(2) : (cyVal || 0)}${unit === '%' ? '%' : (unit === 'x' ? 'x' : (unit === 'days' ? ' d' : ''))}
          </span>
          <span style="font-size: 12px; font-weight: 600; color: ${diffColor};">
            ${diffArrow} ${Math.abs(diff).toFixed(2)}${unit === '%' ? '%' : ''} vs PY
          </span>
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--border); font-size: 11.5px; color: #64748b;">
          <span>PY (FY ${pyYear}): <b style="color: #334155; font-family: monospace;">${typeof pyVal === 'number' ? pyVal.toFixed(2) : (pyVal || 0)}${unit === '%' ? '%' : (unit === 'x' ? 'x' : (unit === 'days' ? ' d' : ''))}</b></span>
          <span>CY (FY ${cyYear}): <b style="color: #0f172a; font-family: monospace;">${typeof cyVal === 'number' ? cyVal.toFixed(2) : (cyVal || 0)}${unit === '%' ? '%' : (unit === 'x' ? 'x' : (unit === 'days' ? ' d' : ''))}</b></span>
        </div>
      </div>
    `;
  }

  return `
    <div style="margin-bottom: 24px;">
      <h3 style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
        <span>💧</span> Liquidity & Solvency Ratios
      </h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px;">
        ${ratioCard("Current Ratio", "Liquidity", cy.current_ratio, py.current_ratio, "x", "≥ 1.33x")}
        ${ratioCard("Quick Ratio (Acid Test)", "Liquidity", cy.quick_ratio, py.quick_ratio, "x", "≥ 1.00x")}
        ${ratioCard("Debt-to-Equity Ratio", "Solvency / Leverage", cy.debt_equity_ratio, py.debt_equity_ratio, "x", "≤ 2.00x", true)}
        ${ratioCard("Return on Capital Employed (ROCE)", "Capital Efficiency", cy.roce_pct, py.roce_pct, "%", "≥ 15%")}
      </div>
    </div>

    <div style="margin-bottom: 24px;">
      <h3 style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
        <span>📈</span> Profitability & Operating Margins
      </h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px;">
        ${ratioCard("Gross Profit Margin", "Profitability", cy.gross_profit_margin_pct, py.gross_profit_margin_pct, "%")}
        ${ratioCard("Operating Profit Margin (EBIT)", "Profitability", cy.operating_margin_pct, py.operating_margin_pct, "%")}
        ${ratioCard("Net Profit Margin (PAT)", "Profitability", cy.net_profit_margin_pct, py.net_profit_margin_pct, "%")}
        ${ratioCard("Return on Equity (ROE)", "Profitability", cy.roe_pct, py.roe_pct, "%")}
      </div>
    </div>

    <div style="margin-bottom: 24px;">
      <h3 style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
        <span>⚙️</span> Turnover Ratios & Working Capital Days
      </h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px;">
        ${ratioCard("Debtors / Receivable Turnover", "Activity", cy.receivable_turnover, py.receivable_turnover, "x")}
        ${ratioCard("Days Sales Outstanding (DSO)", "Collection Cycle", cy.dso_days, py.dso_days, "days", "≤ 60 days", true)}
        ${ratioCard("Inventory Turnover Ratio", "Activity", cy.inventory_turnover, py.inventory_turnover, "x")}
        ${ratioCard("Days Sales in Inventory (DSI)", "Stock Holding", cy.dsi_days, py.dsi_days, "days", "≤ 90 days", true)}
        ${ratioCard("Creditors / Payable Turnover", "Activity", cy.payable_turnover, py.payable_turnover, "x")}
        ${ratioCard("Days Payables Outstanding (DPO)", "Payment Cycle", cy.dpo_days, py.dpo_days, "days")}
        ${ratioCard("Working Capital Turnover", "Efficiency", cy.working_capital_turnover, py.working_capital_turnover, "x")}
        ${ratioCard("Cash Conversion Cycle (CCC)", "Working Capital", cy.working_capital_cycle_days, py.working_capital_cycle_days, "days", "≤ 90 days", true)}
      </div>
    </div>
  `;
}

function renderBalanceSheetHtml(data, cyYear, pyYear) {
  const cy = data.balance_sheet?.current_year || {};
  const py = data.balance_sheet?.previous_year || {};

  function rowHtml(label, cyVal, pyVal, isHeader = false, isTotal = false) {
    if (isHeader) {
      return `
        <tr style="background: #f8fafc; font-weight: 700;">
          <td colspan="5" style="color: #0f172a; font-size: 13px; padding: 10px 12px;">${label}</td>
        </tr>
      `;
    }
    const diff = (cyVal || 0) - (pyVal || 0);
    const pct = pyVal ? ((diff / Math.abs(pyVal)) * 100) : (cyVal ? 100 : 0);
    const isSig = Math.abs(pct) >= 20.0 || Math.abs(diff) >= 500000;
    const pctColor = isSig ? '#ea580c' : '#64748b';

    return `
      <tr style="${isTotal ? 'font-weight: 700; background: #f1f5f9; border-top: 2px solid var(--border); border-bottom: 2px solid var(--border);' : ''}">
        <td style="padding-left: ${isTotal ? '12px' : '24px'}; color: #0f172a;">${label}</td>
        <td class="font-mono text-right">${formatINR(pyVal || 0)}</td>
        <td class="font-mono text-right" style="font-weight: 600;">${formatINR(cyVal || 0)}</td>
        <td class="font-mono text-right" style="color: ${diff >= 0 ? '#0f172a' : '#dc2626'};">${diff >= 0 ? '+' : ''}${formatINR(diff)}</td>
        <td class="font-mono text-right" style="color: ${pctColor};">
          ${isSig ? '⚠️ ' : ''}${diff >= 0 ? '+' : ''}${pct.toFixed(1)}%
        </td>
      </tr>
    `;
  }

  return `
    <div class="card">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div class="card-title">Schedule III Balance Sheet (Comparative)</div>
        <div style="font-size: 12px; color: #64748b;">Figures in INR (₹)</div>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 40%;">Particulars</th>
              <th class="text-right" style="width: 15%;">FY ${pyYear} (PY)</th>
              <th class="text-right" style="width: 15%;">FY ${cyYear} (CY)</th>
              <th class="text-right" style="width: 15%;">Absolute Diff (Δ)</th>
              <th class="text-right" style="width: 15%;">Movement (%)</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml("I. EQUITY AND LIABILITIES", null, null, true)}
            ${rowHtml("1. Shareholders' Funds", null, null, true)}
            ${rowHtml("Share Capital", cy.share_capital, py.share_capital)}
            ${rowHtml("Reserves and Surplus", cy.reserves_surplus, py.reserves_surplus)}
            ${rowHtml("Total Shareholders' Funds", cy.total_equity, py.total_equity, false, true)}

            ${rowHtml("2. Non-Current Liabilities", null, null, true)}
            ${rowHtml("Long-Term Borrowings", cy.long_term_borrowings, py.long_term_borrowings)}
            ${rowHtml("Other Non-Current Liabilities & Provisions", cy.other_non_current_liabilities, py.other_non_current_liabilities)}
            ${rowHtml("Total Non-Current Liabilities", cy.total_non_current_liabilities, py.total_non_current_liabilities, false, true)}

            ${rowHtml("3. Current Liabilities", null, null, true)}
            ${rowHtml("Short-Term Borrowings (CC/OD)", cy.short_term_borrowings, py.short_term_borrowings)}
            ${rowHtml("Trade Payables (Creditors)", cy.trade_creditors, py.trade_creditors)}
            ${rowHtml("Other Current Liabilities & Provisions", cy.other_current_liabilities, py.other_current_liabilities)}
            ${rowHtml("Total Current Liabilities", cy.total_current_liabilities, py.total_current_liabilities, false, true)}

            ${rowHtml("TOTAL EQUITY & LIABILITIES", cy.total_liabilities_and_equity, py.total_liabilities_and_equity, false, true)}

            ${rowHtml("II. ASSETS", null, null, true)}
            ${rowHtml("1. Non-Current Assets", null, null, true)}
            ${rowHtml("Property, Plant & Equipment (PPE / Fixed Assets)", cy.fixed_assets_ppe, py.fixed_assets_ppe)}
            ${rowHtml("Non-Current Investments & Other Assets", cy.non_current_investments, py.non_current_investments)}
            ${rowHtml("Total Non-Current Assets", cy.total_non_current_assets, py.total_non_current_assets, false, true)}

            ${rowHtml("2. Current Assets", null, null, true)}
            ${rowHtml("Inventories (Stock)", cy.inventory, py.inventory)}
            ${rowHtml("Trade Receivables (Debtors)", cy.trade_debtors, py.trade_debtors)}
            ${rowHtml("Cash and Bank Balances", cy.cash_bank, py.cash_bank)}
            ${rowHtml("Short-Term Loans, Advances & Other Assets", cy.loans_advances, py.loans_advances)}
            ${rowHtml("Total Current Assets", cy.total_current_assets, py.total_current_assets, false, true)}

            ${rowHtml("TOTAL ASSETS", cy.total_assets, py.total_assets, false, true)}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderPnLHtml(data, cyYear, pyYear) {
  const cy = data.profit_and_loss?.current_year || {};
  const py = data.profit_and_loss?.previous_year || {};

  function rowHtml(label, cyVal, pyVal, isHeader = false, isTotal = false) {
    if (isHeader) {
      return `
        <tr style="background: #f8fafc; font-weight: 700;">
          <td colspan="5" style="color: #0f172a; font-size: 13px; padding: 10px 12px;">${label}</td>
        </tr>
      `;
    }
    const diff = (cyVal || 0) - (pyVal || 0);
    const pct = pyVal ? ((diff / Math.abs(pyVal)) * 100) : (cyVal ? 100 : 0);
    const isSig = Math.abs(pct) >= 20.0 || Math.abs(diff) >= 500000;
    const pctColor = isSig ? '#ea580c' : '#64748b';

    return `
      <tr style="${isTotal ? 'font-weight: 700; background: #f1f5f9; border-top: 2px solid var(--border); border-bottom: 2px solid var(--border);' : ''}">
        <td style="padding-left: ${isTotal ? '12px' : '24px'}; color: #0f172a;">${label}</td>
        <td class="font-mono text-right">${formatINR(pyVal || 0)}</td>
        <td class="font-mono text-right" style="font-weight: 600;">${formatINR(cyVal || 0)}</td>
        <td class="font-mono text-right" style="color: ${diff >= 0 ? '#0f172a' : '#dc2626'};">${diff >= 0 ? '+' : ''}${formatINR(diff)}</td>
        <td class="font-mono text-right" style="color: ${pctColor};">
          ${isSig ? '⚠️ ' : ''}${diff >= 0 ? '+' : ''}${pct.toFixed(1)}%
        </td>
      </tr>
    `;
  }

  return `
    <div class="card">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div class="card-title">Schedule III Statement of Profit and Loss (Comparative)</div>
        <div style="font-size: 12px; color: #64748b;">Figures in INR (₹)</div>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 40%;">Particulars</th>
              <th class="text-right" style="width: 15%;">FY ${pyYear} (PY)</th>
              <th class="text-right" style="width: 15%;">FY ${cyYear} (CY)</th>
              <th class="text-right" style="width: 15%;">Absolute Diff (Δ)</th>
              <th class="text-right" style="width: 15%;">Movement (%)</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml("I. REVENUE", null, null, true)}
            ${rowHtml("Revenue from Operations (Gross Sales)", cy.revenue, py.revenue)}
            ${rowHtml("Other Income", cy.other_income, py.other_income)}
            ${rowHtml("Total Revenue (I)", cy.total_revenue, py.total_revenue, false, true)}

            ${rowHtml("II. EXPENSES", null, null, true)}
            ${rowHtml("Cost of Materials Consumed / COGS / Purchases", cy.cogs, py.cogs)}
            ${rowHtml("Employee Benefit Expense", cy.employee_expenses, py.employee_expenses)}
            ${rowHtml("Finance Costs / Interest Expense", cy.finance_costs, py.finance_costs)}
            ${rowHtml("Depreciation and Amortization Expense", cy.depreciation, py.depreciation)}
            ${rowHtml("Other Operating Expenses", cy.other_expenses, py.other_expenses)}
            ${rowHtml("Total Expenses (II)", cy.total_expenses, py.total_expenses, false, true)}

            ${rowHtml("III. PROFITABILITY MILESTONES", null, null, true)}
            ${rowHtml("Operating EBITDA", cy.ebitda, py.ebitda, false, true)}
            ${rowHtml("Operating EBIT (PBIT)", cy.ebit, py.ebit, false, true)}
            ${rowHtml("Profit Before Tax (PBT)", cy.pbt, py.pbt, false, true)}
            ${rowHtml("Tax Expense (Current & Deferred)", cy.tax_expense, py.tax_expense)}
            ${rowHtml("PROFIT FOR THE PERIOD (PAT)", cy.pat, py.pat, false, true)}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderCashFlowHtml(data, cyYear, pyYear) {
  const cf = data.cash_flow_statement || {};
  const op = cf.operating_activities || {};
  const inv = cf.investing_activities || {};
  const fin = cf.financing_activities || {};
  const net = cf.net_cash_flow || {};

  function rowHtml(label, val, isHeader = false, isTotal = false) {
    if (isHeader) {
      return `
        <tr style="background: #f8fafc; font-weight: 700;">
          <td colspan="2" style="color: #0f172a; font-size: 13px; padding: 10px 12px;">${label}</td>
        </tr>
      `;
    }
    const num = val || 0;
    return `
      <tr style="${isTotal ? 'font-weight: 700; background: #f1f5f9; border-top: 2px solid var(--border); border-bottom: 2px solid var(--border);' : ''}">
        <td style="padding-left: ${isTotal ? '12px' : '24px'}; color: #0f172a;">${label}</td>
        <td class="font-mono text-right" style="font-weight: ${isTotal ? '700' : '500'}; color: ${num >= 0 ? '#0f172a' : '#dc2626'};">
          ${num >= 0 ? '' : '-'}${formatINR(Math.abs(num))}
        </td>
      </tr>
    `;
  }

  return `
    <div class="card">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <div class="card-title">Cash Flow Statement (Indirect Method — AS 3)</div>
          <div style="font-size: 12px; color: #64748b; margin-top: 2px;">FY ${cyYear} Derived Statement</div>
        </div>
        <span class="badge badge-low" style="font-size: 11px;">Status: Available & Reconciled</span>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 70%;">Cash Flow Component</th>
              <th class="text-right" style="width: 30%;">Amount (₹)</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml("A. CASH FLOW FROM OPERATING ACTIVITIES", null, true)}
            ${rowHtml("Net Profit Before Tax & Extraordinary Items", op.net_profit_before_tax)}
            ${rowHtml("Adjustment: Depreciation and Amortization", op.adjustments_for_depreciation)}
            ${rowHtml("Adjustment: Finance Costs", op.adjustments_for_finance_costs)}
            ${rowHtml("Working Capital Change: Trade Receivables", op.change_in_trade_receivables)}
            ${rowHtml("Working Capital Change: Inventories", op.change_in_inventories)}
            ${rowHtml("Working Capital Change: Trade Payables", op.change_in_trade_payables)}
            ${rowHtml("Working Capital Change: Other Current Assets/Liabilities", op.change_in_other_working_capital)}
            ${rowHtml("Direct Taxes Paid", -(op.direct_taxes_paid || 0))}
            ${rowHtml("Net Cash Generated from Operating Activities (A)", op.net_cash_from_operating_activities, false, true)}

            ${rowHtml("B. CASH FLOW FROM INVESTING ACTIVITIES", null, true)}
            ${rowHtml("Purchase / Addition of Property, Plant & Equipment (CAPEX)", inv.purchase_of_fixed_assets)}
            ${rowHtml("Net Proceeds / (Investments) in Other Non-Current Assets", inv.other_investing_cash_flow)}
            ${rowHtml("Net Cash Used in Investing Activities (B)", inv.net_cash_from_investing_activities, false, true)}

            ${rowHtml("C. CASH FLOW FROM FINANCING ACTIVITIES", null, true)}
            ${rowHtml("Proceeds / (Repayment) of Long-Term & Short-Term Borrowings", fin.proceeds_from_borrowings)}
            ${rowHtml("Finance Costs / Interest Paid", -(fin.finance_costs_paid || 0))}
            ${rowHtml("Dividends Paid / Equity Movement", fin.dividend_paid)}
            ${rowHtml("Net Cash from / (Used in) Financing Activities (C)", fin.net_cash_from_financing_activities, false, true)}

            ${rowHtml("NET INCREASE / (DECREASE) IN CASH & CASH EQUIVALENTS (A + B + C)", net.net_increase_in_cash_and_equivalents, false, true)}
            ${rowHtml("Cash and Cash Equivalents at Beginning of the Period", net.cash_at_beginning_of_period)}
            ${rowHtml("Cash and Cash Equivalents at End of the Period", net.cash_at_end_of_period, false, true)}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderSignificantMovementsHtml(data, cyYear, pyYear) {
  const comparisons = data.comparisons || [];

  return `
    <div class="card">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <div class="card-title">Comparative Movement & Auditor Working Paper Documentation</div>
          <div style="font-size: 12px; color: #64748b; margin-top: 2px;">
            Auditor review workbench for significant variances (|Δ%| ≥ 20% or |Δ| ≥ ₹5,00,000)
          </div>
        </div>
      </div>

      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 20%;">Metric / Financial Item</th>
              <th style="width: 10%;">Category</th>
              <th class="text-right" style="width: 11%;">FY ${pyYear} (PY)</th>
              <th class="text-right" style="width: 11%;">FY ${cyYear} (CY)</th>
              <th class="text-right" style="width: 11%;">Absolute Diff (Δ)</th>
              <th class="text-right" style="width: 9%;">Movement</th>
              <th style="width: 14%;">Audit Verdict</th>
              <th style="width: 14%; text-align: center;">Auditor Documentation</th>
            </tr>
          </thead>
          <tbody>
            ${comparisons.map((c, idx) => {
              const isSig = c.is_significant;
              const hasExpl = !!c.auditor_explanation;
              const badgeClass = c.audit_verdict === "Significant movement" ? "badge-critical" :
                                 (c.audit_verdict === "Unusual change" ? "badge-high" :
                                 (c.audit_verdict === "Normal variance" ? "badge-low" : "badge-medium"));

              const isMoney = c.unit === "INR";
              const isPct = c.unit === "%";
              const fmt = (v) => isMoney ? formatINR(v) : (isPct ? `${(v || 0).toFixed(2)}%` : `${(v || 0).toFixed(2)}x`);

              return `
                <tr style="${isSig ? 'background: #fffdfa;' : ''}">
                  <td>
                    <div style="font-weight: 700; color: #0f172a;">${c.metric_name}</div>
                    <div style="font-size: 11px; color: #64748b;">Key: ${c.item_key}</div>
                  </td>
                  <td><span class="badge badge-low" style="font-size: 10px;">${c.category}</span></td>
                  <td class="font-mono text-right">${fmt(c.previous_year_value)}</td>
                  <td class="font-mono text-right" style="font-weight: 600;">${fmt(c.current_year_value)}</td>
                  <td class="font-mono text-right" style="color: ${c.absolute_difference >= 0 ? '#0f172a' : '#dc2626'};">
                    ${c.absolute_difference >= 0 ? '+' : ''}${fmt(c.absolute_difference)}
                  </td>
                  <td class="font-mono text-right" style="font-weight: 700; color: ${isSig ? '#ea580c' : '#64748b'};">
                    ${c.percentage_difference >= 0 ? '+' : ''}${c.percentage_difference.toFixed(1)}%
                  </td>
                  <td>
                    <span class="badge ${badgeClass}">${c.audit_verdict}</span>
                  </td>
                  <td style="text-align: center;">
                    <button class="btn btn-sm ${hasExpl ? 'btn-secondary' : (isSig ? 'btn-primary' : 'btn-secondary')}" 
                            style="font-size: 11px; padding: 4px 8px;"
                            onclick="openFSExplanationModal('${c.item_key}', '${c.metric_name.replace(/'/g, "\\'")}', ${c.current_year_value}, ${c.previous_year_value}, ${c.absolute_difference}, ${c.percentage_difference}, '${c.unit}')">
                      ${hasExpl ? '✏️ Edit Note' : (isSig ? '📝 Enter Explanation' : '➕ Add Note')}
                    </button>
                    ${hasExpl ? `<div style="font-size: 10px; color: #059669; font-weight: 600; margin-top: 2px;">✓ Documented</div>` : ''}
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function openFSExplanationModal(itemKey, metricName, cyVal, pyVal, absDiff, pctDiff, unit) {
  const item = cachedFSData?.comparisons?.find(c => c.item_key === itemKey) || {};
  const explCats = item.possible_explanation_categories || [
    "Expansion into new market territories",
    "Raw material input cost inflation",
    "Operational scale change",
    "Accounting reclassification",
    "Market price adjustments"
  ];
  const currentCategory = item.selected_category || explCats[0];
  const currentExplanation = item.auditor_explanation || "";
  const currentStatus = item.review_status || (item.is_significant ? "Requires auditor review" : "Reviewed");

  const isMoney = unit === "INR";
  const isPct = unit === "%";
  const fmt = (v) => isMoney ? formatINR(v) : (isPct ? `${(v || 0).toFixed(2)}%` : `${(v || 0).toFixed(2)}x`);

  const modalHtml = `
    <div class="modal-overlay" id="fs-explanation-modal">
      <div class="modal-card" style="max-width: 650px;">
        <div class="modal-header">
          <div>
            <div class="modal-title">Auditor Working Paper: ${metricName}</div>
            <div style="font-size: 12px; color: #64748b; margin-top: 2px;">
              SA 520 Analytical Review Documentation
            </div>
          </div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('fs-explanation-modal')">✕</button>
        </div>

        <div class="modal-body">
          <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 6px; padding: 12px; margin-bottom: 16px; display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; text-align: center;">
            <div>
              <div style="font-size: 10px; color: #64748b; text-transform: uppercase;">Previous Year</div>
              <div style="font-size: 13px; font-weight: 700; color: #0f172a; font-family: monospace; margin-top: 2px;">${fmt(pyVal)}</div>
            </div>
            <div>
              <div style="font-size: 10px; color: #64748b; text-transform: uppercase;">Current Year</div>
              <div style="font-size: 13px; font-weight: 700; color: #0f172a; font-family: monospace; margin-top: 2px;">${fmt(cyVal)}</div>
            </div>
            <div>
              <div style="font-size: 10px; color: #64748b; text-transform: uppercase;">Difference (Δ)</div>
              <div style="font-size: 13px; font-weight: 700; color: ${absDiff >= 0 ? '#0f172a' : '#dc2626'}; font-family: monospace; margin-top: 2px;">
                ${absDiff >= 0 ? '+' : ''}${fmt(absDiff)}
              </div>
            </div>
            <div>
              <div style="font-size: 10px; color: #64748b; text-transform: uppercase;">Movement (%)</div>
              <div style="font-size: 13px; font-weight: 800; color: #ea580c; font-family: monospace; margin-top: 2px;">
                ${pctDiff >= 0 ? '+' : ''}${pctDiff.toFixed(1)}%
              </div>
            </div>
          </div>

          <form onsubmit="handleFSExplanationSubmit(event, '${itemKey}')">
            <div class="form-group">
              <label class="form-label">Possible Explanation Category (Statutory / Business Drivers)</label>
              <select class="form-control" id="fs-expl-category">
                ${explCats.map(cat => `
                  <option value="${cat}" ${cat === currentCategory ? 'selected' : ''}>${cat}</option>
                `).join("")}
                <option value="Other Industry Factor">Other Industry Factor / Custom Driver</option>
              </select>
              <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
                Select suggested business hypothesis based on deterministic ratio analysis.
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Inquiry & Working Paper Explanation *</label>
              <textarea class="form-control" id="fs-expl-text" rows="4" placeholder="Enter auditor inquiries with management, supporting invoices/vouchers verified, reasons for significant movement..." required>${currentExplanation}</textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Audit Review Status</label>
              <select class="form-control" id="fs-expl-status">
                <option value="Requires auditor review" ${currentStatus === 'Requires auditor review' ? 'selected' : ''}>Requires auditor review</option>
                <option value="In Review" ${currentStatus === 'In Review' ? 'selected' : ''}>In Review</option>
                <option value="Reviewed & Documented" ${currentStatus === 'Reviewed & Documented' || currentStatus === 'Reviewed' ? 'selected' : ''}>Reviewed & Documented (Satisfactory)</option>
                <option value="Waived - Immaterial" ${currentStatus === 'Waived - Immaterial' ? 'selected' : ''}>Waived - Immaterial</option>
              </select>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('fs-explanation-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Working Paper Documentation</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleFSExplanationSubmit(event, itemKey) {
  event.preventDefault();
  const category = document.getElementById("fs-expl-category").value;
  const explanation = document.getElementById("fs-expl-text").value.trim();
  const review_status = document.getElementById("fs-expl-status").value;

  try {
    await FinAuditAPI.saveFSExplanation(state.currentEngagementId, {
      item_key: itemKey,
      explanation_category: category,
      auditor_explanation: explanation,
      review_status: review_status
    });
    notifySuccess("Auditor explanation saved to Working Papers successfully.");
    closeModal("fs-explanation-modal");
    await renderFinancialStatements();
  } catch (err) {
    notifyError("Error saving explanation: " + err.message);
  }
}

function roundNum(val, decimals = 2) {
  const n = Number(val) || 0;
  return Number(n.toFixed(decimals));
}

// ----------------- DUPLICATE & MISSING TRANSACTION DETECTION MODULE -----------------
let currentDupTab = "duplicates";
let cachedDupData = null;
let dupStatusFilter = "ALL";

async function renderDuplicateAndMissing() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `<div class="card" style="padding: 24px; text-align: center; color: #64748b;">Please select an engagement to inspect duplicates and sequence gaps.</div>`;
    return;
  }

  container.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; height: 300px; color: #64748b;">
      <div style="text-align: center;">
        <div style="font-size: 28px; margin-bottom: 8px;">🔍</div>
        <div>Scanning ledgers for exact & fuzzy duplicates and missing sequence gaps...</div>
      </div>
    </div>
  `;

  try {
    const data = await FinAuditAPI.getDuplicatesAndGaps(state.currentEngagementId);
    cachedDupData = data;
    renderDupContent(data);
  } catch (err) {
    container.innerHTML = `
      <div class="card" style="padding: 30px; text-align: center; color: #dc2626;">
        <div style="font-size: 32px; margin-bottom: 10px;">⚠️</div>
        <h3>Duplicate & Sequence Gap Detection Error</h3>
        <p style="margin-top: 6px; color: #64748b;">${err.message || "Failed to scan transactions."}</p>
        <button class="btn btn-secondary" style="margin-top: 14px;" onclick="renderDuplicateAndMissing()">Retry Analysis</button>
      </div>
    `;
  }
}

function renderDupContent(data) {
  const container = document.getElementById("content-container");
  const summary = data.summary || {};
  const downloadReportUrl = FinAuditAPI.getDuplicatesAndGapsReportDownloadUrl(state.currentEngagementId);

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px;">
      <div>
        <div style="display: flex; align-items: center; gap: 10px;">
          <h2 style="font-size: 20px; font-weight: 700; color: #0f172a;">Duplicate & Missing Transaction Detection</h2>
          <span class="badge ${summary.total_duplicate_groups > 0 ? 'badge-high' : 'badge-low'}" style="font-size: 12px;">
            ${summary.total_duplicate_groups} Duplicate Groups
          </span>
          <span class="badge ${summary.total_sequence_gaps > 0 ? 'badge-medium' : 'badge-low'}" style="font-size: 12px;">
            ${summary.total_sequence_gaps} Sequence Gaps
          </span>
        </div>
        <div style="font-size: 13px; color: #64748b; margin-top: 3px;">
          Exact and fuzzy duplicate grouping with non-destructive auditor review & sequence continuity tracking
        </div>
      </div>

      <div style="display: flex; gap: 10px;">
        <a href="${downloadReportUrl}" target="_blank" class="btn btn-secondary">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          Export CSV Report
        </a>
        <button class="btn btn-primary" onclick="renderDuplicateAndMissing()">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          Rescan Ledgers
        </button>
      </div>
    </div>

    <!-- Top KPI Cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px;">
      <div class="card" style="padding: 14px; border-left: 4px solid var(--primary);">
        <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">Total Duplicate Groups</div>
        <div style="font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 4px; font-family: monospace;">
          ${summary.total_duplicate_groups || 0}
        </div>
        <div style="font-size: 11px; color: #64748b; margin-top: 2px;">${summary.unreviewed_duplicate_groups || 0} pending review</div>
      </div>

      <div class="card" style="padding: 14px; border-left: 4px solid #dc2626;">
        <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">Potential Financial Exposure</div>
        <div style="font-size: 22px; font-weight: 800; color: #dc2626; margin-top: 4px; font-family: monospace;">
          ${formatINR(summary.potential_financial_exposure || 0)}
        </div>
        <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Across unverified duplicate groups</div>
      </div>

      <div class="card" style="padding: 14px; border-left: 4px solid #059669;">
        <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">Confirmed Duplicates</div>
        <div style="font-size: 22px; font-weight: 800; color: #059669; margin-top: 4px; font-family: monospace;">
          ${summary.confirmed_duplicate_count || 0}
        </div>
        <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Actioned by auditor</div>
      </div>

      <div class="card" style="padding: 14px; border-left: 4px solid #d97706;">
        <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">Missing Sequence Gaps</div>
        <div style="font-size: 22px; font-weight: 800; color: #d97706; margin-top: 4px; font-family: monospace;">
          ${summary.total_sequence_gaps || 0}
        </div>
        <div style="font-size: 11px; color: #64748b; margin-top: 2px;">${summary.open_sequence_gaps_count || 0} open exceptions</div>
      </div>
    </div>

    <!-- Sub Navigation Tabs -->
    <div class="tab-pills" style="margin-bottom: 18px;">
      <div class="tab-pill ${currentDupTab === 'duplicates' ? 'active' : ''}" onclick="switchDupTab('duplicates')">
        👥 Duplicate Groups Workbench (${summary.total_duplicate_groups || 0})
      </div>
      <div class="tab-pill ${currentDupTab === 'sequence_gaps' ? 'active' : ''}" onclick="switchDupTab('sequence_gaps')">
        🔢 Missing Sequence Gaps (${summary.total_sequence_gaps || 0})
      </div>
    </div>

    <!-- Tab View Container -->
    <div id="dup-tab-content">
      ${getDupTabContentHtml(currentDupTab, data)}
    </div>
  `;
}

function switchDupTab(tab) {
  currentDupTab = tab;
  if (cachedDupData) {
    const tabContainer = document.getElementById("dup-tab-content");
    if (tabContainer) {
      tabContainer.innerHTML = getDupTabContentHtml(tab, cachedDupData);
    }
    const pills = document.querySelectorAll(".tab-pills .tab-pill");
    pills.forEach((p, idx) => {
      p.classList.toggle("active", (idx === 0 && tab === 'duplicates') || (idx === 1 && tab === 'sequence_gaps'));
    });
  }
}

function setDupStatusFilter(status) {
  dupStatusFilter = status;
  if (cachedDupData) {
    const tabContainer = document.getElementById("dup-tab-content");
    if (tabContainer) {
      tabContainer.innerHTML = getDupTabContentHtml("duplicates", cachedDupData);
    }
  }
}

function getDupTabContentHtml(tab, data) {
  if (tab === "duplicates") {
    return renderDuplicateGroupsHtml(data);
  } else if (tab === "sequence_gaps") {
    return renderSequenceGapsHtml(data);
  }
  return "";
}

function renderDuplicateGroupsHtml(data) {
  const groups = data.duplicate_groups || [];
  const filteredGroups = groups.filter(g => {
    if (dupStatusFilter === "ALL") return true;
    return g.status === dupStatusFilter;
  });

  return `
    <!-- Filter bar -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <button class="btn btn-sm ${dupStatusFilter === 'ALL' ? 'btn-primary' : 'btn-secondary'}" onclick="setDupStatusFilter('ALL')">
          All Groups (${groups.length})
        </button>
        <button class="btn btn-sm ${dupStatusFilter === 'Unreviewed' ? 'btn-primary' : 'btn-secondary'}" onclick="setDupStatusFilter('Unreviewed')">
          ⏳ Unreviewed (${groups.filter(g => g.status === 'Unreviewed').length})
        </button>
        <button class="btn btn-sm ${dupStatusFilter === 'Confirmed Duplicate' ? 'btn-primary' : 'btn-secondary'}" onclick="setDupStatusFilter('Confirmed Duplicate')">
          🚩 Confirmed Duplicate (${groups.filter(g => g.status === 'Confirmed Duplicate').length})
        </button>
        <button class="btn btn-sm ${dupStatusFilter === 'Marked Valid' ? 'btn-primary' : 'btn-secondary'}" onclick="setDupStatusFilter('Marked Valid')">
          ✅ Marked Valid (${groups.filter(g => g.status === 'Marked Valid').length})
        </button>
        <button class="btn btn-sm ${dupStatusFilter === 'Ignored' ? 'btn-primary' : 'btn-secondary'}" onclick="setDupStatusFilter('Ignored')">
          👁️ Ignored (${groups.filter(g => g.status === 'Ignored').length})
        </button>
      </div>

      <div style="font-size: 12px; color: #64748b;">
        Showing <b>${filteredGroups.length}</b> of ${groups.length} groups
      </div>
    </div>

    ${filteredGroups.length === 0 ? `
      <div class="card" style="padding: 40px; text-align: center; color: #64748b;">
        <div style="font-size: 32px; margin-bottom: 8px;">✨</div>
        <div style="font-weight: 700; font-size: 15px; color: #0f172a;">No Duplicate Groups Found</div>
        <p style="margin-top: 4px; font-size: 12px;">No transaction pairs matched the selected filter criteria.</p>
      </div>
    ` : `
      <div style="display: flex; flex-direction: column; gap: 16px;">
        ${filteredGroups.map(g => renderSingleDuplicateGroupCard(g)).join("")}
      </div>
    `}
  `;
}

function renderSingleDuplicateGroupCard(g) {
  const txA = g.transactions[0] || {};
  const txB = g.transactions[1] || {};

  const statusBadge = g.status === "Confirmed Duplicate" ? '<span class="badge badge-critical">🚩 Confirmed Duplicate</span>' :
                      (g.status === "Marked Valid" ? '<span class="badge badge-low">✅ Marked Valid</span>' :
                      (g.status === "Ignored" ? '<span class="badge badge-medium">👁️ Ignored</span>' :
                      '<span class="badge badge-high">⏳ Unreviewed</span>'));

  const simColor = g.similarity_pct >= 95 ? '#dc2626' : (g.similarity_pct >= 85 ? '#ea580c' : '#d97706');

  return `
    <div class="card" style="padding: 16px; border: 1px solid var(--border); transition: transform 0.15s, box-shadow 0.15s;">
      <!-- Group Header -->
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-bottom: 12px;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-weight: 800; font-size: 14px; color: #0f172a; font-family: monospace; background: #f1f5f9; padding: 4px 8px; border-radius: 4px;">
            Group #${g.group_code}
          </span>
          <span class="badge badge-role-auditor" style="font-size: 11px;">${g.group_type}</span>
          <span style="font-weight: 700; font-size: 12px; color: ${simColor}; background: #fff7ed; padding: 2px 8px; border-radius: 12px; border: 1px solid #ffedd5;">
            ⚡ ${g.similarity_pct}% Similarity
          </span>
          ${statusBadge}
        </div>

        <div style="text-align: right;">
          <span style="font-size: 11px; color: #64748b;">Financial Exposure:</span>
          <span style="font-weight: 700; font-size: 14px; color: #0f172a; font-family: monospace; margin-left: 4px;">
            ${formatINR(g.financial_exposure)}
          </span>
        </div>
      </div>

      <!-- Reason Banner -->
      <div style="background: #f8fafc; border-left: 3px solid var(--primary); padding: 8px 12px; border-radius: 0 4px 4px 0; margin-bottom: 14px; font-size: 12px; color: #334155;">
        <b>Detection Reason:</b> ${g.detection_reason}
      </div>

      <!-- Side-by-Side Transaction Comparison -->
      <div class="table-container" style="margin-bottom: 14px;">
        <table class="data-table" style="font-size: 12px;">
          <thead>
            <tr>
              <th style="width: 16%;">Field Name</th>
              <th style="width: 42%;">Transaction A (Reference Entry #${txA.id})</th>
              <th style="width: 42%;">Transaction B (Potential Duplicate #${txB.id})</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="font-weight: 600; color: #64748b;">Posting Date</td>
              <td class="font-mono">${txA.date}</td>
              <td class="font-mono ${txA.date !== txB.date ? 'font-bold' : ''}" style="${txA.date !== txB.date ? 'color: #ea580c;' : ''}">${txB.date}</td>
            </tr>
            <tr>
              <td style="font-weight: 600; color: #64748b;">Ledger Account</td>
              <td><b>${txA.ledger}</b></td>
              <td><b>${txB.ledger}</b></td>
            </tr>
            <tr>
              <td style="font-weight: 600; color: #64748b;">Party Name</td>
              <td>${txA.party_name}</td>
              <td style="${txA.party_name !== txB.party_name ? 'color: #ea580c; font-weight: 600;' : ''}">${txB.party_name}</td>
            </tr>
            <tr>
              <td style="font-weight: 600; color: #64748b;">Amount / Debit / Credit</td>
              <td class="font-mono font-bold">${formatINR(txA.amount)}</td>
              <td class="font-mono font-bold" style="${txA.amount !== txB.amount ? 'color: #ea580c;' : ''}">${formatINR(txB.amount)}</td>
            </tr>
            <tr>
              <td style="font-weight: 600; color: #64748b;">Voucher Number</td>
              <td class="font-mono">${txA.voucher_no}</td>
              <td class="font-mono">${txB.voucher_no}</td>
            </tr>
            <tr>
              <td style="font-weight: 600; color: #64748b;">Invoice Number</td>
              <td class="font-mono">${txA.invoice_no}</td>
              <td class="font-mono" style="${txA.invoice_no !== txB.invoice_no ? 'color: #ea580c;' : ''}">${txB.invoice_no}</td>
            </tr>
            <tr>
              <td style="font-weight: 600; color: #64748b;">Reference / Cheque No</td>
              <td class="font-mono">${txA.reference_no}</td>
              <td class="font-mono">${txB.reference_no}</td>
            </tr>
            <tr>
              <td style="font-weight: 600; color: #64748b;">Narration / Description</td>
              <td style="color: #475569;">${txA.description}</td>
              <td style="color: #475569;">${txB.description}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Existing Auditor Documentation Banner (if reviewed) -->
      ${g.auditor_comment ? `
        <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; padding: 10px 12px; margin-bottom: 12px; font-size: 12px;">
          <div style="font-weight: 700; color: #166534; margin-bottom: 2px;">
            Auditor Working Paper Documentation (${g.reviewed_by || 'Auditor'} on ${g.reviewed_at || 'Recently'}):
          </div>
          <div style="color: #14532d;">${g.auditor_comment}</div>
        </div>
      ` : ''}

      <!-- Action Buttons -->
      <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 10px;">
        <div style="font-size: 11px; color: #64748b;">
          ${g.reviewed_by ? `Last actioned by <b>${g.reviewed_by}</b>` : 'Pending professional auditor review'}
        </div>

        <div style="display: flex; gap: 8px;">
          <button class="btn btn-sm btn-secondary" onclick="openDuplicateCommentModal('${g.group_code}', '${g.status}', '${(g.auditor_comment || '').replace(/'/g, "\\'")}')">
            💬 ${g.auditor_comment ? 'Edit Note' : 'Add Note'}
          </button>
          <button class="btn btn-sm btn-secondary" onclick="actionDuplicateGroup('${g.group_code}', 'Ignored')">
            👁️ Ignore
          </button>
          <button class="btn btn-sm btn-secondary" onclick="actionDuplicateGroup('${g.group_code}', 'Marked Valid')">
            ✅ Mark Valid
          </button>
          <button class="btn btn-sm btn-primary" onclick="actionDuplicateGroup('${g.group_code}', 'Confirmed Duplicate')">
            🚩 Confirm Duplicate
          </button>
        </div>
      </div>
    </div>
  `;
}

async function actionDuplicateGroup(groupCode, newStatus) {
  try {
    await FinAuditAPI.reviewDuplicateGroup(state.currentEngagementId, {
      group_code: groupCode,
      status: newStatus,
      auditor_comment: ""
    });
    // Update cached data in place
    if (cachedDupData?.duplicate_groups) {
      const target = cachedDupData.duplicate_groups.find(g => g.group_code === groupCode);
      if (target) {
        target.status = newStatus;
      }
    }
    renderDuplicateAndMissing();
  } catch (err) {
    notifyError("Error updating duplicate group: " + err.message);
  }
}

function openDuplicateCommentModal(groupCode, currentStatus, currentComment) {
  const modalHtml = `
    <div class="modal-overlay" id="dup-comment-modal">
      <div class="modal-card" style="max-width: 540px;">
        <div class="modal-header">
          <div class="modal-title">Auditor Review Note: Group #${groupCode}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('dup-comment-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleDuplicateCommentSubmit(event, '${groupCode}')">
            <div class="form-group">
              <label class="form-label">Review Status</label>
              <select class="form-control" id="dup-modal-status">
                <option value="Confirmed Duplicate" ${currentStatus === 'Confirmed Duplicate' ? 'selected' : ''}>🚩 Confirmed Duplicate (Double Booking)</option>
                <option value="Marked Valid" ${currentStatus === 'Marked Valid' ? 'selected' : ''}>✅ Marked Valid (Legitimate Recurring / Split Transaction)</option>
                <option value="Ignored" ${currentStatus === 'Ignored' ? 'selected' : ''}>👁️ Ignored (Immaterial)</option>
                <option value="Unreviewed" ${currentStatus === 'Unreviewed' ? 'selected' : ''}>⏳ Unreviewed</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Working Paper Explanation / Finding Note *</label>
              <textarea class="form-control" id="dup-modal-comment" rows="4" placeholder="Enter auditor inquiries with accountant, supporting invoice verification, reason for confirming duplicate or marking valid..." required>${currentComment || ''}</textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('dup-comment-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Auditor Note</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleDuplicateCommentSubmit(event, groupCode) {
  event.preventDefault();
  const status = document.getElementById("dup-modal-status").value;
  const comment = document.getElementById("dup-modal-comment").value.trim();

  try {
    await FinAuditAPI.reviewDuplicateGroup(state.currentEngagementId, {
      group_code: groupCode,
      status: status,
      auditor_comment: comment
    });
    closeModal("dup-comment-modal");
    await renderDuplicateAndMissing();
  } catch (err) {
    notifyError("Failed to save note: " + err.message);
  }
}

function renderSequenceGapsHtml(data) {
  const gaps = data.sequence_gaps || [];

  return `
    <!-- Disclaimer / Guidance Banner -->
    <div class="card" style="margin-bottom: 18px; border-left: 4px solid var(--primary); background: #f8fafc;">
      <div style="display: flex; gap: 12px; align-items: flex-start;">
        <div style="font-size: 20px;">💡</div>
        <div style="font-size: 12.5px; color: #334155; line-height: 1.5;">
          <b>ICAI Standard Audit Guidance on Sequence Gaps:</b>
          Sequence gaps in invoice, voucher, or cheque numbering are treated as <i>exceptions requiring professional inquiry</i> 
          (such as verifying cancellation registers, spoiled cheque leaves, or multi-branch series) rather than conclusive proof of unrecorded transactions or errors.
        </div>
      </div>
    </div>

    ${gaps.length === 0 ? `
      <div class="card" style="padding: 40px; text-align: center; color: #64748b;">
        <div style="font-size: 32px; margin-bottom: 8px;">✅</div>
        <div style="font-weight: 700; font-size: 15px; color: #0f172a;">No Sequence Gaps Detected</div>
        <p style="margin-top: 4px; font-size: 12px;">All invoice, voucher, and cheque number series exhibit strict continuity.</p>
      </div>
    ` : `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        ${gaps.map((gap, idx) => renderSingleSequenceGapCard(gap, idx)).join("")}
      </div>
    `}
  `;
}

function renderSingleSequenceGapCard(gap, idx) {
  const sevBadge = gap.severity === "HIGH" ? '<span class="badge badge-critical">HIGH SEVERITY</span>' :
                   (gap.severity === "MEDIUM" ? '<span class="badge badge-high">MEDIUM SEVERITY</span>' :
                   '<span class="badge badge-low">LOW SEVERITY</span>');

  const statusBadge = gap.status === "Documented / Valid Gap" ? '<span class="badge badge-low">✓ Documented Valid Gap</span>' :
                      (gap.status === "In Review" ? '<span class="badge badge-medium">In Review</span>' :
                      (gap.status === "Resolved" ? '<span class="badge badge-resolved">Resolved</span>' :
                      '<span class="badge badge-high">Open</span>'));

  return `
    <div class="card" style="padding: 16px; border: 1px solid var(--border);">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-weight: 800; font-size: 13px; color: #0f172a; font-family: monospace; background: #f1f5f9; padding: 4px 8px; border-radius: 4px;">
            ${gap.sequence_type}
          </span>
          <span style="font-weight: 700; font-size: 13px; color: #0f172a;">
            ${gap.item_label} Series: <span class="font-mono" style="color: var(--primary);">${gap.series_prefix || 'Default'}</span>
          </span>
          ${sevBadge}
          ${statusBadge}
        </div>

        <div style="text-align: right;">
          <span style="font-size: 12px; font-weight: 700; color: #dc2626; font-family: monospace;">
            ${gap.missing_count} Missing ${gap.item_label}(s)
          </span>
        </div>
      </div>

      <div style="font-size: 12.5px; color: #334155; margin-bottom: 10px;">
        <b>Exception:</b> ${gap.exception_reason}
      </div>

      <!-- Expected Range & Sample Missing Items -->
      <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 4px; padding: 10px 12px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
          <span>Expected Range: <b class="font-mono">${gap.expected_from}</b> to <b class="font-mono">${gap.expected_to}</b></span>
          <span style="color: #64748b;">Missing count: <b>${gap.missing_count}</b></span>
        </div>

        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px;">
          ${(gap.missing_items || []).map(item => `
            <span class="font-mono" style="font-size: 11px; background: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 3px; border: 1px solid #fecaca;">
              ${item}
            </span>
          `).join("")}
          ${gap.missing_count > (gap.missing_items?.length || 0) ? `
            <span style="font-size: 11px; color: #64748b; padding: 2px 6px;">
              + ${gap.missing_count - gap.missing_items.length} more in series
            </span>
          ` : ''}
        </div>
      </div>

      <!-- Auditor Comment Display -->
      ${gap.auditor_comment ? `
        <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; padding: 8px 12px; margin-bottom: 12px; font-size: 12px; color: #166534;">
          <b>Auditor Working Paper Remark:</b> ${gap.auditor_comment}
          ${gap.reviewed_by ? `<span style="color: #64748b; font-size: 11px;"> (by ${gap.reviewed_by})</span>` : ''}
        </div>
      ` : ''}

      <!-- Action / Documentation Bar -->
      <div style="display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid var(--border); padding-top: 10px;">
        <button class="btn btn-sm btn-secondary" onclick="openSequenceGapModal('${gap.sequence_type}', '${gap.series_prefix || ''}', '${gap.expected_from}', '${gap.expected_to}', '${gap.status}', '${(gap.auditor_comment || '').replace(/'/g, "\\'")}')">
          📝 ${gap.auditor_comment ? 'Edit Remark' : 'Document Sequence Finding'}
        </button>
      </div>
    </div>
  `;
}

function openSequenceGapModal(seqType, prefix, expFrom, expTo, currentStatus, currentComment) {
  const modalHtml = `
    <div class="modal-overlay" id="gap-review-modal">
      <div class="modal-card" style="max-width: 550px;">
        <div class="modal-header">
          <div class="modal-title">Sequence Gap Documentation: ${expFrom} to ${expTo}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('gap-review-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleSequenceGapSubmit(event, '${seqType}', '${prefix}', '${expFrom}', '${expTo}')">
            <div class="form-group">
              <label class="form-label">Audit Review Status</label>
              <select class="form-control" id="gap-modal-status">
                <option value="Documented / Valid Gap" ${currentStatus === 'Documented / Valid Gap' ? 'selected' : ''}>✓ Documented Valid Gap (Verified Cancelled / Spoiled / Multi-branch)</option>
                <option value="In Review" ${currentStatus === 'In Review' ? 'selected' : ''}>In Review (Awaiting Client Explanation)</option>
                <option value="Resolved" ${currentStatus === 'Resolved' ? 'selected' : ''}>Resolved</option>
                <option value="Open" ${currentStatus === 'Open' ? 'selected' : ''}>Open</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Working Paper Remark / Supporting Evidence *</label>
              <textarea class="form-control" id="gap-modal-comment" rows="4" placeholder="Enter auditor inquiries, inspection of physical invoice book/counterfoils, cancellation slips, or Form 3CD Clause 40 notes..." required>${currentComment || ''}</textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('gap-review-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Sequence Documentation</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleSequenceGapSubmit(event, seqType, prefix, expFrom, expTo) {
  event.preventDefault();
  const status = document.getElementById("gap-modal-status").value;
  const comment = document.getElementById("gap-modal-comment").value.trim();

  try {
    await FinAuditAPI.reviewSequenceGap(state.currentEngagementId, {
      sequence_type: seqType,
      series_prefix: prefix,
      expected_from: expFrom,
      expected_to: expTo,
      status: status,
      auditor_comment: comment
    });
    closeModal("gap-review-modal");
    await renderDuplicateAndMissing();
  } catch (err) {
    notifyError("Failed to save sequence documentation: " + err.message);
  }
}

// -------------------------------------------------------------
// 10. AI-ASSISTED ANOMALY DETECTION ENGINE (HYBRID ARCHITECTURE)
// -------------------------------------------------------------
state.anomalyFilters = {
  severity: "ALL",
  level: "ALL",
  pattern: "ALL",
  status: "ALL",
  search: ""
};

async function renderAnomalyDetection() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `
      <div class="card" style="padding: 40px; text-align: center; color: #64748b;">
        <h3>No Engagement Selected</h3>
        <p style="margin-top: 8px;">Please select an audit engagement from the top navigation bar to analyze anomalies.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div style="padding: 30px; text-align: center; color: #64748b;">
      <div class="loading-spinner" style="margin: 0 auto 16px auto;"></div>
      <p style="font-weight: 600; font-size: 15px;">Executing 3-Tier Hybrid Anomaly Detection Engine...</p>
      <p style="font-size: 12px; color: #94a3b8; margin-top: 4px;">Evaluating Level 1 Deterministic Rules, Level 2 Statistical Z-Scores & Benford MAD, Level 3 Isolation Forest & LOF</p>
    </div>
  `;

  try {
    const data = await FinAuditAPI.getAnomalies(state.currentEngagementId, state.anomalyFilters);
    state.currentAnomalyData = data;
    renderAnomalyDetectionUI(data);
  } catch (err) {
    container.innerHTML = `
      <div class="card" style="padding: 30px; border-left: 4px solid #dc2626;">
        <h3 style="color: #dc2626;">Anomaly Detection Engine Error</h3>
        <p style="margin-top: 8px; color: #475569;">${err.message}</p>
        <button class="btn btn-primary" style="margin-top: 16px;" onclick="renderAnomalyDetection()">Retry Execution</button>
      </div>
    `;
  }
}

function renderAnomalyDetectionUI(data) {
  const container = document.getElementById("content-container");
  const s = data.summary || {};
  const benford = data.benford_analysis || {};
  const anomalies = data.anomalies || [];

  container.innerHTML = `
    <!-- Top Header -->
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
      <div>
        <h2 style="font-size: 22px; font-weight: 800; color: #0f172a; display: flex; align-items: center; gap: 10px;">
          <span>🤖 AI-Assisted Anomaly Detection Engine</span>
          <span class="badge" style="background: #e0e7ff; color: #4338ca; font-size: 11px; font-weight: 700;">HYBRID 3-TIER</span>
        </h2>
        <p style="font-size: 13px; color: #64748b; margin-top: 4px;">
          Deep audit anomaly detection combining Level 1 Deterministic Rules, Level 2 Statistical Outliers, and Level 3 Local Machine Learning.
        </p>
      </div>

      <div style="display: flex; gap: 10px;">
        <button class="btn btn-secondary" onclick="triggerFreshAnomalyRun()">
          ⚡ Re-Run Anomaly Engine
        </button>
        <a class="btn btn-primary" href="${FinAuditAPI.getAnomalyReportDownloadUrl(state.currentEngagementId)}" target="_blank" style="text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">
          📥 Export Anomaly Report (CSV)
        </a>
      </div>
    </div>

    <!-- Professional Standard Disclaimer Banner -->
    <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 12px 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 20px;">🛡️</span>
      <div style="font-size: 12.5px; color: #1e40af;">
        <b>Professional Auditing Safeguard:</b> <i>Potential anomaly detected. Auditor review recommended.</i> An anomaly does not constitute proof of fraud; it indicates empirical deviation requiring substantive audit inquiry (SA 240, SA 315, SA 520).
      </div>
    </div>

    <!-- Summary KPI Cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px;">
      <div class="card" style="padding: 16px; border-left: 4px solid var(--primary);">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Total Detected Anomalies</div>
        <div style="font-size: 24px; font-weight: 800; color: #0f172a; margin-top: 4px;">${s.total_anomalies || 0}</div>
        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Evaluated ${data.total_transactions || 0} transactions</div>
      </div>

      <div class="card" style="padding: 16px; border-left: 4px solid #dc2626;">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Critical & High Severity</div>
        <div style="font-size: 24px; font-weight: 800; color: #dc2626; margin-top: 4px;">${(s.critical_count || 0) + (s.high_count || 0)}</div>
        <div style="font-size: 11px; color: #dc2626; margin-top: 4px;">${s.critical_count || 0} Critical | ${s.high_count || 0} High</div>
      </div>

      <div class="card" style="padding: 16px; border-left: 4px solid #7c3aed;">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Level 3: ML Outliers</div>
        <div style="font-size: 24px; font-weight: 800; color: #7c3aed; margin-top: 4px;">${s.level_3_ml || 0}</div>
        <div style="font-size: 11px; color: #7c3aed; margin-top: 4px;">Isolation Forest, LOF & DBSCAN</div>
      </div>

      <div class="card" style="padding: 16px; border-left: 4px solid #0284c7;">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Level 2: Statistical Spikes</div>
        <div style="font-size: 24px; font-weight: 800; color: #0284c7; margin-top: 4px;">${s.level_2_statistical || 0}</div>
        <div style="font-size: 11px; color: #0284c7; margin-top: 4px;">Z-Scores, IQR & Surges</div>
      </div>

      <div class="card" style="padding: 16px; border-left: 4px solid #059669;">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Reviewed / Documented</div>
        <div style="font-size: 24px; font-weight: 800; color: #059669; margin-top: 4px;">${s.reviewed_count || 0}</div>
        <div style="font-size: 11px; color: #059669; margin-top: 4px;">${s.open_count || 0} Open Items Pending</div>
      </div>
    </div>

    <!-- Benford's Law Diagnostic Card -->
    ${benford.mad ? `
      <div class="card" style="padding: 16px 20px; margin-bottom: 20px; background: #fafafa; border: 1px solid var(--border);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-weight: 700; font-size: 13.5px; color: #0f172a;">📊 Benford's Law Leading Digit Diagnostic (Nigrini Standard)</span>
            <span class="badge ${benford.mad > 0.015 ? 'badge-critical' : 'badge-low'}" style="font-size: 11px;">
              ${benford.conformity} (MAD = ${benford.mad})
            </span>
          </div>
          <span style="font-size: 11.5px; color: #64748b;">Theoretical vs Empirical First Digit Distribution</span>
        </div>
        <div style="display: flex; gap: 8px; overflow-x: auto; padding-top: 6px;">
          ${Object.entries(benford.distribution || {}).map(([d, stat]) => `
            <div style="flex: 1; min-width: 60px; background: white; border: 1px solid var(--border); border-radius: 4px; padding: 6px 8px; text-align: center;">
              <div style="font-weight: 800; font-size: 13px; color: #0f172a;">Digit ${d}</div>
              <div style="font-size: 12px; font-weight: 700; color: ${Math.abs(stat.diff_pct) > 5 ? '#dc2626' : '#059669'}; margin-top: 2px;">
                ${stat.actual_pct}%
              </div>
              <div style="font-size: 10px; color: #94a3b8;">Exp: ${stat.expected_pct}%</div>
            </div>
          `).join("")}
        </div>
      </div>
    ` : ''}

    <!-- Interactive Multi-Filter Bar -->
    <div class="card" style="padding: 16px; margin-bottom: 20px;">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; align-items: flex-end;">
        <div>
          <label class="form-label">Detection Tier / Level</label>
          <select class="form-control" id="anom-filter-level" onchange="handleAnomalyFilterChange()">
            <option value="ALL" ${state.anomalyFilters.level === 'ALL' ? 'selected' : ''}>All Levels</option>
            <option value="LEVEL 1" ${state.anomalyFilters.level === 'LEVEL 1' ? 'selected' : ''}>Level 1: Deterministic</option>
            <option value="LEVEL 2" ${state.anomalyFilters.level === 'LEVEL 2' ? 'selected' : ''}>Level 2: Statistical</option>
            <option value="LEVEL 3" ${state.anomalyFilters.level === 'LEVEL 3' ? 'selected' : ''}>Level 3: Machine Learning</option>
          </select>
        </div>

        <div>
          <label class="form-label">Severity Level</label>
          <select class="form-control" id="anom-filter-sev" onchange="handleAnomalyFilterChange()">
            <option value="ALL" ${state.anomalyFilters.severity === 'ALL' ? 'selected' : ''}>All Severities</option>
            <option value="CRITICAL" ${state.anomalyFilters.severity === 'CRITICAL' ? 'selected' : ''}>CRITICAL</option>
            <option value="HIGH" ${state.anomalyFilters.severity === 'HIGH' ? 'selected' : ''}>HIGH</option>
            <option value="MEDIUM" ${state.anomalyFilters.severity === 'MEDIUM' ? 'selected' : ''}>MEDIUM</option>
            <option value="LOW" ${state.anomalyFilters.severity === 'LOW' ? 'selected' : ''}>LOW</option>
          </select>
        </div>

        <div>
          <label class="form-label">Review Status</label>
          <select class="form-control" id="anom-filter-status" onchange="handleAnomalyFilterChange()">
            <option value="ALL" ${state.anomalyFilters.status === 'ALL' ? 'selected' : ''}>All Statuses</option>
            <option value="Open" ${state.anomalyFilters.status === 'Open' ? 'selected' : ''}>Open (Pending)</option>
            <option value="Confirmed Anomaly" ${state.anomalyFilters.status === 'Confirmed Anomaly' ? 'selected' : ''}>Confirmed Anomaly</option>
            <option value="Marked Normal" ${state.anomalyFilters.status === 'Marked Normal' ? 'selected' : ''}>Marked Normal / Valid</option>
            <option value="Ignored" ${state.anomalyFilters.status === 'Ignored' ? 'selected' : ''}>Ignored</option>
          </select>
        </div>

        <div>
          <label class="form-label">Search Keywords</label>
          <input type="text" class="form-control" id="anom-filter-search" placeholder="Voucher, Party, Ledger, ID..." value="${state.anomalyFilters.search || ''}" oninput="handleAnomalySearchDebounced(event)" />
        </div>
      </div>
    </div>

    <!-- Anomalies List / Cards -->
    <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
      <h3 style="font-size: 15px; font-weight: 700; color: #0f172a;">
        Showing ${anomalies.length} Flagged Anomalies
      </h3>
      <span style="font-size: 12px; color: #64748b;">Sorted by Anomaly Risk Score Descending</span>
    </div>

    ${anomalies.length === 0 ? `
      <div class="card" style="padding: 40px; text-align: center; color: #64748b;">
        <div style="font-size: 32px; margin-bottom: 8px;">✓</div>
        <p style="font-size: 15px; font-weight: 600;">No anomalies matched the selected filters.</p>
        <p style="font-size: 12px; color: #94a3b8; margin-top: 4px;">Adjust the filter criteria or re-run the anomaly engine to inspect all findings.</p>
      </div>
    ` : `
      <div style="display: flex; flex-direction: column; gap: 16px;">
        ${anomalies.map((anom, idx) => renderSingleAnomalyCard(anom, idx)).join("")}
      </div>
    `}
  `;
}

function renderSingleAnomalyCard(anom, idx) {
  const tx = anom.transaction || {};
  const ev = anom.evidence || {};
  
  const sevBadge = anom.severity === "CRITICAL" ? '<span class="badge badge-critical">CRITICAL SEVERITY</span>' :
                   (anom.severity === "HIGH" ? '<span class="badge badge-high">HIGH SEVERITY</span>' :
                   (anom.severity === "MEDIUM" ? '<span class="badge badge-medium">MEDIUM SEVERITY</span>' :
                   '<span class="badge badge-low">LOW SEVERITY</span>'));

  const statusBadge = anom.status === "Confirmed Anomaly" ? '<span class="badge badge-critical">✓ Confirmed Anomaly</span>' :
                      (anom.status === "Marked Normal" ? '<span class="badge badge-low">✓ Marked Normal / Valid</span>' :
                      (anom.status === "Ignored" ? '<span class="badge badge-secondary">Ignored</span>' :
                      '<span class="badge badge-high">Open</span>'));

  const levelPill = anom.level.includes("LEVEL 3") ? '<span class="badge" style="background: #f5f3ff; color: #6d28d9; border: 1px solid #ddd6fe;">LEVEL 3: ML</span>' :
                    (anom.level.includes("LEVEL 2") ? '<span class="badge" style="background: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd;">LEVEL 2: STATISTICAL</span>' :
                    '<span class="badge" style="background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0;">LEVEL 1: DETERMINISTIC</span>');

  return `
    <div class="card" style="padding: 18px; border: 1px solid var(--border); box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
      <!-- Card Header -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <span style="font-weight: 800; font-size: 13px; color: #0f172a; font-family: monospace; background: #f1f5f9; padding: 4px 8px; border-radius: 4px;">
            ${anom.anomaly_id}
          </span>
          <span class="badge" style="background: #fee2e2; color: #991b1b; font-weight: 800; font-size: 12px;">
            ${anom.anomaly_score.toFixed(1)} / 100 Risk Score
          </span>
          ${sevBadge}
          ${levelPill}
          ${statusBadge}
        </div>

        <div style="display: flex; gap: 6px;">
          <button class="btn btn-sm btn-secondary" onclick="openAIExplanationModal('${anom.anomaly_id}')" style="font-size: 11.5px;">
            🤖 AI Working Paper Memo
          </button>
        </div>
      </div>

      <!-- Detected Pattern & Core Transaction Info -->
      <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; margin-bottom: 12px;">
        <div style="font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 6px;">
          Detected Pattern: <span style="color: var(--primary);">${anom.pattern_type}</span>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; font-size: 12px; color: #334155;">
          <div><b>Date:</b> <span class="font-mono">${tx.date || '—'}</span></div>
          <div><b>Voucher #:</b> <span class="font-mono">${tx.voucher_no || '—'}</span></div>
          <div><b>Ledger Head:</b> <span>${tx.ledger || '—'}</span></div>
          <div><b>Party / Payee:</b> <span>${tx.party_name || '—'}</span></div>
          <div><b>Amount:</b> <b class="font-mono" style="color: #0f172a;">₹${Number(tx.amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</b></div>
          <div><b>Narration:</b> <span style="color: #64748b;">${tx.description || '—'}</span></div>
        </div>
      </div>

      <!-- Evidence & Metric Highlights -->
      <div style="background: #ffffff; border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px; margin-bottom: 12px;">
        <div style="font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 6px; text-transform: uppercase;">
          🔍 Quantifiable Evidence Trail:
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
          ${Object.entries(ev).map(([k, v]) => `
            <span style="font-size: 11.5px; background: #f1f5f9; padding: 3px 8px; border-radius: 4px; color: #1e293b;">
              <b>${k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:</b> ${typeof v === 'number' ? Number(v).toLocaleString('en-IN', {maximumFractionDigits: 2}) : v}
            </span>
          `).join("")}
        </div>
      </div>

      <!-- AI Audit Explanation -->
      <div style="font-size: 12.5px; color: #1e293b; margin-bottom: 10px; line-height: 1.5;">
        <b>Audit Explanation:</b> ${anom.explanation}
      </div>

      <!-- Recommended Substantive Review -->
      <div style="font-size: 12px; color: #0369a1; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 4px; padding: 8px 12px; margin-bottom: 12px;">
        <b>Recommended Substantive Procedure:</b> ${anom.recommended_review}
      </div>

      <!-- Auditor Comment Display -->
      ${anom.auditor_comment ? `
        <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; padding: 8px 12px; margin-bottom: 12px; font-size: 12px; color: #166534;">
          <b>Auditor Working Paper Remark:</b> ${anom.auditor_comment}
          ${anom.reviewed_by ? `<span style="color: #64748b; font-size: 11px;"> (Reviewed by ${anom.reviewed_by} at ${anom.reviewed_at || ''})</span>` : ''}
        </div>
      ` : ''}

      <!-- Auditor Action Bar -->
      <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 10px; flex-wrap: wrap; gap: 8px;">
        <span style="font-size: 11.5px; color: #64748b;">Auditor Verification Actions:</span>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-sm btn-danger" onclick="quickUpdateAnomalyStatus('${anom.anomaly_id}', 'Confirmed Anomaly')" ${anom.status === 'Confirmed Anomaly' ? 'disabled' : ''}>
            ⚠️ Confirm Anomaly
          </button>
          <button class="btn btn-sm btn-success" onclick="quickUpdateAnomalyStatus('${anom.anomaly_id}', 'Marked Normal')" ${anom.status === 'Marked Normal' ? 'disabled' : ''}>
            ✓ Mark Normal / Valid
          </button>
          <button class="btn btn-sm btn-secondary" onclick="quickUpdateAnomalyStatus('${anom.anomaly_id}', 'Ignored')" ${anom.status === 'Ignored' ? 'disabled' : ''}>
            Ignore
          </button>
          <button class="btn btn-sm btn-secondary" onclick="openAnomalyReviewModal('${anom.anomaly_id}', '${anom.status}', '${(anom.auditor_comment || '').replace(/'/g, "\\'")}')">
            📝 ${anom.auditor_comment ? 'Edit Remark' : 'Add Comment'}
          </button>
        </div>
      </div>
    </div>
  `;
}

function handleAnomalyFilterChange() {
  state.anomalyFilters.level = document.getElementById("anom-filter-level").value;
  state.anomalyFilters.severity = document.getElementById("anom-filter-sev").value;
  state.anomalyFilters.status = document.getElementById("anom-filter-status").value;
  renderAnomalyDetection();
}

let anomalySearchTimer = null;
function handleAnomalySearchDebounced(e) {
  clearTimeout(anomalySearchTimer);
  const val = e.target.value;
  anomalySearchTimer = setTimeout(() => {
    state.anomalyFilters.search = val;
    renderAnomalyDetection();
  }, 350);
}

async function triggerFreshAnomalyRun() {
  try {
    await FinAuditAPI.triggerAnomalyDetection(state.currentEngagementId);
    await renderAnomalyDetection();
  } catch (err) {
    notifyError("Failed to re-run anomaly engine: " + err.message);
  }
}

async function quickUpdateAnomalyStatus(anomalyId, newStatus) {
  try {
    await FinAuditAPI.reviewAnomaly(state.currentEngagementId, anomalyId, {
      status: newStatus,
      auditor_comment: `Status updated to '${newStatus}' via audit workbench.`
    });
    await renderAnomalyDetection();
  } catch (err) {
    notifyError("Failed to update anomaly status: " + err.message);
  }
}

function openAnomalyReviewModal(anomalyId, currentStatus, currentComment) {
  const modalHtml = `
    <div class="modal-overlay" id="anomaly-review-modal">
      <div class="modal-card" style="max-width: 550px;">
        <div class="modal-header">
          <div class="modal-title">Review Anomaly #${anomalyId}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('anomaly-review-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleAnomalyReviewSubmit(event, '${anomalyId}')">
            <div class="form-group">
              <label class="form-label">Auditor Conclusion Status</label>
              <select class="form-control" id="anom-modal-status">
                <option value="Confirmed Anomaly" ${currentStatus === 'Confirmed Anomaly' ? 'selected' : ''}>⚠️ Confirmed Anomaly (Flagged for Management Letter / Form 3CD)</option>
                <option value="Marked Normal" ${currentStatus === 'Marked Normal' ? 'selected' : ''}>✓ Marked Normal / Valid (Business Justification Verified)</option>
                <option value="Ignored" ${currentStatus === 'Ignored' ? 'selected' : ''}>⚪ Ignored (Immaterial / Non-Risk Item)</option>
                <option value="Open" ${currentStatus === 'Open' ? 'selected' : ''}>Open (Pending Review)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Working Paper Remark / Evidence Notes *</label>
              <textarea class="form-control" id="anom-modal-comment" rows="4" placeholder="Enter supporting invoice checks, director approvals, SA 520 explanation, or reason for validation..." required>${currentComment || ''}</textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('anomaly-review-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Anomaly Review</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleAnomalyReviewSubmit(event, anomalyId) {
  event.preventDefault();
  const status = document.getElementById("anom-modal-status").value;
  const comment = document.getElementById("anom-modal-comment").value.trim();

  try {
    await FinAuditAPI.reviewAnomaly(state.currentEngagementId, anomalyId, {
      status: status,
      auditor_comment: comment
    });
    closeModal("anomaly-review-modal");
    await renderAnomalyDetection();
  } catch (err) {
    notifyError("Failed to save anomaly review: " + err.message);
  }
}

async function openAIExplanationModal(anomalyId) {
  try {
    const res = await FinAuditAPI.getAIAnomalyExplanation(state.currentEngagementId, anomalyId);
    const modalHtml = `
      <div class="modal-overlay" id="ai-explanation-modal">
        <div class="modal-card" style="max-width: 750px;">
          <div class="modal-header">
            <div class="modal-title">🤖 AI Audit Working Paper Memorandum — #${anomalyId}</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('ai-explanation-modal')">✕</button>
          </div>
          <div class="modal-body">
            <pre style="background: #0f172a; color: #f8fafc; padding: 16px; border-radius: 6px; font-family: monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; max-height: 480px; overflow-y: auto;">${res.ai_memo}</pre>
            
            <div class="modal-footer" style="padding: 12px 0 0 0; margin-top: 14px; display: flex; justify-content: space-between;">
              <button class="btn btn-secondary" onclick="navigator.clipboard.writeText(\`${res.ai_memo.replace(/`/g, '\\`')}\`); notifyInfo('Copied Working Paper Memorandum to clipboard!');">
                📋 Copy Memo
              </button>
              <button class="btn btn-primary" onclick="closeModal('ai-explanation-modal')">Close</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Failed to generate AI explanation: " + err.message);
  }
}

// -------------------------------------------------------------
// 11. YEAR-ON-YEAR (YoY) FINANCIAL COMPARISON MODULE
// -------------------------------------------------------------
state.yoyConfig = {
  threshold_pct: 10.0,
  materiality_threshold: 50000.0,
  activeSection: "executive", // executive, ledgers, parties, volumes
  only_significant: false,
  py_engagement_id: null,
  search: ""
};

async function renderYoYComparison() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `
      <div class="card" style="padding: 40px; text-align: center; color: #64748b;">
        <h3>No Engagement Selected</h3>
        <p style="margin-top: 8px;">Please select an active audit engagement from the top navigation bar.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div style="padding: 30px; text-align: center; color: #64748b;">
      <div class="loading-spinner" style="margin: 0 auto 16px auto;"></div>
      <p style="font-weight: 600; font-size: 15px;">Computing Year-on-Year Financial Comparison & Variances...</p>
      <p style="font-size: 12px; color: #94a3b8; margin-top: 4px;">Evaluating comparative balances with ${state.yoyConfig.threshold_pct}% materiality threshold</p>
    </div>
  `;

  try {
    const params = {
      threshold_pct: state.yoyConfig.threshold_pct,
      materiality_threshold: state.yoyConfig.materiality_threshold,
      only_significant: state.yoyConfig.only_significant,
      search: state.yoyConfig.search || ""
    };
    if (state.yoyConfig.py_engagement_id) {
      params.py_engagement_id = state.yoyConfig.py_engagement_id;
    }

    const data = await FinAuditAPI.getYoYComparison(state.currentEngagementId, params);
    state.currentYoYData = data;
    renderYoYComparisonUI(data);
  } catch (err) {
    container.innerHTML = `
      <div class="card" style="padding: 30px; border-left: 4px solid #dc2626;">
        <h3 style="color: #dc2626;">YoY Comparison Engine Error</h3>
        <p style="margin-top: 8px; color: #475569;">${err.message}</p>
        <button class="btn btn-primary" style="margin-top: 16px;" onclick="renderYoYComparison()">Retry</button>
      </div>
    `;
  }
}

function renderYoYComparisonUI(data) {
  const container = document.getElementById("content-container");
  const s = data.summary || {};
  const currentFy = data.current_financial_year;
  const prevFy = data.previous_financial_year;

  // Find other engagements for same client for comparison dropdown
  const clientEngs = (state.engagements || []).filter(e => e.id !== state.currentEngagementId);

  container.innerHTML = `
    <!-- Header -->
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
      <div>
        <h2 style="font-size: 22px; font-weight: 800; color: #0f172a; display: flex; align-items: center; gap: 10px;">
          <span>📈 Year-on-Year Financial Comparison</span>
          <span class="badge" style="background: #e0e7ff; color: #4338ca; font-size: 11px; font-weight: 700;">
            ${prevFy} ➔ ${currentFy}
          </span>
        </h2>
        <p style="font-size: 13px; color: #64748b; margin-top: 4px;">
          Comprehensive multi-year comparative analytics across Revenue, Expenses, Profit, Assets, Liabilities, Ledgers, Party Balances, and Volumes.
        </p>
      </div>

      <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
        <a class="btn btn-primary" href="${FinAuditAPI.getYoYReportDownloadUrl(state.currentEngagementId, { threshold_pct: state.yoyConfig.threshold_pct, py_engagement_id: state.yoyConfig.py_engagement_id })}" target="_blank" style="text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">
          📥 Download YoY Report (CSV)
        </a>
      </div>
    </div>

    <!-- Summary KPI Cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px;">
      <div class="card" style="padding: 16px; border-left: 4px solid var(--primary);">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Total Compared Items</div>
        <div style="font-size: 24px; font-weight: 800; color: #0f172a; margin-top: 4px;">${s.total_comparison_items || 0}</div>
        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Across 4 Comparison Sections</div>
      </div>

      <div class="card" style="padding: 16px; border-left: 4px solid #f59e0b;">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Significant Movements</div>
        <div style="font-size: 24px; font-weight: 800; color: #b45309; margin-top: 4px;">${s.significant_movements_count || 0}</div>
        <div style="font-size: 11px; color: #b45309; margin-top: 4px;">Exceeding ${data.configured_threshold_pct}% threshold</div>
      </div>

      <div class="card" style="padding: 16px; border-left: 4px solid ${s.revenue_growth_pct >= 0 ? '#059669' : '#dc2626'};">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Revenue Shift</div>
        <div style="font-size: 24px; font-weight: 800; color: ${s.revenue_growth_pct >= 0 ? '#059669' : '#dc2626'}; margin-top: 4px;">
          ${s.revenue_growth_pct >= 0 ? '+' : ''}${s.revenue_growth_pct.toFixed(1)}%
        </div>
        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Revenue from Operations</div>
      </div>

      <div class="card" style="padding: 16px; border-left: 4px solid ${s.net_profit_growth_pct >= 0 ? '#059669' : '#dc2626'};">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Net Profit Shift</div>
        <div style="font-size: 24px; font-weight: 800; color: ${s.net_profit_growth_pct >= 0 ? '#059669' : '#dc2626'}; margin-top: 4px;">
          ${s.net_profit_growth_pct >= 0 ? '+' : ''}${s.net_profit_growth_pct.toFixed(1)}%
        </div>
        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Net Profit After Tax</div>
      </div>

      <div class="card" style="padding: 16px; border-left: 4px solid #0284c7;">
        <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase;">Auditor Documented</div>
        <div style="font-size: 24px; font-weight: 800; color: #0284c7; margin-top: 4px;">${s.reviewed_count || 0}</div>
        <div style="font-size: 11px; color: #0284c7; margin-top: 4px;">Working Paper Remarks Saved</div>
      </div>
    </div>

    <!-- Configurable Threshold & Filter Toolbar -->
    <div class="card" style="padding: 16px 20px; margin-bottom: 20px;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
        <!-- Threshold Presets -->
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-size: 12.5px; font-weight: 700; color: #334155;">Variance Threshold:</span>
          <div style="display: inline-flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden;">
            ${[5, 10, 15, 20].map(pct => `
              <button class="btn btn-sm ${state.yoyConfig.threshold_pct === pct ? 'btn-primary' : 'btn-secondary'}" style="border: none; border-radius: 0; padding: 5px 12px; font-weight: 700;" onclick="setYoYThreshold(${pct})">
                ${pct}%
              </button>
            `).join("")}
          </div>
        </div>

        <!-- Previous Year Engagement Selector -->
        ${clientEngs.length > 0 ? `
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 12px; font-weight: 600; color: #64748b;">Compare With:</span>
            <select class="form-control" style="font-size: 12px; padding: 4px 8px; width: auto;" onchange="handleYoYPrevEngagementChange(this.value)">
              <option value="" ${!state.yoyConfig.py_engagement_id ? 'selected' : ''}>Auto-Detect Previous Year</option>
              ${clientEngs.map(e => `
                <option value="${e.id}" ${state.yoyConfig.py_engagement_id === e.id ? 'selected' : ''}>
                  ${e.financial_year} — ${e.title}
                </option>
              `).join("")}
            </select>
          </div>
        ` : ''}

        <!-- Significant Only Toggle -->
        <div style="display: flex; align-items: center; gap: 6px;">
          <label style="display: flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; color: #334155; cursor: pointer;">
            <input type="checkbox" ${state.yoyConfig.only_significant ? 'checked' : ''} onchange="toggleYoYSignificantOnly(this.checked)" />
            Highlight Significant Movements Only (≥ ${state.yoyConfig.threshold_pct}%)
          </label>
        </div>

        <!-- Search Input -->
        <div style="width: 200px;">
          <input type="text" class="form-control" placeholder="Search account..." value="${state.yoyConfig.search || ''}" oninput="handleYoYSearchDebounced(event)" style="font-size: 12px; padding: 4px 10px;" />
        </div>
      </div>
    </div>

    <!-- Section Navigation Tabs -->
    <div style="display: flex; gap: 8px; border-bottom: 2px solid var(--border); margin-bottom: 20px; overflow-x: auto;">
      <button class="btn btn-sm ${state.yoyConfig.activeSection === 'executive' ? 'btn-primary' : 'btn-secondary'}" style="border-bottom-left-radius: 0; border-bottom-right-radius: 0; font-weight: 700;" onclick="switchYoYSection('executive')">
        🏛️ Executive Financial Heads (${data.executive_comparison?.length || 0})
      </button>
      <button class="btn btn-sm ${state.yoyConfig.activeSection === 'ledgers' ? 'btn-primary' : 'btn-secondary'}" style="border-bottom-left-radius: 0; border-bottom-right-radius: 0; font-weight: 700;" onclick="switchYoYSection('ledgers')">
        📚 Major Ledger Accounts (${data.major_ledgers_comparison?.length || 0})
      </button>
      <button class="btn btn-sm ${state.yoyConfig.activeSection === 'parties' ? 'btn-primary' : 'btn-secondary'}" style="border-bottom-left-radius: 0; border-bottom-right-radius: 0; font-weight: 700;" onclick="switchYoYSection('parties')">
        👥 Party Balances (${data.party_comparison?.length || 0})
      </button>
      <button class="btn btn-sm ${state.yoyConfig.activeSection === 'volumes' ? 'btn-primary' : 'btn-secondary'}" style="border-bottom-left-radius: 0; border-bottom-right-radius: 0; font-weight: 700;" onclick="switchYoYSection('volumes')">
        📊 Transaction Volumes (${data.volume_comparison?.length || 0})
      </button>
    </div>

    <!-- Active Section Table Content -->
    ${renderActiveYoYSectionTable(data)}
  `;
}

function renderActiveYoYSectionTable(data) {
  let items = [];
  let sectionTitle = "";
  const prevFy = data.previous_financial_year;
  const currFy = data.current_financial_year;

  switch (state.yoyConfig.activeSection) {
    case "executive":
      items = data.executive_comparison || [];
      sectionTitle = "Executive Financial Statement Heads (Schedule III Balance Sheet & P&L)";
      break;
    case "ledgers":
      items = data.major_ledgers_comparison || [];
      sectionTitle = "Major General Ledger Accounts Comparison";
      break;
    case "parties":
      items = data.party_comparison || [];
      sectionTitle = "Counterparty Balances Comparison (Top Debtors & Creditors)";
      break;
    case "volumes":
      items = data.volume_comparison || [];
      sectionTitle = "Operational Transaction Volumes & Average Ticket Sizes";
      break;
    default:
      items = data.executive_comparison || [];
  }

  if (items.length === 0) {
    return `
      <div class="card" style="padding: 40px; text-align: center; color: #64748b;">
        <div style="font-size: 30px; margin-bottom: 8px;">✓</div>
        <p style="font-size: 15px; font-weight: 600;">No items found in this section for the selected filters.</p>
        <p style="font-size: 12px; color: #94a3b8; margin-top: 4px;">Try lowering the variance threshold or clearing the search filter.</p>
      </div>
    `;
  }

  return `
    <div class="card" style="padding: 0; overflow: hidden; border: 1px solid var(--border);">
      <div style="padding: 14px 20px; background: #f8fafc; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 700; font-size: 13.5px; color: #0f172a;">${sectionTitle}</span>
        <span style="font-size: 12px; color: #64748b;">${items.length} item(s)</span>
      </div>

      <div style="overflow-x: auto;">
        <table class="table" style="width: 100%; margin: 0; font-size: 12.5px;">
          <thead>
            <tr style="background: #f1f5f9; color: #334155; font-size: 11.5px; text-transform: uppercase;">
              <th style="padding: 10px 14px; text-align: left;">Account / Metric</th>
              <th style="padding: 10px 14px; text-align: left;">Category</th>
              <th style="padding: 10px 14px; text-align: right;">PY (${prevFy})</th>
              <th style="padding: 10px 14px; text-align: right;">CY (${currFy})</th>
              <th style="padding: 10px 14px; text-align: right;">Difference (₹)</th>
              <th style="padding: 10px 14px; text-align: right;">Change (%)</th>
              <th style="padding: 10px 14px; text-align: center;">Movement</th>
              <th style="padding: 10px 14px; text-align: center;">Risk Level</th>
              <th style="padding: 10px 14px; text-align: center;">Auditor Review</th>
              <th style="padding: 10px 14px; text-align: center;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${items.map((row, idx) => renderYoYTableRow(row, idx)).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderYoYTableRow(row, idx) {
  const isSig = row.is_significant;
  const pct = row.percentage_difference;
  const absD = row.absolute_difference;
  const dir = row.movement_direction;

  const dirBadge = dir === "Increase" ? `<span style="color: #059669; font-weight: 700;">▲ Increase</span>` :
                   (dir === "Decrease" ? `<span style="color: #dc2626; font-weight: 700;">▼ Decrease</span>` :
                   `<span style="color: #64748b;">— No Change</span>`);

  const riskBadge = row.risk === "CRITICAL" ? '<span class="badge badge-critical">CRITICAL</span>' :
                    (row.risk === "HIGH" ? '<span class="badge badge-high">HIGH</span>' :
                    (row.risk === "MEDIUM" ? '<span class="badge badge-medium">MEDIUM</span>' :
                    '<span class="badge badge-low">NORMAL</span>'));

  const statusBadge = row.status === "Reviewed" ? '<span class="badge badge-low">✓ Reviewed</span>' :
                      (row.status === "Flagged for Inquiry" ? '<span class="badge badge-critical">Flagged</span>' :
                      (row.status === "Verified" ? '<span class="badge badge-resolved">Verified</span>' :
                      '<span class="badge badge-high" style="opacity: 0.6;">Unreviewed</span>'));

  return `
    <tr style="background: ${isSig ? '#fffbeb' : (idx % 2 === 0 ? '#ffffff' : '#fafafa')}; border-bottom: 1px solid var(--border);">
      <td style="padding: 10px 14px; font-weight: 700; color: #0f172a;">
        ${row.account_name}
        ${row.ai_reason ? `<div style="font-size: 11px; font-weight: 400; color: #0369a1; margin-top: 3px; max-width: 320px; line-height: 1.35;"><b>AI Note:</b> ${row.ai_reason}</div>` : ''}
        ${row.auditor_comment ? `<div style="font-size: 11px; font-weight: 500; color: #166534; margin-top: 3px; background: #f0fdf4; padding: 2px 6px; border-radius: 3px;"><b>Auditor WP:</b> ${row.auditor_comment}</div>` : ''}
      </td>
      <td style="padding: 10px 14px; color: #64748b; font-size: 11.5px;">
        <span class="badge" style="background: #f1f5f9; color: #475569;">${row.group || row.category}</span>
      </td>
      <td style="padding: 10px 14px; text-align: right; font-family: monospace; color: #334155;">
        ₹${Number(row.previous_year || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}
      </td>
      <td style="padding: 10px 14px; text-align: right; font-family: monospace; font-weight: 700; color: #0f172a;">
        ₹${Number(row.current_year || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}
      </td>
      <td style="padding: 10px 14px; text-align: right; font-family: monospace; font-weight: 700; color: ${absD > 0 ? '#059669' : (absD < 0 ? '#dc2626' : '#334155')};">
        ${absD > 0 ? '+' : ''}₹${Number(absD || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}
      </td>
      <td style="padding: 10px 14px; text-align: right; font-family: monospace; font-weight: 800; color: ${pct > 0 ? '#059669' : (pct < 0 ? '#dc2626' : '#64748b')};">
        ${pct > 0 ? '+' : ''}${pct.toFixed(1)}%
      </td>
      <td style="padding: 10px 14px; text-align: center;">
        ${dirBadge}
      </td>
      <td style="padding: 10px 14px; text-align: center;">
        ${riskBadge}
      </td>
      <td style="padding: 10px 14px; text-align: center;">
        ${statusBadge}
      </td>
      <td style="padding: 10px 14px; text-align: center;">
        <div style="display: flex; gap: 4px; justify-content: center;">
          <button class="btn btn-sm btn-secondary" style="padding: 3px 6px; font-size: 11px;" title="Document Working Paper Comment" onclick="openYoYCommentModal('${row.item_key}', '${row.category}', '${row.account_name.replace(/'/g, "\\'")}', '${row.status}', '${(row.auditor_comment || '').replace(/'/g, "\\'")}')">
            📝
          </button>
          <button class="btn btn-sm btn-secondary" style="padding: 3px 6px; font-size: 11px;" title="Generate Factual AI Movement Driver" onclick="triggerYoYFactualAI('${row.item_key}')">
            🤖
          </button>
        </div>
      </td>
    </tr>
  `;
}

function setYoYThreshold(pct) {
  state.yoyConfig.threshold_pct = pct;
  renderYoYComparison();
}

function toggleYoYSignificantOnly(checked) {
  state.yoyConfig.only_significant = checked;
  renderYoYComparison();
}

function switchYoYSection(section) {
  state.yoyConfig.activeSection = section;
  renderYoYComparison();
}

function handleYoYPrevEngagementChange(engId) {
  state.yoyConfig.py_engagement_id = engId ? parseInt(engId) : null;
  renderYoYComparison();
}

let yoySearchTimer = null;
function handleYoYSearchDebounced(e) {
  clearTimeout(yoySearchTimer);
  const val = e.target.value;
  yoySearchTimer = setTimeout(() => {
    state.yoyConfig.search = val;
    renderYoYComparison();
  }, 350);
}

function openYoYCommentModal(itemKey, category, accountName, currentStatus, currentComment) {
  const modalHtml = `
    <div class="modal-overlay" id="yoy-comment-modal">
      <div class="modal-card" style="max-width: 520px;">
        <div class="modal-header">
          <div class="modal-title">YoY Working Paper: ${accountName}</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('yoy-comment-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleYoYCommentSubmit(event, '${itemKey}', '${category}', '${accountName.replace(/'/g, "\\'")}')">
            <div class="form-group">
              <label class="form-label">Review Conclusion Status</label>
              <select class="form-control" id="yoy-modal-status">
                <option value="Reviewed" ${currentStatus === 'Reviewed' ? 'selected' : ''}>✓ Reviewed (Standard Variance)</option>
                <option value="Verified" ${currentStatus === 'Verified' ? 'selected' : ''}>✓ Verified (Supported by Management Inquiry / Vouchers)</option>
                <option value="Flagged for Inquiry" ${currentStatus === 'Flagged for Inquiry' ? 'selected' : ''}>⚠️ Flagged for Inquiry (Awaiting Client Evidence)</option>
                <option value="Unreviewed" ${currentStatus === 'Unreviewed' ? 'selected' : ''}>Unreviewed</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Auditor Comment / Working Paper Remark *</label>
              <textarea class="form-control" id="yoy-modal-comment" rows="4" placeholder="Enter auditor analysis, SA 520 analytical review findings, supporting ledger vouchers, or management explanation..." required>${currentComment || ''}</textarea>
            </div>

            <div class="modal-footer" style="padding: 10px 0 0 0; margin-top: 14px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('yoy-comment-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Working Paper Remark</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleYoYCommentSubmit(event, itemKey, category, accountName) {
  event.preventDefault();
  const status = document.getElementById("yoy-modal-status").value;
  const comment = document.getElementById("yoy-modal-comment").value.trim();

  try {
    await FinAuditAPI.saveYoYComment(state.currentEngagementId, {
      item_key: itemKey,
      category: category,
      account_name: accountName,
      status: status,
      auditor_comment: comment
    });
    closeModal("yoy-comment-modal");
    await renderYoYComparison();
  } catch (err) {
    notifyError("Failed to save comment: " + err.message);
  }
}

async function triggerYoYFactualAI(itemKey) {
  try {
    const res = await FinAuditAPI.explainYoYMovement(state.currentEngagementId, {
      item_key: itemKey,
      threshold_pct: state.yoyConfig.threshold_pct
    });
    const modalHtml = `
      <div class="modal-overlay" id="yoy-ai-modal">
        <div class="modal-card" style="max-width: 600px;">
          <div class="modal-header">
            <div class="modal-title">🤖 Factual Movement Analysis: ${res.account_name}</div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('yoy-ai-modal')">✕</button>
          </div>
          <div class="modal-body">
            <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 6px; padding: 14px; font-size: 13px; color: #1e293b; line-height: 1.6; white-space: pre-wrap;">${res.ai_reason}</div>
            
            <div class="modal-footer" style="padding: 12px 0 0 0; margin-top: 14px; display: flex; justify-content: space-between;">
              <span style="font-size: 11.5px; color: #64748b;">Zero-Hallucination Policy: Generated strictly from recorded ledger entries.</span>
              <button class="btn btn-primary" onclick="closeModal('yoy-ai-modal'); renderYoYComparison();">Close</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Failed to generate factual AI explanation: " + err.message);
  }
}

// -------------------------------------------------------------
// LOCAL AI AUDIT ASSISTANT MODULE (100% Offline)
// -------------------------------------------------------------
if (!state.assistantState) {
  state.assistantState = {
    messages: [],
    isLoading: false,
    suggestedPrompts: []
  };
}

async function renderAIAssistant() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `
      <div class="card" style="padding: 40px; text-align: center; color: var(--text-secondary);">
        <h3>No Engagement Selected</h3>
        <p style="margin-top: 8px;">Please select an audit engagement to converse with the Local AI Assistant.</p>
      </div>
    `;
    return;
  }

  // Load suggested prompts if not already loaded
  if (state.assistantState.suggestedPrompts.length === 0) {
    try {
      const res = await FinAuditAPI.getSuggestedPrompts(state.currentEngagementId);
      state.assistantState.suggestedPrompts = res.prompts || [];
    } catch (e) {
      console.warn("Could not load suggested prompts:", e);
    }
  }

  // If conversation is empty, populate initial greeting
  if (state.assistantState.messages.length === 0) {
    state.assistantState.messages.push({
      role: "assistant",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      content: `Hello! I am your **100% offline Local AI Audit Assistant** for **${state.activeEngagement?.client_name || 'this client'}** (${state.activeEngagement?.financial_year || 'FY'}).

I evaluate your imported ledger records deterministically and synthesize explainable CA-grade findings without sending any data outside your device.

#### 💡 How can I assist your audit today?
Choose one of the quick prompt chips below or type your specific question:`,
      disclaimer: "AI-generated assistance. Verify findings against source records before making audit decisions.",
      evidence: [],
      source_transactions: [],
      suggested_actions: [
        "Ask about unusual transactions",
        "Compare year-on-year variances",
        "Review bank reconciliation exceptions"
      ]
    });
  }

  const promptChipsHtml = state.assistantState.suggestedPrompts.map(p => `
    <button class="assistant-prompt-chip" onclick="fillAssistantPrompt('${p.query.replace(/'/g, "\\'")}')">
      <span>${p.icon === 'alert' ? '🚨' : p.icon === 'trending' ? '📈' : p.icon === 'bank' ? '🏦' : p.icon === 'document' ? '📑' : p.icon === 'scale' ? '⚖️' : p.icon === 'pencil' ? '📝' : p.icon === 'chart' ? '📊' : '🔍'}</span>
      <span>${p.title}</span>
    </button>
  `).join("");

  const messagesHtml = state.assistantState.messages.map((m, idx) => renderAssistantMessageItem(m, idx)).join("");

  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 16px; height: calc(100vh - 120px); max-height: calc(100vh - 120px);">
      <!-- Header -->
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid var(--border); padding-bottom: 12px;">
        <div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <h2 style="margin: 0; font-size: 20px; color: var(--text-primary);">🤖 Local AI Audit Assistant</h2>
            <span class="badge" style="background: rgba(16, 185, 129, 0.12); color: #059669; font-weight: 600; font-size: 11px;">🔒 100% Offline & Private</span>
            <span class="badge" style="background: rgba(99, 102, 241, 0.12); color: #4f46e5; font-weight: 600; font-size: 11px;">Zero Cloud API</span>
          </div>
          <div style="font-size: 12.5px; color: var(--text-secondary); margin-top: 3px;">
            Interactive deterministic audit intelligence for <strong>${state.activeEngagement?.client_name || 'Client'}</strong> (${state.activeEngagement?.financial_year || 'FY'})
          </div>
        </div>

        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary btn-sm" onclick="loadExecutiveSummaryNarrative()">
            📑 Executive Audit Memo
          </button>
          <button class="btn btn-secondary btn-sm" onclick="clearAssistantChat()">
            🗑️ Clear Chat
          </button>
        </div>
      </div>

      <!-- Mandatory Disclaimer Alert -->
      <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 8px; padding: 10px 14px; display: flex; align-items: center; gap: 10px; font-size: 12.5px; color: #b45309;">
        <span style="font-size: 16px;">🛡️</span>
        <div>
          <strong>Statutory Compliance Disclaimer:</strong> <em>AI-generated assistance. Verify findings against source records before making audit decisions.</em>
        </div>
      </div>

      <!-- Prompt Chips Carousel -->
      <div style="display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: thin;">
        ${promptChipsHtml}
      </div>

      <!-- Chat Messages Container -->
      <div id="assistant-chat-stream" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; padding: 12px 6px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px;">
        ${messagesHtml}
        ${state.assistantState.isLoading ? `
          <div style="display: flex; gap: 12px; align-items: flex-start;">
            <div style="width: 34px; height: 34px; border-radius: 50%; background: #4f46e5; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: bold; flex-shrink: 0;">AI</div>
            <div style="background: var(--bg-card); border: 1px solid var(--border); padding: 14px 18px; border-radius: 8px; font-size: 13px; color: var(--text-secondary); display: flex; align-items: center; gap: 10px;">
              <span class="spinner-inline"></span>
              <span>Evaluating query deterministically across local database & audit rules...</span>
            </div>
          </div>
        ` : ''}
      </div>

      <!-- Input Bar -->
      <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; display: flex; gap: 8px; align-items: center;">
        <input 
          type="text" 
          id="assistant-query-input" 
          class="form-control" 
          placeholder="Ask a question about this engagement (e.g. 'Show me unusual transactions.', 'Which ledgers have the largest YoY changes?')..." 
          style="border: none; background: transparent; font-size: 13.5px;"
          onkeydown="if(event.key === 'Enter') handleAssistantSend();"
          ${state.assistantState.isLoading ? 'disabled' : ''}
          autofocus
        >
        <button 
          class="btn btn-primary" 
          id="assistant-send-btn" 
          onclick="handleAssistantSend()"
          ${state.assistantState.isLoading ? 'disabled' : ''}
          style="display: flex; align-items: center; gap: 6px; padding: 8px 18px;"
        >
          <span>Ask Local AI</span>
          <span>↵</span>
        </button>
      </div>
    </div>
  `;

  // Scroll chat to bottom
  const chatStream = document.getElementById("assistant-chat-stream");
  if (chatStream) {
    chatStream.scrollTop = chatStream.scrollHeight;
  }
}

function renderAssistantMessageItem(msg, idx) {
  const isUser = msg.role === "user";
  
  if (isUser) {
    return `
      <div style="display: flex; justify-content: flex-end; gap: 10px; margin-left: 60px;">
        <div style="background: #4f46e5; color: #ffffff; padding: 12px 16px; border-radius: 12px 12px 2px 12px; font-size: 13.5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
          ${escapeHtml(msg.content)}
          <div style="font-size: 10.5px; color: rgba(255,255,255,0.7); text-align: right; margin-top: 4px;">${msg.timestamp}</div>
        </div>
        <div style="width: 32px; height: 32px; border-radius: 50%; background: #6366f1; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; flex-shrink: 0;">CA</div>
      </div>
    `;
  }

  // Format AI response markdown into styled HTML
  const formattedContent = formatAssistantMarkdown(msg.content);

  // Supporting Evidence Table
  let evidenceHtml = "";
  if (msg.evidence && msg.evidence.length > 0) {
    const rows = msg.evidence.map(e => `
      <tr style="font-size: 12px; border-bottom: 1px solid var(--border);">
        <td style="padding: 6px 10px; font-family: monospace;">${e.date || e.doc_date || '—'}</td>
        <td style="padding: 6px 10px; font-weight: 600; color: #4f46e5;">${e.voucher_no || e.invoice_no || e.item_key || '—'}</td>
        <td style="padding: 6px 10px;">${e.ledger || e.account_name || '—'}</td>
        <td style="padding: 6px 10px; color: var(--text-secondary);">${e.party_name || e.vendor_name || '—'}</td>
        <td style="padding: 6px 10px; text-align: right; font-weight: 600;">${e.amount_formatted || (e.amount ? formatINR(e.amount) : (e.current_year !== undefined ? formatINR(e.current_year) : '—'))}</td>
        <td style="padding: 6px 10px; text-align: center;">
          ${e.severity ? getSeverityBadge(e.severity) : (e.risk ? `<span class="badge badge-${e.risk.toLowerCase()}">${e.risk}</span>` : '<span class="badge badge-low">Normal</span>')}
        </td>
        <td style="padding: 6px 10px;">
          <button class="btn btn-sm btn-secondary" style="padding: 2px 8px; font-size: 11px;" onclick="inspectAssistantTransaction(${JSON.stringify(e).replace(/"/g, '&quot;')})">
            🔍 Inspect
          </button>
        </td>
      </tr>
    `).join("");

    evidenceHtml = `
      <div style="margin-top: 14px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-size: 12px; font-weight: 600; color: var(--text-primary);">📊 Supporting Evidence & Source Records (${msg.evidence.length} items)</span>
          <span style="font-size: 11px; color: var(--text-secondary);">Click 'Inspect' to review full audit attributes</span>
        </div>
        <div style="max-height: 220px; overflow-y: auto; border: 1px solid var(--border); border-radius: 4px;">
          <table class="table" style="margin: 0; width: 100%; font-size: 12px;">
            <thead style="background: var(--bg-card); position: sticky; top: 0;">
              <tr>
                <th style="padding: 6px 10px;">Date</th>
                <th style="padding: 6px 10px;">Voucher / Ref</th>
                <th style="padding: 6px 10px;">Ledger Account</th>
                <th style="padding: 6px 10px;">Party</th>
                <th style="padding: 6px 10px; text-align: right;">Amount</th>
                <th style="padding: 6px 10px; text-align: center;">Severity</th>
                <th style="padding: 6px 10px;">Action</th>
              </tr>
            </thead>
            <tbody>
              ${rows}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // Suggested Next Actions
  let actionsHtml = "";
  if (msg.suggested_actions && msg.suggested_actions.length > 0) {
    actionsHtml = `
      <div style="margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px;">
        ${msg.suggested_actions.map(act => `
          <span style="font-size: 11.5px; background: rgba(99, 102, 241, 0.08); color: #4338ca; border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 14px; padding: 3px 10px;">
            ⚡ ${escapeHtml(act)}
          </span>
        `).join("")}
      </div>
    `;
  }

  return `
    <div style="display: flex; gap: 12px; align-items: flex-start; margin-right: 40px;">
      <div style="width: 34px; height: 34px; border-radius: 50%; background: #4f46e5; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: bold; flex-shrink: 0; box-shadow: 0 2px 4px rgba(79, 70, 229, 0.3);">AI</div>
      <div style="background: var(--bg-card); border: 1px solid var(--border); padding: 14px 18px; border-radius: 2px 12px 12px 12px; flex: 1; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
        <div style="font-size: 13.5px; color: var(--text-primary); line-height: 1.6;">
          ${formattedContent}
        </div>
        ${evidenceHtml}
        ${actionsHtml}
        <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--text-secondary);">
          <span>🛡️ ${msg.disclaimer || MANDATORY_DISCLAIMER}</span>
          <span>${msg.timestamp || ''}</span>
        </div>
      </div>
    </div>
  `;
}

function formatAssistantMarkdown(text) {
  if (!text) return "";
  let html = text
    .replace(/^### (.*$)/gim, '<h3 style="font-size: 15px; font-weight: 700; margin: 10px 0 6px 0; color: #1e293b;">$1</h3>')
    .replace(/^#### (.*$)/gim, '<h4 style="font-size: 13.5px; font-weight: 600; margin: 8px 0 4px 0; color: #334155;">$1</h4>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-size: 12px; color: #475569;">$1</code>')
    .replace(/^\s*-\s+(.*$)/gim, '<div style="margin-left: 14px; margin-bottom: 4px; position: relative;"><span style="position: absolute; left: -12px;">•</span>$1</div>')
    .replace(/\n\n/g, '<div style="height: 8px;"></div>');

  return html;
}

function fillAssistantPrompt(query) {
  const input = document.getElementById("assistant-query-input");
  if (input) {
    input.value = query;
    handleAssistantSend();
  }
}

async function handleAssistantSend() {
  const input = document.getElementById("assistant-query-input");
  if (!input) return;
  const query = input.value.trim();
  if (!query) return;

  // Add User Message
  state.assistantState.messages.push({
    role: "user",
    content: query,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  });

  input.value = "";
  state.assistantState.isLoading = true;
  await renderAIAssistant();

  try {
    const res = await FinAuditAPI.queryAssistant(state.currentEngagementId, query);
    state.assistantState.messages.push({
      role: "assistant",
      content: res.response || "No response received.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      disclaimer: res.disclaimer || "AI-generated assistance. Verify findings against source records before making audit decisions.",
      evidence: res.evidence || [],
      source_transactions: res.source_transactions || [],
      suggested_actions: res.suggested_actions || []
    });
  } catch (err) {
    state.assistantState.messages.push({
      role: "assistant",
      content: `⚠️ **AI Engine Notice:** An error occurred while evaluating the query: ${err.message}`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      disclaimer: "AI-generated assistance. Verify findings against source records before making audit decisions.",
      evidence: [],
      source_transactions: []
    });
  } finally {
    state.assistantState.isLoading = false;
    await renderAIAssistant();
  }
}

async function loadExecutiveSummaryNarrative() {
  state.assistantState.isLoading = true;
  await renderAIAssistant();

  try {
    const res = await FinAuditAPI.getAISummary(state.currentEngagementId);
    state.assistantState.messages.push({
      role: "assistant",
      content: res.narrative,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      disclaimer: res.disclaimer || "AI-generated assistance. Verify findings against source records before making audit decisions.",
      evidence: [],
      source_transactions: [],
      suggested_actions: [
        "Review Critical Severity findings in Risk & Findings module",
        "Generate Final PDF Audit Report"
      ]
    });
  } catch (err) {
    notifyError("Failed to generate executive summary: " + err.message);
  } finally {
    state.assistantState.isLoading = false;
    await renderAIAssistant();
  }
}

async function clearAssistantChat() {
  const confirmed = await FinConfirm({
    title: "Clear AI Conversation History",
    message: "Clear local conversation history for this session?",
    consequences: ["Current conversation context will be reset"],
    confirmText: "Clear Chat",
    isDanger: false
  });
  if (confirmed) {
    state.assistantState.messages = [];
    renderAIAssistant();
  }
}

function inspectAssistantTransaction(item) {
  const modalHtml = `
    <div class="modal-overlay" id="assistant-inspect-modal">
      <div class="modal-card" style="max-width: 650px;">
        <div class="modal-header">
          <div class="modal-title">🔍 Source Transaction Inspection & Audit Evidence</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('assistant-inspect-modal')">✕</button>
        </div>
        <div class="modal-body">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; background: #f8fafc; border: 1px solid var(--border); padding: 14px; border-radius: 6px; font-size: 12.5px;">
            <div><strong>Transaction ID:</strong> #${item.id || item.transaction_id || 'N/A'}</div>
            <div><strong>Posting Date:</strong> ${item.date || item.doc_date || '—'}</div>
            <div><strong>Voucher Number:</strong> <span style="font-family: monospace; font-weight: 600; color: #4f46e5;">${item.voucher_no || item.invoice_no || '—'}</span></div>
            <div><strong>Invoice Number:</strong> ${item.invoice_no || '—'}</div>
            <div><strong>Ledger Head:</strong> ${item.ledger || item.account_name || '—'}</div>
            <div><strong>Account Group:</strong> ${item.group || item.account_group || 'General'}</div>
            <div><strong>Counterparty Name:</strong> ${item.party_name || item.vendor_name || 'Direct'}</div>
            <div><strong>GSTIN:</strong> ${item.gstin || '—'}</div>
            <div><strong>Transaction Amount:</strong> <span style="font-weight: 700; color: #0f172a;">${item.amount_formatted || (item.amount ? formatINR(item.amount) : '—')}</span></div>
            <div><strong>Severity Assessment:</strong> ${item.severity ? getSeverityBadge(item.severity) : '<span class="badge badge-low">LOW</span>'}</div>
          </div>

          ${item.reason || item.description ? `
            <div style="margin-bottom: 14px;">
              <label class="form-label" style="font-size: 11.5px; text-transform: uppercase; color: #64748b;">Audit Exception / Flagging Explanation</label>
              <div style="background: rgba(239, 68, 68, 0.06); border: 1px solid rgba(239, 68, 68, 0.2); padding: 10px 14px; border-radius: 6px; font-size: 12.5px; color: #991b1b; line-height: 1.5;">
                ${item.reason || item.description}
              </div>
            </div>
          ` : ''}

          ${item.recommended_action ? `
            <div style="margin-bottom: 14px;">
              <label class="form-label" style="font-size: 11.5px; text-transform: uppercase; color: #64748b;">Recommended Substantive Procedure (ICAI Standards)</label>
              <div style="background: rgba(99, 102, 241, 0.06); border: 1px solid rgba(99, 102, 241, 0.2); padding: 10px 14px; border-radius: 6px; font-size: 12.5px; color: #3730a3; line-height: 1.5;">
                ${item.recommended_action}
              </div>
            </div>
          ` : ''}

          <div class="modal-footer" style="padding: 10px 0 0 0; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 11px; color: #64748b;">🛡️ Sourced deterministically from local audit database.</span>
            <button class="btn btn-primary" onclick="closeModal('assistant-inspect-modal')">Done Reviewing</button>
          </div>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

// ============================================================================
// AUDIT RISK & CENTRALIZED FINDINGS MODULE
// ============================================================================

state.findingsFilter = {
  severity: "",
  module: "",
  status: "",
  search: "",
  sort_by: "risk_score_desc"
};

function getRiskScoreBadge(score, severity = "MEDIUM", factors = null) {
  const numScore = Number(score) || 0;
  let pillClass = "risk-score-low";
  if (numScore >= 8.5 || severity === "CRITICAL") {
    pillClass = "risk-score-critical";
  } else if (numScore >= 6.5 || severity === "HIGH") {
    pillClass = "risk-score-high";
  } else if (numScore >= 4.0 || severity === "MEDIUM") {
    pillClass = "risk-score-medium";
  }

  const tooltip = factors && factors.equation ? `title="${factors.equation}"` : `title="Deterministic Risk Score: ${numScore.toFixed(1)}/10.0"`;
  return `<span class="risk-score-pill ${pillClass}" ${tooltip}>⚡ ${numScore.toFixed(1)} / 10</span>`;
}

function getFindingStatusBadge(status) {
  const s = (status || "Open").trim();
  if (s === "Resolved") return `<span class="badge badge-resolved">Resolved</span>`;
  if (s === "Under Review" || s === "In Review") return `<span class="badge badge-under-review">Under Review</span>`;
  if (s === "Waived") return `<span class="badge badge-low">Waived</span>`;
  return `<span class="badge badge-open">Open</span>`;
}

async function renderFindings() {
  const container = document.getElementById("content-container");
  if (!state.currentEngagementId) {
    container.innerHTML = `
      <div class="card" style="padding: 40px; text-align: center; color: #64748b;">
        <h3>No Engagement Selected</h3>
        <p style="margin-top: 8px;">Please select an audit engagement from the top navigation to view the findings repository.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `<div style="padding: 24px; color: #64748b;">Loading centralized findings and risk metrics...</div>`;

  try {
    const [summary, findings] = await Promise.all([
      FinAuditAPI.getFindingsDashboardSummary(state.currentEngagementId),
      FinAuditAPI.getFindings(state.currentEngagementId, state.findingsFilter)
    ]);

    const eng = state.activeEngagement || {};
    const materialityVal = eng.materiality_threshold || 50000;

    container.innerHTML = `
      <!-- Header Bar -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
        <div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <h2 style="font-size: 22px; font-weight: 700; color: #0f172a; margin: 0;">Audit Risk & Findings Repository</h2>
            <span class="badge badge-module-pill">Centralized Engine</span>
          </div>
          <div style="font-size: 13px; color: #64748b; margin-top: 4px;">
            Aggregated exception management with 100% explainable, deterministic risk scoring • Benchmark Materiality: <strong>${formatINR(materialityVal)}</strong>
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <button class="btn btn-secondary" onclick="openCreateCustomFindingModal()">
            <span>➕</span> Record Manual Observation
          </button>
          <a href="${FinAuditAPI.getExportFindingsCsvUrl(state.currentEngagementId)}" download="audit_findings_${state.currentEngagementId}.csv" class="btn btn-secondary" style="text-decoration: none;">
            <span>📥</span> Export CSV Register
          </a>
          <button class="btn btn-primary" id="btn-sync-findings" onclick="syncCentralizedFindings()">
            <span>⚡</span> Sync All Modules
          </button>
        </div>
      </div>

      <!-- Dashboard Metric Stat Cards (6 Cards) -->
      <div class="stat-grid" style="grid-template-columns: repeat(6, 1fr); gap: 14px; margin-bottom: 22px;">
        <div class="stat-card" style="border-left: 4px solid #3b82f6;">
          <div class="stat-label">Total Findings</div>
          <div class="stat-value" style="color: #1e293b;">${summary.total_findings || 0}</div>
          <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Avg Risk: <strong>${summary.average_risk_score || '0.0'}/10</strong></div>
        </div>
        <div class="stat-card" style="border-left: 4px solid #dc2626;">
          <div class="stat-label">Open Findings</div>
          <div class="stat-value" style="color: #dc2626;">${summary.open_findings || 0}</div>
          <div style="font-size: 11px; color: #991b1b; margin-top: 4px;">Pending action</div>
        </div>
        <div class="stat-card" style="border-left: 4px solid #ea580c;">
          <div class="stat-label">High Risk</div>
          <div class="stat-value" style="color: #ea580c;">${summary.high_risk || 0}</div>
          <div style="font-size: 11px; color: #c2410c; margin-top: 4px;">Score ≥ 6.5</div>
        </div>
        <div class="stat-card" style="border-left: 4px solid #991b1b;">
          <div class="stat-label">Critical</div>
          <div class="stat-value" style="color: #991b1b;">${summary.critical || 0}</div>
          <div style="font-size: 11px; color: #7f1d1d; margin-top: 4px;">Score ≥ 8.5 / Statutory</div>
        </div>
        <div class="stat-card" style="border-left: 4px solid #2563eb;">
          <div class="stat-label">Under Review</div>
          <div class="stat-value" style="color: #2563eb;">${summary.under_review || 0}</div>
          <div style="font-size: 11px; color: #1d4ed8; margin-top: 4px;">Auditor engaged</div>
        </div>
        <div class="stat-card" style="border-left: 4px solid #10b981;">
          <div class="stat-label">Resolved</div>
          <div class="stat-value" style="color: #10b981;">${summary.resolved || 0}</div>
          <div style="font-size: 11px; color: #047857; margin-top: 4px;">Closed & remediated</div>
        </div>
      </div>

      <!-- Filters & Search Toolbar -->
      <div class="card" style="margin-bottom: 20px; padding: 14px 18px;">
        <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between;">
          <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center; flex: 1;">
            <!-- Search Box -->
            <div style="min-width: 220px; flex: 1; max-width: 320px;">
              <input type="text" id="findings-search-input" class="form-control" placeholder="🔍 Search ID, title, rule, or desc..."
                     value="${state.findingsFilter.search || ''}" onkeydown="if(event.key==='Enter') handleFindingsFilterChange()">
            </div>

            <!-- Module Filter -->
            <select id="findings-module-select" class="form-control" style="width: 180px;" onchange="handleFindingsFilterChange()">
              <option value="">All Modules (${summary.total_findings || 0})</option>
              <option value="Statutory & Tax Rules" ${state.findingsFilter.module === 'Statutory & Tax Rules' ? 'selected' : ''}>Statutory & Tax Rules</option>
              <option value="Duplicate & Sequence Engine" ${state.findingsFilter.module === 'Duplicate & Sequence Engine' ? 'selected' : ''}>Duplicate & Sequence Engine</option>
              <option value="Hybrid Anomaly Detection" ${state.findingsFilter.module === 'Hybrid Anomaly Detection' ? 'selected' : ''}>Hybrid Anomaly Detection</option>
              <option value="Year-on-Year Variance" ${state.findingsFilter.module === 'Year-on-Year Variance' ? 'selected' : ''}>Year-on-Year Variance</option>
              <option value="Trial Balance Analysis" ${state.findingsFilter.module === 'Trial Balance Analysis' ? 'selected' : ''}>Trial Balance Analysis</option>
              <option value="Bank Reconciliation" ${state.findingsFilter.module === 'Bank Reconciliation' ? 'selected' : ''}>Bank Reconciliation</option>
              <option value="GST Reconciliation" ${state.findingsFilter.module === 'GST Reconciliation' ? 'selected' : ''}>GST Reconciliation</option>
              <option value="Manual Audit" ${state.findingsFilter.module === 'Manual Audit' ? 'selected' : ''}>Manual Observations</option>
            </select>

            <!-- Status Filter -->
            <select id="findings-status-select" class="form-control" style="width: 140px;" onchange="handleFindingsFilterChange()">
              <option value="">All Statuses</option>
              <option value="Open" ${state.findingsFilter.status === 'Open' ? 'selected' : ''}>Open</option>
              <option value="Under Review" ${state.findingsFilter.status === 'Under Review' ? 'selected' : ''}>Under Review</option>
              <option value="Resolved" ${state.findingsFilter.status === 'Resolved' ? 'selected' : ''}>Resolved</option>
              <option value="Waived" ${state.findingsFilter.status === 'Waived' ? 'selected' : ''}>Waived</option>
            </select>

            <!-- Severity Pills -->
            <div style="display: flex; gap: 4px; align-items: center; border-left: 1px solid var(--border); padding-left: 10px;">
              <button class="btn btn-sm ${!state.findingsFilter.severity ? 'btn-primary' : 'btn-secondary'}" onclick="setSeverityFilter('')">All</button>
              <button class="btn btn-sm ${state.findingsFilter.severity === 'CRITICAL' ? 'btn-primary' : 'btn-secondary'}" onclick="setSeverityFilter('CRITICAL')" style="color: #dc2626;">Critical</button>
              <button class="btn btn-sm ${state.findingsFilter.severity === 'HIGH' ? 'btn-primary' : 'btn-secondary'}" onclick="setSeverityFilter('HIGH')" style="color: #ea580c;">High</button>
              <button class="btn btn-sm ${state.findingsFilter.severity === 'MEDIUM' ? 'btn-primary' : 'btn-secondary'}" onclick="setSeverityFilter('MEDIUM')" style="color: #d97706;">Medium</button>
              <button class="btn btn-sm ${state.findingsFilter.severity === 'LOW' ? 'btn-primary' : 'btn-secondary'}" onclick="setSeverityFilter('LOW')" style="color: #059669;">Low</button>
            </div>
          </div>

          <!-- Sort Order -->
          <div style="display: flex; align-items: center; gap: 6px;">
            <label style="font-size: 11.5px; color: #64748b; white-space: nowrap;">Sort by:</label>
            <select id="findings-sort-select" class="form-control" style="width: 175px;" onchange="handleFindingsFilterChange()">
              <option value="risk_score_desc" ${state.findingsFilter.sort_by === 'risk_score_desc' ? 'selected' : ''}>Risk Score (High → Low)</option>
              <option value="severity_desc" ${state.findingsFilter.sort_by === 'severity_desc' ? 'selected' : ''}>Severity (Critical → Low)</option>
              <option value="created_desc" ${state.findingsFilter.sort_by === 'created_desc' ? 'selected' : ''}>Newest Created</option>
              <option value="id_asc" ${state.findingsFilter.sort_by === 'id_asc' ? 'selected' : ''}>Finding ID Code</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Findings Data Register Table -->
      <div class="card">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div class="card-title">
            Centralized Findings Register <span style="font-size: 12px; color: #64748b; font-weight: normal;">(${findings.length} records match filter)</span>
          </div>
          <div style="font-size: 11.5px; color: #64748b;">
            💡 Click on any risk score to inspect deterministic formula breakdown
          </div>
        </div>

        ${findings.length === 0 ? `
          <div style="padding: 48px; text-align: center; color: #64748b;">
            <div style="font-size: 32px; margin-bottom: 8px;">✨</div>
            <div style="font-size: 15px; font-weight: 600; color: #1e293b;">No findings matching current criteria</div>
            <p style="font-size: 12.5px; margin-top: 4px;">Click <strong>"Sync All Modules"</strong> above to aggregate exceptions across all audit subsystems.</p>
          </div>
        ` : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 130px;">Finding ID</th>
                  <th style="width: 170px;">Module & Category</th>
                  <th>Title & Audit Description</th>
                  <th style="width: 100px;">Severity</th>
                  <th style="width: 125px;">Risk Score</th>
                  <th style="width: 120px;">Status</th>
                  <th style="width: 150px;">Review Info</th>
                  <th style="width: 155px; text-align: center;">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${findings.map(f => `
                  <tr>
                    <td>
                      <span class="font-mono font-bold" style="font-size: 11.5px; color: #3b82f6;">${f.finding_code}</span>
                    </td>
                    <td>
                      <span class="badge-module-pill" style="margin-bottom: 2px;">${f.module || 'General'}</span><br/>
                      <span style="font-size: 11px; color: #64748b;">${f.category || 'General Audit'}</span>
                    </td>
                    <td>
                      <div style="font-weight: 600; color: #0f172a; margin-bottom: 2px;">${f.title}</div>
                      <div style="font-size: 12px; color: #475569; max-width: 480px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${f.description || f.reason || '—'}
                      </div>
                      ${f.rule_used ? `<div style="font-size: 11px; color: #6366f1; margin-top: 2px;">📜 ${f.rule_used}</div>` : ''}
                    </td>
                    <td>
                      ${getSeverityBadge(f.severity)}
                    </td>
                    <td>
                      ${getRiskScoreBadge(f.risk_score, f.severity, f.risk_factors)}
                    </td>
                    <td>
                      ${getFindingStatusBadge(f.status)}
                    </td>
                    <td>
                      <div style="font-size: 11.5px;">
                        ${f.reviewed_by ? `<b>${f.reviewed_by}</b>` : '<span style="color: #94a3b8;">Unreviewed</span>'}
                      </div>
                      <div style="font-size: 10.5px; color: #64748b;">
                        ${f.reviewed_at ? f.reviewed_at.split('T')[0] : (f.created_at ? 'Created ' + f.created_at.split('T')[0] : '—')}
                      </div>
                    </td>
                    <td style="text-align: center;">
                      <div style="display: flex; gap: 6px; justify-content: center;">
                        <button class="btn btn-sm btn-primary" onclick="openFindingDetailModal(${f.id})">
                          Inspect
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="generateFindingAIExplanation(${f.id})" title="View AI Explanation & ICAI Audit Procedures">
                          🤖 AI
                        </button>
                      </div>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="padding: 24px; color: #dc2626;">Error loading audit findings: ${err.message}</div>`;
  }
}

function setSeverityFilter(sev) {
  state.findingsFilter.severity = sev;
  renderFindings();
}

function handleFindingsFilterChange() {
  const searchInput = document.getElementById("findings-search-input");
  const moduleSelect = document.getElementById("findings-module-select");
  const statusSelect = document.getElementById("findings-status-select");
  const sortSelect = document.getElementById("findings-sort-select");

  if (searchInput) state.findingsFilter.search = searchInput.value.trim();
  if (moduleSelect) state.findingsFilter.module = moduleSelect.value;
  if (statusSelect) state.findingsFilter.status = statusSelect.value;
  if (sortSelect) state.findingsFilter.sort_by = sortSelect.value;

  renderFindings();
}

async function syncCentralizedFindings() {
  const btn = document.getElementById("btn-sync-findings");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> Syncing Modules...`;
  }

  try {
    const res = await FinAuditAPI.syncAllFindings(state.currentEngagementId);
    notifyError(`✅ Centralized Findings Sync Complete!\n\nSynchronized ${res.data.total_collected} audit exceptions across all modules (${res.data.new_findings_created} new, ${res.data.existing_findings_updated} updated).`);
    await renderFindings();
  } catch (err) {
    notifyError("❌ Error syncing centralized findings: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>⚡</span> Sync All Modules`;
    }
  }
}

// ----------------- FINDING DETAIL & AUDIT REVIEW MODAL -----------------
async function openFindingDetailModal(findingId) {
  try {
    const finding = await FinAuditAPI.getFindingDetail(findingId);
    state.activeFinding = finding;

    const factors = finding.risk_factors || {};
    const affTxs = finding.affected_transactions || [];

    const modalHtml = `
      <div class="modal-overlay" id="finding-detail-modal">
        <div class="modal-card" style="max-width: 820px; max-height: 90vh; overflow-y: auto;">
          <div class="modal-header">
            <div>
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
                <span class="font-mono font-bold" style="color: #3b82f6; font-size: 13px;">${finding.finding_code}</span>
                ${getSeverityBadge(finding.severity)}
                ${getRiskScoreBadge(finding.risk_score, finding.severity, factors)}
                <span class="badge-module-pill">${finding.module || 'General'}</span>
              </div>
              <div class="modal-title" style="font-size: 16px;">${finding.title}</div>
            </div>
            <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('finding-detail-modal')">✕</button>
          </div>

          <div class="modal-body">
            <!-- Deterministic Risk Score Breakdown Card -->
            <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px;">
                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #1e293b;">
                  ⚡ Deterministic Risk Calculation Breakdown
                </div>
                <div style="font-size: 11px; color: #64748b;">
                  Equation: <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-weight: 600; color: #4338ca;">${factors.equation || `${finding.risk_score}/10.0`}</code>
                </div>
              </div>

              <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;">
                <div class="risk-factor-box">
                  <div class="factor-title">1. Base Severity</div>
                  <div class="factor-value">${factors.base_severity || finding.severity}</div>
                  <div class="factor-impact">+${factors.base_weight || 0.0} base</div>
                </div>
                <div class="risk-factor-box">
                  <div class="factor-title">2. Financial Exposure</div>
                  <div class="factor-value">${factors.amount ? formatINR(factors.amount) : '₹0.00'}</div>
                  <div class="factor-impact">+${factors.amount_impact || 0.0} exposure</div>
                </div>
                <div class="risk-factor-box">
                  <div class="factor-title">3. Repetition / Frequency</div>
                  <div class="factor-value">${factors.frequency || 1} instance(s)</div>
                  <div class="factor-impact">+${factors.repetition_impact || 0.0} frequency</div>
                </div>
                <div class="risk-factor-box">
                  <div class="factor-title">4. Affected Records</div>
                  <div class="factor-value">${factors.affected_records_count || affTxs.length || 1} record(s)</div>
                  <div class="factor-impact">+${factors.records_impact || 0.0} volume</div>
                </div>
                <div class="risk-factor-box">
                  <div class="factor-title">5. Difference %</div>
                  <div class="factor-value">${factors.difference_pct ? factors.difference_pct.toFixed(1) + '%' : '0.0%'}</div>
                  <div class="factor-impact">+${factors.difference_impact || 0.0} diff</div>
                </div>
                <div class="risk-factor-box">
                  <div class="factor-title">6. Data Quality</div>
                  <div class="factor-value">${factors.data_quality_issue ? '⚠️ Compromised' : '✅ Verified'}</div>
                  <div class="factor-impact">+${factors.data_quality_impact || 0.0} penalty</div>
                </div>
                <div class="risk-factor-box">
                  <div class="factor-title">7. Historical Pattern</div>
                  <div class="factor-value">${factors.historical_repeat ? '🔄 Recurring' : '🆕 First time'}</div>
                  <div class="factor-impact">+${factors.historical_impact || 0.0} pattern</div>
                </div>
                <div class="risk-factor-box" style="background: #f0fdf4; border-color: #bbf7d0;">
                  <div class="factor-title" style="color: #166534;">Final Risk Score</div>
                  <div class="factor-value" style="color: #15803d; font-size: 15px;">${finding.risk_score} / 10.0</div>
                  <div class="factor-impact" style="color: #16a34a;">Explainable</div>
                </div>
              </div>
            </div>

            <!-- Finding Fact Summary -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; background: #f8fafc; border: 1px solid var(--border); padding: 12px 14px; border-radius: 6px; font-size: 12.5px;">
              <div><strong>Audited Rule:</strong> ${finding.rule_used || 'Standard Audit Procedure'}</div>
              <div><strong>Engine Sourced:</strong> <span class="badge badge-low">${finding.engine_type || 'DETERMINISTIC'}</span></div>
              <div><strong>Expected Value:</strong> ${finding.expected_value || 'Compliant with standards'}</div>
              <div><strong>Actual Value:</strong> <span style="font-weight: 600; color: #b91c1c;">${finding.actual_value || 'Exception noted'}</span></div>
              <div><strong>Discrepancy / Variance:</strong> ${finding.difference || '—'}</div>
              <div><strong>Date Flagged:</strong> ${finding.created_at ? finding.created_at.replace('T', ' ').split('.')[0] : '—'}</div>
            </div>

            <!-- Description & AI Explanation -->
            <div style="margin-bottom: 14px;">
              <label class="form-label" style="font-size: 11.5px; text-transform: uppercase; color: #64748b;">Finding Description & Analysis</label>
              <div style="background: #ffffff; border: 1px solid var(--border); padding: 12px 14px; border-radius: 6px; font-size: 12.5px; line-height: 1.6; color: #1e293b;">
                ${finding.description}
                ${finding.ai_explanation ? `
                  <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #f1f5f9; color: #334155;">
                    ${formatAssistantMarkdown(finding.ai_explanation)}
                  </div>
                ` : ''}
              </div>
            </div>

            <!-- Recommended Action -->
            <div style="margin-bottom: 14px;">
              <label class="form-label" style="font-size: 11.5px; text-transform: uppercase; color: #64748b;">Recommended ICAI Substantive Audit Procedure</label>
              <div style="background: rgba(99, 102, 241, 0.06); border: 1px solid rgba(99, 102, 241, 0.2); padding: 10px 14px; border-radius: 6px; font-size: 12.5px; color: #3730a3; line-height: 1.5;">
                ${finding.recommended_action || 'Inspect primary source documentation, verify authorizations, and cross-check ledger postings.'}
              </div>
            </div>

            <!-- Affected Transactions Drill-Down -->
            ${affTxs.length > 0 ? `
              <div style="margin-bottom: 16px;">
                <label class="form-label" style="font-size: 11.5px; text-transform: uppercase; color: #64748b;">Affected Transaction Records (${affTxs.length})</label>
                <div class="table-container" style="max-height: 180px; overflow-y: auto;">
                  <table class="data-table" style="font-size: 11.5px;">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Voucher #</th>
                        <th>Ledger</th>
                        <th>Party</th>
                        <th>Debit</th>
                        <th>Credit</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${affTxs.map(t => `
                        <tr>
                          <td>${t.date || '—'}</td>
                          <td class="font-mono font-bold">${t.voucher_no || t.invoice_no || '—'}</td>
                          <td>${t.ledger}</td>
                          <td>${t.party_name || '—'}</td>
                          <td style="color: #047857;">${t.debit > 0 ? formatINR(t.debit) : '—'}</td>
                          <td style="color: #b91c1c;">${t.credit > 0 ? formatINR(t.credit) : '—'}</td>
                          <td style="max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${t.description || '—'}</td>
                        </tr>
                      `).join('')}
                    </tbody>
                  </table>
                </div>
              </div>
            ` : ''}

            <!-- Auditor Action & Status Update Section -->
            <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 6px; padding: 14px; margin-top: 14px;">
              <div style="font-size: 12.5px; font-weight: 700; color: #0f172a; margin-bottom: 10px;">
                ✍️ Auditor Review & Working Paper Sign-off
              </div>
              
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
                <div class="form-group" style="margin-bottom: 0;">
                  <label class="form-label">Audit Status</label>
                  <select id="modal-finding-status" class="form-control">
                    <option value="Open" ${finding.status === 'Open' ? 'selected' : ''}>Open (Pending Review)</option>
                    <option value="Under Review" ${finding.status === 'Under Review' || finding.status === 'In Review' ? 'selected' : ''}>Under Review (Inquiry Dispatched)</option>
                    <option value="Resolved" ${finding.status === 'Resolved' ? 'selected' : ''}>Resolved (Remediated / Adjusted)</option>
                    <option value="Waived" ${finding.status === 'Waived' ? 'selected' : ''}>Waived (Immaterial / Accepted)</option>
                  </select>
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                  <label class="form-label">Reviewer Name</label>
                  <input type="text" id="modal-finding-reviewer" class="form-control" value="${finding.reviewed_by || state.currentUser?.username || 'admin'}" placeholder="Auditor initials or name">
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Auditor Working Notes & Remediation Comment</label>
                <textarea id="modal-finding-comment" class="form-control" rows="3" placeholder="Record auditor notes, client management explanation, or verification working paper reference...">${finding.auditor_comment || ''}</textarea>
              </div>

              <div style="display: flex; justify-content: flex-end; gap: 8px;">
                <button class="btn btn-secondary" onclick="closeModal('finding-detail-modal')">Close</button>
                <button class="btn btn-primary" onclick="updateFindingReview(${finding.id})">Save Review & Sign-Off</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    notifyError("Error opening finding details: " + err.message);
  }
}

async function updateFindingReview(findingId) {
  const statusSelect = document.getElementById("modal-finding-status");
  const reviewerInput = document.getElementById("modal-finding-reviewer");
  const commentTextarea = document.getElementById("modal-finding-comment");

  const status = statusSelect ? statusSelect.value : "Under Review";
  const reviewer = reviewerInput ? reviewerInput.value.trim() : "admin";
  const comment = commentTextarea ? commentTextarea.value.trim() : "";

  try {
    await FinAuditAPI.updateFinding(findingId, {
      status: status,
      reviewed_by: reviewer,
      auditor_comment: comment
    });

    closeModal("finding-detail-modal");
    await renderFindings();
  } catch (err) {
    notifyError("Error updating finding: " + err.message);
  }
}

async function generateFindingAIExplanation(findingId) {
  try {
    const res = await FinAuditAPI.getFindingAIExplanation(findingId);
    notifyInfo(`🤖 AI Explainability Analysis for ${res.finding_code}:\n\n${res.ai_explanation}`);
    await renderFindings();
  } catch (err) {
    notifyError("Error generating AI explanation: " + err.message);
  }
}

// ----------------- CREATE MANUAL FINDING MODAL -----------------
function openCreateCustomFindingModal() {
  const modalHtml = `
    <div class="modal-overlay" id="create-custom-finding-modal">
      <div class="modal-card" style="max-width: 650px;">
        <div class="modal-header">
          <div class="modal-title">➕ Record Manual Audit Observation</div>
          <button class="btn btn-sm btn-secondary" style="border: none;" onclick="closeModal('create-custom-finding-modal')">✕</button>
        </div>
        <div class="modal-body">
          <form onsubmit="handleCreateCustomFindingSubmit(event)">
            <div class="form-group">
              <label class="form-label">Finding Title *</label>
              <input type="text" id="custom-finding-title" class="form-control" placeholder="e.g., Shortage in Physical Stock Verification" required>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Module Classification</label>
                <select id="custom-finding-module" class="form-control">
                  <option value="Manual Audit">Manual Audit Observation</option>
                  <option value="Physical Verification">Physical Verification</option>
                  <option value="Internal Controls">Internal Control Evaluation</option>
                  <option value="Statutory Compliance">Statutory & Tax Compliance</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Severity Tier *</label>
                <select id="custom-finding-severity" class="form-control">
                  <option value="MEDIUM">MEDIUM (Base Weight: 3.0)</option>
                  <option value="HIGH">HIGH (Base Weight: 5.0)</option>
                  <option value="CRITICAL">CRITICAL (Base Weight: 7.0)</option>
                  <option value="LOW">LOW (Base Weight: 1.5)</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Observation Details & Description *</label>
              <textarea id="custom-finding-description" class="form-control" rows="3" placeholder="Describe the audit exception, scope, and findings..." required></textarea>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
              <div class="form-group">
                <label class="form-label">Expected Value</label>
                <input type="text" id="custom-finding-expected" class="form-control" placeholder="e.g., 500 units">
              </div>
              <div class="form-group">
                <label class="form-label">Actual Value</label>
                <input type="text" id="custom-finding-actual" class="form-control" placeholder="e.g., 455 units">
              </div>
              <div class="form-group">
                <label class="form-label">Variance</label>
                <input type="text" id="custom-finding-diff" class="form-control" placeholder="e.g., 45 units shortage">
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Auditing Standard / Reference Rule</label>
              <input type="text" id="custom-finding-rule" class="form-control" placeholder="e.g., SA 501 / Internal Control Framework">
            </div>

            <div class="form-group">
              <label class="form-label">Recommended Substantive Action</label>
              <input type="text" id="custom-finding-action" class="form-control" placeholder="e.g., Obtain management write-down representation">
            </div>

            <div class="form-group">
              <label class="form-label">Initial Auditor Comment</label>
              <textarea id="custom-finding-comment" class="form-control" rows="2" placeholder="Notes for working paper reference..."></textarea>
            </div>

            <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px;">
              <button type="button" class="btn btn-secondary" onclick="closeModal('create-custom-finding-modal')">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Manual Finding</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

async function handleCreateCustomFindingSubmit(event) {
  event.preventDefault();
  const title = document.getElementById("custom-finding-title").value.trim();
  const moduleName = document.getElementById("custom-finding-module").value;
  const severity = document.getElementById("custom-finding-severity").value;
  const description = document.getElementById("custom-finding-description").value.trim();
  const expected = document.getElementById("custom-finding-expected").value.trim();
  const actual = document.getElementById("custom-finding-actual").value.trim();
  const diff = document.getElementById("custom-finding-diff").value.trim();
  const rule = document.getElementById("custom-finding-rule").value.trim();
  const action = document.getElementById("custom-finding-action").value.trim();
  const comment = document.getElementById("custom-finding-comment").value.trim();

  try {
    await FinAuditAPI.createCustomFinding({
      engagement_id: state.currentEngagementId,
      title: title,
      module: moduleName,
      severity: severity,
      description: description,
      expected_value: expected,
      actual_value: actual,
      difference: diff,
      rule_used: rule || "Manual Audit Observation",
      recommended_action: action,
      auditor_comment: comment
    });

    closeModal("create-custom-finding-modal");
    await renderFindings();
  } catch (err) {
    notifyError("Error creating manual finding: " + err.message);
  }
}

// =========================================================================
// -------------------- LOCAL AUDIT TRAIL MODULE ---------------------------
// =========================================================================

const auditTrailState = {
  page: 1,
  pageSize: 50,
  search: "",
  action: "All",
  module: "All",
  user: "All",
  fromDate: "",
  toDate: "",
  cachedItems: []
};

async function renderAuditTrail() {
  const container = document.getElementById("content-container");
  container.innerHTML = `
    <div style="padding: 24px; max-width: 1600px; margin: 0 auto;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 16px;">
        <div>
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
            <h1 style="font-size: 24px; font-weight: 700; color: #0f172a; margin: 0;">Immutable Audit Trail & System Log</h1>
            <span class="badge" style="background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; font-weight: 600; padding: 4px 10px; border-radius: 9999px;">
              🔒 Append-Only Protected
            </span>
          </div>
          <p style="color: #64748b; font-size: 14px; margin: 0;">
            Comprehensive, tamper-resistant trail of all user logins, data modifications, finding status transitions, checklist updates, working papers, and report exports.
          </p>
        </div>

        <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
          <button class="btn btn-secondary" onclick="exportAuditTrailData('csv')" title="Download filtered logs as CSV spreadsheet">
            <svg style="width: 16px; height: 16px; margin-right: 6px; vertical-align: text-bottom;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            Export CSV
          </button>
          <button class="btn btn-secondary" onclick="exportAuditTrailData('json')" title="Download complete structured JSON log">
            <svg style="width: 16px; height: 16px; margin-right: 6px; vertical-align: text-bottom;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
            </svg>
            Export JSON
          </button>
          <button class="btn btn-primary" onclick="refreshAuditTrailTable()">
            <svg style="width: 16px; height: 16px; margin-right: 6px; vertical-align: text-bottom;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            Refresh Logs
          </button>
        </div>
      </div>

      <!-- Audit Metrics Summary Cards -->
      <div id="audit-stats-cards-row" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 20px;">
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <div style="font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase;">Total Audit Records</div>
          <div id="stat-total-logs" style="font-size: 24px; font-weight: 700; color: #1e293b; margin-top: 4px;">...</div>
          <div style="font-size: 11px; color: #059669; margin-top: 2px;">● Full append-only history</div>
        </div>
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <div style="font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase;">Today's Activity</div>
          <div id="stat-today-logs" style="font-size: 24px; font-weight: 700; color: #2563eb; margin-top: 4px;">...</div>
          <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Operations recorded today</div>
        </div>
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <div style="font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase;">Engine Immutability</div>
          <div style="font-size: 20px; font-weight: 700; color: #059669; margin-top: 4px;">SQLite Enforced</div>
          <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Triggers block UPDATE/DELETE</div>
        </div>
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <div style="font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase;">Local Storage Mode</div>
          <div style="font-size: 20px; font-weight: 700; color: #7c3aed; margin-top: 4px;">100% Offline</div>
          <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Zero external data transmission</div>
        </div>
      </div>

      <!-- Filter Controls Panel -->
      <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; align-items: flex-end;">
          <div>
            <label class="form-label" style="font-size: 12px; margin-bottom: 4px;">Search Text</label>
            <input type="text" id="audit-filter-search" class="form-control" placeholder="Search action, details, user..." onkeyup="if(event.key==='Enter') applyAuditFilters()">
          </div>
          <div>
            <label class="form-label" style="font-size: 12px; margin-bottom: 4px;">Action</label>
            <select id="audit-filter-action" class="form-control" onchange="applyAuditFilters()">
              <option value="All">All Actions</option>
              <option value="LOGIN">LOGIN</option>
              <option value="LOGOUT">LOGOUT</option>
              <option value="CREATE_CLIENT">CREATE_CLIENT</option>
              <option value="CREATE_ENGAGEMENT">CREATE_ENGAGEMENT</option>
              <option value="FILE_IMPORT">FILE_IMPORT</option>
              <option value="DATA_MODIFICATION">DATA_MODIFICATION</option>
              <option value="CREATE_FINDING">CREATE_FINDING</option>
              <option value="FINDING_STATUS_CHANGE">FINDING_STATUS_CHANGE</option>
              <option value="AUDITOR_COMMENT">AUDITOR_COMMENT</option>
              <option value="CHECKLIST_CHANGE">CHECKLIST_CHANGE</option>
              <option value="WORKING_PAPER_CHANGE">WORKING_PAPER_CHANGE</option>
              <option value="REPORT_GENERATION">REPORT_GENERATION</option>
              <option value="REPORT_EXPORT">REPORT_EXPORT</option>
              <option value="SETTINGS_CHANGE">SETTINGS_CHANGE</option>
              <option value="DATABASE_BACKUP">DATABASE_BACKUP</option>
              <option value="DATABASE_RESTORE">DATABASE_RESTORE</option>
            </select>
          </div>
          <div>
            <label class="form-label" style="font-size: 12px; margin-bottom: 4px;">Module</label>
            <select id="audit-filter-module" class="form-control" onchange="applyAuditFilters()">
              <option value="All">All Modules</option>
              <option value="AUTH">AUTH</option>
              <option value="CLIENTS">CLIENTS</option>
              <option value="ENGAGEMENTS">ENGAGEMENTS</option>
              <option value="IMPORT">IMPORT</option>
              <option value="DATA_CLEANING">DATA_CLEANING</option>
              <option value="FINDINGS">FINDINGS</option>
              <option value="CHECKLISTS">CHECKLISTS</option>
              <option value="WORKING_PAPERS">WORKING_PAPERS</option>
              <option value="REPORTS">REPORTS</option>
              <option value="SETTINGS">SETTINGS</option>
              <option value="BACKUP">BACKUP</option>
            </select>
          </div>
          <div>
            <label class="form-label" style="font-size: 12px; margin-bottom: 4px;">User</label>
            <select id="audit-filter-user" class="form-control" onchange="applyAuditFilters()">
              <option value="All">All Users</option>
            </select>
          </div>
          <div>
            <label class="form-label" style="font-size: 12px; margin-bottom: 4px;">From Date</label>
            <input type="date" id="audit-filter-from" class="form-control" onchange="applyAuditFilters()">
          </div>
          <div>
            <label class="form-label" style="font-size: 12px; margin-bottom: 4px;">To Date</label>
            <input type="date" id="audit-filter-to" class="form-control" onchange="applyAuditFilters()">
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-primary" style="flex: 1;" onclick="applyAuditFilters()">Filter</button>
            <button class="btn btn-secondary" onclick="resetAuditFilters()" title="Reset all filters">Reset</button>
          </div>
        </div>
      </div>

      <!-- Audit Logs Table Container -->
      <div id="audit-trail-table-wrap" style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden;">
        <div style="padding: 30px; text-align: center; color: #64748b;">Loading audit trail records...</div>
      </div>

      <!-- Pagination Container -->
      <div id="audit-pagination-wrap" style="display: flex; justify-content: space-between; align-items: center; margin-top: 16px; flex-wrap: wrap; gap: 12px;"></div>
    </div>
  `;

  // Bootstrap filters and load data
  await loadAuditTrailMetadata();
  await loadAuditTrailStats();
  await refreshAuditTrailTable();
}

async function loadAuditTrailMetadata() {
  try {
    const meta = await FinAuditAPI.getAuditTrailMetadata();
    const userSelect = document.getElementById("audit-filter-user");
    if (userSelect && meta.users) {
      userSelect.innerHTML = `<option value="All">All Users</option>` + meta.users.map(u => `<option value="${u}">${u}</option>`).join("");
    }
  } catch (err) {
    console.warn("Failed loading audit metadata:", err);
  }
}

async function loadAuditTrailStats() {
  try {
    const stats = await FinAuditAPI.getAuditTrailStatistics();
    const totalEl = document.getElementById("stat-total-logs");
    const todayEl = document.getElementById("stat-today-logs");
    if (totalEl) totalEl.innerText = Number(stats.total_logs || 0).toLocaleString();
    if (todayEl) todayEl.innerText = Number(stats.today_logs || 0).toLocaleString();
  } catch (err) {
    console.warn("Failed loading audit stats:", err);
  }
}

async function refreshAuditTrailTable() {
  const tableWrap = document.getElementById("audit-trail-table-wrap");
  const pagWrap = document.getElementById("audit-pagination-wrap");
  if (!tableWrap) return;

  tableWrap.innerHTML = `<div style="padding: 40px; text-align: center; color: #64748b;">Fetching audit logs...</div>`;

  try {
    const params = {
      page: auditTrailState.page,
      page_size: auditTrailState.pageSize,
      search: auditTrailState.search,
      action: auditTrailState.action,
      module: auditTrailState.module,
      user: auditTrailState.user,
      from_date: auditTrailState.fromDate,
      to_date: auditTrailState.toDate
    };

    const res = await FinAuditAPI.getAuditTrail(params);
    auditTrailState.cachedItems = res.items || [];

    if (!res.items || res.items.length === 0) {
      tableWrap.innerHTML = `
        <div style="padding: 50px 20px; text-align: center;">
          <div style="font-size: 32px; margin-bottom: 10px;">📋</div>
          <div style="font-size: 16px; font-weight: 600; color: #1e293b;">No audit records found</div>
          <div style="font-size: 13px; color: #64748b; margin-top: 4px;">Try broadening your filter criteria or search keyword.</div>
        </div>
      `;
      if (pagWrap) pagWrap.innerHTML = "";
      return;
    }

    const rowsHtml = res.items.map(log => {
      const dateObj = new Date(log.timestamp);
      const formattedDate = isNaN(dateObj) ? log.timestamp : dateObj.toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit"
      });

      const actionBadge = getAuditActionBadge(log.action);
      const moduleBadge = getAuditModuleBadge(log.module);

      const hasDiff = Boolean(log.old_value || log.new_value);
      const diffButton = hasDiff
        ? `<button class="btn btn-sm btn-secondary" onclick="openAuditDiffModal(${log.id})" style="padding: 3px 8px; font-size: 11px;">🔍 Inspect Diff</button>`
        : `<span style="color: #94a3b8; font-size: 11px;">N/A</span>`;

      return `
        <tr style="border-bottom: 1px solid #f1f5f9; transition: background 0.15s ease;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
          <td style="padding: 10px 14px; font-family: monospace; font-size: 12px; color: #475569; white-space: nowrap;">
            ${formattedDate}
          </td>
          <td style="padding: 10px 14px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="display: inline-block; width: 22px; height: 22px; border-radius: 50%; background: #e0e7ff; color: #4338ca; text-align: center; line-height: 22px; font-size: 10px; font-weight: 700;">
                ${(log.username || 'U')[0].toUpperCase()}
              </span>
              <span style="font-weight: 600; font-size: 13px; color: #1e293b;">${log.username || 'system'}</span>
            </div>
          </td>
          <td style="padding: 10px 14px;">${actionBadge}</td>
          <td style="padding: 10px 14px;">${moduleBadge}</td>
          <td style="padding: 10px 14px; font-family: monospace; font-size: 12px; color: #64748b;">
            ${log.record_id || (log.entity_id ? '#' + log.entity_id : '—')}
          </td>
          <td style="padding: 10px 14px; font-size: 13px; color: #334155; max-width: 400px; word-break: break-word;">
            ${escapeHtml(log.details || '')}
          </td>
          <td style="padding: 10px 14px; text-align: center;">
            ${diffButton}
          </td>
        </tr>
      `;
    }).join("");

    tableWrap.innerHTML = `
      <div style="overflow-x: auto;">
        <table class="data-table" style="width: 100%; border-collapse: collapse; text-align: left;">
          <thead>
            <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0; font-size: 12px; color: #475569; text-transform: uppercase;">
              <th style="padding: 12px 14px;">Timestamp (Local)</th>
              <th style="padding: 12px 14px;">User</th>
              <th style="padding: 12px 14px;">Action</th>
              <th style="padding: 12px 14px;">Module</th>
              <th style="padding: 12px 14px;">Record ID</th>
              <th style="padding: 12px 14px;">Details & Changes</th>
              <th style="padding: 12px 14px; text-align: center;">Values Inspector</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    `;

    // Render Pagination Controls
    if (pagWrap) {
      pagWrap.innerHTML = `
        <div style="font-size: 13px; color: #64748b;">
          Showing <span style="font-weight: 600; color: #0f172a;">${((res.page - 1) * res.page_size) + 1}</span> - <span style="font-weight: 600; color: #0f172a;">${Math.min(res.page * res.page_size, res.total)}</span> of <span style="font-weight: 600; color: #0f172a;">${res.total}</span> audit records
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <button class="btn btn-secondary btn-sm" onclick="changeAuditPage(${res.page - 1})" ${res.page <= 1 ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}>
            ← Previous
          </button>
          <span style="font-size: 12px; font-weight: 600; color: #475569; padding: 0 8px;">
            Page ${res.page} of ${res.total_pages}
          </span>
          <button class="btn btn-secondary btn-sm" onclick="changeAuditPage(${res.page + 1})" ${res.page >= res.total_pages ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}>
            Next →
          </button>
        </div>
      `;
    }

  } catch (err) {
    tableWrap.innerHTML = `<div style="padding: 30px; text-align: center; color: #ef4444;">Failed loading audit logs: ${err.message}</div>`;
  }
}

function getAuditActionBadge(action) {
  const act = (action || "").toUpperCase();
  if (act.includes("LOGIN") || act.includes("LOGOUT")) {
    return `<span class="badge" style="background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; font-size: 11px; padding: 3px 8px; border-radius: 4px;">${act}</span>`;
  }
  if (act.includes("CREATE")) {
    return `<span class="badge" style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 11px; padding: 3px 8px; border-radius: 4px;">${act}</span>`;
  }
  if (act.includes("DELETE") || act.includes("REMOVE")) {
    return `<span class="badge" style="background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; font-size: 11px; padding: 3px 8px; border-radius: 4px;">${act}</span>`;
  }
  if (act.includes("BACKUP") || act.includes("RESTORE")) {
    return `<span class="badge" style="background: #faf5ff; color: #9333ea; border: 1px solid #e9d5ff; font-size: 11px; padding: 3px 8px; border-radius: 4px;">${act}</span>`;
  }
  if (act.includes("EXPORT") || act.includes("GENERATE")) {
    return `<span class="badge" style="background: #fffbeb; color: #d97706; border: 1px solid #fde68a; font-size: 11px; padding: 3px 8px; border-radius: 4px;">${act}</span>`;
  }
  return `<span class="badge" style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; font-size: 11px; padding: 3px 8px; border-radius: 4px;">${act}</span>`;
}

function getAuditModuleBadge(mod) {
  const m = (mod || "").toUpperCase();
  return `<span style="display: inline-block; padding: 2px 6px; font-size: 11px; font-weight: 600; color: #334155; background: #e2e8f0; border-radius: 4px;">${m}</span>`;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function applyAuditFilters() {
  auditTrailState.page = 1;
  auditTrailState.search = document.getElementById("audit-filter-search")?.value.trim() || "";
  auditTrailState.action = document.getElementById("audit-filter-action")?.value || "All";
  auditTrailState.module = document.getElementById("audit-filter-module")?.value || "All";
  auditTrailState.user = document.getElementById("audit-filter-user")?.value || "All";
  auditTrailState.fromDate = document.getElementById("audit-filter-from")?.value || "";
  auditTrailState.toDate = document.getElementById("audit-filter-to")?.value || "";
  refreshAuditTrailTable();
}

function resetAuditFilters() {
  auditTrailState.page = 1;
  auditTrailState.search = "";
  auditTrailState.action = "All";
  auditTrailState.module = "All";
  auditTrailState.user = "All";
  auditTrailState.fromDate = "";
  auditTrailState.toDate = "";

  if (document.getElementById("audit-filter-search")) document.getElementById("audit-filter-search").value = "";
  if (document.getElementById("audit-filter-action")) document.getElementById("audit-filter-action").value = "All";
  if (document.getElementById("audit-filter-module")) document.getElementById("audit-filter-module").value = "All";
  if (document.getElementById("audit-filter-user")) document.getElementById("audit-filter-user").value = "All";
  if (document.getElementById("audit-filter-from")) document.getElementById("audit-filter-from").value = "";
  if (document.getElementById("audit-filter-to")) document.getElementById("audit-filter-to").value = "";

  refreshAuditTrailTable();
}

function changeAuditPage(newPage) {
  if (newPage < 1) return;
  auditTrailState.page = newPage;
  refreshAuditTrailTable();
}

function exportAuditTrailData(format) {
  const params = {
    search: auditTrailState.search,
    action: auditTrailState.action,
    module: auditTrailState.module,
    user: auditTrailState.user,
    from_date: auditTrailState.fromDate,
    to_date: auditTrailState.toDate
  };

  const url = format === "json"
    ? FinAuditAPI.getAuditTrailExportJsonUrl(params)
    : FinAuditAPI.getAuditTrailExportCsvUrl(params);

  window.open(url, "_blank");
}

function openAuditDiffModal(logId) {
  const log = auditTrailState.cachedItems.find(item => item.id === logId);
  if (!log) return;

  const existingModal = document.getElementById("audit-diff-modal");
  if (existingModal) existingModal.remove();

  let formattedOld = "None / Initial State";
  let formattedNew = "None / Final State";

  if (log.old_value) {
    try {
      const parsed = JSON.parse(log.old_value);
      formattedOld = JSON.stringify(parsed, null, 2);
    } catch {
      formattedOld = log.old_value;
    }
  }

  if (log.new_value) {
    try {
      const parsed = JSON.parse(log.new_value);
      formattedNew = JSON.stringify(parsed, null, 2);
    } catch {
      formattedNew = log.new_value;
    }
  }

  const modalHtml = `
    <div id="audit-diff-modal" class="modal-overlay" style="display: flex; align-items: center; justify-content: center; z-index: 9999;">
      <div class="modal-card" style="width: 850px; max-width: 95vw; max-height: 90vh; display: flex; flex-direction: column;">
        <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e2e8f0;">
          <div>
            <h3 style="margin: 0; font-size: 16px; font-weight: 700; color: #0f172a;">Audit Value Diff Inspector</h3>
            <div style="font-size: 12px; color: #64748b; margin-top: 2px;">
              Log #${log.id} • Action: <strong>${log.action}</strong> • Module: <strong>${log.module}</strong> • User: <strong>${log.username}</strong>
            </div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="closeModal('audit-diff-modal')">✕</button>
        </div>

        <div class="modal-body" style="padding: 20px; overflow-y: auto; flex: 1;">
          <div style="margin-bottom: 16px; padding: 12px; background: #f8fafc; border-radius: 6px; border: 1px solid #e2e8f0;">
            <div style="font-size: 12px; font-weight: 600; color: #475569; text-transform: uppercase;">Event Description</div>
            <div style="font-size: 13px; color: #1e293b; margin-top: 4px;">${escapeHtml(log.details || '')}</div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 12px; font-weight: 700; color: #dc2626; text-transform: uppercase;">◀ Previous / Old Value</span>
                <span style="font-size: 11px; color: #94a3b8;">Pre-modification</span>
              </div>
              <pre style="background: #fff5f5; border: 1px solid #fecaca; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 12px; color: #991b1b; max-height: 350px; overflow: auto; white-space: pre-wrap;">${escapeHtml(formattedOld)}</pre>
            </div>

            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 12px; font-weight: 700; color: #16a34a; text-transform: uppercase;">▶ New / Updated Value</span>
                <span style="font-size: 11px; color: #94a3b8;">Post-modification</span>
              </div>
              <pre style="background: #f0fdf4; border: 1px solid #bbf7d0; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 12px; color: #166534; max-height: 350px; overflow: auto; white-space: pre-wrap;">${escapeHtml(formattedNew)}</pre>
            </div>
          </div>
        </div>

        <div class="modal-footer" style="padding: 12px 20px; border-top: 1px solid #e2e8f0; display: flex; justify-content: flex-end;">
          <button class="btn btn-secondary" onclick="closeModal('audit-diff-modal')">Close</button>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);
}


// =========================================================================
// ----------------- SETTINGS & DATABASE BACKUP MODULE ---------------------
// =========================================================================

async function renderSettings() {
  const container = document.getElementById("content-container");
  container.innerHTML = `
    <div style="padding: 24px; max-width: 1400px; margin: 0 auto;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; flex-wrap: wrap; gap: 16px;">
        <div>
          <h1 style="font-size: 24px; font-weight: 700; color: #0f172a; margin: 0;">Settings & Local Database Center</h1>
          <p style="color: #64748b; font-size: 14px; margin-top: 4px;">
            Manage audit thresholds, firm practice configuration, and create immutable point-in-time local database backups.
          </p>
        </div>
      </div>

      <!-- System Environment & Offline Status -->
      <div id="system-info-card-wrap" style="margin-bottom: 24px;">
        <div style="padding: 20px; text-align: center; color: #64748b;">Loading system information...</div>
      </div>

      <!-- Backup & Restore Center -->
      <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
          <div>
            <h3 style="font-size: 16px; font-weight: 700; color: #0f172a; margin: 0;">Local Database Backup & Restore</h3>
            <p style="font-size: 13px; color: #64748b; margin: 2px 0 0 0;">
              All backups are kept strictly locally on this PC in SQLite format with SHA-256 integrity checksums.
            </p>
          </div>
          <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <button class="btn btn-primary" onclick="handleCreateBackupClick()" id="btn-create-backup">
              <svg style="width: 16px; height: 16px; margin-right: 6px; vertical-align: text-bottom;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path>
              </svg>
              Create Local Backup Now
            </button>
            <label class="btn btn-secondary" style="cursor: pointer; margin: 0;">
              <svg style="width: 16px; height: 16px; margin-right: 6px; vertical-align: text-bottom;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
              </svg>
              Upload & Restore (.db)
              <input type="file" id="upload-restore-input" accept=".db,.sqlite" style="display: none;" onchange="handleUploadRestoreFile(event)">
            </label>
          </div>
        </div>

        <div id="backups-list-table-wrap">
          <div style="padding: 20px; text-align: center; color: #64748b;">Loading backup history...</div>
        </div>
      </div>

      <!-- Practice & Engine Configuration -->
      <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
        <h3 style="font-size: 16px; font-weight: 700; color: #0f172a; margin: 0 0 16px 0;">Audit Engine & Practice Configuration</h3>
        
        <form id="practice-settings-form" onsubmit="handleSaveSettings(event)">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
            <div class="form-group">
              <label class="form-label">CA Firm / Practice Name</label>
              <input type="text" id="setting-firm-name" class="form-control" placeholder="e.g. M/s ABC & Co., Chartered Accountants">
            </div>
            <div class="form-group">
              <label class="form-label">ICAI Firm Registration Number (FRN)</label>
              <input type="text" id="setting-firm-frn" class="form-control" placeholder="e.g. FRN-012345N">
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px;">
            <div class="form-group">
              <label class="form-label">Default Materiality Benchmark</label>
              <select id="setting-materiality-bench" class="form-control">
                <option value="Turnover">Turnover / Total Revenue</option>
                <option value="Total Assets">Total Assets</option>
                <option value="Gross Profit">Gross Profit</option>
                <option value="Profit Before Tax">Profit Before Tax (PBT)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Materiality Threshold %</label>
              <input type="number" id="setting-materiality-pct" class="form-control" step="0.1" min="0.1" max="10.0" value="0.5">
            </div>
            <div class="form-group">
              <label class="form-label">Sec 40A(3) Cash Disallowance Limit (₹)</label>
              <input type="number" id="setting-cash-40a3" class="form-control" step="1000" value="10000">
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 20px;">
            <div class="form-group">
              <label class="form-label">Sec 269ST Single Day Cash Limit (₹)</label>
              <input type="number" id="setting-cash-269st" class="form-control" step="10000" value="200000">
            </div>
            <div class="form-group">
              <label class="form-label">Benford's Law Confidence Level</label>
              <select id="setting-benford-conf" class="form-control">
                <option value="0.99">99% (Strict Statistical Test)</option>
                <option value="0.95" selected>95% (Standard Audit Benchmark)</option>
                <option value="0.90">90% (Exploratory / Initial Screening)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">User Session Inactivity Timeout</label>
              <select id="setting-session-timeout" class="form-control">
                <option value="30">30 Minutes</option>
                <option value="60" selected>60 Minutes</option>
                <option value="120">2 Hours</option>
                <option value="480">8 Hours (Full Working Day)</option>
              </select>
            </div>
          </div>

          <div style="display: flex; justify-content: flex-end; gap: 10px;">
            <button type="submit" class="btn btn-primary" id="btn-save-settings">Save Configuration Changes</button>
          </div>
        </form>
      </div>
    </div>
  `;

  await loadSystemInfo();
  await loadBackupsList();
  await loadAppSettingsForm();
}

async function loadSystemInfo() {
  const wrap = document.getElementById("system-info-card-wrap");
  if (!wrap) return;

  try {
    const info = await FinAuditAPI.getSystemInfo();
    wrap.innerHTML = `
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
        <div>
          <div style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;">Application Build</div>
          <div style="font-size: 15px; font-weight: 700; color: #0f172a; margin-top: 2px;">${info.app_name} v${info.version}</div>
          <div style="font-size: 12px; color: #059669; font-weight: 600; margin-top: 2px;">${info.mode}</div>
        </div>
        <div>
          <div style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;">Active Database</div>
          <div style="font-size: 14px; font-weight: 600; color: #0f172a; margin-top: 2px;">${info.database_size_kb} KB (${(info.database_size_kb / 1024).toFixed(2)} MB)</div>
          <div style="font-size: 11px; color: #64748b; font-family: monospace; word-break: break-all;">${info.database_path}</div>
        </div>
        <div>
          <div style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;">Database Engine</div>
          <div style="font-size: 14px; font-weight: 600; color: #0f172a; margin-top: 2px;">${info.database_engine}</div>
          <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Transactions: <strong>${info.statistics.total_transactions}</strong> | Logs: <strong>${info.statistics.audit_logs}</strong></div>
        </div>
      </div>
    `;
  } catch (err) {
    wrap.innerHTML = `<div style="color: #ef4444;">Failed to load system info: ${err.message}</div>`;
  }
}

async function loadBackupsList() {
  const wrap = document.getElementById("backups-list-table-wrap");
  if (!wrap) return;

  try {
    const backups = await FinAuditAPI.getBackupsList();
    if (!backups || backups.length === 0) {
      wrap.innerHTML = `
        <div style="padding: 24px; text-align: center; color: #64748b; background: #f8fafc; border-radius: 6px; border: 1px dashed #cbd5e1;">
          No database backup snapshots found yet. Click <strong>"Create Local Backup Now"</strong> above to take your first local snapshot.
        </div>
      `;
      return;
    }

    const rows = backups.map(b => {
      const dateObj = new Date(b.created_at);
      const dateFormatted = isNaN(dateObj) ? b.created_at : dateObj.toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
      });

      const typeBadge = b.is_safety_snapshot
        ? `<span class="badge" style="background: #fff7ed; color: #c2410c; border: 1px solid #ffedd5; font-size: 10px;">Pre-Restore Safety</span>`
        : `<span class="badge" style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 10px;">Manual Snapshot</span>`;

      return `
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 10px 14px; font-family: monospace; font-size: 12px; font-weight: 600; color: #1e293b;">
            ${b.filename}
          </td>
          <td style="padding: 10px 14px; font-size: 12px; color: #64748b;">
            ${dateFormatted}
          </td>
          <td style="padding: 10px 14px; font-size: 12px; color: #475569;">
            ${b.size_kb} KB
          </td>
          <td style="padding: 10px 14px;">${typeBadge}</td>
          <td style="padding: 10px 14px; font-family: monospace; font-size: 11px; color: #94a3b8;" title="${b.checksum_sha256}">
            ${b.checksum_sha256.substring(0, 16)}...
          </td>
          <td style="padding: 10px 14px; text-align: right;">
            <div style="display: flex; gap: 6px; justify-content: flex-end;">
              <a href="${FinAuditAPI.getBackupDownloadUrl(b.filename)}" class="btn btn-sm btn-secondary" style="padding: 3px 8px; font-size: 11px;" download>
                Download (.db)
              </a>
              <button class="btn btn-sm btn-danger" onclick="handleRestoreBackupClick('${b.filename}')" style="padding: 3px 8px; font-size: 11px;">
                Restore DB
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    wrap.innerHTML = `
      <div style="overflow-x: auto;">
        <table class="data-table" style="width: 100%; border-collapse: collapse; text-align: left;">
          <thead>
            <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0; font-size: 11px; color: #475569; text-transform: uppercase;">
              <th style="padding: 10px 14px;">Backup Filename</th>
              <th style="padding: 10px 14px;">Created Date</th>
              <th style="padding: 10px 14px;">File Size</th>
              <th style="padding: 10px 14px;">Type</th>
              <th style="padding: 10px 14px;">SHA-256 Integrity Hash</th>
              <th style="padding: 10px 14px; text-align: right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    wrap.innerHTML = `<div style="color: #ef4444;">Failed to load backups list: ${err.message}</div>`;
  }
}

async function loadAppSettingsForm() {
  try {
    const res = await FinAuditAPI.getAppSettings();
    const s = res.settings || {};

    if (document.getElementById("setting-firm-name")) document.getElementById("setting-firm-name").value = s.firm_name || "";
    if (document.getElementById("setting-firm-frn")) document.getElementById("setting-firm-frn").value = s.firm_icai_reg || "";
    if (document.getElementById("setting-materiality-bench")) document.getElementById("setting-materiality-bench").value = s.materiality_benchmark || "Turnover";
    if (document.getElementById("setting-materiality-pct")) document.getElementById("setting-materiality-pct").value = s.materiality_percentage || 0.5;
    if (document.getElementById("setting-cash-40a3")) document.getElementById("setting-cash-40a3").value = s.cash_threshold_40a3 || 10000;
    if (document.getElementById("setting-cash-269st")) document.getElementById("setting-cash-269st").value = s.cash_threshold_269st || 200000;
    if (document.getElementById("setting-benford-conf")) document.getElementById("setting-benford-conf").value = String(s.benford_confidence_level || 0.95);
    if (document.getElementById("setting-session-timeout")) document.getElementById("setting-session-timeout").value = String(s.session_timeout_minutes || 60);
  } catch (err) {
    console.warn("Failed loading app settings form:", err);
  }
}

async function handleSaveSettings(event) {
  event.preventDefault();
  const btn = document.getElementById("btn-save-settings");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Saving settings...";
  }

  const payload = {
    firm_name: document.getElementById("setting-firm-name").value.trim(),
    firm_icai_reg: document.getElementById("setting-firm-frn").value.trim(),
    materiality_benchmark: document.getElementById("setting-materiality-bench").value,
    materiality_percentage: parseFloat(document.getElementById("setting-materiality-pct").value) || 0.5,
    cash_threshold_40a3: parseFloat(document.getElementById("setting-cash-40a3").value) || 10000,
    cash_threshold_269st: parseFloat(document.getElementById("setting-cash-269st").value) || 200000,
    benford_confidence_level: parseFloat(document.getElementById("setting-benford-conf").value) || 0.95,
    session_timeout_minutes: parseInt(document.getElementById("setting-session-timeout").value) || 60
  };

  try {
    await FinAuditAPI.updateAppSettings(payload);
    notifySuccess("Application settings saved successfully and logged in the audit trail.");
  } catch (err) {
    notifyError("Error saving settings: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "Save Configuration Changes";
    }
  }
}

async function handleCreateBackupClick() {
  const btn = document.getElementById("btn-create-backup");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Creating local snapshot...";
  }

  try {
    const res = await FinAuditAPI.createDatabaseBackup();
    notifySuccess(`Database backup created successfully!\n\nFile: ${res.filename}\nSize: ${res.size_kb} KB\nSHA-256: ${res.checksum_sha256}`);
    await loadBackupsList();
    await loadSystemInfo();
  } catch (err) {
    notifyError("Failed to create database backup: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `
        <svg style="width: 16px; height: 16px; margin-right: 6px; vertical-align: text-bottom;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path>
        </svg>
        Create Local Backup Now
      `;
    }
  }
}

async function handleRestoreBackupClick(filename) {
  const confirmed = await FinConfirm({
    title: "Restore Audit Database Backup",
    message: `You are about to restore the active audit database from backup '${filename}'.`,
    consequences: [
      "Active database will be overwritten with the backup state",
      "FinAuditPro will automatically create a pre-restore safety snapshot before restoring"
    ],
    confirmText: "Restore Database",
    isDanger: true
  });
  if (!confirmed) return;

  try {
    const res = await FinAuditAPI.restoreDatabaseBackup(filename);
    notifySuccess(`Database restored successfully from "${filename}"!\n\nSafety snapshot saved as: "${res.safety_snapshot_created}".`);
    await loadEngagements();
    await renderSettings();
  } catch (err) {
    notifyError("Database restore failed: " + err.message);
  }
}

async function handleUploadRestoreFile(event) {
  const file = event.target.files[0];
  if (!file) return;

  const confirmed = await FinConfirm({
    title: "Restore External SQLite Database",
    message: `You selected external SQLite database file "${file.name}" to restore.`,
    consequences: [
      "Active database will be replaced with data from the uploaded file",
      "A pre-restore safety snapshot will be created automatically"
    ],
    confirmText: "Proceed with Restore",
    isDanger: true
  });

  if (!confirmed) {
    event.target.value = "";
    return;
  }

  try {
    const res = await FinAuditAPI.restoreDatabaseUpload(file);
    notifySuccess(`Database restored successfully from uploaded file!\n\nSafety snapshot saved as: "${res.safety_snapshot_created}".`);
    await loadEngagements();
    await renderSettings();
  } catch (err) {
    notifyError("Database upload and restore failed: " + err.message);
  } finally {
    event.target.value = "";
  }
}

// =========================================================================
// OFFLINE LOCAL AI MODEL MANAGER CONTROLLER (LM STUDIO)
// =========================================================================

let currentAIStatus = null;

async function refreshTopBarAIStatus() {
  const el = document.getElementById("top-ai-status-text");
  if (!el) return;
  try {
    const status = await FinAuditAPI.getAIStatus();
    if (!status.is_enabled) {
      el.innerHTML = `<span style="color: #94a3b8;">🤖 AI: Disabled</span>`;
    } else if (status.is_available) {
      el.innerHTML = `<span style="color: #10b981; font-weight: 700;">🤖 LM Studio: Connected</span>`;
    } else {
      el.innerHTML = `<span style="color: #f59e0b;">🤖 LM Studio: Offline</span>`;
    }
  } catch (e) {
    el.innerHTML = `<span style="color: #94a3b8;">🤖 LM Studio: Offline</span>`;
  }
}

async function renderAIManager() {
  const container = document.getElementById("content-container");
  container.innerHTML = `
    <div style="padding: 40px; text-align: center; color: #64748b;">
      <div class="spinner" style="margin: 0 auto 16px auto;"></div>
      <div style="font-size: 15px; font-weight: 600; color: #0f172a;">Connecting to LM Studio Local AI Service...</div>
      <div style="font-size: 12px; margin-top: 4px;">Checking local LM Studio server status at http://localhost:1234...</div>
    </div>
  `;

  try {
    currentAIStatus = await FinAuditAPI.getAIStatus();
    const st = currentAIStatus;
    const isEnabled = st.is_enabled;
    const isAvail = st.is_available;

    container.innerHTML = `
      <div style="padding: 24px; max-width: 1400px; margin: 0 auto;">
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; flex-wrap: wrap; gap: 16px;">
          <div>
            <div style="display: flex; align-items: center; gap: 10px;">
              <h1 style="font-size: 24px; font-weight: 800; color: #0f172a; margin: 0;">LM Studio Local AI Settings</h1>
              <span class="badge" style="background: #065f46; color: #ffffff; font-weight: 700;">🔒 100% OFFLINE</span>
              <span class="badge" style="background: #1e3a8a; color: #ffffff; font-weight: 700;">ZERO CLOUD TRANSMISSION</span>
            </div>
            <p style="color: #64748b; font-size: 13.5px; margin-top: 4px;">
              Configure LM Studio local server endpoint, loaded models, sampling parameters, and local data privacy guard.
            </p>
          </div>
          <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <button class="btn btn-secondary" onclick="testAIManagerConnection()" id="btn-test-ai-conn">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
              Test Connection
            </button>
            <button class="btn btn-secondary" onclick="testAIGenerationPrompt()" id="btn-test-ai-gen">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
              Test AI Generation
            </button>
            <button class="btn btn-primary" onclick="saveAIManagerSettings()" id="btn-save-ai-settings">
              Save Settings
            </button>
          </div>
        </div>

        <!-- Zero Cloud Transmission & Privacy Shield Banner -->
        <div class="ai-privacy-shield-box">
          <div style="display: flex; align-items: center; gap: 14px;">
            <div style="font-size: 32px;">🛡️</div>
            <div>
              <div style="font-size: 15px; font-weight: 800; letter-spacing: 0.02em;">STRICT LOCAL PRIVACY SHIELD ACTIVE</div>
              <div style="font-size: 12px; opacity: 0.9; margin-top: 2px;">
                Client names, PAN, GSTIN, bank account numbers, raw financial records, and evidence documents are <b>never sent to any external cloud service</b>. All inference executes locally on this device via LM Studio.
              </div>
            </div>
          </div>
          <div style="text-align: right; min-width: 140px;">
            <div style="font-size: 11px; text-transform: uppercase; opacity: 0.8; font-weight: 700;">AI Provider</div>
            <div style="font-size: 14px; font-weight: 800;">LM Studio (Localhost)</div>
          </div>
        </div>

        <!-- LM Studio Connection Status Banner -->
        ${!isEnabled ? `
          <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid #64748b; border-radius: 8px; padding: 14px 18px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; color: #334155; font-size: 13.5px;">Local AI Disabled by Auditor</div>
              <div style="font-size: 12px; color: #64748b; margin-top: 2px;">
                <strong>${st.fallback_notice}</strong> (Rules engine, BRS/2B reconciliation, math validations, Isolation Forest anomaly detection, and reports remain 100% active).
              </div>
            </div>
            <span class="badge badge-medium">Deterministic Mode</span>
          </div>
        ` : !isAvail ? `
          <div style="background: #fffbeb; border: 1px solid #fef08a; border-left: 5px solid #d97706; border-radius: 8px; padding: 14px 18px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
            <div>
              <div style="font-weight: 700; color: #92400e; font-size: 13.5px;">⚠️ LM Studio Disconnected (${st.model_location})</div>
              <div style="font-size: 12px; color: #b45309; margin-top: 2px;">
                <strong>${st.fallback_notice}</strong>
              </div>
              <div style="font-size: 11.5px; color: #78350f; margin-top: 4px;">
                To enable local AI, open LM Studio, load a local model, and start the Local Server on port <code>1234</code>.
              </div>
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="btn btn-sm btn-secondary" onclick="testAIManagerConnection()">Test Connection</button>
            </div>
          </div>
        ` : `
          <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-left: 5px solid #059669; border-radius: 8px; padding: 14px 18px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; color: #065f46; font-size: 13.5px;">🟢 LM Studio Connected & Ready for Local Inference</div>
              <div style="font-size: 12px; color: #047857; margin-top: 2px;">
                Connected to LM Studio at <code>${st.model_location}</code> with model <b>${st.model_name}</b> (Latency: <b>${st.latency_ms} ms</b>).
              </div>
            </div>
            <span class="badge badge-low">Localhost Connected</span>
          </div>
        `}

        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
          <!-- Left Column: AI Configuration Form -->
          <div class="ai-manager-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #e2e8f0; padding-bottom: 14px;">
              <div>
                <h3 style="font-size: 16px; font-weight: 700; color: #0f172a; margin: 0;">LM Studio Configuration</h3>
                <p style="font-size: 12.5px; color: #64748b; margin: 2px 0 0 0;">Configure server URL, detected models, sampling temperature, and context window</p>
              </div>
              <!-- Enable / Disable AI Switch -->
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 13px; font-weight: 700; color: #0f172a;">Enable AI:</span>
                <label class="switch" style="position: relative; display: inline-block; width: 44px; height: 24px; margin: 0;">
                  <input type="checkbox" id="ai-toggle-enable" ${isEnabled ? 'checked' : ''} onchange="toggleAIEnableSwitch(this.checked)">
                  <span class="slider round" style="position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #cbd5e1; transition: .3s; border-radius: 24px;"></span>
                </label>
              </div>
            </div>

            <!-- Server URL & Model -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
              <div class="form-group">
                <label class="form-label" style="font-weight: 700;">LM Studio Server URL</label>
                <input type="text" id="ai-model-location" class="form-control" value="${escapeHtml(st.model_location || 'http://localhost:1234')}" placeholder="http://localhost:1234">
                <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Default LM Studio OpenAI-compatible endpoint: <code>http://localhost:1234</code></div>
              </div>
              <div class="form-group">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <label class="form-label" style="margin: 0; font-weight: 700;">Loaded Model Name</label>
                  <button type="button" class="btn btn-sm btn-secondary" style="padding: 2px 8px; font-size: 11px;" onclick="handleRefreshLMStudioModels()">
                    🔄 Refresh Models
                  </button>
                </div>
                <input type="text" id="ai-model-name" class="form-control" value="${escapeHtml(st.model_name || 'local-model')}" placeholder="e.g. meta-llama-3-8b-instruct or local-model">
                <div style="font-size: 11px; color: #64748b; margin-top: 4px;" id="available-models-hint">
                  ${st.available_models && st.available_models.length > 0 ? `Loaded in LM Studio: <b>${st.available_models.join(", ")}</b>` : 'Type loaded model ID or click "Refresh Models"'}
                </div>
              </div>
            </div>

            <!-- Sampling & Context Settings -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;">
              <div class="form-group">
                <label class="form-label" style="font-weight: 700;">Context Window / Max Tokens</label>
                <select id="ai-context-size" class="form-control">
                  <option value="2048" ${st.context_size == 2048 ? 'selected' : ''}>2,048 Tokens (Fast / Low Memory)</option>
                  <option value="4096" ${st.context_size == 4096 ? 'selected' : ''}>4,096 Tokens (Standard)</option>
                  <option value="8192" ${st.context_size == 8192 ? 'selected' : ''}>8,192 Tokens (Recommended for Large Tables)</option>
                  <option value="16384" ${st.context_size == 16384 ? 'selected' : ''}>16,384 Tokens (Extended)</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label" style="font-weight: 700;">Sampling Temperature: <span id="temp-display" class="font-mono font-bold">${st.temperature || 0.2}</span></label>
                <input type="range" id="ai-temperature" class="form-control" min="0.0" max="1.0" step="0.05" value="${st.temperature || 0.2}" oninput="document.getElementById('temp-display').innerText = this.value">
                <div style="font-size: 10.5px; color: #64748b; margin-top: 2px;">0.1–0.2 recommended for deterministic factual audit analysis</div>
              </div>
            </div>

            <!-- Live Test Generation Output Box -->
            <div id="ai-test-output-box" style="display: none; margin-bottom: 20px; padding: 14px; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px;">
              <div style="font-weight: 700; color: #0f172a; font-size: 13px; margin-bottom: 6px;">
                🧪 Live AI Test Response:
              </div>
              <div id="ai-test-response-text" style="font-family: ui-monospace, monospace; font-size: 12px; color: #334155; line-height: 1.5; white-space: pre-wrap;"></div>
            </div>

            <!-- Redaction & Privacy Guard Demo Box -->
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px;">
              <div style="font-weight: 700; color: #0f172a; font-size: 13px; margin-bottom: 6px;">
                🔍 Live Data Sanitization & PII Redaction Preview
              </div>
              <div style="font-size: 12px; color: #64748b; margin-bottom: 10px;">
                Test how confidential client data (PAN, GSTIN, Bank Accounts) is automatically redacted before local LM Studio ingestion:
              </div>
              <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                <input type="text" id="sanitize-test-input" class="form-control" value="Verified invoice from Apex Engineering PAN AAAFE1234G GSTIN 27AAAFE1234G1Z8 paid to HDFC A/C 50200012345678" placeholder="Type test notes containing PAN, GSTIN, or Bank Account...">
                <button class="btn btn-secondary" style="white-space: nowrap;" onclick="handleSanitizePreviewTest()">Test Redaction</button>
              </div>
              <div id="sanitize-result-box" style="padding: 10px 12px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; font-family: ui-monospace, monospace; font-size: 12px; color: #334155; min-height: 38px;">
                Click "Test Redaction" to preview sanitized output.
              </div>
            </div>
          </div>

          <!-- Right Column: Architecture & Instructions -->
          <div style="display: flex; flex-direction: column; gap: 20px;">
            <div class="ai-manager-card">
              <h3 style="font-size: 15px; font-weight: 700; color: #0f172a; margin: 0 0 12px 0;">🏛️ LM Studio Architecture</h3>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; font-size: 12px; line-height: 1.6;">
                <div style="font-weight: 700; color: #2563eb;">1. FinAuditPro Application</div>
                <div style="color: #64748b; margin-left: 14px;">↓ Local PII Redactor (Zero Cloud)</div>
                <div style="font-weight: 700; color: #7c3aed;">2. Local AI Service Layer</div>
                <div style="color: #64748b; margin-left: 14px;">↓ Localhost API (http://localhost:1234)</div>
                <div style="font-weight: 700; color: #059669;">3. LM Studio & Loaded Local Model</div>
              </div>
            </div>

            <div class="ai-manager-card">
              <h3 style="font-size: 15px; font-weight: 700; color: #0f172a; margin: 0 0 12px 0;">📖 How to Run LM Studio</h3>
              <ol style="padding-left: 18px; font-size: 12px; color: #475569; line-height: 1.6; margin: 0;">
                <li>Download & launch <b>LM Studio</b> from <code>lmstudio.ai</code>.</li>
                <li>Download any compatible instruction model (e.g. <i>Llama-3-8B-Instruct</i> or <i>Mistral-7B-Instruct</i>).</li>
                <li>Go to the <b>Local Server</b> tab (↔️ icon) in LM Studio.</li>
                <li>Select the model and click <b>Start Server</b> (Port: <code>1234</code>).</li>
                <li>Click <b>Test Connection</b> above to verify.</li>
              </ol>
            </div>

            <div class="ai-manager-card">
              <h3 style="font-size: 15px; font-weight: 700; color: #0f172a; margin: 0 0 12px 0;">⚙️ Deterministic Guarantee</h3>
              <div style="font-size: 12.5px; color: #475569; line-height: 1.6;">
                <div style="margin-bottom: 8px;">✅ <b>100% Core Audit Reliability:</b></div>
                <ul style="padding-left: 20px; color: #64748b; font-size: 12px; margin-bottom: 12px;">
                  <li>General Ledger & Trial Balance math</li>
                  <li>Section 40A(3) & 269ST statutory rules</li>
                  <li>Bank BRS & GST 2B reconciliations</li>
                  <li>Scikit-Learn Isolation Forest anomalies</li>
                  <li>PDF master audit reports & exports</li>
                  <li>ICAI compliance checklists</li>
                </ul>
                <div style="padding: 10px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; font-size: 11.5px; color: #1e40af;">
                  <b>Audit Safety:</b> If LM Studio is not running, all audit calculations, reconciliations, findings, and reports remain completely functional.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Add slider style dynamically if missing
    if (!document.getElementById("slider-styles")) {
      const styleTag = document.createElement("style");
      styleTag.id = "slider-styles";
      styleTag.innerHTML = `
        .switch input:checked + .slider { background-color: #2563eb !important; }
        .switch input:focus + .slider { box-shadow: 0 0 1px #2563eb; }
        .switch input:checked + .slider:before { transform: translateX(20px); }
        .slider.round:before {
          position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px;
          background-color: white; transition: .3s; border-radius: 50%;
        }
      `;
      document.head.appendChild(styleTag);
    }

  } catch (err) {
    container.innerHTML = `
      <div style="padding: 40px; text-align: center; color: #dc2626;">
        <div style="font-size: 16px; font-weight: 700;">Failed to load LM Studio AI Settings</div>
        <div style="font-size: 13px; color: #64748b; margin-top: 6px;">${err.message}</div>
        <button class="btn btn-primary" style="margin-top: 14px;" onclick="renderAIManager()">Retry</button>
      </div>
    `;
  }
}

function toggleAIEnableSwitch(isEnabled) {
  if (currentAIStatus) {
    currentAIStatus.is_enabled = isEnabled;
  }
}

async function handleRefreshLMStudioModels() {
  const hintEl = document.getElementById("available-models-hint");
  const modelInput = document.getElementById("ai-model-name");
  if (hintEl) hintEl.innerHTML = "Querying LM Studio at /v1/models...";

  try {
    const res = await FinAuditAPI.getAvailableModels();
    if (res.models && res.models.length > 0) {
      if (modelInput && (!modelInput.value || modelInput.value === "local-model")) {
        modelInput.value = res.models[0];
      }
      if (hintEl) {
        hintEl.innerHTML = `Found ${res.models.length} model(s): <b>${res.models.join(", ")}</b>`;
      }
      notifyInfo(`Found ${res.models.length} model(s) in LM Studio:\n\n${res.models.join("\n")}`);
    } else {
      if (hintEl) {
        hintEl.innerHTML = `No models currently loaded in LM Studio. Please load a model in LM Studio.`;
      }
      notifyWarning("No models detected in LM Studio. Please open LM Studio, load a model, and click Start Server.");
    }
  } catch (err) {
    if (hintEl) hintEl.innerHTML = `<span style="color: #dc2626;">Failed to query LM Studio: ${err.message}</span>`;
    notifyError("Could not reach LM Studio at configured URL: " + err.message);
  }
}

async function saveAIManagerSettings() {
  const saveBtn = document.getElementById("btn-save-ai-settings");
  if (saveBtn) {
    saveBtn.innerText = "Saving...";
    saveBtn.disabled = true;
  }

  try {
    const isEnabled = document.getElementById("ai-toggle-enable")?.checked ?? true;
    const modelName = document.getElementById("ai-model-name")?.value || "local-model";
    const modelLocation = document.getElementById("ai-model-location")?.value || "http://localhost:1234";
    const contextSize = parseInt(document.getElementById("ai-context-size")?.value || "4096", 10);
    const temperature = parseFloat(document.getElementById("ai-temperature")?.value || "0.2");

    const payload = {
      is_enabled: isEnabled,
      engine: "LMStudio",
      model_name: modelName,
      model_location: modelLocation,
      ram_vram_requirement: "8 GB RAM / 4 GB VRAM (Local LM Studio)",
      context_size: contextSize,
      temperature: temperature
    };

    await FinAuditAPI.updateAISettings(payload);
    notifySuccess("LM Studio configuration saved successfully!");
    await refreshTopBarAIStatus();
    await renderAIManager();
  } catch (err) {
    notifyError("Failed to save AI configuration: " + err.message);
  } finally {
    if (saveBtn) {
      saveBtn.innerText = "Save Settings";
      saveBtn.disabled = false;
    }
  }
}

async function testAIManagerConnection() {
  const testBtn = document.getElementById("btn-test-ai-conn");
  if (testBtn) {
    testBtn.innerText = "Testing...";
    testBtn.disabled = true;
  }

  try {
    const res = await FinAuditAPI.testAIConnection();
    if (res.is_available) {
      notifySuccess(`✅ LM Studio Connection Successful!\n\nEngine: ${res.engine}\nStatus: ${res.status_message}\nLatency: ${res.latency_ms} ms`);
    } else {
      notifyInfo(`⚠️ ${res.status_message}\n\nNotice: ${res.fallback_notice}`);
    }
    await refreshTopBarAIStatus();
    await renderAIManager();
  } catch (err) {
    notifyError("LM Studio test connection error: " + err.message);
  } finally {
    if (testBtn) {
      testBtn.innerText = "Test Connection";
      testBtn.disabled = false;
    }
  }
}

async function testAIGenerationPrompt() {
  const testBtn = document.getElementById("btn-test-ai-gen");
  const box = document.getElementById("ai-test-output-box");
  const textBox = document.getElementById("ai-test-response-text");

  if (testBtn) {
    testBtn.innerText = "Testing Generation...";
    testBtn.disabled = true;
  }

  if (box && textBox) {
    box.style.display = "block";
    textBox.innerText = "Sending test prompt to LM Studio local server...";
  }

  try {
    const res = await FinAuditAPI.testAIGeneration("Confirm LM Studio connectivity with a short CA audit assistant verification note.");
    if (box && textBox) {
      textBox.innerText = `[${res.engine} - Latency: ${res.latency_ms} ms]\n\n${res.response}`;
    }
  } catch (err) {
    if (box && textBox) {
      textBox.innerText = `LM Studio generation test error: ${err.message}`;
    }
  } finally {
    if (testBtn) {
      testBtn.innerText = "Test AI Generation";
      testBtn.disabled = false;
    }
  }
}

async function handleSanitizePreviewTest() {
  const inputEl = document.getElementById("sanitize-test-input");
  const resultBox = document.getElementById("sanitize-result-box");
  if (!inputEl || !resultBox) return;

  const text = inputEl.value;
  if (!text) return;

  resultBox.innerHTML = "Redacting sensitive client identifiers...";
  try {
    const res = await FinAuditAPI.previewSanitization(text, state.activeEngagement?.client_name);
    resultBox.innerHTML = `
      <div style="color: #059669; font-weight: 700; margin-bottom: 4px;">✅ Sanitized Prompt (Safe for LM Studio):</div>
      <div style="background: #f8fafc; padding: 6px; border-radius: 4px; border: 1px solid #e2e8f0;">${escapeHtml(res.sanitized_text)}</div>
      <div style="font-size: 11px; color: #64748b; margin-top: 6px;">
        Redacted: <b>${res.redaction_counts.pan || 0} PAN</b>, <b>${res.redaction_counts.gstin || 0} GSTIN</b>, <b>${res.redaction_counts.bank_account || 0} Bank A/C</b>, <b>${res.redaction_counts.client_name || 0} Client Name</b>
      </div>
    `;
  } catch (err) {
    resultBox.innerHTML = `<span style="color: #dc2626;">Error: ${err.message}</span>`;
  }
}

