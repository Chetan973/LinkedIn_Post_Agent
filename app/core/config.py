from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = Field(default="LinkedIn AI Agent")
    API_V1_STR: str = Field(default="/api/v1")

    # Database (Async PostgreSQL - Supabase or self-hosted)
    DATABASE_URL: str = Field(default="postgresql+psycopg_async://postgres:password@localhost:5432/linkedin_agent")

    # Redis (Celery)
    CELERY_BROKER_URL: str = Field(default="redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://redis:6379/0")

    # LangSmith
    LANGCHAIN_TRACING_V2: bool = Field(default=True)
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com")
    LANGCHAIN_API_KEY: str = Field(default="")
    LANGCHAIN_PROJECT: str = Field(default="linkedin-content-agent")

    # LLM
    OPENAI_API_KEY: str = Field(default="")

    # LLM Fallback (Gemini 3.5 Flash with Ollama fallback)
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL_NAME: str = Field(default="gemini-2.5-flash")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL_NAME: str = Field(default="gemma3:4b")

    # LinkedIn OAuth & Publishing
    LINKEDIN_ACCESS_TOKEN: str = Field(default="")
    LINKEDIN_PERSON_URN: str = Field(default="")

    # Retry & Rate Limiting
    LINKEDIN_MAX_RETRIES: int = Field(default=3)
    LINKEDIN_RETRY_BACKOFF: float = Field(default=2.0)
    LINKEDIN_POSTS_PER_DAY: int = Field(default=100)
    MAX_CONCURRENT_LLM_CALLS: int = Field(default=2)

    # Image Rendering (PIL/Pillow Template)
    PROFILE_NAME: str = Field(default="Chetan P")
    PROFILE_ROLE: str = Field(default="Gen AI Engineer")
    TEMPLATE_IMAGE_PATH: str = Field(default="assets/branding/linkedin_template.png")
    FONTS_PATH: str = Field(default="assets/fonts/")
    IMAGE_BRAND_COLOR: str = Field(default="#0077B5")

    # Supabase Authentication (LinkedIn OAuth via Supabase Auth)
    SUPABASE_JWT_SECRET: str = Field(default="")  # JWT signing secret from Supabase dashboard

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
