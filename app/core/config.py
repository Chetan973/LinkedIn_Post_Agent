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

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
