import re
import time
import json
import secrets
from fastapi import APIRouter, HTTPException, Depends, Header
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from backend.app.schemas import (
    UserLogin, UserCreate, UserUpdate, UserStatusUpdate,
    ChangePasswordRequest, AdminResetPasswordRequest, UserResponse,
    InitialAdminCreate, FirmProfileSetup, SecuritySetup, BackupSetup,
    UserInviteCreate, UserActivationSubmit
)
from backend.app.auth import (
    verify_password, hash_password, create_access_token,
    get_current_user, require_role, normalize_role, invalidate_user_sessions
)
from backend.app.database import get_db_connection
from backend.app.utils.audit_logger import log_audit_event

router = APIRouter(prefix="/api/auth", tags=["User Management & Authentication"])

USERNAME_REGEX = r"^[a-zA-Z0-9_.]{3,50}$"
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"

COMMON_WEAK_PASSWORDS = {
    "password123456", "admin12345678", "administrator1", "123456789012",
    "passwordpassword", "welcome123456", "qwertyuiop12"
}

def _ensure_rate_limit_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
    """)

def _check_setup_rate_limit():
    conn = get_db_connection()
    _ensure_rate_limit_table(conn)
    now = time.time()
    cutoff = now - 60
    conn.execute("DELETE FROM rate_limits WHERE key = 'setup' AND timestamp < ?", (cutoff,))
    
    row = conn.execute("SELECT COUNT(*) as count FROM rate_limits WHERE key = 'setup'").fetchone()
    if row and row["count"] >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many initial setup attempts. Please wait 60 seconds before retrying."
        )
    conn.execute("INSERT INTO rate_limits (key, timestamp) VALUES ('setup', ?)", (now,))

def _check_login_rate_limit(key: str):
    conn = get_db_connection()
    _ensure_rate_limit_table(conn)
    now = time.time()
    cutoff = now - 300 # 5 minute window
    db_key = f"login_{key}"
    conn.execute("DELETE FROM rate_limits WHERE key = ? AND timestamp < ?", (db_key, cutoff))
    
    row = conn.execute("SELECT COUNT(*) as count FROM rate_limits WHERE key = ? AND timestamp >= ?", (db_key, cutoff)).fetchone()
    if row and row["count"] >= 10:
        raise HTTPException(
            status_code=429,
            detail="Too many unsuccessful attempts. Please try again later."
        )

def _record_login_failure(key: str):
    conn = get_db_connection()
    _ensure_rate_limit_table(conn)
    now = time.time()
    db_key = f"login_{key}"
    conn.execute("INSERT INTO rate_limits (key, timestamp) VALUES (?, ?)", (db_key, now))

def _clear_login_failures(key: str):
    conn = get_db_connection()
    _ensure_rate_limit_table(conn)
    db_key = f"login_{key}"
    conn.execute("DELETE FROM rate_limits WHERE key = ?", (db_key,))


# ----------------- FIRST-LAUNCH DETECTION & SETUP STATUS -----------------

@router.get("/setup-status")
def get_setup_status():
    """
    Evaluates first-run state of FinAuditPro:
    - UNINITIALIZED: No users exist (Fresh install).
    - SETUP_REQUIRED: Users exist, but firm profile or initial setup wizard pending.
    - CONFIGURED: Setup completed, ready for normal login.
    """
    conn = get_db_connection()
    try:
        user_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        setup_done_row = conn.execute("SELECT value FROM app_settings WHERE key = 'is_initial_setup_completed'").fetchone()
        firm_row = conn.execute("SELECT value FROM app_settings WHERE key = 'firm_name'").fetchone()
        sec_row = conn.execute("SELECT value FROM app_settings WHERE key = 'session_timeout_minutes'").fetchone()
        backup_row = conn.execute("SELECT value FROM app_settings WHERE key = 'backup_location'").fetchone()

        firm_name = firm_row["value"].replace('"', '') if firm_row and firm_row["value"] else ""
        is_setup_done = bool(setup_done_row and setup_done_row["value"] == "1")

        if user_count == 0:
            state = "UNINITIALIZED"
        elif not is_setup_done:
            state = "SETUP_REQUIRED"
        else:
            state = "CONFIGURED"

        return {
            "state": state,
            "is_setup_completed": user_count > 0,
            "wizard_completed": is_setup_done,
            "user_count": user_count,
            "firm_name": firm_name,
            "firm_configured": bool(firm_row),
            "security_configured": bool(sec_row),
            "backup_configured": bool(backup_row)
        }
    except Exception as e:
        return {
            "state": "DATABASE_ERROR",
            "is_setup_completed": False,
            "user_count": 0,
            "error": "FinAuditPro could not safely open this installation."
        }
    finally:
        conn.close()


# ----------------- FIRST ADMINISTRATOR CREATION (STEP 1) -----------------

@router.post("/initial-setup")
def initial_setup(user_data: InitialAdminCreate):
    """
    First-run setup endpoint: Creates the primary Master Administrator (Partner)
    if and only if zero users currently exist in the database.
    Atomic, rate-limited, and requires a strong password.
    """
    _check_setup_rate_limit()

    username = user_data.username.strip()
    email = user_data.email.strip()
    password = user_data.password

    if not re.match(USERNAME_REGEX, username):
        raise HTTPException(status_code=400, detail="Username must be 3-50 characters (letters, numbers, underscores, dots only).")
    
    if not re.match(EMAIL_REGEX, email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    if password.lower() in COMMON_WEAK_PASSWORDS:
        raise HTTPException(status_code=400, detail="Password is too common or easily guessable. Please choose a stronger passphrase.")

    conn = get_db_connection()
    try:
        # Atomic immediate transaction lock to prevent setup race conditions
        conn.execute("BEGIN IMMEDIATE")
        user_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]

        if user_count > 0:
            conn.rollback()
            raise HTTPException(
                status_code=400,
                detail="FinAuditPro has already been initialized. Please sign in or contact an existing Administrator."
            )

        pwd_hash = hash_password(password)
        now_str = datetime.now().isoformat()
        designation = user_data.designation or "Engagement Partner (FCA)"

        cursor = conn.execute("""
            INSERT INTO users (
                username, email, full_name, role, designation, status,
                password_hash, is_active, phone, created_at
            ) VALUES (?, ?, ?, 'Admin', ?, 'ACTIVE', ?, 1, ?, ?)
        """, (username, email, user_data.full_name.strip(), designation, pwd_hash, user_data.phone or "", now_str))

        new_id = cursor.lastrowid

        # Mark wizard started
        conn.execute("""
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES ('initial_admin_created', '1', ?)
        """, (now_str,))

        log_audit_event(
            conn,
            action="INITIAL_SETUP",
            module="AUTH",
            record_id=new_id,
            details=f"Master Administrator account '{username}' created during first-run system setup",
            user={"id": new_id, "username": username}
        )

        conn.commit()

        token = create_access_token({"sub": username, "role": "Admin", "uid": new_id, "token_version": 1})

        return {
            "status": "success",
            "message": "Master Administrator account created successfully.",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": new_id,
                "username": username,
                "full_name": user_data.full_name.strip(),
                "role": "Admin",
                "designation": designation,
                "email": email,
                "phone": user_data.phone or "",
                "created_at": now_str
            }
        }
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


# ----------------- INITIAL SETUP WIZARD STEPS -----------------

@router.post("/setup/firm-profile")
def setup_firm_profile(
    profile: FirmProfileSetup,
    current_user: dict = Depends(require_role(["Admin"]))
):
    """Wizard Step 2: Configure Audit Firm Profile."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    try:
        settings_data = {
            "firm_name": profile.firm_name.strip(),
            "firm_address": profile.address or "",
            "firm_city": profile.city or "",
            "firm_state": profile.state or "Maharashtra",
            "firm_country": profile.country or "India",
            "firm_pin_code": profile.pin_code or "",
            "firm_email": profile.email or "",
            "firm_phone": profile.phone or "",
            "firm_website": profile.website or "",
            "firm_icai_reg": profile.icai_reg_number or ""
        }

        for k, v in settings_data.items():
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (k, json.dumps(v), now_str)
            )

        log_audit_event(
            conn=conn,
            action="SETUP_FIRM_PROFILE",
            module="SETTINGS",
            record_id=profile.firm_name,
            new_value=settings_data,
            details=f"Configured audit firm profile: {profile.firm_name}",
            user=current_user
        )
        conn.commit()
        return {"status": "success", "message": "Firm profile configured successfully.", "profile": settings_data}
    finally:
        conn.close()


