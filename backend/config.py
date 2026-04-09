from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    REDIRECT_URI: str = "http://localhost:8080/exchange_token"
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rakshak"
    
    PINECONE_API_KEY: str
    PINECONE_INDEX_DISEASES: str = "diseases"
    PINECONE_INDEX_USER_DOCS: str = "user-docs"
    PINECONE_INDEX_USER_VITALS: str = "user-vitals-history"
    
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

settings = Settings()
