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
    """Read the configured session timeout, falling back safely if settings cannot be read."""
    conn = None
    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'session_timeout_minutes'"
        ).fetchone()
        if row and row["value"]:
            return max(5, int(row["value"]))
    except Exception:
        return 60
    finally:
        if conn is not None:
            conn.close()
    return 60


def get_jwt_secret() -> str:
    """Return an environment secret or atomically create/read the persisted local secret."""
    env_secret = os.environ.get("FINAUDIT_SECRET_KEY")
    if env_secret:
        return env_secret

    conn = None
    try:
        conn = get_db_connection()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_settings "
            "(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
        )
        # Serialize first-time creation so concurrent requests cannot overwrite one another's key.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'jwt_secret_key'"
        ).fetchone()
        if row and row["value"]:
            secret = row["value"]
            conn.commit()
            return secret

        new_secret = secrets.token_hex(32)
        now_str = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('jwt_secret_key', ?, ?)",
            (new_secret, now_str),
        )
        conn.commit()
        return new_secret
    except Exception as exc:
        if conn is not None and conn.in_transaction:
            conn.rollback()
        raise RuntimeError(
            "JWT secret is unavailable; refusing to start authentication."
        ) from exc
    finally:
        if conn is not None:
            conn.close()


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
    
    # Ensure token_version is included; close the connection even if the query fails.
    if "token_version" not in to_encode:
        conn = None
        try:
            conn = get_db_connection()
            user = conn.execute(
                "SELECT token_version FROM users WHERE username = ?",
                (data.get("sub"),),
            ).fetchone()
            to_encode["token_version"] = (
                user["token_version"] if user and user["token_version"] else 1
            )
        except Exception:
            to_encode["token_version"] = 1
        finally:
            if conn is not None:
                conn.close()

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
    """Persist explicit token revocation; surface failures instead of falsely reporting success."""
    conn = get_db_connection()
    try:
        now = datetime.now(timezone.utc)
        expires = exp_timestamp or (now + timedelta(days=1))
        conn.execute(
            "INSERT OR REPLACE INTO revoked_tokens (jti, username, revoked_at, expires_at) VALUES (?, ?, ?, ?)",
            (jti, username, now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def invalidate_user_sessions(user_id: int):
    """Atomically increment token_version; never hide a failed session invalidation."""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "UPDATE users SET token_version = COALESCE(token_version, 1) + 1 WHERE id = ?",
            (user_id,),
        )
        if cursor.rowcount != 1:
            raise RuntimeError(f"Cannot invalidate sessions: user id {user_id} was not found.")
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    secret = get_jwt_secret()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
        )
        username = payload.get("sub")
        jti = payload.get("jti")
        token_version = payload.get("token_version", 1)
        if not isinstance(username, str) or not username.strip():
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        if isinstance(token_version, bool) or not isinstance(token_version, int) or token_version < 1:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or malformed authentication token")

    conn = get_db_connection()
    try:
        if jti:
            revoked = conn.execute(
                "SELECT 1 FROM revoked_tokens WHERE jti = ?",
                (jti,),
            ).fetchone()
            if revoked:
                raise HTTPException(status_code=401, detail="Token has been revoked. Please log in again.")

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()

    if user is None:
        raise HTTPException(status_code=401, detail="User account not found")

    user_dict = dict(user)
    status = str(user_dict.get("status") or "ACTIVE").strip().upper()
    if not user_dict.get("is_active", 1) or status == "DISABLED":
        raise HTTPException(
            status_code=403,
            detail="Account is disabled. Please contact your audit administrator.",
        )
    if status == "LOCKED":
        raise HTTPException(status_code=403, detail="Account is locked. Please contact your audit administrator.")
    if status == "INVITED":
        raise HTTPException(status_code=403, detail="Account activation is required before signing in.")
    if status not in {"ACTIVE", ""}:
        raise HTTPException(status_code=403, detail="Account status is invalid. Please contact your audit administrator.")

    current_version = user_dict.get("token_version", 1) or 1
    # Any mismatch is invalid: accepting a future version is fail-open behavior.
    if token_version != current_version:
        raise HTTPException(
            status_code=401,
            detail="Session has been invalidated due to a password or role change. Please log in again.",
        )

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
