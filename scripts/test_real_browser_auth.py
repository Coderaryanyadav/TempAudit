import sys
import time
from playwright.sync_api import sync_playwright

def test_browser_login_and_refresh():
    print("[*] Launching Chromium browser in real headless mode...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("[*] Navigating to http://127.0.0.1:8000...")
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        time.sleep(1)

        # Check if login overlay is displayed
        overlay = page.locator("#login-screen-overlay")
        assert overlay.is_visible(), "Login screen overlay must be visible on initial load"

        # Check if Welcome Splash or Direct Login is shown
        if page.locator("button:has-text('Sign In')").is_visible():
            print("[*] Welcome splash detected. Clicking 'Sign In'...")
            page.locator("button:has-text('Sign In')").click()
            time.sleep(0.5)

        # Fill login form
        print("[*] Entering credentials for 'admin'...")
        page.wait_for_selector("#login-username", state="visible")
        page.fill("#login-username", "admin")
        page.fill("#login-password", "SecureAdmin2026!")

        print("[*] Submitting login form...")
        page.click("#login-submit-btn")

        # Wait for overlay to disappear or dashboard to become active
        print("[*] Waiting for dashboard UI to load...")
        page.wait_for_selector("#login-screen-overlay", state="hidden", timeout=10000)
        page.wait_for_selector("#app-container", state="visible")
        
        # Verify authenticated state in UI
        time.sleep(1)
        token = page.evaluate("localStorage.getItem('finaudit_token')")
        assert token and len(token) > 20, f"JWT token must be stored in localStorage, got {token}"
        print(f"[+] Login successful! Stored JWT token: {token[:15]}...")

        # Verify active dashboard tab
        active_tab = page.locator(".nav-item.active").text_content()
        print(f"[+] Active navigation tab: {active_tab.strip()}")

        # -------------------------------------------------------------
        # STEP 4: REFRESH IN REAL BROWSER
        # -------------------------------------------------------------
        print("[*] Reloading (refreshing) browser page...")
        page.reload(wait_until="networkidle")
        time.sleep(1.5)

        # STEP 5: VERIFY SESSION RESTORED AND DASHBOARD STILL VISIBLE
        print("[*] Verifying post-refresh state...")
        overlay_after_refresh = page.locator("#login-screen-overlay")
        is_overlay_hidden = not overlay_after_refresh.is_visible() or page.evaluate("document.getElementById('login-screen-overlay').style.display === 'none'")
        assert is_overlay_hidden, "Login screen overlay must NOT appear after refreshing an authenticated session!"
        
        retained_token = page.evaluate("localStorage.getItem('finaudit_token')")
        assert retained_token == token, "JWT token must be preserved across reload"

        # Verify protected dashboard content is rendered
        app_visible = page.is_visible("#app-container")
        assert app_visible, "Main app container must remain visible"
        print("[+] Session successfully restored! User remains authenticated on dashboard after real browser reload.")

        # -------------------------------------------------------------
        # STEP 6: SECOND TAB PERSISTENCE
        # -------------------------------------------------------------
        print("[*] Opening second browser tab to verify session consistency...")
        page2 = context.new_page()
        page2.goto("http://127.0.0.1:8000", wait_until="networkidle")
        time.sleep(1)
        page2_overlay_hidden = not page2.locator("#login-screen-overlay").is_visible() or page2.evaluate("document.getElementById('login-screen-overlay').style.display === 'none'")
        assert page2_overlay_hidden, "Second tab must immediately restore authenticated session"
        print("[+] Second tab session verified: user immediately authenticated without re-prompting login.")

        browser.close()
        print("[SUCCESS] Real-browser end-to-end authentication, refresh, and multi-tab tests passed cleanly!")

if __name__ == "__main__":
    test_browser_login_and_refresh()
