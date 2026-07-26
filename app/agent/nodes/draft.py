"""Content drafting node for LangGraph workflow.

Generates high-quality technical LinkedIn content using LLM with fallback.
Tracks which LLM was used (Gemini primary vs Ollama fallback).
"""

import logging
import asyncio
from langchain_core.messages import HumanMessage, AIMessage
from app.agent.state import AgentState
from app.core.config import settings
from app.core.prompt_loader import get_linkedin_system_prompt, get_linkedin_user_message, extract_clean_text, enforce_aggressive_whitespace
from app.Services.llm_fallback import FallbackLLM

logger = logging.getLogger(__name__)

# Concurrency control - limit simultaneous LLM calls
llm_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_LLM_CALLS)

# Load system prompt from markdown file
SYSTEM_PROMPT = get_linkedin_system_prompt()


async def draft_post_node(state: dict) -> dict:
    """LangGraph node for drafting LinkedIn content.

    Generates technical content on the given topic using LLM with fallback.
    Tracks which LLM was used (primary Gemini or fallback Ollama).

    Args:
        state: LangGraph state containing:
            - topic: Topic for post generation
            - selected_category: Category (for context, optional)

    Returns:
        Updated state dict with:
            - draft_content: Generated post content (string)
            - llm_used: Model used ("gemini-3.5-flash" or "ollama-gemma3:4b")
            - llm_attempt: Attempt number (1=primary, 2+=fallback)
            - messages: Conversation messages for history
    """
    topic = state.get("topic", "")
    if not topic:
        raise ValueError("Topic is required for content generation")

    async with llm_semaphore:
        llm = FallbackLLM(temperature=0.7)

        # Load user message from markdown prompt file (single source of truth)
        user_message = get_linkedin_user_message(topic)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await llm.ainvoke(messages)

            # Use universal extractor to handle ALL LangChain response formats
            # Extracts text from: AIMessage objects, dicts, lists, stringified objects, metadata
            draft_text = extract_clean_text(response)

            # Enforce aggressive whitespace around checklist items and mini-headers
            # Ensures blank lines between ☑️ items and 💡🚀🧠👇 headers for scannability
            draft_text = enforce_aggressive_whitespace(draft_text)

            logger.info(
                f"Draft generated using {response.model_used} "
                f"({len(draft_text)} chars, "
                f"fallback={response.fallback_triggered})"
            )

            return {
                "draft_content": draft_text,
                "llm_used": response.model_used,
                "llm_attempt": 2 if response.fallback_triggered else 1,
                "draft_tokens_used": response.tokens_used or 0,
                "messages": [
                    HumanMessage(content=user_message),
                    AIMessage(content=draft_text),
                ],
            }

        except Exception as e:
            logger.error(
                f"CRITICAL: Both primary and fallback LLMs failed for topic '{topic}'. "
                f"Primary error: {str(e)[:200]}. "
                f"Workflow cannot continue without post content."
            )
            # Return error state - workflow will fail gracefully at validation stage
            raise ValueError(
                f"Post generation failed: Both LLMs unavailable. Topic: {topic}"
            ) from e
