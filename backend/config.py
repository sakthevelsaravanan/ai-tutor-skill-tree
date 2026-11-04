from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env', extra='ignore')
    DB_HOST: str = '127.0.0.1'
    DB_PORT: int = 5433
    DB_USER: str = 'ai_tutor_app'
    DB_PASSWORD: str = ''
    DB_NAME: str = 'ai_tutor_db'
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / 'chroma_data')
    JWT_SECRET: str
    COOKIE_SECURE: bool = False
    GROQ_API_KEY: str = ''
    MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024

settings = Settings()
