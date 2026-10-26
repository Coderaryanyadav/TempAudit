#!/usr/bin/env python3
import os
import sys
import time
from playwright.sync_api import sync_playwright

def take_ultra_hd_screenshots(base_url="http://127.0.0.1:8000", output_dir="docs/screenshots"):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(project_root, output_dir)
    os.makedirs(target_dir, exist_ok=True)

    print("=" * 80)
    print("💎 FINAUDITPRO - ULTRA-HD (RETINA 2X) FULL-VIEWPORT SCREENSHOT ENGINE")
    print(f"Target URL: {base_url}")
    print(f"Output Directory: {target_dir}")
    print("Viewport: 1920x1080 @ 2x Device Scale Factor (3840x2160 Ultra-Sharp)")
    print("=" * 80)

    screens = [
        ("dashboard", "01_Dashboard"),
        ("clients", "02_Clients"),
        ("engagements", "03_Engagements"),
        ("import", "04_Data_Import"),
        ("cleaning_logs", "05_Data_Cleaning_Logs"),
        ("trial_balance", "06_Trial_Balance"),
        ("general_ledger", "07_General_Ledger"),
        ("reconciliation", "08_Reconciliation_BRS_GST"),
        ("financial_statements", "09_Financial_Statements"),
        ("yoy_comparison", "10_YoY_Comparison"),
        ("duplicate_missing", "11_Duplicates_and_Gaps"),
        ("anomaly_detection", "12_Anomaly_Detection"),
        ("findings", "13_Risk_and_Findings"),
        ("assistant", "14_Audit_Assistant"),
        ("checklist", "15_Audit_Checklist"),
        ("working_papers", "16_Working_Papers"),
        ("reports", "17_Audit_Reports_PDF"),
        ("audit_trail", "18_Audit_Trail_Log"),
        ("users", "19_User_Management"),
        ("ai_manager", "20_Assistant_Settings"),
        ("settings", "21_System_Settings"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1920x1080 with device_scale_factor=2 gives crystal-clear 4K Retina rendering (3840x2160)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2
        )
        page = context.new_page()

        # Step 0: Capture Initial Landing & Login Screen
        print("\n[+] Capturing ultra-HD login & landing screen...")
        page.goto(base_url, wait_until="networkidle")
        time.sleep(1.2)
        login_img = os.path.join(target_dir, "00_Login_Screen.png")
        page.screenshot(path=login_img)
        print(f"  -> Saved: {os.path.basename(login_img)} (Ultra-HD)")

        # Handle welcome splash if visible
        if page.locator("button:has-text('Sign In')").is_visible():
            page.locator("button:has-text('Sign In')").click()
            time.sleep(0.5)

        # Authenticate
        print("[+] Logging in with admin credentials...")
        page.wait_for_selector("#login-username", state="visible")
        page.fill("#login-username", "admin")
        for pwd in ["admin123", "SecureAdmin2026!"]:
            page.fill("#login-password", pwd)
            page.click("#login-submit-btn")
            time.sleep(1.0)
            if not page.locator("#login-screen-overlay").is_visible():
                break

        page.wait_for_selector("#login-screen-overlay", state="hidden", timeout=10000)
        page.wait_for_selector("#app-container", state="visible")
        time.sleep(1.5)

        # Remove temporary toast notifications that might block screen content
        page.evaluate("""() => {
            document.querySelectorAll('.toast, .notification, [class*="toast"]').forEach(el => el.remove());
        }""")

        # Ensure active engagement is selected so all audit modules render populated data
        try:
            page.evaluate("""() => {
                const sel = document.getElementById('global-engagement-selector') || document.querySelector('select[name="engagement"]') || document.getElementById('engagement-select');
                if (sel && sel.options && sel.options.length > 1) {
                    sel.selectedIndex = 1;
                    sel.dispatchEvent(new Event('change'));
                }
            }""")
            time.sleep(1.0)
        except Exception:
            pass

        # Helper JavaScript to expand internal scrollable containers so full tables are captured
        expand_page_js = """() => {
            // Remove any floating toasts or temporary popups
            document.querySelectorAll('.toast, .notification, [class*="toast"], .alert-floating').forEach(el => el.remove());
            
            // Allow container to fit entire content naturally
            const container = document.getElementById('content-container');
            if (container) {
                container.style.overflow = 'visible';
                container.style.height = 'auto';
                container.style.maxHeight = 'none';
            }
            const wrapper = document.getElementById('main-wrapper');
            if (wrapper) {
                wrapper.style.overflow = 'visible';
                wrapper.style.height = 'auto';
            }
            const app = document.getElementById('app-container');
            if (app) {
                app.style.overflow = 'visible';
                app.style.height = 'auto';
            }
            const body = document.body;
            body.style.overflow = 'visible';
            body.style.height = 'auto';
            
            // Also ensure sidebar expands along with the document
            const sidebar = document.getElementById('sidebar');
            if (sidebar) {
                sidebar.style.minHeight = Math.max(document.body.scrollHeight, window.innerHeight) + 'px';
            }
        }"""

        restore_page_js = """() => {
            const container = document.getElementById('content-container');
            if (container) {
                container.style.overflow = '';
                container.style.height = '';
                container.style.maxHeight = '';
            }
            const wrapper = document.getElementById('main-wrapper');
            if (wrapper) {
                wrapper.style.overflow = '';
                wrapper.style.height = '';
            }
            const app = document.getElementById('app-container');
            if (app) {
                app.style.overflow = '';
                app.style.height = '';
            }
            document.body.style.overflow = '';
            document.body.style.height = '';
            const sidebar = document.getElementById('sidebar');
            if (sidebar) {
                sidebar.style.minHeight = '';
            }
        }"""

        # Capture each screen in Ultra-HD Full-Page
        print(f"\n[+] Capturing all {len(screens)} application screens in Ultra-HD (Full Page)...")
        for tab_id, file_prefix in screens:
            try:
                page.evaluate(f"navigateTo('{tab_id}')")
                time.sleep(1.5) # Allow network requests, table rendering, and SVG charts to complete

                # Expand container to full content height for complete capture
                page.evaluate(expand_page_js)
                time.sleep(0.3)

                out_path = os.path.join(target_dir, f"{file_prefix}.png")
                page.screenshot(path=out_path, full_page=True)
                
                # Restore style for clean subsequent navigations
                page.evaluate(restore_page_js)

                print(f"  [✓] Captured Ultra-HD: {file_prefix}.png")
            except Exception as e:
                print(f"  [✗] Failed to capture {tab_id}: {e}")

        browser.close()

    print("\n" + "=" * 80)
    print(f"🎉 COMPLETED! All 22 Ultra-HD screenshots saved to:\n{target_dir}")
    print("=" * 80)

if __name__ == "__main__":
    take_ultra_hd_screenshots()
