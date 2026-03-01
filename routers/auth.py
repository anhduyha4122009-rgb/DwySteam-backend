from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional
from datetime import datetime, timezone, timedelta

from database import get_supabase
from schemas import RegisterRequest, LoginRequest, AuthResponse
from utils import hash_password, verify_password, create_token, get_current_user, log_action
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=dict)
async def register(body: RegisterRequest, request: Request):
    db = get_supabase()

    # Check username hoặc email đã tồn tại chưa
    existing = db.table("users").select("id").or_(
        f"email.eq.{body.email},username.eq.{body.username}"
    ).execute()

    if existing.data:
        raise HTTPException(status_code=400, detail="Username hoặc email đã tồn tại")

    # Tạo user mới
    new_user = db.table("users").insert({
        "username": body.username,
        "email": body.email,
        "password_hash": hash_password(body.password),
        "tier": "freemium",
    }).execute()

    user = new_user.data[0]
    log_action(user["id"], "register", ip=request.client.host)

    return {"message": "Đăng ký thành công"}


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request):
    db = get_supabase()

    # Tìm user theo email
    result = db.table("users").select("*").eq("email", body.email).single().execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Email hoặc password không đúng")

    user = result.data

    # Check bị ban chưa
    if user.get("is_banned"):
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

    # Verify password
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email hoặc password không đúng")

    # Tạo token và lưu session
    token = create_token(user["id"])
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)

    db.table("sessions").insert({
        "user_id": user["id"],
        "token": token,
        "expires_at": expires_at.isoformat(),
    }).execute()

    log_action(user["id"], "login", ip=request.client.host)

    return AuthResponse(
        token=token,
        user_id=user["id"],
        username=user["username"],
        tier=user["tier"],
        tier_expires_at=user.get("tier_expires_at"),
    )


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None), request: Request = None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    token = authorization.split(" ")[1]
    db = get_supabase()

    # Xóa session
    db.table("sessions").delete().eq("token", token).execute()

    return {"message": "Đã đăng xuất"}
