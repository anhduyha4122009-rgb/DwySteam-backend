from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional
from datetime import datetime, timezone, timedelta

from database import get_supabase
from schemas import RedeemKeyRequest, RedeemKeyResponse
from utils import get_current_user, log_action

router = APIRouter(prefix="/key", tags=["key"])


def _get_user_from_header(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    token = authorization.split(" ")[1]
    user = get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token hết hạn hoặc không hợp lệ")
    return user


@router.post("/redeem", response_model=RedeemKeyResponse)
async def redeem_key(
    body: RedeemKeyRequest,
    request: Request,
    authorization: Optional[str] = Header(None)
):
    user = _get_user_from_header(authorization)
    db = get_supabase()

    # Tìm key
    key_result = db.table("keys").select("*").eq("code", body.code.upper().strip()).single().execute()
    if not key_result.data:
        raise HTTPException(status_code=404, detail="Key không tồn tại")

    key = key_result.data

    # Check key đã được dùng chưa
    if key.get("used_by"):
        raise HTTPException(status_code=400, detail="Key này đã được sử dụng")

    # Tính thời hạn mới
    now = datetime.now(timezone.utc)

    if key["duration_hours"] is None:
        # Lifetime key
        new_tier = key["tier"]
        new_expires_at = None
    else:
        new_tier = key["tier"]
        # Nếu user đang có tier hợp lệ cùng loại, cộng thêm thời gian
        current_expires = user.get("tier_expires_at")
        if current_expires and user["tier"] == new_tier:
            current_dt = datetime.fromisoformat(current_expires.replace("Z", "+00:00"))
            base = max(now, current_dt)
        else:
            base = now
        new_expires_at = base + timedelta(hours=key["duration_hours"])

    # Cập nhật user
    update_data = {"tier": new_tier}
    if new_expires_at:
        update_data["tier_expires_at"] = new_expires_at.isoformat()
    else:
        update_data["tier_expires_at"] = None

    db.table("users").update(update_data).eq("id", user["id"]).execute()

    # Đánh dấu key đã dùng
    db.table("keys").update({
        "used_by": user["id"],
        "used_at": now.isoformat(),
    }).eq("id", key["id"]).execute()

    log_action(user["id"], "redeem_key", detail={
        "key_id": key["id"],
        "tier": new_tier,
        "duration_hours": key["duration_hours"],
    }, ip=request.client.host)

    return RedeemKeyResponse(
        message="Kích hoạt key thành công!",
        tier=new_tier,
        tier_expires_at=new_expires_at,
    )
