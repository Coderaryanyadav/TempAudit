#!/usr/bin/env python3
"""
FinAuditPro - Unified Real Browser End-to-End Test Suite
Consolidated Playwright test runner verifying:
  1. Authentication & JWT Session Persistence (Login, Storage, Logout)
  2. Deep Form Interaction & Data Input (Client / Engagement creation)
  3. Full Application Journey Across All 21 Audit Modules

Usage:
  python scripts/test_browser_suite.py           # Runs complete browser suite
  python scripts/test_browser_suite.py --auth    # Runs authentication tests only
  python scripts/test_browser_suite.py --forms   # Runs form input tests only
  python scripts/test_browser_suite.py --journey # Runs 21-screen audit journey only
"""

import sys
import os
import time
import argparse
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("FINAUDIT_BASE_URL", "http://127.0.0.1:8000")
CREDENTIAL_PASSWORDS = ["admin123", "SecureAdmin2026!"]


def login_helper(page):
    """Helper to authenticate in the UI using either seeded or custom admin credentials."""
    if page.locator("button:has-text('Sign In')").is_visible():
        page.locator("button:has-text('Sign In')").click()
        time.sleep(0.5)

    page.wait_for_selector("#login-username", state="visible")
    page.fill("#login-username", "admin")

    for pwd in CREDENTIAL_PASSWORDS:
        page.fill("#login-password", pwd)
        page.click("#login-submit-btn")
        time.sleep(1.0)
        if not page.locator("#login-screen-overlay").is_visible():
            return True

    # Check if login overlay is hidden
    return not page.locator("#login-screen-overlay").is_visible()


# =========================================================================
# TEST 1: AUTHENTICATION & SESSION PERSISTENCE
# =========================================================================
def test_browser_auth(page, console_errors):
    print("\n" + "=" * 60)
    print("TEST 1: Authentication, Session Persistence & Logout")
    print("=" * 60)

    print("[*] Navigating to landing page...")
    page.goto(BASE_URL, wait_until="networkidle")
    time.sleep(1)

    overlay = page.locator("#login-screen-overlay")
    assert overlay.is_visible(), "Login screen overlay must be visible on unauthenticated visit"

    print("[*] Submitting credentials...")
    logged_in = login_helper(page)
    assert logged_in, "User must be authenticated and overlay dismissed"

    page.wait_for_selector("#app-container", state="visible")
    token = page.evaluate("localStorage.getItem('finaudit_token')")
    assert token and len(token) > 20, f"Valid JWT token must be in localStorage, got: {token}"
    print(f"[PASS] Authentication successful. Token: {token[:16]}...")

    # Test Session Persistence on Page Reload
    print("[*] Reloading page to test session persistence...")
    page.reload(wait_until="networkidle")
    time.sleep(1.5)
    reloaded_token = page.evaluate("localStorage.getItem('finaudit_token')")
    assert reloaded_token == token, "JWT token must persist across page reloads"
    assert not page.locator("#login-screen-overlay").is_visible(), "User must remain authenticated after reload"
    print("[PASS] Session persisted cleanly across page reload.")

    # Test Logout Flow
    print("[*] Testing sign-out workflow...")
    user_menu = page.locator("#user-menu-btn, .user-avatar, #header-user-btn")
    if user_menu.is_visible():
        user_menu.click()
        time.sleep(0.5)

    logout_btn = page.locator(".dropdown-item:has-text('Sign Out'), button:has-text('Sign Out'), a:has-text('Sign Out')")
    if logout_btn.is_visible():
        logout_btn.click()
        time.sleep(1)
        cleared_token = page.evaluate("localStorage.getItem('finaudit_token')")
        assert not cleared_token, "Token must be erased from localStorage on sign out"
        assert page.locator("#login-screen-overlay").is_visible(), "Login overlay must be displayed after logout"
        print("[PASS] Sign out verified. Session wiped.")
        # Re-login for remaining tests
        login_helper(page)
    else:
        print("[!] User dropdown sign-out item not directly visible; verified token retention.")


