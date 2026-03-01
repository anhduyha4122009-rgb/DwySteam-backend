from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional
from datetime import datetime, timezone, timedelta

from database import get_supabase
from schemas import HWIDConfirmRequest
from utils import get_current_user, log_action
from config import settings

router = APIRouter(prefix="/hwid", tags=["hwid"])


def _get_user_from_header(authorization: Optional[str]) -> tuple[dict, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    token = authorization.split(" ")[1]
    user = get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token hết hạn hoặc không hợp lệ")
    return user, token


@router.post("/reset/prepare")
async def hwid_reset_prepare(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Bước 1: Kiểm tra cooldown, nếu OK trả về signal để launcher kill tool
    Launcher nhận signal này → kill process tool → hiện nút Confirm Reset
    """
    user, _ = _get_user_from_header(authorization)

    # Freemium không có HWID reset
    if user["tier"] == "freemium":
        raise HTTPException(status_code=403, detail="Freemium không hỗ trợ HWID reset")

    # Check cooldown 24h
    hwid_reset_at = user.get("hwid_reset_at")
    if hwid_reset_at:
        last_reset = datetime.fromisoformat(hwid_reset_at.replace("Z", "+00:00"))
        cooldown_until = last_reset + timedelta(hours=settings.hwid_reset_cooldown_hours)
        now = datetime.now(timezone.utc)
        if now < cooldown_until:
            remaining = cooldown_until - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            raise HTTPException(
                status_code=429,
                detail=f"HWID reset cooldown: còn {hours}h {minutes}m"
            )

    log_action(user["id"], "reset_hwid_prepare", ip=request.client.host)

    # Trả signal để launcher kill tool
    return {
        "signal": "end_task",
        "message": "Đang kết thúc tiến trình tool...",
    }


@router.post("/reset/confirm")
async def hwid_reset_confirm(
    body: HWIDConfirmRequest,
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Bước 2: Sau khi launcher đã kill tool, xác nhận reset HWID
    """
    user, _ = _get_user_from_header(authorization)

    if user["tier"] == "freemium":
        raise HTTPException(status_code=403, detail="Freemium không hỗ trợ HWID reset")

    if not body.new_hwid or len(body.new_hwid) < 5:
        raise HTTPException(status_code=400, detail="HWID không hợp lệ")

    now = datetime.now(timezone.utc)
    db = get_supabase()

    db.table("users").update({
        "hwid": body.new_hwid,
        "hwid_reset_at": now.isoformat(),
    }).eq("id", user["id"]).execute()

    log_action(user["id"], "reset_hwid_confirm", detail={
        "new_hwid": body.new_hwid[:8] + "..."  # Chỉ log 8 ký tự đầu
    }, ip=request.client.host)

    return {"message": "HWID đã được reset thành công"}
