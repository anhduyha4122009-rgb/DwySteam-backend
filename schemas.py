from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator


# ============================================
# AUTH
# ============================================
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    def username_valid(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username phải từ 3-50 ký tự")
        return v

    @field_validator("password")
    def password_valid(cls, v):
        if len(v) < 6:
            raise ValueError("Password phải ít nhất 6 ký tự")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    username: str
    tier: str
    tier_expires_at: Optional[datetime]


# ============================================
# KEY
# ============================================
class RedeemKeyRequest(BaseModel):
    code: str


class RedeemKeyResponse(BaseModel):
    message: str
    tier: str
    tier_expires_at: Optional[datetime]


# ============================================
# HWID
# ============================================
class HWIDPrepareRequest(BaseModel):
    pass  # Không cần body, dùng token


class HWIDConfirmRequest(BaseModel):
    new_hwid: str


# ============================================
# TOOLS
# ============================================
class ToolResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    required_tier: str
    version: str
    file_size: Optional[int]


class DownloadResponse(BaseModel):
    signed_url: str
    expires_in_seconds: int


# ============================================
# VERIFY
# ============================================
class VerifyRequest(BaseModel):
    hwid: str


class VerifyResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None  # "expired" | "hwid_mismatch" | "banned"


# ============================================
# ADMIN
# ============================================
class GenerateKeysRequest(BaseModel):
    tier: str
    duration_hours: Optional[int] = None  # None = lifetime
    quantity: int

    @field_validator("tier")
    def tier_valid(cls, v):
        if v not in ("freemium", "premium", "pro", "lifetime"):
            raise ValueError("Tier không hợp lệ")
        return v

    @field_validator("quantity")
    def quantity_valid(cls, v):
        if v < 1 or v > 500:
            raise ValueError("Quantity phải từ 1-500")
        return v


class GenerateKeysResponse(BaseModel):
    generated: int
    codes: List[str]


class KeyInfo(BaseModel):
    id: str
    code: str
    tier: str
    duration_hours: Optional[int]
    used_by: Optional[str]
    used_at: Optional[datetime]
    created_at: datetime


class UserInfo(BaseModel):
    id: str
    username: str
    email: str
    tier: str
    tier_expires_at: Optional[datetime]
    hwid: Optional[str]
    hwid_reset_at: Optional[datetime]
    is_banned: bool
    created_at: datetime
