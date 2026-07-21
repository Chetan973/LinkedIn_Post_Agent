from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "LinkedIn AI Agent"
    API_V1_STR: str = "/api/v1"

    # Database (Async PostgreSQL - Supabase or self-hosted)
    DATABASE_URL: str = "postgresql+psycopg_async://postgres:Postgre$ql134@localhost:5432/linkedin_agent"

    # Redis (Celery)
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # LangSmith
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "linkedin-content-agent"

    # LLM
    OPENAI_API_KEY: str = ""

    # LLM Fallback (Gemini 2.5 Flash with Ollama fallback)
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL_NAME: str = "llama3"

    # LinkedIn OAuth & Publishing
    LINKEDIN_ACCESS_TOKEN: str = ""
    LINKEDIN_PERSON_URN: str = ""

    # Retry & Rate Limiting
    LINKEDIN_MAX_RETRIES: int = 3
    LINKEDIN_RETRY_BACKOFF: float = 2.0  # exponential backoff multiplier
    LINKEDIN_POSTS_PER_DAY: int = 100  # LinkedIn rate limit
    MAX_CONCURRENT_LLM_CALLS: int = 2  # Prevent token exhaustion

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
