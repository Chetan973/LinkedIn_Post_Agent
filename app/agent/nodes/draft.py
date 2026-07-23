"""Content drafting node for LangGraph workflow.

Generates high-quality technical LinkedIn content using LLM with fallback.
Tracks which LLM was used (Gemini primary vs Ollama fallback).
"""

import logging
import asyncio
from langchain_core.messages import HumanMessage, AIMessage
from app.agent.state import AgentState
from app.core.config import settings
from app.Services.llm_fallback import FallbackLLM

logger = logging.getLogger(__name__)

# Concurrency control - limit simultaneous LLM calls
llm_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_LLM_CALLS)

SYSTEM_PROMPT = """You are a world-class backend engineer and technical thought leader specializing in:
- Cloud infrastructure, distributed systems, and scalability patterns
- RESTful APIs, microservices architecture, and system design
- Generative AI, LLMs, and advanced ML systems
- Database optimization, performance engineering, and reliability

Your task is to write HIGHLY TECHNICAL content with TECHNICAL MOTIVE THOUGHTS suited for advanced backend engineering audiences. Each post should:

1. Demonstrate deep technical expertise and insights
2. Share lessons learned from real-world backend engineering challenges
3. Provide actionable technical knowledge and best practices
4. Use precise technical terminology while remaining clear
5. Include practical examples, architectural patterns, or technical decisions

Writing style:
- 2-3 well-crafted paragraphs (3000-3500 characters total)
- Lead with the core technical insight
- Include specific technical details (not generic)
- Reference relevant systems, patterns, or technologies
- End with a thought-provoking question or call-to-action
- Use relevant hashtags (#backend #engineering #systems etc.)
- Professional, authoritative, yet approachable tone

CRITICAL:
- Write for an ADVANCED backend engineering audience (not entry-level)
- Focus on original perspectives and insights
- Problem-solving and innovation mindset
- NO markdown, NO HTML tags, NO code blocks
- NEVER mention other posts or content"""


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

        user_message = f"""Write a HIGHLY TECHNICAL LinkedIn post about the following topic.
Focus on TECHNICAL MOTIVE THOUGHTS and deep engineering insights.

Topic: {topic}

Requirements:
- Write for an ADVANCED backend engineering audience
- Include specific technical details and engineering principles
- Share lessons learned or insights from real-world systems
- Use precise technical terminology
- 2-3 well-crafted paragraphs
- 3000-3500 characters (target length for engagement without truncation)
- Include hashtags and a thought-provoking question
- Professional, authoritative tone
- NO markdown, NO HTML, NO code blocks

Make this a standout technical post that demonstrates deep expertise and original thinking."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await llm.ainvoke(messages)

            # Extract content and validate it's a string
            draft_text = response.content if isinstance(response.content, str) else str(response.content)

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
            logger.error(f"Error drafting post for topic '{topic}': {str(e)}")
            raise
