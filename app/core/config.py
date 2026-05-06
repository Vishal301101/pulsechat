from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENVIRONMENT: str = "development"
    APP_NAME: str = "PulseChat"
    VERSION: str = "0.1.0"

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# Why lru_cache? Settings() reads from disk every time it's called. 
# lru_cache means it reads once, caches the result, and returns the same object every subsequent call. 
# Important for performance — this function gets called hundreds of times per request.

# Why BaseSettings and not just os.getenv()? 
# BaseSettings gives you type validation — if SECRET_KEY is missing from .env, it raises a clear error on startup instead of a confusing None reference error deep in your JWT code.
# It also auto-converts types: ACCESS_TOKEN_EXPIRE_MINUTES=30 in .env is a string, but BaseSettings converts it to int automatically.
