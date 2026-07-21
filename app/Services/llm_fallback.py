import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from app.core.config import settings

logger = logging.getLogger(__name__)

class FallbackLLM:
    """Primary Gemini 2.5 Flash model with automated Ollama fallback."""
    def __init__(self, temperature: float = 0.7):
        self.primary = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature
        )
        self.fallback = ChatOllama(
            model=settings.OLLAMA_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature
        )

    async def ainvoke(self, messages, **kwargs):
        try:
            logger.info("Invoking primary model: gemini-2.5-flash")
            return await self.primary.ainvoke(messages, **kwargs)
        except Exception as e:
            logger.warning(f"Primary model (Gemini) failed: {str(e)}. Falling back to Ollama...")
            try:
                return await self.fallback.ainvoke(messages, **kwargs)
            except Exception as fallback_err:
                logger.error(f"Both primary and fallback LLM providers failed: {str(fallback_err)}")
                raise