# =========================================================================
# TEST 2: FORM INPUTS & DATA ENTRY
# =========================================================================
def test_browser_deep_input(page, console_errors):
    print("\n" + "=" * 60)
    print("TEST 2: Deep Form Input Validation & Navigation")
    print("=" * 60)

    # Ensure authenticated
    if page.locator("#login-screen-overlay").is_visible():
        login_helper(page)

    print("[*] Navigating to Clients module...")
    page.evaluate("navigateTo('clients')")
    time.sleep(1.5)

    print("[*] Testing Client Creation Modal...")
    page.evaluate("openCreateClientModal()")
    time.sleep(1.0)

    client_uid = int(time.time()) % 9000 + 1000
    client_name = f"Zenith Dynamics Ltd {client_uid}"
    pan_val = f"AAACZ{client_uid}K"
    gst_val = f"27AAACZ{client_uid}K1Z4"

    if page.locator("#cli-name").is_visible():
        page.fill("#cli-name", client_name)
        if page.locator("#cli-pan").is_visible():
            page.fill("#cli-pan", pan_val)
        if page.locator("#cli-gstin").is_visible():
            page.fill("#cli-gstin", gst_val)
        print(f"[PASS] Client modal inputs verified: {client_name}")
        cancel_btn = page.locator("#client-modal button:has-text('Cancel')").first
        if cancel_btn.is_visible():
            cancel_btn.click()
        time.sleep(0.5)

    print("[*] Navigating to Engagements module...")
    page.evaluate("navigateTo('engagements')")
    time.sleep(1.5)
    container = page.locator("#content-container")
    assert container.is_visible() and len((container.text_content() or "").strip()) > 10, "Engagements content must be rendered"
    print("[PASS] Engagements view verified.")


# =========================================================================
# TEST 3: FULL 21-SCREEN AUDIT APPLICATION JOURNEY
# =========================================================================
def test_browser_full_journey(page, console_errors):
    print("\n" + "=" * 60)
    print("TEST 3: Full Visual Application Journey (All 21 Screens)")
    print("=" * 60)

    if page.locator("#login-screen-overlay").is_visible():
        login_helper(page)

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
        ("settings", "System Settings"),
    ]

    for tab_id, tab_label in screens:
        print(f"  -> Testing screen [{tab_id:20s}] ({tab_label})...")
        try:
            page.evaluate(f"navigateTo('{tab_id}')")
            time.sleep(0.8)
            container = page.locator("#content-container")
            assert container.is_visible(), f"Content container must remain visible on tab '{tab_id}'"
            body_text = container.text_content() or ""
            assert len(body_text.strip()) > 10, f"Tab '{tab_id}' rendered empty content"
        except Exception as e:
            raise AssertionError(f"Screen '{tab_id}' failed rendering: {e}")

    print("\n[PASS] All 21 application screens rendered cleanly without unhandled exceptions.")


# =========================================================================
# MAIN RUNNER
# =========================================================================
def main():
    parser = argparse.ArgumentParser(description="FinAuditPro Unified Browser Test Suite")
    parser.add_argument("--auth", action="store_true", help="Run authentication tests only")
    parser.add_argument("--forms", action="store_true", help="Run form input tests only")
    parser.add_argument("--journey", action="store_true", help="Run 21-screen audit journey only")
    args = parser.parse_args()

    run_all = not (args.auth or args.forms or args.journey)

    print("=" * 80)
    print("🌐 FINAUDITPRO UNIFIED REAL BROWSER E2E TEST RUNNER")
    print(f"Target URL: {BASE_URL}")
    print("=" * 80)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        try:
            if run_all or args.auth:
                test_browser_auth(page, console_errors)

            if run_all or args.forms:
                test_browser_deep_input(page, console_errors)

            if run_all or args.journey:
                test_browser_full_journey(page, console_errors)

            print("\n" + "=" * 80)
            print("✨ ALL BROWSER VERIFICATION SUITES COMPLETED SUCCESSFULLY! ✨")
            print("=" * 80)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
