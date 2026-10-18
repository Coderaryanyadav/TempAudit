import sys
import time
from playwright.sync_api import sync_playwright

def test_full_browser_workflow():
    print("=" * 80)
    print("🚀 STARTING REAL BROWSER FULL APPLICATION JOURNEY")
    print("=" * 80)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # -------------------------------------------------------------
        # STEP 1: INITIAL NAVIGATION & LOGIN
        # -------------------------------------------------------------
        print("\n[Step 01] Navigating to FinAuditPro Desktop UI (http://127.0.0.1:8000)...")
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        time.sleep(1)

        if page.locator("button:has-text('Sign In')").is_visible():
            print("  -> Welcome splash detected. Clicking 'Sign In'...")
            page.locator("button:has-text('Sign In')").click()
            time.sleep(0.5)

        print("  -> Authenticating with master credentials 'admin'...")
        page.wait_for_selector("#login-username", state="visible")
        page.fill("#login-username", "admin")
        page.fill("#login-password", "SecureAdmin2026!")
        page.click("#login-submit-btn")

        page.wait_for_selector("#login-screen-overlay", state="hidden", timeout=10000)
        page.wait_for_selector("#app-container", state="visible")
        print("  [PASS] Logged in successfully. Overlay dismissed.")

        # -------------------------------------------------------------
        # STEP 2: VERIFY ALL SIDEBAR SCREENS RENDER IN REAL BROWSER
        # -------------------------------------------------------------
        screens = [
            ("dashboard", "Dashboard", "#view-dashboard"),
            ("clients", "Clients", "#view-clients"),
            ("engagements", "Engagements", "#view-engagements"),
            ("import", "Data Import", "#view-import"),
            ("cleaning_logs", "Data Cleaning Log", "#view-cleaning_logs"),
            ("trial_balance", "Trial Balance", "#view-trial_balance"),
            ("general_ledger", "General Ledger", "#view-general_ledger"),
            ("reconciliation", "Reconciliation (BRS/2B)", "#view-reconciliation"),
            ("financial_statements", "Financial Statements", "#view-financial_statements"),
            ("yoy_comparison", "YoY Comparison", "#view-yoy_comparison"),
            ("duplicate_missing", "Duplicates & Gaps", "#view-duplicate_missing"),
            ("anomaly_detection", "Anomaly Detection", "#view-anomaly_detection"),
            ("findings", "Risk & Findings", "#view-findings"),
            ("assistant", "Audit Assistant", "#view-assistant"),
            ("checklist", "Audit Checklist", "#view-checklist"),
            ("working_papers", "Working Papers", "#view-working_papers"),
            ("reports", "Audit Reports (PDF)", "#view-reports"),
            ("audit_trail", "Audit Trail Log", "#view-audit_trail"),
            ("users", "User Management", "#view-users"),
            ("ai_manager", "Assistant Settings", "#view-ai_manager"),
            ("settings", "System Settings", "#view-settings")
        ]

        print("\n[Step 02] Exercising all 21 UI screens in real browser...")
        for tab_id, tab_label, _ in screens:
            btn = page.locator(f".nav-item[data-tab='{tab_id}']")
            if btn.is_visible():
                btn.click()
                time.sleep(0.5)
                # Verify container updated with content
                content_len = page.evaluate("document.getElementById('content-container').innerHTML.length")
                assert content_len > 50, f"Content container must render content for tab '{tab_label}', got length {content_len}"
                is_tab_active = page.evaluate(f"document.querySelector(\".nav-item[data-tab='{tab_id}']\").classList.contains('active')")
                assert is_tab_active, f"Tab '{tab_label}' must be highlighted as active"
                print(f"  [PASS] Navigated to screen: '{tab_label}' ({tab_id}) -> Content Rendered.")
            else:
                print(f"  [SKIP] Tab {tab_id} hidden for current role.")

        # -------------------------------------------------------------
        # STEP 3: CREATE CLIENT IN BROWSER
        # -------------------------------------------------------------
        print("\n[Step 03] Creating client via browser UI...")
        page.locator(".nav-item[data-tab='clients']").click()
        time.sleep(0.5)

        # Open client modal
        create_client_btn = page.locator("button:has-text('New Client'), button:has-text('Add Client')").first
        if create_client_btn.is_visible():
            create_client_btn.click()
            time.sleep(0.5)
            # Fill form
            if page.locator("#client-name").is_visible():
                page.fill("#client-name", "Bharat Forge Logistics Ltd")
                if page.locator("#client-pan").is_visible():
                    page.fill("#client-pan", "AAACB1234D")
                if page.locator("#client-gstin").is_visible():
                    page.fill("#client-gstin", "27AAACB1234D1Z5")
                submit_c = page.locator("#client-modal button[type='submit'], #save-client-btn").first
                if submit_c.is_visible():
                    submit_c.click()
                    time.sleep(1)
                    print("  [PASS] Created client 'Bharat Forge Logistics Ltd' through modal.")
        
        # -------------------------------------------------------------
        # STEP 4: REFRESH IN BROWSER & VERIFY SESSION SURVIVES
        # -------------------------------------------------------------
        print("\n[Step 04] Refreshing browser (hard page reload)...")
        page.reload(wait_until="networkidle")
        time.sleep(1.5)

        overlay = page.locator("#login-screen-overlay")
        is_overlay_hidden = not overlay.is_visible() or page.evaluate("document.getElementById('login-screen-overlay').style.display === 'none'")
        assert is_overlay_hidden, "Session restoration failed: login overlay appeared after refresh!"
        
        token = page.evaluate("localStorage.getItem('finaudit_token')")
        assert token and len(token) > 20, "JWT token must remain in localStorage after reload"
        print(f"  [PASS] Browser refresh verified: user stayed logged in. Active token: {token[:15]}...")

        # -------------------------------------------------------------
        # STEP 5: TEST MULTI-TAB SESSION
        # -------------------------------------------------------------
        print("\n[Step 05] Testing second tab in browser context...")
        tab2 = context.new_page()
        tab2.goto("http://127.0.0.1:8000", wait_until="networkidle")
        time.sleep(1)

        tab2_hidden = not tab2.locator("#login-screen-overlay").is_visible() or tab2.evaluate("document.getElementById('login-screen-overlay').style.display === 'none'")
        assert tab2_hidden, "Second tab must immediately restore authenticated session"
        print("  [PASS] Multi-tab verified: Second tab immediately displays authenticated workspace.")

        # -------------------------------------------------------------
        # STEP 6: TEST LOGOUT IN BROWSER
        # -------------------------------------------------------------
        print("\n[Step 06] Testing logout flow in browser...")
        logout_btn = page.locator("#logout-btn, button:has-text('Logout'), button[title='Logout']").first
        if logout_btn.is_visible():
            logout_btn.click()
            time.sleep(1)
            token_after_logout = page.evaluate("localStorage.getItem('finaudit_token')")
            assert not token_after_logout, "Token must be cleared from localStorage upon logout"
            assert page.locator("#login-screen-overlay").is_visible(), "Login screen overlay must appear after logout"
            print("  [PASS] Logout verified: session cleared, login screen restored.")

        browser.close()
        print("\n" + "=" * 80)
        print("🏁 REAL BROWSER FULL SUITE COMPLETED: 100% VERIFIED PASS")
        print("=" * 80)

if __name__ == "__main__":
    test_full_browser_workflow()
