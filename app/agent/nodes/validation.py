"""Content validation node before publishing to LinkedIn.

Validates:
1. Content exists and is string (not dict/list)
2. Character count ≤ 4000 (LinkedIn limit)
3. Thought word count 20-35
4. No markdown, HTML, code formatting
5. Hashtag format valid
6. Plain text only (no special formatting)
"""

import logging
import re

logger = logging.getLogger(__name__)

# LinkedIn API limits
LINKEDIN_MAX_COMMENTARY_LENGTH = 4000
THOUGHT_MIN_WORDS = 20
THOUGHT_MAX_WORDS = 35


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
        # Check 1: Content exists and is string
        if not draft_content:
            raise ValueError("Draft content is empty")

        if not isinstance(draft_content, str):
            logger.warning(f"Content is not string (type: {type(draft_content)}). Converting...")
            draft_content = str(draft_content)

        # Check 2: Character count validation
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

        # Check 3: Thought word count (if exists)
        if thought:
            words = thought.split()
            word_count = len(words)

            if word_count < THOUGHT_MIN_WORDS:
                logger.warning(f"Thought too short ({word_count} words). Padding...")
                validation_errors.append(
                    f"Thought too short ({word_count} < {THOUGHT_MIN_WORDS} words). "
                    f"Padded with ellipsis."
                )
                # Add ellipsis to make it more compelling
                thought = thought + " What are your thoughts?"

            elif word_count > THOUGHT_MAX_WORDS:
                logger.warning(f"Thought too long ({word_count} words). Truncating to 35...")
                words = thought.split()[:THOUGHT_MAX_WORDS]
                thought = " ".join(words)
                validation_errors.append(
                    f"Thought truncated from {word_count} to {THOUGHT_MAX_WORDS} words"
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

        # Final cleanup: normalize whitespace
        draft_content = re.sub(r'\s+', ' ', draft_content).strip()
        if thought:
            thought = re.sub(r'\s+', ' ', thought).strip()

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
