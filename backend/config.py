import os
from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Settings(BaseSettings):
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "root")
    DB_NAME: str = os.getenv("DB_NAME", "ai_tutor_db")

    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", os.path.join(BASE_DIR, "chroma_data"))
    JWT_SECRET: str = os.getenv("JWT_SECRET", "aitutor-jwt-secret-2026")
    JWT_ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
