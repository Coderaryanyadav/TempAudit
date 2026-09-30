import hashlib
import os
import hmac
import jwt
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.database import get_db_connection
import secrets

ALGORITHM = "HS256"

def get_session_timeout_minutes() -> int:
    """Reads configured session timeout from app_settings or defaults to 60 minutes."""
    try:
        conn = get_db_connection()
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'session_timeout_minutes'").fetchone()
        conn.close()
        if row and row["value"]:
            return max(5, int(row["value"]))
    except Exception:
        pass
    return 60

def get_jwt_secret() -> str:
    """Retrieves secret key from environment or persisted database settings."""
    env_secret = os.environ.get("FINAUDIT_SECRET_KEY")
    if env_secret:
        return env_secret
    
    try:
        conn = get_db_connection()
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'jwt_secret_key'").fetchone()
        if row and row["value"]:
            secret = row["value"]
            conn.close()
            return secret
        
        new_secret = secrets.token_hex(32)
        now_str = datetime.now(timezone.utc).isoformat()
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('jwt_secret_key', ?, ?)", (new_secret, now_str))
        conn.commit()
        conn.close()
        return new_secret
    except Exception:
        return "finauditpro-local-secure-key-2026-offline"

SECRET_KEY = get_jwt_secret()

security = HTTPBearer(auto_error=False)

JWT_ISSUER = "finauditpro"
JWT_AUDIENCE = "finauditpro-app"

def hash_password(password: str, salt: str = None) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with 100,000 iterations and random salt."""
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"pbkdf2_sha256${salt}${hashed}"

def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verifies plain password against stored hash using PBKDF2."""
    try:
        if stored_hash.startswith("pbkdf2_sha256$"):
            _, salt, hashed = stored_hash.split('$', 2)
            check_hash = hashlib.pbkdf2_hmac(
                'sha256',
                plain_password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            ).hex()
            return hmac.compare_digest(hashed, check_hash)
        return False
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        timeout_mins = get_session_timeout_minutes()
        expire = now_utc + timedelta(minutes=timeout_mins)
    
    # Ensure token_version is included
    if "token_version" not in to_encode:
        try:
            conn = get_db_connection()
            user = conn.execute("SELECT token_version FROM users WHERE username = ?", (data.get("sub"),)).fetchone()
            conn.close()
            to_encode["token_version"] = user["token_version"] if user and user["token_version"] else 1
        except Exception:
            to_encode["token_version"] = 1

    to_encode.update({
        "exp": expire,
        "iat": now_utc,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": secrets.token_hex(16)
    })
    secret = get_jwt_secret()
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    return encoded_jwt

def revoke_token_by_jti(jti: str, username: str, exp_timestamp: Optional[datetime] = None):
    """Adds a token's JTI to revoked_tokens table."""
    try:
        conn = get_db_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        exp_str = exp_timestamp.isoformat() if exp_timestamp else (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        conn.execute("INSERT OR REPLACE INTO revoked_tokens (jti, username, revoked_at, expires_at) VALUES (?, ?, ?, ?)",
                     (jti, username, now_str, exp_str))
        conn.commit()
        conn.close()
    except Exception:
        pass

def invalidate_user_sessions(user_id: int):
    """Increments the user's token_version, instantly invalidating all previously issued JWTs."""
    try:
        conn = get_db_connection()
        conn.execute("UPDATE users SET token_version = COALESCE(token_version, 1) + 1 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    secret = get_jwt_secret()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE
        )
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        token_version: int = payload.get("token_version", 1)
        if not username:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or malformed authentication token")

    conn = get_db_connection()
    # Check if JTI was explicitly revoked (Flaw 27)
    if jti:
        revoked = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
        if revoked:
            conn.close()
            raise HTTPException(status_code=401, detail="Token has been revoked. Please log in again.")

    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User account not found")
    
    user_dict = dict(user)
    if not user_dict.get("is_active", 1):
        raise HTTPException(status_code=403, detail="Account is disabled. Please contact your audit administrator.")

    # Check token_version for password changes / admin resets (Flaws 28, 29)
    current_version = user_dict.get("token_version", 1) or 1
    if token_version < current_version:
        raise HTTPException(status_code=401, detail="Session has been invalidated due to a password or role change. Please log in again.")

    return user_dict

def normalize_role(role: Optional[str]) -> Optional[str]:
    """Normalizes user roles. Fails closed (returns None) on unknown or unexpected role values."""
    if not role:
        return None
    r = role.strip().lower()
    if r in ["admin", "administrator"]:
        return "Admin"
    elif r in ["auditor", "senior auditor", "manager", "senior audit manager"]:
        return "Auditor"
    elif r in ["audit staff", "staff", "assistant", "audit assistant"]:
        return "Audit Staff"
    return None

def require_role(allowed_roles: List[str]):
    def role_checker(current_user: dict = Depends(get_current_user)):
        user_role = normalize_role(current_user.get("role"))
        normalized_allowed = [normalize_role(r) for r in allowed_roles if normalize_role(r) is not None]
        if not user_role or user_role not in normalized_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Access forbidden: Role '{current_user.get('role')}' is not authorized for this action."
            )
        return current_user
    return role_checker

def require_engagement_access(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Centralized Engagement Authorization (Flaw 11 & 20).
    Verifies engagement exists and user has authorization to access/modify it.
    - Admin and Auditor roles can access all engagements in the practice.
    - Audit Staff can access engagements where they are assigned or created by them.
    """
    if not engagement_id:
        raise HTTPException(status_code=400, detail="Invalid engagement ID")

    conn = get_db_connection()
    eng = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    conn.close()

    if not eng:
        raise HTTPException(status_code=404, detail=f"Engagement {engagement_id} not found")

    eng_dict = dict(eng)
    user_role = normalize_role(current_user.get("role"))

    # Admin and Auditor roles have practice-wide engagement access
    if user_role in ["Admin", "Auditor"]:
        return eng_dict

    # Audit Staff must be assigned to engagement
    user_id = current_user.get("id")
    if (eng_dict.get("assigned_staff_id") == user_id or 
        eng_dict.get("lead_auditor_id") == user_id):
        return eng_dict

    raise HTTPException(
        status_code=403,
        detail=f"Access forbidden: You do not have authorization for Engagement #{engagement_id}."
    )
