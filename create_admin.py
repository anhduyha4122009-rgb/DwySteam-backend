"""
Chạy script này 1 lần duy nhất để tạo admin account.
Usage: python create_admin.py
"""
import os
import bcrypt
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("=== TẠO ADMIN ACCOUNT ===")
email = input("Admin email: ")
password = input("Admin password: ")

# Dùng bcrypt trực tiếp, tự động xử lý encoding
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")

result = db.table("users").insert({
    "username": "admin",
    "email": email,
    "password_hash": hashed,
    "tier": "lifetime",
    "tier_expires_at": None,
}).execute()

if result.data:
    print(f"\n✅ Tạo admin thành công!")
    print(f"   Username: admin")
    print(f"   Email: {email}")
    print(f"   Tier: lifetime")
else:
    print("\n❌ Lỗi khi tạo admin:", result)
