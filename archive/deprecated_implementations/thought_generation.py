"""Thought generation node for image overlay.

Generates or extracts a short, powerful thought (20-35 words) from the draft
content to be used as text overlay on the LinkedIn image template.

Thought must be plain text with no markdown, hashtags, emojis, code, or URLs.
"""

import logging
import re
from langchain_core.messages import HumanMessage, AIMessage
from app.Services.llm_fallback import FallbackLLM

logger = logging.getLogger(__name__)


def _extract_first_insight(text: str, max_words: int = 35) -> str:
    """Extract first sentence/insight from text as fallback.

    If LLM fails, extract and truncate the first meaningful sentence.
    """
    # Remove markdown/html/code
    cleaned = re.sub(r'[*_`#~]', '', text)
    cleaned = re.sub(r'<[^>]+>', '', cleaned)

    # Split on sentence boundaries
    sentences = re.split(r'[.!?]\s+', cleaned)
    if sentences:
        first = sentences[0].strip()
        words = first.split()
        if len(words) > max_words:
            words = words[:max_words]
        return " ".join(words)

    # Fallback: just truncate first words
    words = cleaned.split()[:max_words]
    return " ".join(words)


def _clean_thought(text: str) -> str:
    """Remove markdown, emojis, hashtags, code, URLs from thought."""
    # Remove markdown
    text = re.sub(r'[*_`#~\[\]]', '', text)

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)

    # Remove emojis (basic attempt)
    text = re.sub(r'[\U0001F600-\U0001F64F]', '', text)  # Emoticons
    text = re.sub(r'[\U0001F300-\U0001F5FF]', '', text)  # Symbols
    text = re.sub(r'[\U0001F680-\U0001F6FF]', '', text)  # Transport
    text = re.sub(r'[\U0001F1E0-\U0001F1FF]', '', text)  # Flags

    # Remove hashtags (keep words, remove # symbol)
    text = re.sub(r'#(\w+)', r'\1', text)

    # Remove code markers
    text = re.sub(r'`.*?`', '', text)

    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


async def thought_generation_node(state: dict) -> dict:
    """LangGraph node for generating image overlay thought.

    Extracts or generates a short, powerful thought (20-35 words) from the
    draft content to be displayed as text overlay on the LinkedIn image.

    The thought must be:
    - Plain text only (no markdown, code, HTML, hashtags, emojis, URLs)
    - Professional and thought-provoking
    - Suitable for large text display on image
    - Actionable or insightful
    - Exactly 20-35 words

    Args:
        state: LangGraph state containing:
            - draft_content: Generated post content

    Returns:
        Updated state dict with:
            - ai_thought: Generated thought (20-35 words, plain text)
            - thought_tokens_used: Tokens used for generation
            - messages: Conversation messages
    """
    draft_content = state.get("draft_content", "")

    if not draft_content:
        logger.warning("No draft content for thought generation")
        return {"ai_thought": None, "thought_tokens_used": 0}

    llm = FallbackLLM(temperature=0.5)  # Lower temp for consistency

    prompt = f"""Extract or generate ONE powerful technical thought from this LinkedIn post.

Post excerpt:
{draft_content[:500]}

Requirements for the thought:
1. Exactly 20-35 words
2. NO hashtags, NO emojis, NO markdown, NO code blocks, NO URLs
3. Professional and thought-provoking
4. Suitable for large text on image
5. Actionable or insightful
6. Plain text only

Return ONLY the thought, nothing else. No quotation marks, no additional text."""

    messages = [{"role": "user", "content": prompt}]

    try:
        response = await llm.ainvoke(messages)

        # Extract and clean the thought
        raw_thought = response.content if isinstance(response.content, str) else str(response.content)
        raw_thought = raw_thought.strip().strip('"\'')  # Remove quotes

        # Remove any remaining markdown/special chars
        thought = _clean_thought(raw_thought)

        # Validate word count
        words = thought.split()
        word_count = len(words)

        if word_count < 20:
            logger.warning(f"Thought too short ({word_count} words). Extracting from draft...")
            thought = _extract_first_insight(draft_content, max_words=35)
            words = thought.split()
            word_count = len(words)

        if word_count > 35:
            logger.warning(f"Thought too long ({word_count} words). Truncating to 35...")
            thought = " ".join(words[:35])
            word_count = 35

        logger.info(
            f"Generated thought ({word_count} words): "
            f"{thought[:60]}..."
        )

        return {
            "ai_thought": thought,
            "thought_tokens_used": response.tokens_used or 0,
            "messages": [
                HumanMessage(content=prompt),
                AIMessage(content=thought),
            ],
        }

    except Exception as e:
        logger.error(f"Error generating thought: {str(e)}")
        logger.info("Falling back to extracting first insight from draft...")
        try:
            thought = _extract_first_insight(draft_content)
            logger.info(f"Extracted thought: {thought[:60]}...")
            return {
                "ai_thought": thought,
                "thought_tokens_used": 0,
                "messages": [],
            }
        except Exception as extract_err:
            logger.error(f"Failed to extract thought: {str(extract_err)}")
            return {"ai_thought": None, "thought_tokens_used": 0}
