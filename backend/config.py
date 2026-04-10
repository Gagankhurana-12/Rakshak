from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    REDIRECT_URI: str
    FRONTEND_URL: str
    CORS_ORIGINS: str
    
    DATABASE_URL: str
    
    PINECONE_API_KEY: str
    PINECONE_INDEX_DISEASES: str = "diseases"
    PINECONE_INDEX_USER_DOCS: str = "user-docs"
    PINECONE_INDEX_USER_VITALS: str = "user-vitals-history"
    
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_TEMPERATURE_PERSONALIZED: float = 0.0
    LLM_TEMPERATURE_GENERAL: float = 0.0
    LLM_TIMEOUT_SECONDS: float = 25.0
    LLM_MAX_TOKENS: int = 400

    ANALYZE_CACHE_TTL_SECONDS: int = 45
    ANALYZE_CACHE_SIZE: int = 128
    
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

settings = Settings()