@router.post("/setup/security-config")
def setup_security_config(
    sec: SecuritySetup,
    current_user: dict = Depends(require_role(["Admin"]))
):
    """Wizard Step 3: Configure Session Security & AI Privacy Mode."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("session_timeout_minutes", str(sec.session_timeout_minutes), now_str)
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("local_ai_mode", json.dumps(sec.local_ai_mode), now_str)
        )

        log_audit_event(
            conn=conn,
            action="SETUP_SECURITY",
            module="SETTINGS",
            details=f"Security configured: Timeout {sec.session_timeout_minutes}m, AI Mode: {sec.local_ai_mode}",
            user=current_user
        )
        conn.commit()
        return {"status": "success", "message": "Security and AI privacy preferences saved."}
    finally:
        conn.close()


@router.post("/setup/backup-config")
def setup_backup_config(
    backup: BackupSetup,
    current_user: dict = Depends(require_role(["Admin"]))
):
    """Wizard Step 4: Configure Backup Directory & Automated Snapshots."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("backup_location", json.dumps(backup.backup_location or "backups"), now_str)
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("auto_backup_enabled", json.dumps(backup.auto_backup_enabled), now_str)
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("backup_retention_days", str(backup.backup_retention_days), now_str)
        )

        log_audit_event(
            conn=conn,
            action="SETUP_BACKUP",
            module="SETTINGS",
            details=f"Backup location set to '{backup.backup_location}'",
            user=current_user
        )
        conn.commit()
        return {"status": "success", "message": "Backup preferences saved successfully."}
    finally:
        conn.close()


