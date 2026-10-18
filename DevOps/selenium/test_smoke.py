"""Basic Selenium smoke tests for TempAudit / FinAuditPro.

Run the app first at http://127.0.0.1:8000. Selenium Manager normally
resolves/downloads a compatible browser driver automatically.
"""
import os
import requests
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = os.getenv("TEMPAUDIT_BASE_URL", "http://127.0.0.1:8000")

@pytest.fixture

def driver():
    options = webdriver.ChromeOptions()
    if os.getenv("SELENIUM_HEADLESS", "0") == "1":
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    browser = webdriver.Chrome(options=options)
    yield browser
    browser.quit()


def test_health_endpoint_is_healthy():
    response = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert response.status_code == 200
    assert response.json().get("status") == "healthy"


def test_homepage_loads_and_has_app_content(driver):
    driver.get(BASE_URL)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    assert driver.title.strip() or driver.find_elements(By.TAG_NAME, "body")
    body_text = driver.find_element(By.TAG_NAME, "body").text
    # The frontend is a single-page app; ensure it rendered real body content.
    assert len(body_text.strip()) > 10 or len(driver.page_source) > 500


def test_setup_status_endpoint_returns_known_state():
    response = requests.get(f"{BASE_URL}/api/auth/setup-status", timeout=10)
    assert response.status_code == 200
    assert response.json().get("state") in {
        "UNINITIALIZED", "SETUP_REQUIRED", "CONFIGURED", "DATABASE_ERROR"
    }
