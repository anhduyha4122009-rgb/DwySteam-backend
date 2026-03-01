from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional, List

from database import get_supabase
from schemas import ToolResponse, DownloadResponse
from utils import get_current_user, tier_has_access, is_tier_active, log_action

router = APIRouter(prefix="/tools", tags=["tools"])


def _get_user_from_header(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    token = authorization.split(" ")[1]
    user = get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token hết hạn hoặc không hợp lệ")
    return user


@router.get("", response_model=List[ToolResponse])
async def list_tools(authorization: Optional[str] = Header(None)):
    """
    Trả về danh sách tool user được phép thấy và dùng theo tier
    """
    user = _get_user_from_header(authorization)
    db = get_supabase()

    # Lấy tất cả tool đang active
    all_tools = db.table("tools").select("*").eq("is_active", True).execute()

    # Filter theo tier của user
    user_tier = user["tier"]
    tier_ok = is_tier_active(user_tier, user.get("tier_expires_at"))

    # Nếu tier hết hạn thì fallback về freemium
    effective_tier = user_tier if tier_ok else "freemium"

    accessible = [
        t for t in all_tools.data
        if tier_has_access(effective_tier, t["required_tier"])
    ]

    return [ToolResponse(
        id=t["id"],
        name=t["name"],
        description=t.get("description"),
        required_tier=t["required_tier"],
        version=t["version"],
        file_size=t.get("file_size"),
    ) for t in accessible]


@router.get("/{tool_id}/download", response_model=DownloadResponse)
async def download_tool(
    tool_id: str,
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Tạo signed URL tạm thời (60s) để download tool
    """
    user = _get_user_from_header(authorization)
    db = get_supabase()

    # Lấy thông tin tool
    tool_result = db.table("tools").select("*").eq("id", tool_id).eq("is_active", True).single().execute()
    if not tool_result.data:
        raise HTTPException(status_code=404, detail="Tool không tồn tại")

    tool = tool_result.data

    # Check tier
    user_tier = user["tier"]
    tier_ok = is_tier_active(user_tier, user.get("tier_expires_at"))
    effective_tier = user_tier if tier_ok else "freemium"

    if not tier_has_access(effective_tier, tool["required_tier"]):
        raise HTTPException(status_code=403, detail=f"Tool này yêu cầu tier {tool['required_tier']}")

    # Bắt buộc phải có HWID trước khi download
    if not user.get("hwid"):
        raise HTTPException(
            status_code=403,
            detail="Bạn cần chạy launcher để đăng ký HWID trước khi download"
        )

    # Tạo signed URL từ Supabase Storage (hết hạn sau 60s)
    signed = db.storage.from_("tools").create_signed_url(tool["file_path"], 60)

    if not signed or not signed.get("signedURL"):
        raise HTTPException(status_code=500, detail="Không thể tạo link download")

    log_action(user["id"], "download_tool", detail={
        "tool_id": tool_id,
        "tool_name": tool["name"],
    }, ip=request.client.host)

    return DownloadResponse(
        signed_url=signed["signedURL"],
        expires_in_seconds=60,
    )