@router.post("/setup/complete")
def complete_setup(current_user: dict = Depends(require_role(["Admin"]))):
    """Wizard Step 5: Mark first-run onboarding as complete."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('is_initial_setup_completed', '1', ?)",
            (now_str,)
        )
        log_audit_event(
            conn=conn,
            action="SETUP_COMPLETE",
            module="AUTH",
            details="First-run setup wizard completed successfully",
            user=current_user
        )
        conn.commit()
        return {"status": "success", "message": "Setup completed. Welcome to FinAuditPro!"}
    finally:
        conn.close()


# ----------------- LOGIN & AUTHENTICATION -----------------

@router.post("/login")
def login(creds: UserLogin):
    """
    Authenticate user with username/email and password.
    Generic error response to prevent user enumeration. Rate limited against brute-force.
    """
    login_identifier = creds.username.strip()
    _check_login_rate_limit(login_identifier)

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (login_identifier, login_identifier)
        ).fetchone()

        if not user or not verify_password(creds.password, user["password_hash"]):
            _record_login_failure(login_identifier)
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        user_dict = dict(user)

        # Check invitation status
        if user_dict.get("status") == "INVITED":
            raise HTTPException(
                status_code=403,
                detail="Your account is pending activation. Please use your activation link or contact your administrator."
            )

        # Check disabled status
        if not user_dict.get("is_active", 1) or user_dict.get("status") == "DISABLED":
            raise HTTPException(
                status_code=403,
                detail="Your user account has been disabled by the Administrator. Please contact audit administration."
            )

        _clear_login_failures(login_identifier)

        now_str = datetime.now().isoformat()
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_str, user["id"]))

        role = normalize_role(user["role"])

        log_audit_event(
            conn,
            action="LOGIN",
            module="AUTH",
            record_id=user["id"],
            new_value={"username": user["username"], "role": role, "login_time": now_str},
            details=f"User '{user['username']}' logged in successfully",
            user={"id": user["id"], "username": user["username"]}
        )
        conn.commit()

        token = create_access_token({
            "sub": user_dict["username"],
            "role": role,
            "uid": user_dict["id"],
            "token_version": user_dict.get("token_version", 1) or 1
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "full_name": user["full_name"],
                "role": role,
                "designation": user_dict.get("designation"),
                "email": user["email"],
                "phone": user["phone"],
                "last_login": now_str,
                "created_at": user["created_at"]
            }
        }
    finally:
        conn.close()


@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """Log the logout event in the audit trail and invalidate user session."""
    invalidate_user_sessions(current_user["id"])
    conn = get_db_connection()
    try:
        log_audit_event(
            conn,
            action="LOGOUT",
            module="AUTH",
            record_id=current_user.get("id"),
            details=f"User '{current_user.get('username')}' logged out",
            user=current_user
        )
        conn.commit()
        return {"message": "Logged out successfully"}
    finally:
        conn.close()


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user profile and role permissions."""
    role = normalize_role(current_user.get("role"))
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "full_name": current_user["full_name"],
        "role": role,
        "designation": current_user.get("designation"),
        "email": current_user.get("email"),
        "phone": current_user.get("phone"),
        "is_active": current_user.get("is_active", 1),
        "status": current_user.get("status", "ACTIVE"),
        "last_login": current_user.get("last_login"),
        "created_at": current_user.get("created_at"),
        "permissions": {
            "can_manage_users": role == "Admin",
            "can_manage_settings": role == "Admin",
            "can_create_clients": role in ["Admin", "Auditor"],
            "can_create_engagements": role in ["Admin", "Auditor"],
            "can_run_audit": role in ["Admin", "Auditor"],
            "can_generate_reports": role in ["Admin", "Auditor"],
            "can_edit_findings": role in ["Admin", "Auditor"],
            "can_view_working_papers": True,
            "can_add_working_paper_notes": True,
            "can_update_checklist": True
        }
    }


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Change password for currently authenticated user and invalidate old tokens."""
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (current_user["id"],)).fetchone()
        
        if not user or not verify_password(req.old_password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password entered is incorrect.")

        if len(req.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters long.")

        new_hash = hash_password(req.new_password)
        now_str = datetime.now().isoformat()
        
        new_version = (user["token_version"] or 1) + 1
        conn.execute("UPDATE users SET password_hash = ?, token_version = ? WHERE id = ?", (new_hash, new_version, user["id"]))
        
        log_audit_event(
            conn=conn,
            action="CHANGE_PASSWORD",
            module="AUTH",
            record_id=user["id"],
            user=user,
            details="User updated account password",
            timestamp=now_str
        )
        conn.commit()
        return {"message": "Password changed successfully. Please log in with your new password."}
    finally:
        conn.close()


# ----------------- LOCAL USER INVITATION & ACTIVATION FLOW -----------------

@router.get("/activation-info/{token}")
def get_activation_info(token: str):
    """
    Public Endpoint: Checks validity of a user activation token.
    Returns invitee details for the onboarding screen.
    """
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT id, username, email, full_name, role, designation, status, activation_expires_at FROM users WHERE activation_token = ?",
            (token.strip(),)
        ).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Invalid or unrecognized activation token.")

        u = dict(user)
        exp_str = u.get("activation_expires_at")
        if exp_str:
            try:
                exp_dt = datetime.fromisoformat(exp_str)
                if datetime.now() > exp_dt:
                    return {
                        "is_valid": False,
                        "expired": True,
                        "message": "This activation token has expired. Please ask your administrator to issue a new one."
                    }
            except Exception:
                pass

        return {
            "is_valid": True,
            "expired": False,
            "user_id": u["id"],
            "username": u["username"],
            "full_name": u["full_name"],
            "email": u["email"],
            "role": u["role"],
            "designation": u["designation"]
        }
    finally:
        conn.close()


@router.post("/activate-user")
def activate_user(req: UserActivationSubmit):
    """
    Public Endpoint: Activates an invited user account by setting their permanent password.
    Transitions account from INVITED to ACTIVE. Issues immediate access token.
    """
    token = req.activation_token.strip()
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE activation_token = ?", (token,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Invalid or expired activation token.")

        u = dict(user)
        exp_str = u.get("activation_expires_at")
        if exp_str:
            try:
                exp_dt = datetime.fromisoformat(exp_str)
                if datetime.now() > exp_dt:
                    raise HTTPException(status_code=400, detail="Activation token has expired. Request a new token from your administrator.")
            except Exception:
                pass

        new_hash = hash_password(req.password)
        now_str = datetime.now().isoformat()
        full_name = req.full_name.strip() if req.full_name else u["full_name"]
        phone = req.phone.strip() if req.phone else u.get("phone", "")

        conn.execute("""
            UPDATE users
            SET password_hash = ?, full_name = ?, phone = ?, status = 'ACTIVE', is_active = 1,
                activation_token = NULL, activation_expires_at = NULL, token_version = COALESCE(token_version, 1) + 1
            WHERE id = ?
        """, (new_hash, full_name, phone, u["id"]))

        log_audit_event(
            conn=conn,
            action="ACTIVATE_USER",
            module="AUTH",
            record_id=u["id"],
            details=f"User '{u['username']}' completed account onboarding and activation",
            user={"id": u["id"], "username": u["username"]}
        )
        conn.commit()

        role = normalize_role(u["role"])
        access_token = create_access_token({"sub": u["username"], "role": role, "uid": u["id"], "token_version": 2})

        return {
            "status": "success",
            "message": "Account activated successfully. Welcome to FinAuditPro!",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": u["id"],
                "username": u["username"],
                "full_name": full_name,
                "role": role,
                "email": u["email"]
            }
        }
    finally:
        conn.close()


# ----------------- ADMIN USER MANAGEMENT -----------------

@router.get("/users")
def list_users(current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: List all users."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, username, email, full_name, role, designation, status, is_active, phone,
                   activation_token, activation_expires_at, last_login, created_at
            FROM users
            ORDER BY id ASC
        """).fetchall()
        
        users = []
        for r in rows:
            u = dict(r)
            u["role"] = normalize_role(u["role"])
            users.append(u)
        return users
    finally:
        conn.close()


