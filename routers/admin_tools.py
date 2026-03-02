# routers/admin_tools.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pathlib import Path
import uuid
from database import supabase  # chỉnh nếu file bạn đặt khác
from utils import require_admin  # hàm check admin token (nếu bạn đã có)
from datetime import datetime

router = APIRouter(prefix="/admin/tools", tags=["admin-tools"])

@router.post("/upload")
async def upload_tool(
    name: str = Form(...),
    version: str = Form(...),
    required_tier: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    admin=Depends(require_admin),
):
    if not file.filename.lower().endswith(".exe"):
        raise HTTPException(status_code=400, detail="Chỉ nhận .exe")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File rỗng")

    tool_id = str(uuid.uuid4())
    storage_path = f"{tool_id}/{file.filename}"

    # Upload lên Supabase Storage bucket "tools"
    up = supabase.storage.from_("tools").upload(
        path=storage_path,
        file=content,
        file_options={"contentType": "application/octet-stream", "upsert": "true"},
    )
    # Một số bản supabase-py trả dict có error
    if isinstance(up, dict) and up.get("error"):
        raise HTTPException(status_code=500, detail=str(up["error"]))

    # Insert record vào bảng tools
    ins = supabase.table("tools").insert({
        "id": tool_id,
        "name": name,
        "description": description,
        "required_tier": required_tier,
        "version": version,
        "file_path": storage_path,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }).execute()

    # tuỳ lib, ins.data có thể list
    return {"ok": True, "tool_id": tool_id, "file_path": storage_path}