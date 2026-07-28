import logging
from dataclasses import dataclass
from typing import Optional, Union, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.core.config import settings
from app.core.prompt_loader import calculate_message_checksum, get_prompt_preview

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM with metadata.

    Attributes:
        content: The generated text response
        model_used: Which model generated this (gemini-3.5-flash or groq-llama-3.1-8b-instant)
        fallback_triggered: Whether primary failed and fallback was used
        tokens_used: Estimated tokens used (if available)
    """
    content: str
    model_used: str
    fallback_triggered: bool
    tokens_used: Optional[int] = None


class FallbackLLM:
    """Primary Gemini 3.5 Flash model with automated Groq fallback.

    Provides transparent fallback: tries Gemini first, falls back to Groq
    (llama-3.1-8b-instant) on any error. Returns metadata about which model was used.
    Groq provides millisecond-level latency and never suffers from local socket drops.
    """

    def __init__(self, temperature: float = 0.7):
        """Initialize with primary (Gemini) and fallback (Groq) LLMs.

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

        # Validate Groq API key is set
        if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
            logger.warning(
                "GROQ_API_KEY is not set or uses placeholder. "
                "Get your key from: https://console.groq.com/keys"
            )

        self.fallback = ChatGroq(
            model=settings.GROQ_MODEL_NAME,
            api_key=settings.GROQ_API_KEY,
            temperature=temperature,
            timeout=10.0,  # Max 10 seconds per request
            max_retries=1,  # Fail fast to other fallback, not retry internally
        )

    def _convert_to_langchain_messages(
        self, messages: Union[List[dict], List[BaseMessage]]
    ) -> List[BaseMessage]:
        """Convert dict-based messages to LangChain message objects.

        Ensures both primary (Gemini) and fallback (Groq) receive identical
        message structure. Validates that system messages propagate correctly.

        Args:
            messages: List of message dicts or LangChain message objects

        Returns:
            List of LangChain message objects (SystemMessage, HumanMessage, etc.)
        """
        if not messages:
            return []

        converted = []
        for msg in messages:
            if isinstance(msg, BaseMessage):
                # Already a LangChain message
                converted.append(msg)
            elif isinstance(msg, dict):
                # Convert dict to appropriate LangChain message
                role = msg.get("role", "user").lower()
                content = msg.get("content", "")

                if role == "system":
                    converted.append(SystemMessage(content=content))
                elif role == "user":
                    converted.append(HumanMessage(content=content))
                elif role == "assistant":
                    converted.append(AIMessage(content=content))
                else:
                    # Default to HumanMessage for unknown roles
                    converted.append(HumanMessage(content=content))
            else:
                # Fallback for unexpected types
                logger.warning(f"Unexpected message type: {type(msg)}. Converting to HumanMessage.")
                converted.append(HumanMessage(content=str(msg)))

        return converted

    async def ainvoke(self, messages, **kwargs) -> LLMResponse:
        """Invoke LLM with transparent fallback.

        Tries Gemini first, falls back to Groq on any error (503, timeout, rate limit).
        Returns both content and metadata about which model succeeded.

        Validates system prompt propagation: both primary and fallback receive
        identical message structure via LangChain message objects.

        Args:
            messages: List of message dicts with 'role'/'content' or LangChain message objects
            **kwargs: Additional arguments for LLM

        Returns:
            LLMResponse with content and metadata

        Raises:
            ValueError: If both primary (Gemini) and fallback (Groq) fail
        """
        # Convert to LangChain message objects to ensure consistent propagation
        lc_messages = self._convert_to_langchain_messages(messages)
        checksum = calculate_message_checksum(lc_messages)

        # Log system prompt for audit trail
        sys_prompt_preview = "[NO SYSTEM PROMPT]"
        for msg in lc_messages:
            if isinstance(msg, SystemMessage):
                sys_prompt_preview = get_prompt_preview(msg.content, max_chars=100)
                break

        try:
            logger.info(
                f"Invoking primary model: {settings.GEMINI_MODEL_NAME} "
                f"(checksum={checksum}) | system_prompt={sys_prompt_preview}"
            )
            response = await self.primary.ainvoke(lc_messages, **kwargs)

            # Extract content (may be string or have .content attribute)
            content = response.content if isinstance(response.content, str) else str(response.content)

            logger.info(
                f"Primary model succeeded ({settings.GEMINI_MODEL_NAME}). "
                f"Response length: {len(content)} chars | checksum={checksum}"
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
                f"Triggering instant fallback to {settings.GROQ_MODEL_NAME} "
                f"with identical messages (checksum={checksum})..."
            )

            try:
                logger.info(
                    f"Invoking fallback model: {settings.GROQ_MODEL_NAME} "
                    f"(Groq - millisecond latency, cloud-based) "
                    f"(checksum={checksum}) | system_prompt={sys_prompt_preview}"
                )
                response = await self.fallback.ainvoke(lc_messages, **kwargs)

                # Extract content
                content = response.content if isinstance(response.content, str) else str(response.content)

                logger.info(
                    f"Fallback model succeeded ({settings.GROQ_MODEL_NAME}). "
                    f"Response length: {len(content)} chars | checksum={checksum}"
                )

                return LLMResponse(
                    content=content,
                    model_used=settings.GROQ_MODEL_NAME,
                    fallback_triggered=True,
                    tokens_used=None,
                )

            except Exception as fallback_err:
                logger.error(
                    f"Both primary ({settings.GEMINI_MODEL_NAME}) and fallback "
                    f"({settings.GROQ_MODEL_NAME}) failed with identical messages (checksum={checksum}). "
                    f"Primary: {str(primary_err)[:80]}. "
                    f"Fallback: {str(fallback_err)[:80]}"
                )
                raise ValueError(
                    f"LLM invocation failed: Primary ({settings.GEMINI_MODEL_NAME}): "
                    f"{str(primary_err)[:80]} | Fallback ({settings.GROQ_MODEL_NAME}): "
                    f"{str(fallback_err)[:80]}"
                )
