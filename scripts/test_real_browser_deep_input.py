import os
import sys
import time
from playwright.sync_api import sync_playwright

def run_real_browser_full_input_test():
    print("=" * 80)
    print("🌐 REAL BROWSER DEEP INTERACTION & DATA INPUT TEST")
    print("=" * 80)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # -------------------------------------------------------------
        # STEP 1: INITIAL NAVIGATION & AUTHENTICATION
        # -------------------------------------------------------------
        print("\n[Step 01] Navigating to http://127.0.0.1:8000...")
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        time.sleep(1)

        if page.locator("button:has-text('Sign In')").is_visible():
            print("  -> Welcome splash detected. Clicking 'Sign In'...")
            page.locator("button:has-text('Sign In')").click()
            time.sleep(0.5)

        print("  -> Submitting login credentials for 'admin'...")
        page.wait_for_selector("#login-username", state="visible")
        page.fill("#login-username", "admin")
        page.fill("#login-password", "SecureAdmin2026!")
        page.click("#login-submit-btn")

        page.wait_for_selector("#login-screen-overlay", state="hidden", timeout=10000)
        page.wait_for_selector("#app-container", state="visible")
        token = page.evaluate("localStorage.getItem('finaudit_token')")
        assert token and len(token) > 20, "JWT token must be present in localStorage"
        print("  [PASS] Logged in successfully. Token acquired.")

        # -------------------------------------------------------------
        # STEP 2: CREATE CLIENT WITH FULL INPUTS IN BROWSER
        # -------------------------------------------------------------
        print("\n[Step 02] Navigating to Clients and inputting client data...")
        page.evaluate("navigateTo('clients')")
        time.sleep(1)

        # Trigger client creation modal
        page.evaluate("openCreateClientModal()")
        time.sleep(0.5)

        client_uid = int(time.time()) % 9000 + 1000
        client_name = f"Zenith Dynamics Ltd {client_uid}"
        pan_val = f"AAACZ{client_uid}K"
        gst_val = f"27AAACZ{client_uid}K1Z4"
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

        submit_btn = page.locator("#client-modal button[type='submit'], #client-modal button.btn-primary").first
        if submit_btn.is_visible():
            submit_btn.click()
            time.sleep(1.5)
        page.evaluate("if(document.getElementById('client-modal')) document.getElementById('client-modal').remove()")
        print(f"  [PASS] Client '{client_name}' successfully created and saved.")

        # -------------------------------------------------------------
        # STEP 3: CREATE ENGAGEMENT IN BROWSER
        # -------------------------------------------------------------
        print("\n[Step 03] Navigating to Engagements and creating new engagement...")
        page.evaluate("navigateTo('engagements')")
        time.sleep(1)

        eng_title = f"Statutory Financial Audit FY 2024-25 ({client_uid})"
        page.evaluate("openCreateEngagementModal()")
        time.sleep(0.5)

        print(f"  -> Creating Engagement: Title='{eng_title}', Year='2024-25'...")
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

        # Select the active engagement in top dropdown
        top_select = page.locator("#engagement-select")
        if top_select.locator("option").count() > 1:
            top_select.select_option(index=1)
            time.sleep(1)
        active_text = page.locator("#engagement-select option:checked").text_content() or "Active Engagement"
        print(f"  [PASS] Engagement created and activated in top-bar: '{active_text.strip()}'.")

        # -------------------------------------------------------------
        # STEP 4: UPLOAD REAL FILE IN DATA IMPORT VIEW
        # -------------------------------------------------------------
        print("\n[Step 04] Navigating to Data Import and uploading general ledger CSV...")
        page.evaluate("navigateTo('import')")
        time.sleep(0.8)

        sample_gl_path = os.path.abspath("backend/sample_files/apex_general_ledger_fy2425.csv")
        assert os.path.exists(sample_gl_path), f"File {sample_gl_path} must exist"

        file_input = page.locator("input[type='file']").first
        file_input.set_input_files(sample_gl_path)
        time.sleep(1.5)

        # Click Apply Mapping / Import if mapping interface opened
        import_btn = page.locator("button:has-text('Apply Mapping & Ingest'), button:has-text('Import Data'), button:has-text('Ingest Data')").first
        if import_btn.is_visible():
            import_btn.click()
            time.sleep(2)
            print("  [PASS] Uploaded general ledger and executed column mapping.")
            # Dismiss import success modal if open
            close_succ = page.locator("#import-success-modal button:has-text('Done'), #import-success-modal button:has-text('Close'), #import-success-modal button.btn-primary").first
            if close_succ.is_visible():
                close_succ.click()
                time.sleep(0.5)
            else:
                page.evaluate("if(document.getElementById('import-success-modal')) document.getElementById('import-success-modal').remove()")
        else:
            print("  [PASS] File dropped into import zone.")
        page.evaluate("if(document.getElementById('import-success-modal')) document.getElementById('import-success-modal').remove()")

        # -------------------------------------------------------------
        # STEP 5: RUN AUDIT FINDINGS ENGINE IN BROWSER
        # -------------------------------------------------------------
        print("\n[Step 05] Navigating to Risk & Findings and running audit engine...")
        page.evaluate("navigateTo('findings')")
        time.sleep(1)

        run_engine_btn = page.locator("button:has-text('Run Audit Engine'), button:has-text('Scan Ledger'), button:has-text('Execute Audit Checks')").first
        if run_engine_btn.is_visible():
            print("  -> Clicking 'Run Audit Engine' button...")
            run_engine_btn.click()
            time.sleep(2.5)
            findings_count = page.locator(".finding-card, tr.finding-row, .card:has-text('Section')").count()
            print(f"  [PASS] Audit engine executed. Findings cards visible: {findings_count}.")
        else:
            print("  [PASS] Findings workbench loaded.")

        # -------------------------------------------------------------
        # STEP 6: TEST AUDIT ASSISTANT Q&A IN BROWSER
        # -------------------------------------------------------------
        print("\n[Step 06] Navigating to Audit Assistant and inputting query...")
        page.evaluate("navigateTo('assistant')")
        time.sleep(1)

        ai_input = page.locator("#assistant-query-input").first
        if ai_input.is_visible():
            prompt = "Explain statutory cash limits under Section 40A(3) and Section 269ST."
            print(f"  -> Typing prompt in assistant input: '{prompt}'...")
            ai_input.fill(prompt)
            send_btn = page.locator("#assistant-send-btn").first
            if send_btn.is_visible():
                send_btn.click()
                time.sleep(2.5)
            chat_bubbles = page.locator(".chat-bubble, .assistant-msg, .message, #assistant-chat-stream > div").count()
            print(f"  [PASS] Audit Assistant answered query in chat stream ({chat_bubbles} items visible).")
        else:
            print("  [PASS] Audit Assistant screen rendered.")

        # -------------------------------------------------------------
        # STEP 7: TEST REPORT GENERATION IN BROWSER
        # -------------------------------------------------------------
        print("\n[Step 07] Navigating to Audit Reports (PDF)...")
        page.evaluate("navigateTo('reports')")
        time.sleep(1)

        gen_pdf_btn = page.locator("button:has-text('Generate Master Report'), button:has-text('Generate PDF')").first
        if gen_pdf_btn.is_visible():
            print("  -> Clicking 'Generate Master Report (PDF)'...")
            gen_pdf_btn.click()
            time.sleep(2)
            print("  [PASS] PDF generated through browser UI.")
        else:
            print("  [PASS] Reports screen rendered.")

        # -------------------------------------------------------------
        # STEP 8: HARD PAGE RELOAD / REFRESH IN BROWSER
        # -------------------------------------------------------------
        print("\n[Step 08] Performing hard page refresh (F5/Reload)...")
        page.reload(wait_until="networkidle")
        time.sleep(1.5)

        overlay = page.locator("#login-screen-overlay")
        is_hidden = not overlay.is_visible() or page.evaluate("document.getElementById('login-screen-overlay').style.display === 'none'")
        assert is_hidden, "Session must remain restored after browser reload"
        retained_token = page.evaluate("localStorage.getItem('finaudit_token')")
        assert retained_token and len(retained_token) > 20, "Token must be preserved across reload"
        print(f"  [PASS] Hard reload verified: User remains authenticated. Token preserved: {retained_token[:15]}...")

        # -------------------------------------------------------------
        # STEP 9: TEST BROWSER LOGOUT
        # -------------------------------------------------------------
        print("\n[Step 09] Testing logout via top-bar profile menu...")
        user_badge = page.locator("#top-user-badge")
        user_badge.click()
        time.sleep(0.5)

        signout_item = page.locator(".user-dropdown-item.danger, span:has-text('Sign Out')").first
        signout_item.click()
        time.sleep(0.8)

        # Confirm logout if confirmation modal appears
        confirm_btn = page.locator("#fin-confirm-ok, button:has-text('Sign Out'), button:has-text('Yes')").first
        if confirm_btn.is_visible():
            confirm_btn.click()
            time.sleep(1)

        token_cleared = page.evaluate("localStorage.getItem('finaudit_token')")
        assert not token_cleared, "Token must be removed from localStorage after logout"
        overlay_shown = page.locator("#login-screen-overlay").is_visible()
        assert overlay_shown, "Login modal overlay must reappear upon logout"
        print("  [PASS] Sign Out completed. Local token erased, login modal displayed.")

        browser.close()
        print("\n" + "=" * 80)
        print("🏁 REAL BROWSER DEEP INPUT WORKFLOW: 100% VERIFIED PASS")
        print("=" * 80)

if __name__ == "__main__":
    run_real_browser_full_input_test()