@router.post("/users")
def create_user(user_data: UserCreate, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Create new user directly with password or initial state."""
    username = user_data.username.strip()
    email = user_data.email.strip()

    if not re.match(USERNAME_REGEX, username):
        raise HTTPException(status_code=400, detail="Username must be 3-50 characters (letters, numbers, underscores, dots only).")
    
    if not re.match(EMAIL_REGEX, email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    role = normalize_role(user_data.role)

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (username, email)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username or email address is already registered.")

        pwd_hash = hash_password(user_data.password)
        now_str = datetime.now().isoformat()

        cursor = conn.execute("""
            INSERT INTO users (username, email, full_name, role, designation, status, password_hash, is_active, phone, created_at)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, 1, ?, ?)
        """, (username, email, user_data.full_name.strip(), role, "Auditor", pwd_hash, user_data.phone or "", now_str))

        new_id = cursor.lastrowid

        log_audit_event(
            conn=conn,
            action="CREATE_USER",
            module="USER_MANAGEMENT",
            record_id=new_id,
            user=current_user,
            details=f"Created user '{username}' with role '{role}'",
            timestamp=now_str
        )

        conn.commit()
        return {"message": "User created successfully", "user_id": new_id, "username": username, "role": role}
    finally:
        conn.close()


@router.post("/users/invite")
def invite_user(invite_data: UserInviteCreate, current_user: dict = Depends(require_role(["Admin"]))):
    """
    Admin: Creates a new user in 'INVITED' state and issues an offline activation token (valid 48h).
    """
    username = invite_data.username.strip()
    email = invite_data.email.strip()

    if not re.match(USERNAME_REGEX, username):
        raise HTTPException(status_code=400, detail="Username must be 3-50 characters.")
    if not re.match(EMAIL_REGEX, email):
        raise HTTPException(status_code=400, detail="Invalid email address.")

    role = normalize_role(invite_data.role)
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now() + timedelta(hours=48)).isoformat()
    now_str = datetime.now().isoformat()

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (username, email)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username or email address is already registered.")

        # Temporary placeholder hash
        dummy_hash = hash_password(secrets.token_hex(16))

        cursor = conn.execute("""
            INSERT INTO users (
                username, email, full_name, role, designation, status,
                password_hash, is_active, phone, activation_token, activation_expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, 'INVITED', ?, 0, ?, ?, ?, ?)
        """, (
            username, email, invite_data.full_name.strip(), role,
            invite_data.designation or role, dummy_hash, invite_data.phone or "",
            token, expires_at, now_str
        ))
        new_id = cursor.lastrowid

        log_audit_event(
            conn=conn,
            action="INVITE_USER",
            module="USER_MANAGEMENT",
            record_id=new_id,
            user=current_user,
            details=f"Invited user '{username}' with role '{role}' (Token: {token[:8]}...)",
            timestamp=now_str
        )
        conn.commit()

        return {
            "status": "success",
            "message": f"Invitation generated for {invite_data.full_name}.",
            "user_id": new_id,
            "username": username,
            "activation_token": token,
            "activation_expires_at": expires_at
        }
    finally:
        conn.close()


@router.put("/users/{user_id}")
def update_user(user_id: int, update_data: UserUpdate, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Update user profile and role."""
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        updates = []
        params = []

        if update_data.full_name is not None:
            updates.append("full_name = ?")
            params.append(update_data.full_name.strip())

        if update_data.email is not None:
            email = update_data.email.strip()
            if not re.match(EMAIL_REGEX, email):
                raise HTTPException(status_code=400, detail="Invalid email format")
            updates.append("email = ?")
            params.append(email)

        if update_data.phone is not None:
            updates.append("phone = ?")
            params.append(update_data.phone.strip())

        if update_data.role is not None:
            new_role = normalize_role(update_data.role)
            if user["id"] == current_user["id"] and new_role != "Admin":
                admin_count = conn.execute("SELECT COUNT(*) as c FROM users WHERE role = 'Admin' AND is_active = 1").fetchone()["c"]
                if admin_count <= 1:
                    raise HTTPException(status_code=400, detail="Cannot demote the only active Administrator.")
            updates.append("role = ?")
            params.append(new_role)

        if updates:
            params.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", tuple(params))
            now_str = datetime.now().isoformat()
            log_audit_event(
                conn=conn,
                action="UPDATE_USER",
                module="USER_MANAGEMENT",
                record_id=user_id,
                user=current_user,
                details=f"Updated user profile for {user['username']}",
                timestamp=now_str
            )
            conn.commit()

        return {"message": "User details updated successfully"}
    finally:
        conn.close()


