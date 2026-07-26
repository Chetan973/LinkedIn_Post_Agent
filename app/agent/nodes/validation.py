"""Content validation node before publishing to LinkedIn.

Validates:
1. Content exists and is string (not dict/list)
2. Character count ≤ 4000 (LinkedIn limit)
3. Thought word count 5-9 (warns if outside range, never truncates)
4. No markdown, HTML, code formatting
5. Hashtag format valid
6. Preserves newlines in commentary (never collapses to single line)
7. Enforces aggressive whitespace around checklist items and headers
"""

import logging
import re
from app.core.prompt_loader import enforce_aggressive_whitespace

logger = logging.getLogger(__name__)

# LinkedIn API limits & minimalist post bounds
LINKEDIN_MAX_COMMENTARY_LENGTH = 4000

# Minimalist post format: 150-230 words (~800-1,200 chars)
# These are soft bounds with warnings; not hard failures
MINIMALIST_POST_MIN_WORDS = 120  # Soft minimum (actual target: 150-230)
MINIMALIST_POST_MAX_WORDS = 250  # Soft maximum (actual target: 150-230)
MINIMALIST_POST_MIN_CHARS = 600  # Approximately 120 words
MINIMALIST_POST_MAX_CHARS = 1600  # Approximately 250 words

# Image thought bounds
THOUGHT_MIN_WORDS = 5
THOUGHT_MAX_WORDS = 9


