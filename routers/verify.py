from fastapi import APIRouter, Header
from typing import Optional
from datetime import datetime, timezone

from database import get_supabase
from schemas import VerifyRequest, VerifyResponse
from utils import decode_token, is_tier_active, log_action

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=VerifyResponse)
async def verify(
    body: VerifyRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Launcher và tool gọi endpoint này mỗi 5 phút.
    Trả về valid=True nếu OK, valid=False + reason nếu cần tắt tool.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return VerifyResponse(valid=False, reason="invalid_token")

    token = authorization.split(" ")[1]
    user_id = decode_token(token)

    if not user_id:
        return VerifyResponse(valid=False, reason="invalid_token")

    db = get_supabase()

    # Lấy thông tin user
    result = db.table("users").select("*").eq("id", user_id).single().execute()
    if not result.data:
        return VerifyResponse(valid=False, reason="invalid_token")

    user = result.data

    # Check bị ban
    if user.get("is_banned"):
        log_action(user_id, "verify_fail", detail={"reason": "banned"})
        return VerifyResponse(valid=False, reason="banned")

    # Check tier còn hạn không
    if not is_tier_active(user["tier"], user.get("tier_expires_at")):
        log_action(user_id, "verify_fail", detail={"reason": "expired"})
        return VerifyResponse(valid=False, reason="expired")

    # Check HWID
    if user.get("hwid") and user["hwid"] != body.hwid:
        log_action(user_id, "verify_fail", detail={"reason": "hwid_mismatch"})
        return VerifyResponse(valid=False, reason="hwid_mismatch")

    # Cập nhật last_verified_at trong session
    db.table("sessions").update({
        "last_verified_at": datetime.now(timezone.utc).isoformat()
    }).eq("token", token).execute()

    log_action(user_id, "verify_success")

    return VerifyResponse(valid=True)
