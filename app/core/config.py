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

    # LLM Fallback (Gemini 3.5 Flash with Groq instant fallback)
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL_NAME: str = Field(default="gemini-3.5-flash")
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL_NAME: str = Field(default="llama-3.1-8b-instant")

    # LinkedIn OAuth & Publishing
    LINKEDIN_ACCESS_TOKEN: str = Field(default="")
    LINKEDIN_PERSON_URN: str = Field(default="")
    LINKEDIN_USER_EMAIL: str = Field(default="vinayuttangi@gmail.com")  # Fallback user email for Swagger UI testing
    LINKEDIN_USER_NAME: str = Field(default="VINAYAKA P")  # Fallback user name for Swagger UI testing
    LINKEDIN_PROFILE_URL: str = Field(default="https://linkedin.com/in/vinayuttangi")  # Fallback LinkedIn profile URL

    # Retry & Rate Limiting
    LINKEDIN_MAX_RETRIES: int = Field(default=3)
    LINKEDIN_RETRY_BACKOFF: float = Field(default=2.0)
    LINKEDIN_POSTS_PER_DAY: int = Field(default=100)
    MAX_CONCURRENT_LLM_CALLS: int = Field(default=2)

    # Image Rendering (PIL/Pillow Template)
    PROFILE_NAME: str = Field(default="Chetan P")
    PROFILE_ROLE: str = Field(default="Gen AI Engineer")
    TEMPLATE_IMAGE_PATH: str = Field(default="assets/branding/linkedin_template.png")

    # Per-user branding (URN -> template mapping, see app/branding/config.py)
    # Chetan  -> assets/branding/linkedin_template.png       (blank, draws name/role/badge)
    # Pranav  -> assets/branding/Pranav_Linkedin_Template.jpeg (prebranded, thought only)
    CHETAN_PERSON_URN: str = Field(default="")
    PRANAV_PERSON_URN: str = Field(default="")

    # Y coordinate where the thought's first line starts on Pranav's pre-branded
    # template. The brand block (photo/name/role/badge) is centered mid-image and
    # ends near y=505, so the thought is anchored below it. Tunable without a code
    # change if the template artwork moves.
    PRANAV_THOUGHT_TOP_Y: int = Field(default=545)
    FONTS_PATH: str = Field(default="assets/fonts/")
    IMAGE_BRAND_COLOR: str = Field(default="#0077B5")

    # Supabase Authentication & OAuth
    SUPABASE_URL: str = Field(default="")  # Supabase project URL (https://xxxxx.supabase.co)
    SUPABASE_ANON_KEY: str = Field(default="")  # Supabase anon/public key
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="")  # Service role key (for server-side operations)
    SUPABASE_JWT_SECRET: str = Field(default="")  # JWT signing secret from Supabase dashboard

    # LinkedIn OIDC Provider Configuration
    SUPABASE_LINKEDIN_OIDC_PROVIDER: str = Field(default="linkedin_oidc")  # Supabase provider ID
    LINKEDIN_CLIENT_ID: str = Field(default="")  # LinkedIn OAuth app client ID (from LinkedIn developers portal)
    LINKEDIN_CLIENT_SECRET: str = Field(default="")  # LinkedIn OAuth app client secret
    OAUTH_REDIRECT_URI: str = Field(default="http://localhost:8000/api/v1/auth/linkedin/callback")

    # Token Management
    TOKEN_REFRESH_THRESHOLD_SECONDS: int = Field(default=300)  # Refresh token if exp < 5 min away
    TOKEN_REFRESH_RETRY_ATTEMPTS: int = Field(default=3)
    TOKEN_REFRESH_RETRY_DELAY_MS: int = Field(default=100)

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
