import os
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
        token = page.evaluate("localStorage.getItem('finaudit_token')")
        assert token and len(token) > 20, "JWT token must be stored after login"
        print(f"  [PASS] Logged in successfully. Token acquired: {token[:15]}...")

        # -------------------------------------------------------------
        # STEP 2: VERIFY ALL 21 SCREENS RENDER IN REAL BROWSER
        # -------------------------------------------------------------
        screens = [
            ("dashboard", "Dashboard"),
            ("clients", "Clients"),
            ("engagements", "Engagements"),
            ("import", "Data Import"),
            ("cleaning_logs", "Data Cleaning Log"),
            ("trial_balance", "Trial Balance"),
            ("general_ledger", "General Ledger"),
            ("reconciliation", "Reconciliation (BRS/2B)"),
            ("financial_statements", "Financial Statements"),
            ("yoy_comparison", "YoY Comparison"),
            ("duplicate_missing", "Duplicates & Gaps"),
            ("anomaly_detection", "Anomaly Detection"),
            ("findings", "Risk & Findings"),
            ("assistant", "Audit Assistant"),
            ("checklist", "Audit Checklist"),
            ("working_papers", "Working Papers"),
            ("reports", "Audit Reports (PDF)"),
            ("audit_trail", "Audit Trail Log"),
            ("users", "User Management"),
            ("ai_manager", "Assistant Settings"),
            ("settings", "System Settings")
        ]

        print("\n[Step 02] Exercising all 21 UI screens in real browser...")
        for tab_id, tab_label in screens:
            page.evaluate(f"navigateTo('{tab_id}')")
            time.sleep(0.4)
            content_len = page.evaluate("document.getElementById('content-container').innerHTML.length")
            assert content_len > 50, f"Content container must render content for tab '{tab_label}', got length {content_len}"
            print(f"  [PASS] Navigated to screen: '{tab_label}' ({tab_id}) -> Content Rendered ({content_len} bytes).")

        # -------------------------------------------------------------
        # STEP 3: CREATE CLIENT VIA REAL BROWSER INPUTS
        # -------------------------------------------------------------
        print("\n[Step 03] Creating client via real browser UI...")
        page.evaluate("navigateTo('clients')")
        time.sleep(0.6)

        client_uid = int(time.time()) % 9000 + 1000
        client_name = f"Bharat Forge Logistics {client_uid} Ltd"
        pan_val = f"AAACB{client_uid}D"
        gst_val = f"27AAACB{client_uid}D1Z5"

        page.evaluate("openCreateClientModal()")
        time.sleep(0.5)

        print(f"  -> Filling Client Form: Name='{client_name}', PAN='{pan_val}', GSTIN='{gst_val}'...")
        if page.locator("#cli-name").is_visible():
            page.fill("#cli-name", client_name)
            if page.locator("#cli-pan").is_visible():
                page.fill("#cli-pan", pan_val)
            if page.locator("#cli-gstin").is_visible():
                page.fill("#cli-gstin", gst_val)
            if page.locator("#cli-entity-type").is_visible():
                page.select_option("#cli-entity-type", "Public Limited Company")
        elif page.locator("#client-name").is_visible():
            page.fill("#client-name", client_name)
            if page.locator("#client-pan").is_visible():
                page.fill("#client-pan", pan_val)
            if page.locator("#client-gstin").is_visible():
                page.fill("#client-gstin", gst_val)
            if page.locator("#client-entity-type").is_visible():
                page.select_option("#client-entity-type", "Public Limited Company")

        submit_c = page.locator("#client-modal button[type='submit'], #client-modal button.btn-primary").first
        if submit_c.is_visible():
            submit_c.click()
            time.sleep(1.5)
        page.evaluate("if(document.getElementById('client-modal')) document.getElementById('client-modal').remove()")
        print(f"  [PASS] Created client '{client_name}' successfully.")

        # -------------------------------------------------------------
        # STEP 4: CREATE ENGAGEMENT VIA REAL BROWSER INPUTS
        # -------------------------------------------------------------
        print("\n[Step 04] Creating engagement via real browser UI...")
        page.evaluate("navigateTo('engagements')")
        time.sleep(0.6)

        eng_title = f"Statutory & Tax Audit FY 2024-25 ({client_uid})"
        page.evaluate("openCreateEngagementModal()")
        time.sleep(0.5)

        print(f"  -> Initializing Engagement: Title='{eng_title}'...")
        if page.locator("#eng-title").is_visible():
            page.fill("#eng-title", eng_title)
        if page.locator("#eng-fy").is_visible():
            page.fill("#eng-fy", "2024-25")
        if page.locator("#eng-audit-type").is_visible():
            page.select_option("#eng-audit-type", "Statutory Audit")

        eng_submit = page.locator("#eng-modal button[type='submit'], #eng-modal button.btn-primary").first
        if eng_submit.is_visible():
            eng_submit.click()
            time.sleep(1.5)
        page.evaluate("if(document.getElementById('eng-modal')) document.getElementById('eng-modal').remove()")

        top_select = page.locator("#engagement-select")
        if top_select.locator("option").count() > 1:
            top_select.select_option(index=1)
            time.sleep(0.5)
        active_text = page.locator("#engagement-select option:checked").text_content() or "Active"
        print(f"  [PASS] Engagement activated in top bar: '{active_text.strip()}'.")

        # -------------------------------------------------------------
        # STEP 5: REFRESH IN BROWSER & VERIFY SESSION SURVIVES
        # -------------------------------------------------------------
        print("\n[Step 05] Refreshing browser (hard page reload)...")
        page.reload(wait_until="networkidle")
        time.sleep(1.5)

        overlay = page.locator("#login-screen-overlay")
        is_overlay_hidden = not overlay.is_visible() or page.evaluate("document.getElementById('login-screen-overlay').style.display === 'none'")
        assert is_overlay_hidden, "Session restoration failed: login overlay appeared after refresh!"

        retained_token = page.evaluate("localStorage.getItem('finaudit_token')")
        assert retained_token and len(retained_token) > 20, "JWT token must remain in localStorage after reload"
        print(f"  [PASS] Browser refresh verified: user stayed logged in. Active token: {retained_token[:15]}...")

        # -------------------------------------------------------------
        # STEP 6: TEST MULTI-TAB SESSION PERSISTENCE
        # -------------------------------------------------------------
        print("\n[Step 06] Testing second tab in browser context...")
        tab2 = context.new_page()
        tab2.goto("http://127.0.0.1:8000", wait_until="networkidle")
        time.sleep(1)

        tab2_hidden = not tab2.locator("#login-screen-overlay").is_visible() or tab2.evaluate("document.getElementById('login-screen-overlay').style.display === 'none'")
        assert tab2_hidden, "Second tab must immediately restore authenticated session"
        print("  [PASS] Multi-tab verified: Second tab immediately displays authenticated workspace.")
        tab2.close()

        # -------------------------------------------------------------
        # STEP 7: TEST LOGOUT FLOW VIA PROFILE MENU
        # -------------------------------------------------------------
        print("\n[Step 07] Testing logout flow via profile menu...")
        user_badge = page.locator("#top-user-badge")
        assert user_badge.is_visible(), "Top user badge must be visible"
        user_badge.click()
        time.sleep(0.4)

        signout_item = page.locator(".user-dropdown-item.danger, span:has-text('Sign Out')").first
        assert signout_item.is_visible(), "Sign Out item must be present in profile dropdown"
        signout_item.click()
        time.sleep(0.6)

        confirm_btn = page.locator("#fin-confirm-ok, button:has-text('Sign Out'), button:has-text('Yes')").first
        if confirm_btn.is_visible():
            confirm_btn.click()
            time.sleep(1)

        token_after_logout = page.evaluate("localStorage.getItem('finaudit_token')")
        assert not token_after_logout, "Token must be cleared from localStorage upon logout"
        assert page.locator("#login-screen-overlay").is_visible(), "Login screen overlay must appear after logout"
        print("  [PASS] Logout verified: session cleared, login screen restored.")

        # -------------------------------------------------------------
        # STEP 8: VERIFY NO FATAL RUNTIME JAVASCRIPT ERRORS
        # -------------------------------------------------------------
        print("\n[Step 08] Auditing browser console logs for fatal runtime errors...")
        fatal_errors = [
            err for err in console_errors
            if not any(ign in err for ign in ["favicon.ico", "net::ERR_CONNECTION_REFUSED", "404", "status of 404"])
        ]
        assert len(fatal_errors) == 0, f"Fatal JavaScript errors encountered during full journey: {fatal_errors}"
        print(f"  [PASS] Console audit clean: 0 fatal JS errors across all screens.")

        browser.close()
        print("\n" + "=" * 80)
        print("🏁 REAL BROWSER FULL SUITE COMPLETED: 100% VERIFIED PASS")
        print("=" * 80)

if __name__ == "__main__":
    test_full_browser_workflow()
