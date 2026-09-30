import re
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import List, Optional
from backend.app.schemas import (
    UserLogin, UserCreate, UserUpdate, UserStatusUpdate,
    ChangePasswordRequest, AdminResetPasswordRequest, UserResponse
)
from backend.app.auth import (
    verify_password, hash_password, create_access_token,
    get_current_user, require_role, normalize_role
)
from backend.app.database import get_db_connection

from backend.app.utils.audit_logger import log_audit_event

router = APIRouter(prefix="/api/auth", tags=["User Management & Authentication"])

USERNAME_REGEX = r"^[a-zA-Z0-9_.]{3,50}$"
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"

@router.post("/login")
def login(creds: UserLogin):
    """Authenticate user with username and password, update last_login, return JWT token."""
    username = creds.username.strip()
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)).fetchone()

    if not user or not verify_password(creds.password, user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user["is_active"]:
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="Your user account has been disabled by the Administrator. Please contact audit administration."
        )

    now_str = datetime.now().isoformat()
    # Update last login timestamp
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_str, user["id"]))

    role = normalize_role(user["role"])

    # Record login in audit trail
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
    conn.close()

    token = create_access_token({"sub": user["username"], "role": role, "uid": user["id"]})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": role,
            "email": user["email"],
            "phone": user["phone"],
            "last_login": now_str,
            "created_at": user["created_at"]
        }
    }

@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """Log the logout event in the audit trail."""
    conn = get_db_connection()
    log_audit_event(
        conn,
        action="LOGOUT",
        module="AUTH",
        record_id=current_user.get("id"),
        details=f"User '{current_user.get('username')}' logged out",
        user=current_user
    )
    conn.commit()
    conn.close()
    return {"message": "Logged out successfully"}

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user profile and permissions."""
    role = normalize_role(current_user.get("role"))
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "full_name": current_user["full_name"],
        "role": role,
        "email": current_user.get("email"),
        "phone": current_user.get("phone"),
        "is_active": current_user.get("is_active", 1),
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
    """Change password for currently authenticated user."""
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (current_user["id"],)).fetchone()
    
    if not user or not verify_password(req.old_password, user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=400, detail="Current password entered is incorrect.")

    if len(req.new_password) < 6:
        conn.close()
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long.")

    new_hash = hash_password(req.new_password)
    now_str = datetime.now().isoformat()
    
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
    conn.execute("""
    INSERT INTO audit_logs (user_id, username, action, entity_type, entity_id, details, timestamp)
    VALUES (?, ?, 'CHANGE_PASSWORD', 'user', ?, 'User updated account password', ?)
    """, (user["id"], user["username"], user["id"], now_str))
    
    conn.commit()
    conn.close()
    return {"message": "Password changed successfully"}

# ----------------- ADMIN USER MANAGEMENT -----------------

@router.get("/users")
def list_users(current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: List all users."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, username, email, full_name, role, is_active, phone, last_login, created_at
        FROM users
        ORDER BY id ASC
    """).fetchall()
    
    users = []
    for r in rows:
        u = dict(r)
        u["role"] = normalize_role(u["role"])
        users.append(u)
    conn.close()
    return users

@router.post("/users")
def create_user(user_data: UserCreate, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Create new user with role assignment and hashed password."""
    username = user_data.username.strip()
    email = user_data.email.strip()

    if not re.match(USERNAME_REGEX, username):
        raise HTTPException(status_code=400, detail="Username must be 3-50 characters (letters, numbers, underscores, dots only).")
    
    if not re.match(EMAIL_REGEX, email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    role = normalize_role(user_data.role)

    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)", (username, email)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Username or email address is already registered.")

    pwd_hash = hash_password(user_data.password)
    now_str = datetime.now().isoformat()

    cursor = conn.execute("""
    INSERT INTO users (username, email, full_name, role, password_hash, is_active, phone, created_at)
    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
    """, (username, email, user_data.full_name.strip(), role, pwd_hash, user_data.phone or "", now_str))

    new_id = cursor.lastrowid

    conn.execute("""
    INSERT INTO audit_logs (user_id, username, action, entity_type, entity_id, details, timestamp)
    VALUES (?, ?, 'CREATE_USER', 'user', ?, ?, ?)
    """, (current_user["id"], current_user["username"], new_id, f"Created user {username} with role {role}", now_str))

    conn.commit()
    conn.close()
    return {"message": "User created successfully", "user_id": new_id, "username": username, "role": role}

@router.put("/users/{user_id}")
def update_user(user_id: int, update_data: UserUpdate, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Update user profile and role."""
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    updates = []
    params = []

    if update_data.full_name is not None:
        updates.append("full_name = ?")
        params.append(update_data.full_name.strip())

    if update_data.email is not None:
        email = update_data.email.strip()
        if not re.match(EMAIL_REGEX, email):
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid email format")
        updates.append("email = ?")
        params.append(email)

    if update_data.phone is not None:
        updates.append("phone = ?")
        params.append(update_data.phone.strip())

    if update_data.role is not None:
        new_role = normalize_role(update_data.role)
        # Prevent demoting self if only active admin
        if user["id"] == current_user["id"] and new_role != "Admin":
            admin_count = conn.execute("SELECT COUNT(*) as c FROM users WHERE role = 'Admin' AND is_active = 1").fetchone()["c"]
            if admin_count <= 1:
                conn.close()
                raise HTTPException(status_code=400, detail="Cannot demote the only active Administrator.")
        updates.append("role = ?")
        params.append(new_role)

    if updates:
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", tuple(params))
        now_str = datetime.now().isoformat()
        conn.execute("""
        INSERT INTO audit_logs (user_id, username, action, entity_type, entity_id, details, timestamp)
        VALUES (?, ?, 'UPDATE_USER', 'user', ?, ?, ?)
        """, (current_user["id"], current_user["username"], user_id, f"Updated user profile for {user['username']}", now_str))
        conn.commit()

    conn.close()
    return {"message": "User details updated successfully"}

@router.put("/users/{user_id}/status")
def toggle_user_status(user_id: int, status_req: UserStatusUpdate, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Enable or disable a user account."""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="You cannot disable your own active administrator account.")

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    new_status = 1 if status_req.is_active else 0
    now_str = datetime.now().isoformat()

    conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    action_desc = "Enabled" if new_status else "Disabled"
    conn.execute("""
    INSERT INTO audit_logs (user_id, username, action, entity_type, entity_id, details, timestamp)
    VALUES (?, ?, 'TOGGLE_USER_STATUS', 'user', ?, ?, ?)
    """, (current_user["id"], current_user["username"], user_id, f"{action_desc} user account {user['username']}", now_str))

    conn.commit()
    conn.close()
    return {"message": f"User account {user['username']} has been {'enabled' if new_status else 'disabled'}.", "is_active": new_status}

@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, req: AdminResetPasswordRequest, current_user: dict = Depends(require_role(["Admin"]))):
    """Admin: Reset a user's password directly."""
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long.")

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    new_hash = hash_password(req.new_password)
    now_str = datetime.now().isoformat()

    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.execute("""
    INSERT INTO audit_logs (user_id, username, action, entity_type, entity_id, details, timestamp)
    VALUES (?, ?, 'ADMIN_RESET_PASSWORD', 'user', ?, ?, ?)
    """, (current_user["id"], current_user["username"], user_id, f"Admin reset password for {user['username']}", now_str))

    conn.commit()
    conn.close()
    return {"message": f"Password for {user['username']} has been reset successfully."}
