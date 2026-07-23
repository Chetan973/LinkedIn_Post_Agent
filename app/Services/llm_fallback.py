import logging
from dataclasses import dataclass
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM with metadata.

    Attributes:
        content: The generated text response
        model_used: Which model generated this (gemini-3.5-flash or ollama-gemma3:4b)
        fallback_triggered: Whether primary failed and fallback was used
        tokens_used: Estimated tokens used (if available)
    """
    content: str
    model_used: str
    fallback_triggered: bool
    tokens_used: Optional[int] = None


class FallbackLLM:
    """Primary Gemini 3.5 Flash model with automated Ollama fallback.

    Provides transparent fallback: tries Gemini first, falls back to Ollama
    on any error. Returns metadata about which model was used.
    """

    def __init__(self, temperature: float = 0.7):
        """Initialize with primary (Gemini) and fallback (Ollama) LLMs.

        Args:
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        """
        # Validate Gemini API key is set
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
            logger.warning(
                "GEMINI_API_KEY is not set or uses placeholder. "
                "Get your key from: https://aistudio.google.com/apikey"
            )

        self.primary = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
        )
        self.fallback = ChatOllama(
            model=settings.OLLAMA_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
        )

    async def ainvoke(self, messages, **kwargs) -> LLMResponse:
        """Invoke LLM with transparent fallback.

        Tries Gemini first, falls back to Ollama on any error.
        Returns both content and metadata about which model succeeded.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional arguments for LLM

        Returns:
            LLMResponse with content and metadata

        Raises:
            Exception if both primary and fallback fail
        """
        try:
            logger.info(f"Invoking primary model: {settings.GEMINI_MODEL_NAME}")
            response = await self.primary.ainvoke(messages, **kwargs)

            # Extract content (may be string or have .content attribute)
            content = response.content if isinstance(response.content, str) else str(response.content)

            logger.info(
                f"Primary model succeeded ({settings.GEMINI_MODEL_NAME}). "
                f"Response length: {len(content)} chars"
            )

            return LLMResponse(
                content=content,
                model_used=settings.GEMINI_MODEL_NAME,
                fallback_triggered=False,
                tokens_used=None,
            )

        except Exception as primary_err:
            logger.warning(
                f"Primary model ({settings.GEMINI_MODEL_NAME}) failed: {str(primary_err)[:100]}. "
                f"Triggering fallback to {settings.OLLAMA_MODEL_NAME}..."
            )

            try:
                logger.info(
                    f"Invoking fallback model: {settings.OLLAMA_MODEL_NAME} "
                    f"at {settings.OLLAMA_BASE_URL}"
                )
                response = await self.fallback.ainvoke(messages, **kwargs)

                # Extract content
                content = response.content if isinstance(response.content, str) else str(response.content)

                logger.info(
                    f"Fallback model succeeded ({settings.OLLAMA_MODEL_NAME}). "
                    f"Response length: {len(content)} chars"
                )

                return LLMResponse(
                    content=content,
                    model_used=settings.OLLAMA_MODEL_NAME,
                    fallback_triggered=True,
                    tokens_used=None,
                )

            except Exception as fallback_err:
                logger.error(
                    f"Both primary ({settings.GEMINI_MODEL_NAME}) and fallback "
                    f"({settings.OLLAMA_MODEL_NAME}) failed. "
                    f"Primary: {str(primary_err)[:80]}. "
                    f"Fallback: {str(fallback_err)[:80]}"
                )
                raise