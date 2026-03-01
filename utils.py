import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from config import settings
from database import get_supabase

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================================
# TIER
# ============================================
TIER_LEVEL = {
    "freemium": 1,
    "premium": 2,
    "pro": 3,
    "lifetime": 4,
}


def tier_has_access(user_tier: str, required_tier: str) -> bool:
    """Check xem user_tier có đủ để dùng required_tier không"""
    return TIER_LEVEL.get(user_tier, 0) >= TIER_LEVEL.get(required_tier, 99)


def is_tier_active(tier: str, tier_expires_at: Optional[str]) -> bool:
    """Check xem tier còn hạn không"""
    if tier == "freemium":
        return True
    if tier == "lifetime":
        return True
    if tier_expires_at is None:
        return False
    expires = datetime.fromisoformat(tier_expires_at.replace("Z", "+00:00"))
    return expires > datetime.now(timezone.utc)


# ============================================
# PASSWORD
# ============================================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ============================================
# JWT TOKEN
# ============================================
def create_token(user_id: str) -> str:
    from datetime import timedelta
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[str]:
    """Trả về user_id nếu token hợp lệ, None nếu không"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


# ============================================
# KEY GENERATOR
# ============================================
def generate_key_code() -> str:
    """Tạo key dạng XXXX-XXXX-XXXX-XXXX"""
    chars = string.ascii_uppercase + string.digits
    parts = ["".join(secrets.choice(chars) for _ in range(4)) for _ in range(4)]
    return "-".join(parts)


# ============================================
# LOGGING
# ============================================
def log_action(user_id: Optional[str], action: str, detail: Optional[dict] = None, ip: Optional[str] = None):
    """Ghi log vào bảng logs - không raise exception dù fail"""
    try:
        db = get_supabase()
        db.table("logs").insert({
            "user_id": user_id,
            "action": action,
            "detail": detail,
            "ip_address": ip,
        }).execute()
    except Exception:
        pass  # Log fail không được làm crash hệ thống


# ============================================
# GET CURRENT USER (từ token)
# ============================================
def get_current_user(token: str) -> Optional[dict]:
    """Lấy thông tin user từ token, trả về None nếu invalid"""
    user_id = decode_token(token)
    if not user_id:
        return None
    db = get_supabase()
    result = db.table("users").select("*").eq("id", user_id).single().execute()
    if not result.data:
        return None
    user = result.data
    if user.get("is_banned"):
        return None
    return user
