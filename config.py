from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 720
    verify_interval_minutes: int = 5
    hwid_reset_cooldown_hours: int = 24
    admin_secret: str

    class Config:
        env_file = ".env"


settings = Settings()
