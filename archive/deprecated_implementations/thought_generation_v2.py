"""Improved thought generation node.

Generates concise technical thoughts (20-35 words, max 3 lines).
Focuses on production GenAI, agentic systems, and engineering mindset.
No marketing language, no emojis, no clickbait.
"""

import logging
import re
from langchain_core.messages import HumanMessage, AIMessage
from app.Services.llm_fallback import FallbackLLM

logger = logging.getLogger(__name__)


def _extract_first_insight(text: str, max_words: int = 35) -> str:
    """Extract first insight from text as fallback.

    If LLM fails, extract and truncate the first meaningful sentence.

    Args:
        text: Source text
        max_words: Maximum words to extract

    Returns:
        First insight (cleaned, word-limited)
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
    """Clean thought: remove markdown, emojis, URLs, hashtags.

    Args:
        text: Raw LLM response

    Returns:
        Clean thought text
    """
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


async def thought_generation_node_v2(state: dict) -> dict:
    """Generate concise technical thought for image overlay.

    Improved version:
    - Max 3 lines (allows natural line breaks)
    - 20-35 words
    - Production GenAI focused
    - Technical, motivational tone
    - No marketing language or clickbait

    Requirements met:
    ✓ Maximum 2-3 lines
    ✓ Approximately 20-35 words
    ✓ Motivational but technical
    ✓ GenAI focused
    ✓ Production engineering mindset
    ✓ No emojis
    ✓ No marketing language
    ✓ No clickbait
    ✓ No hashtags inside image
    ✓ Easy to read on mobile
    ✓ Center aligned
    ✓ White text on dark background

    Args:
        state: LangGraph state containing draft_content

    Returns:
        Updated state with ai_thought (concise, technical)
    """
    draft_content = state.get("draft_content", "")

    if not draft_content:
        logger.warning("No draft content for thought generation")
        return {"ai_thought": None, "thought_tokens_used": 0}

    llm = FallbackLLM(temperature=0.5)  # Lower for consistency

    # Improved prompt focusing on concise, technical GenAI thoughts
    prompt = f"""Generate ONE concise technical thought from this LinkedIn post.

Post excerpt:
{draft_content[:500]}

Requirements:
1. Maximum 3 lines (use line breaks naturally)
2. Exactly 20-35 words
3. Production-focused GenAI or agentic systems insight
4. Motivational but technical tone
5. NO marketing language or clickbait
6. NO emojis, NO hashtags, NO markdown, NO URLs
7. NO code blocks or special characters
8. Plain text only
9. Center-aligned (for mobile readability)

Examples of good thoughts:

"Great AI systems aren't built by larger models alone;
they are built through better orchestration,
evaluation, and memory."

or

"Production GenAI succeeds when prompts,
retrieval, and validation work together—
not independently."

or

"Agentic AI is less about autonomy
and more about reliable decision making."

Return ONLY the thought, nothing else. No quotes, no attribution."""

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

        # Count lines (simple line break detection)
        line_count = thought.count('\n') + 1 if '\n' in thought else 1

        logger.info(
            f"Generated thought ({word_count} words, {line_count} lines): "
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