@router.put("/users/{user_id}/status")
def toggle_user_status(user_id: int, status_req: UserStatusUpdate, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Enable or disable a user account."""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="You cannot disable your own active administrator account.")

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        new_status = 1 if status_req.is_active else 0
        new_status_str = "ACTIVE" if new_status else "DISABLED"
        now_str = datetime.now().isoformat()

        conn.execute(
            "UPDATE users SET is_active = ?, status = ?, token_version = COALESCE(token_version, 1) + 1 WHERE id = ?",
            (new_status, new_status_str, user_id)
        )
        action_desc = "Enabled" if new_status else "Disabled"
        log_audit_event(
            conn=conn,
            action="TOGGLE_USER_STATUS",
            module="USER_MANAGEMENT",
            record_id=user_id,
            user=current_user,
            details=f"{action_desc} user account {user['username']}",
            timestamp=now_str
        )
        conn.commit()
        return {"message": f"User account {user['username']} has been {action_desc.lower()}.", "is_active": new_status}
    finally:
        conn.close()


@router.post("/users/{user_id}/reset-activation")
def reset_user_activation(user_id: int, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Generates a new activation token for an invited user."""
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        token = secrets.token_urlsafe(24)
        expires_at = (datetime.now() + timedelta(hours=48)).isoformat()
        now_str = datetime.now().isoformat()

        conn.execute("""
            UPDATE users
            SET activation_token = ?, activation_expires_at = ?, status = 'INVITED', is_active = 0
            WHERE id = ?
        """, (token, expires_at, user_id))

        log_audit_event(
            conn=conn,
            action="RESET_ACTIVATION",
            module="USER_MANAGEMENT",
            record_id=user_id,
            user=current_user,
            details=f"Re-issued activation token for {user['username']}",
            timestamp=now_str
        )
        conn.commit()
        return {
            "status": "success",
            "message": f"New activation token generated for {user['username']}.",
            "activation_token": token,
            "activation_expires_at": expires_at
        }
    finally:
        conn.close()


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, req: AdminResetPasswordRequest, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Reset a user's password directly."""
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters long.")

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        new_hash = hash_password(req.new_password)
        now_str = datetime.now().isoformat()

        conn.execute(
            "UPDATE users SET password_hash = ?, token_version = COALESCE(token_version, 1) + 1 WHERE id = ?",
            (new_hash, user_id)
        )
        log_audit_event(
            conn=conn,
            action="ADMIN_RESET_PASSWORD",
            module="USER_MANAGEMENT",
            record_id=user_id,
            user=current_user,
            details=f"Admin reset password for {user['username']}",
            timestamp=now_str
        )
        conn.commit()
        return {"message": f"Password for {user['username']} has been reset successfully."}
    finally:
        conn.close()
