"""Engineering principle for image overlay.

Generates ONE ultra-concise principle loaded from .prompts/linkedin_post_formatter.md:
• Exactly ONE complete sentence
• 5-9 words maximum (single line only)
• Grammatically complete and syntactically whole
• Plain text only (no emojis, hashtags, markdown)
• Renderable on image card in ONE line
"""

import logging
import re
import random
from langchain_core.messages import HumanMessage, AIMessage
from app.core.prompt_loader import get_image_thought_system_prompt, get_image_thought_prompt, extract_clean_text
from app.services.llm_fallback import FallbackLLM

logger = logging.getLogger(__name__)

# Emergency fallback thoughts when all LLMs fail (LLM outage, network errors, etc.)
# All are guaranteed 5-9 words, single line, production-focused
EMERGENCY_THOUGHTS = [
    "Reliable architectures demand continuous production observability.",
    "Structured systems outperform probabilistic engineering at scale.",
    "Predictable schemas prevent silent production failures.",
    "Disciplined state design ensures dependable system recovery.",
    "Observability transforms production failures into architectural improvements.",
    "Distributed consensus requires rigorous protocol verification always.",
    "Deterministic workflows beat clever optimization every time.",
    "Simple architectures scale further than complex systems.",
]


def _clean_thought(text: str) -> str:
    """Clean thought: remove markdown, emojis, URLs, hashtags, quotes.

    Args:
        text: Raw LLM response

    Returns:
        Clean thought text
    """
    # Remove quotes
    text = text.strip().strip('"\'').strip()

    # Remove markdown
    text = re.sub(r'[*_`#~\[\]]', '', text)

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)

    # Remove emojis
    text = re.sub(r'[\U0001F600-\U0001F64F]', '', text)  # Emoticons
    text = re.sub(r'[\U0001F300-\U0001F5FF]', '', text)  # Symbols
    text = re.sub(r'[\U0001F680-\U0001F6FF]', '', text)  # Transport
    text = re.sub(r'[\U0001F1E0-\U0001F1FF]', '', text)  # Flags

    # Remove hashtags (keep words, remove # symbol)
    text = re.sub(r'#(\w+)', r'\1', text)

    # Remove code markers
    text = re.sub(r'`.*?`', '', text)

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


async def thought_generation_node(state: dict) -> dict:
    """Generate one ultra-concise engineering principle for image overlay.

    Loads prompt specifications from .prompts/linkedin_post_formatter.md
    IMAGE THOUGHT RULES section.

    Generates:
    • Exactly ONE complete sentence
    • 5-9 words maximum (single line)
    • Grammatically complete, syntactically whole
    • Renderable on image card in one line
    • No emojis, hashtags, markdown, quotes

    Args:
        state: LangGraph state containing draft_content

    Returns:
        Updated state with ai_thought (5-9 words, one sentence)
    """
    draft_content = state.get("draft_content", "")

    if not draft_content:
        logger.warning("No draft content for thought generation")
        return {"ai_thought": None, "thought_tokens_used": 0}

    # Lower temperature for focused, consistent thought generation
    llm = FallbackLLM(temperature=0.5)

    # Load system prompt and user prompt from markdown files
    system_prompt = get_image_thought_system_prompt()
    base_prompt = get_image_thought_prompt()

    # Prompt for engineering principle extraction
    user_prompt = f"""{base_prompt}

Post excerpt:
{draft_content[:500]}

Return ONLY the principle. No quotes."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await llm.ainvoke(messages)

        # Extract clean text first (handles LangChain objects, dicts, stringified metadata)
        raw_thought = extract_clean_text(response)
        thought = _clean_thought(raw_thought)

        # Validate word count (5-9 words, single-line, no truncation)
        words = thought.split()
        word_count = len(words)

        # Accept thoughts up to 10 words without modification
        # Never truncate—preserve complete sentences
        if word_count > 10:
            logger.warning(f"Thought exceeds ideal length ({word_count} words). Consider reprompting LLM for ≤9 words.")

        # Count lines (simple newline detection)
        line_count = thought.count('\n') + 1

        logger.info(
            f"Generated thought ({word_count} words, {line_count} lines)",
            extra={"preview": thought[:60]}
        )

        return {
            "ai_thought": thought,
            "thought_tokens_used": response.tokens_used or 0,
            "messages": [
                HumanMessage(content=user_prompt),
                AIMessage(content=thought),
            ],
        }

    except (NameError, AttributeError, TypeError, KeyError) as e:
        # Bug in our own code, NOT an LLM failure. Log loudly - silently falling
        # back here would mask defects and ship canned thoughts forever.
        logger.error(
            f"CODE DEFECT in thought_generation (not an LLM failure): "
            f"{type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        thought = random.choice(EMERGENCY_THOUGHTS)
        logger.warning(f"Using emergency fallback thought after code defect: {thought}")
        return {
            "ai_thought": thought,
            "thought_tokens_used": 0,
            "messages": [],
        }

    except Exception as e:
        logger.error(f"Error generating thought (LLM failure): {str(e)}")
        # Emergency fallback: use pre-verified safe thoughts (guaranteed 5-9 words)
        # This ensures image thoughts remain valid even during complete LLM outage
        try:
            thought = random.choice(EMERGENCY_THOUGHTS)
            words = thought.split()
            word_count = len(words)

            logger.warning(
                f"Using emergency fallback thought ({word_count} words): {thought[:60]}..."
            )

            return {
                "ai_thought": thought,
                "thought_tokens_used": 0,
                "messages": [],
            }
        except Exception as fallback_err:
            logger.error(f"Critical: Emergency fallback failed: {str(fallback_err)}")
            return {"ai_thought": None, "thought_tokens_used": 0}
