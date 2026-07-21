import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from app.core.config import settings

logger = logging.getLogger(__name__)


class FallbackLLM:
    """Primary Gemini 2.5 Flash model with automated Ollama fallback."""

    def __init__(self, temperature: float = 0.7):
        # Validate Gemini API key is set
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
            logger.warning(
                "GEMINI_API_KEY is not set or uses placeholder. "
                "Get your key from: https://aistudio.google.com/apikey"
            )

        self.primary = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
        )
        self.fallback = ChatOllama(
            model=settings.OLLAMA_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
        )

    async def ainvoke(self, messages, **kwargs):
        try:
            logger.info("Invoking primary model: gemini-2.5-flash")
            return await self.primary.ainvoke(messages, **kwargs)
        except Exception as e:
            logger.warning(f"Primary model (Gemini) failed: {str(e)}. Falling back to Ollama...")
            try:
                logger.info(f"Invoking fallback model: {settings.OLLAMA_MODEL_NAME} at {settings.OLLAMA_BASE_URL}")
                return await self.fallback.ainvoke(messages, **kwargs)
            except Exception as fallback_err:
                logger.error(f"Both primary and fallback LLM providers failed: {str(fallback_err)}")
                raise