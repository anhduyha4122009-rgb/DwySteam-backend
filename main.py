from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, key, hwid, tools, verify, admin

app = FastAPI(
    title="Steam Lite API",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI - tắt đi khi production nếu muốn
    redoc_url=None,
)

# CORS - cho phép launcher và web admin gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # Đổi thành domain cụ thể khi production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router
app.include_router(auth.router)
app.include_router(key.router)
app.include_router(hwid.router)
app.include_router(tools.router)
app.include_router(verify.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Steam Lite API is running"}


@app.get("/health")
async def health():
    """Endpoint để ping server, tránh free tier sleep"""
    return {"status": "ok"}
