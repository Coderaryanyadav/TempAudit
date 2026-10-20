import os
import sys
import time
import socket
import subprocess
import signal
import json
import urllib.request
import urllib.error
import pytest


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout: float = 8.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def http_request(url: str, method: str = "GET", data: dict = None, headers: dict = None) -> tuple:
    hdrs = headers or {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed


def test_genuine_subprocess_restart_persistence(tmp_path):
    """
    Spawns an actual OS uvicorn process, writes data via HTTP API,
    terminates the process completely, boots a new OS process against the
    identical database, and asserts data persistence and service health.
    """
    db_path = str(tmp_path / "proc_restart_test.db")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # 1. Initialize schema and admin account in isolated DB
    env = os.environ.copy()
    env["FINAUDIT_DB_PATH"] = db_path
    env["FINAUDIT_SECRET_KEY"] = "test_secret_for_restart_persistence_12345"
    env["FINAUDIT_ENV"] = "testing"
    env["PYTHONPATH"] = project_root

    # Run DB init
    init_cmd = [
        sys.executable,
        "-c",
        (
            "from backend.app.database import init_db, get_db_connection;"
            "from backend.app.auth import hash_password;"
            "init_db();"
            "conn = get_db_connection();"
            "conn.execute(\"INSERT INTO users (username, email, full_name, password_hash, role, is_active, created_at) VALUES ('restart_admin', 'admin@restart.test', 'Admin User', ?, 'Admin', 1, datetime('now'))\", (hash_password('RestartPass!123'),));"
            "conn.commit(); conn.close();"
        ),
    ]
    subprocess.check_call(init_cmd, env=env)

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    # 2. Launch Subprocess 1
    proc1 = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        assert wait_for_server(f"{base_url}/api/health", timeout=8.0), "Process 1 failed to become healthy"

        # Login to obtain JWT
        status, login_res = http_request(
            f"{base_url}/api/auth/login",
            method="POST",
            data={"username": "restart_admin", "password": "RestartPass!123"},
        )
        assert status == 200, f"Login failed: {login_res}"
        token = login_res["access_token"]
        auth_hdr = {"Authorization": f"Bearer {token}"}

        # Create a client record in Process 1
        status, client_res = http_request(
            f"{base_url}/api/clients",
            method="POST",
            data={
                "name": "Restart Persistence Client Pvt Ltd",
                "entity_type": "Private Limited",
                "pan": "ABCDE9999F",
                "industry": "Manufacturing",
            },
            headers=auth_hdr,
        )
        assert status == 200, f"Client creation failed: {client_res}"
        created_client_id = client_res["id"]
        assert created_client_id is not None

    finally:
        # 3. Terminate Process 1 completely
        proc1.terminate()
        try:
            proc1.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc1.kill()
            proc1.wait(timeout=2.0)

    assert proc1.poll() is not None, "Process 1 did not terminate"

    # Verify that the server is actually down
    server_down = False
    try:
        urllib.request.urlopen(f"{base_url}/api/health", timeout=1.0)
    except Exception:
        server_down = True
    assert server_down, "Server still responded after Process 1 termination"

    # 4. Launch Subprocess 2 on the SAME database
    proc2 = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        assert wait_for_server(f"{base_url}/api/health", timeout=8.0), "Process 2 failed to become healthy"

        # Login again to fresh process
        status, login_res2 = http_request(
            f"{base_url}/api/auth/login",
            method="POST",
            data={"username": "restart_admin", "password": "RestartPass!123"},
        )
        assert status == 200
        token2 = login_res2["access_token"]
        auth_hdr2 = {"Authorization": f"Bearer {token2}"}

        # Verify client created in Process 1 is intact and accessible in Process 2
        status, clients_res = http_request(f"{base_url}/api/clients", headers=auth_hdr2)
        assert status == 200
        client_names = [c["name"] for c in clients_res]
        assert "Restart Persistence Client Pvt Ltd" in client_names, (
            f"Persisted client not found after genuine process restart! Found: {client_names}"
        )

    finally:
        # 5. Cleanly terminate Process 2
        proc2.terminate()
        try:
            proc2.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc2.kill()
            proc2.wait(timeout=2.0)
