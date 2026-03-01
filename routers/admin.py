from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List

from database import get_supabase
from schemas import GenerateKeysRequest, GenerateKeysResponse, KeyInfo, UserInfo
from utils import get_current_user, generate_key_code, log_action
from config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(authorization: Optional[str]) -> dict:
    """Chỉ admin (lifetime tier + là admin) mới vào được"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    token = authorization.split(" ")[1]
    user = get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token hết hạn")
    # Chỉ user có username "admin" mới được dùng admin routes
    # Bạn có thể thêm cột is_admin vào bảng users sau nếu muốn
    if user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    return user


@router.post("/keys/generate", response_model=GenerateKeysResponse)
async def generate_keys(
    body: GenerateKeysRequest,
    authorization: Optional[str] = Header(None)
):
    admin = _require_admin(authorization)
    db = get_supabase()

    generated_codes = []
    attempts = 0
    max_attempts = body.quantity * 5  # Tránh infinite loop nếu key trùng

    while len(generated_codes) < body.quantity and attempts < max_attempts:
        attempts += 1
        code = generate_key_code()

        # Check trùng
        existing = db.table("keys").select("id").eq("code", code).execute()
        if existing.data:
            continue

        generated_codes.append(code)

    if not generated_codes:
        raise HTTPException(status_code=500, detail="Không thể generate key")

    # Insert hàng loạt
    insert_data = [{
        "code": code,
        "tier": body.tier,
        "duration_hours": body.duration_hours,
    } for code in generated_codes]

    db.table("keys").insert(insert_data).execute()

    log_action(admin["id"], "admin_generate_keys", detail={
        "tier": body.tier,
        "duration_hours": body.duration_hours,
        "quantity": len(generated_codes),
    })

    return GenerateKeysResponse(
        generated=len(generated_codes),
        codes=generated_codes,
    )


@router.get("/keys", response_model=List[KeyInfo])
async def list_keys(
    used: Optional[bool] = None,  # None = tất cả, True = đã dùng, False = chưa dùng
    authorization: Optional[str] = Header(None)
):
    _require_admin(authorization)
    db = get_supabase()

    query = db.table("keys").select("*").order("created_at", desc=True)

    if used is True:
        query = query.not_.is_("used_by", "null")
    elif used is False:
        query = query.is_("used_by", "null")

    result = query.execute()

    return [KeyInfo(
        id=k["id"],
        code=k["code"],
        tier=k["tier"],
        duration_hours=k.get("duration_hours"),
        used_by=k.get("used_by"),
        used_at=k.get("used_at"),
        created_at=k["created_at"],
    ) for k in result.data]


@router.get("/users", response_model=List[UserInfo])
async def list_users(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    db = get_supabase()

    result = db.table("users").select("*").order("created_at", desc=True).execute()

    return [UserInfo(
        id=u["id"],
        username=u["username"],
        email=u["email"],
        tier=u["tier"],
        tier_expires_at=u.get("tier_expires_at"),
        hwid=u.get("hwid"),
        hwid_reset_at=u.get("hwid_reset_at"),
        is_banned=u.get("is_banned", False),
        created_at=u["created_at"],
    ) for u in result.data]


@router.patch("/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    authorization: Optional[str] = Header(None)
):
    admin = _require_admin(authorization)
    db = get_supabase()

    result = db.table("users").select("id, is_banned").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User không tồn tại")

    new_status = not result.data["is_banned"]
    db.table("users").update({"is_banned": new_status}).eq("id", user_id).execute()

    log_action(admin["id"], "admin_ban_user", detail={
        "target_user_id": user_id,
        "banned": new_status,
    })

    return {"message": f"User đã bị {'khóa' if new_status else 'mở khóa'}"}


@router.get("/stats")
async def get_stats(authorization: Optional[str] = Header(None)):
    """Stats cho admin dashboard: total keys, active keys, lifetime users"""
    _require_admin(authorization)
    db = get_supabase()

    total_keys = db.table("keys").select("id", count="exact").execute()
    active_keys = db.table("keys").select("id", count="exact").is_("used_by", "null").execute()
    lifetime_users = db.table("users").select("id", count="exact").eq("tier", "lifetime").execute()
    total_users = db.table("users").select("id", count="exact").execute()

    return {
        "total_generated_codes": total_keys.count,
        "active_keys": active_keys.count,
        "lifetime_users": lifetime_users.count,
        "total_users": total_users.count,
    }