async def validate_content_node(state: dict) -> dict:
    """LangGraph node for content validation.

    Performs comprehensive pre-flight checks before publishing to LinkedIn.
    Automatically truncates or cleans content to meet requirements.

    Args:
        state: LangGraph state containing draft_content and ai_thought

    Returns:
        Updated state dict with:
            - draft_content: Validated/cleaned content
            - ai_thought: Validated/cleaned thought
            - char_count: Final character count
            - validation_status: "passed" or "failed"
            - validation_errors: List of errors (if any)

    Raises:
        ValueError if validation fails and cannot be recovered
    """
    draft_content = state.get("draft_content", "")
    thought = state.get("ai_thought")
    validation_errors = []

    try:
        # Safety Net: Enforce aggressive whitespace before all other validations
        # This catches any formatting issues from LLM or prior processing
        draft_content = enforce_aggressive_whitespace(draft_content)

        # Check 1: Content exists and is string
        if not draft_content:
            raise ValueError("Draft content is empty")

        if not isinstance(draft_content, str):
            logger.warning(f"Content is not string (type: {type(draft_content)}). Converting...")
            draft_content = str(draft_content)

        # Check 2: Character count validation (LinkedIn hard limit: 4000)
        char_count = len(draft_content)
        if char_count > LINKEDIN_MAX_COMMENTARY_LENGTH:
            logger.warning(
                f"Content {char_count} chars exceeds LinkedIn limit {LINKEDIN_MAX_COMMENTARY_LENGTH}. "
                f"Truncating..."
            )
            # Smart truncation: break at last sentence if possible
            truncated = draft_content[:LINKEDIN_MAX_COMMENTARY_LENGTH]
            last_period = truncated.rfind('.')
            if last_period > LINKEDIN_MAX_COMMENTARY_LENGTH * 0.8:
                draft_content = truncated[:last_period + 1]
            else:
                draft_content = truncated[:LINKEDIN_MAX_COMMENTARY_LENGTH - 3].rstrip() + "..."
            char_count = len(draft_content)
            validation_errors.append(
                f"Content truncated from {len(state.get('draft_content', ''))} "
                f"to {char_count} chars"
            )

        logger.info(f"Content character count: {char_count}/{LINKEDIN_MAX_COMMENTARY_LENGTH} ✓")

        # Check 2.5: Minimalist post format bounds (soft warnings, not hard failures)
        word_count = len(draft_content.split())
        if word_count < MINIMALIST_POST_MIN_WORDS or word_count > MINIMALIST_POST_MAX_WORDS:
            if word_count < MINIMALIST_POST_MIN_WORDS:
                logger.warning(
                    f"Post is too brief ({word_count} words). Minimalist target is 150-230 words. "
                    f"Consider expanding with more architectural details."
                )
                validation_errors.append(
                    f"Post too brief ({word_count} words, target 150-230). Expand with more content."
                )
            elif word_count > MINIMALIST_POST_MAX_WORDS:
                logger.warning(
                    f"Post is too wordy ({word_count} words). Minimalist target is 150-230 words. "
                    f"Use single-line checklist items (☑️) instead of multi-line descriptions."
                )
                validation_errors.append(
                    f"Post too verbose ({word_count} words, target 150-230). Use checklist format."
                )

        # Check 3: Thought word count (if exists)
        if thought:
            words = thought.split()
            word_count = len(words)

            if word_count < THOUGHT_MIN_WORDS:
                logger.warning(f"Thought too short ({word_count} words). Consider reprompting LLM for ≥5 words...")
                validation_errors.append(
                    f"Thought too short ({word_count} < {THOUGHT_MIN_WORDS} words). "
                    f"LLM should regenerate with more content."
                )

            elif word_count > THOUGHT_MAX_WORDS:
                logger.warning(f"Thought exceeds ideal length ({word_count} words). Consider reprompting LLM for ≤9 words...")
                validation_errors.append(
                    f"Thought too long ({word_count} > {THOUGHT_MAX_WORDS} words). "
                    f"Never truncate—regenerate with fewer words for single-line rendering."
                )

        # Check 4: Remove markdown, code, HTML
        markdown_patterns = [
            (r'```[\s\S]*?```', 'code blocks'),
            (r'\*\*.*?\*\*', 'bold markdown'),
            (r'__.*?__', 'bold markdown'),
            (r'_.*?_', 'italic markdown'),
            (r'\[.*?\]\(.*?\)', 'links'),
            (r'<[^>]+>', 'HTML tags'),
            (r'`[^`]+`', 'inline code'),
        ]

        for pattern, desc in markdown_patterns:
            if re.search(pattern, draft_content):
                logger.warning(f"Markdown detected ({desc}). Removing...")
                draft_content = re.sub(pattern, "", draft_content)
                validation_errors.append(f"Removed {desc}")

        # Check 5: Validate hashtag format
        hashtags = re.findall(r'#\w+', draft_content)
        valid_hashtags = [tag for tag in hashtags if re.match(r'^#[a-zA-Z0-9_]+$', tag)]
        invalid_hashtags = set(hashtags) - set(valid_hashtags)

        if invalid_hashtags:
            logger.warning(f"Invalid hashtags: {invalid_hashtags}. Removing...")
            for tag in invalid_hashtags:
                draft_content = draft_content.replace(tag, "")
            validation_errors.append(f"Removed invalid hashtags: {invalid_hashtags}")

        logger.info(f"Hashtags valid ✓ (found {len(valid_hashtags)} valid hashtags)")

        # Check 6: No accidental markdown in thought
        if thought:
            if re.search(r'[*_`#~<>\[\]]', thought):
                logger.warning("Markdown detected in thought. Removing...")
                thought = re.sub(r'[*_`#~<>\[\]]', '', thought)
                validation_errors.append("Removed markdown from thought")

        # Final cleanup: normalize whitespace while PRESERVING newlines
        # Replace multiple spaces on same line with single space, but preserve newlines
        draft_content = re.sub(r'[ \t]+', ' ', draft_content)  # Collapse multiple spaces/tabs on same line
        draft_content = re.sub(r'\n\s*\n', '\n', draft_content)  # Collapse multiple blank lines to single newline
        draft_content = draft_content.strip()  # Only strip leading/trailing whitespace, NOT newlines

        if thought:
            thought = re.sub(r'[ \t]+', ' ', thought).strip()  # For thought, preserve single line but normalize spaces

        # CRITICAL: Sanitize dangerous characters that trigger LinkedIn API truncation bug
        # LinkedIn's server silently drops all text from these characters onward if unescaped
        original_content = draft_content
        draft_content = re.sub(r'[\(\)\[\]\{\}]', '-', draft_content)  # Replace ()[]{}  with -
        draft_content = re.sub(r'[\|~]', '', draft_content)            # Remove pipe and tilde

        if draft_content != original_content:
            logger.warning("Sanitized LinkedIn API reserved characters ()([]{}|~) to prevent silent text truncation.")

        logger.info(
            f"All validations passed ✓ "
            f"({len(validation_errors) if validation_errors else 'no errors'})"
        )

        return {
            "draft_content": draft_content,
            "ai_thought": thought,
            "char_count": len(draft_content),
            "validation_status": "passed",
            "validation_errors": validation_errors,
        }

    except ValueError as e:
        logger.error(f"Validation failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected validation error: {str(e)}")
        raise
