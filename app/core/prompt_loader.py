"""Load LinkedIn formatting prompts from markdown files."""

import ast
import hashlib
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def calculate_message_checksum(messages: list) -> str:
    """Calculate checksum of message list for validation.

    Verifies that the same prompt reaches both primary and fallback models.

    Args:
        messages: List of message dicts or LangChain message objects

    Returns:
        SHA256 checksum of serialized messages
    """
    try:
        # Convert messages to serializable format
        serializable = []
        for msg in messages:
            if isinstance(msg, dict):
                serializable.append(msg)
            elif hasattr(msg, "type") and hasattr(msg, "content"):
                # LangChain message object
                serializable.append({"type": msg.type, "content": msg.content})
            else:
                serializable.append({"content": str(msg)})

        # Create checksum
        msg_str = str(serializable)
        checksum = hashlib.sha256(msg_str.encode()).hexdigest()[:16]
        return checksum
    except Exception as e:
        logger.error(f"Failed to calculate message checksum: {e}")
        return "CHECKSUM_ERROR"


def get_prompt_preview(content: str, max_chars: int = 100) -> str:
    """Get a preview snippet of prompt content for logging.

    Args:
        content: Full prompt content
        max_chars: Maximum characters to include

    Returns:
        Preview string (truncated if longer than max_chars)
    """
    if not content:
        return "[EMPTY]"
    preview = content.replace("\n", " ").strip()
    if len(preview) > max_chars:
        return preview[:max_chars] + "..."
    return preview


def enforce_aggressive_whitespace(text: str) -> str:
    """Universally enforce double line breaks (\n\n) between every line for breathable minimalist layout.

    This is the foolproof approach that does NOT depend on Unicode regex character classes.
    Works with ANY emoji, ANY special character, ANY Unicode variation selector.

    Algorithm:
    1. Split text into lines, filter empty lines
    2. Join with aggressive double newlines
    3. Result: Guaranteed \n\n between every sentence, bullet, and header

    Args:
        text: Raw LLM output or draft content (may have collapsed spacing)

    Returns:
        Text with universal double-line-break spacing between all content lines
    """
    if not text:
        return ""

    # Split into lines, strip whitespace, discard empty lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Join with aggressive double newlines - guarantees vertical spacing
    formatted_text = "\n\n".join(lines)

    return formatted_text


def extract_clean_text(content) -> str:
    """Universally extract clean plain text from LangChain objects, dicts, lists, or stringified metadata.

    Handles:
    - Actual LangChain response objects with .content attribute
    - Actual dicts and lists (e.g., [{'type': 'text', 'text': '...'}])
    - Stringified dicts/lists (e.g., "[{'type': 'text', 'text': '...'}]")
    - Stringified dicts already partially sanitized (e.g., "-[{'type': 'text'...")
    - Plain strings (passed through)
    - Anything else (converted to string as fallback)

    NEVER returns stringified metadata. Always extracts the actual text field.

    Args:
        content: Any content from LLM response (AIMessage, dict, list, str, etc.)

    Returns:
        Clean plain text string with no metadata, signatures, or LangChain artifacts
    """
    if not content:
        return ""

    # Step 1: If it's an AIMessage or object with .content attribute, extract that first
    if hasattr(content, "content"):
        content = content.content

    # Step 2: If it's a list, extract text blocks from each item
    if isinstance(content, list):
        blocks = []
        for item in content:
            extracted = extract_clean_text(item)  # Recursive call
            if extracted:
                blocks.append(extracted)
        return " ".join(blocks).strip()

    # Step 3: If it's a dict, extract 'text' or 'content' fields
    if isinstance(content, dict):
        text = content.get("text", "") or content.get("content", "")
        if isinstance(text, str):
            return text.strip()
        # If 'text' field is itself a dict or list, recurse
        return extract_clean_text(text)

    # Step 4: If it's a string, check if it's a stringified Python object
    if isinstance(content, str):
        clean_str = content.strip()

        # Check if string looks like a stringified list/dict (with or without leading dashes)
        # Examples: "[{'type': 'text'...", "{...}", "--'type': 'text'...", "-[{'type':..."
        looks_stringified = (
            (clean_str.startswith("[") and clean_str.endswith("]")) or
            (clean_str.startswith("{") and clean_str.endswith("}")) or
            clean_str.startswith("--'") or
            clean_str.startswith("-'") or
            clean_str.startswith("-[{")
        )

        if looks_stringified:
            try:
                # Try to parse stringified content
                # First, remove leading dashes from partially sanitized strings
                parse_str = clean_str.lstrip("-")
                evaluated = ast.literal_eval(parse_str)
                # Recursively extract text from the parsed structure
                return extract_clean_text(evaluated)
            except (ValueError, SyntaxError) as e:
                logger.debug(f"Could not parse stringified content: {e}. Returning as-is.")
                # If parsing fails, check if we can manually extract text pattern
                # This handles edge cases where ast.literal_eval fails
                if "'text':" in clean_str:
                    # Try manual extraction for format: "{'text': 'actual text', ...}"
                    try:
                        # Find text between quotes after 'text':
                        import re
                        match = re.search(r"'text':\s*'([^']*)'", clean_str)
                        if match:
                            return match.group(1)
                    except Exception:
                        pass
                # Return the string as-is if all parsing attempts fail
                return clean_str

        # It's a plain string, return it
        return clean_str

    # Step 5: Fallback for any other type
    result = str(content).strip()
    if not result or result.startswith(("-", "['", "[{", "{'", "'type'")):
        # If stringified, try to extract
        return extract_clean_text(result)
    return result


def load_production_system_prompt() -> str:
    """Load the comprehensive production system prompt from SYSTEM_PROMPT.md.

    This is the authoritative prompt that includes:
    - Role & identity (Expert LinkedIn Branding Strategist)
    - Domain whitelist (14 approved domains)
    - Behavioral guardrails (tone, formatting, factual accuracy)
    - Workflow execution rules
    - Success criteria

    Returns:
        Full system prompt string (364 lines)
    """
    prompt_file = Path(__file__).parent.parent.parent / ".prompts" / "SYSTEM_PROMPT.md"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Production system prompt not found: {prompt_file}")

    content = prompt_file.read_text(encoding="utf-8")
    return content.strip()


def load_linkedin_formatter_prompt() -> dict:
    """Load LinkedIn post formatting rules from markdown file.

    Returns:
        dict with 'linkedin_rules' and 'image_thought_rules' sections
    """
    prompt_file = Path(__file__).parent.parent.parent / ".prompts" / "linkedin_post_formatter.md"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    content = prompt_file.read_text(encoding="utf-8")

    # Extract sections by delimiter
    sections = content.split("=========================================================")

    result = {
        "full_content": content,
        "linkedin_rules": None,
        "image_thought_rules": None,
    }

    # Parse sections
    for i, section in enumerate(sections):
        section_lower = section.lower().strip()

        if "linkedin post formatting rules" in section_lower and i + 1 < len(sections):
            result["linkedin_rules"] = sections[i + 1].strip()
        elif "image thought rules" in section_lower and i + 1 < len(sections):
            result["image_thought_rules"] = sections[i + 1].strip()

    return result


def get_linkedin_system_prompt() -> str:
    """Get the system prompt for drafting LinkedIn posts.

    Loads the comprehensive production system prompt from SYSTEM_PROMPT.md.
    This prompt includes:
    - Domain whitelist (14 approved technical domains)
    - Behavioral guardrails (tone, formatting, factual accuracy)
    - Topic freshness enforcement (prefer latest, trending technologies)
    - Formatting rules (minimalist style, whitespace, forbidden characters)
    - Workflow execution rules

    Returns:
        System prompt string for LLM (includes domain whitelist, guardrails, formatting rules)
    """
    production_prompt = load_production_system_prompt()

    # Append formatting rules from linkedin_post_formatter.md for clarity
    formatter_data = load_linkedin_formatter_prompt()
    linkedin_rules = formatter_data.get("linkedin_rules", "")

    # Combine production prompt with formatting rules
    system_prompt = f"""{production_prompt}

---

## FORMATTING DETAILS

{linkedin_rules}

---

## TOPIC FRESHNESS ENFORCEMENT

**CRITICAL:** This agent is designed to champion LATEST, TRENDING, and MODERN technologies:
- Favor recent innovations and production-proven patterns from the past 12-24 months
- Emphasize emerging technologies, tools, and approaches that senior engineers are actively adopting
- Avoid recycling stale, overexplained concepts (e.g., basic MVC, simple CRUD, introductory patterns)
- Each topic should feel contemporary and directly relevant to ongoing backend/ML engineering challenges
- When selecting from multiple valid topics, choose the most current and production-relevant one
- Acknowledge cutting-edge frameworks, languages, and infrastructure approaches that shape modern systems"""

    return system_prompt


def get_image_thought_system_prompt() -> str:
    """Get the system prompt for generating image thoughts.

    Provides LLM with context about thought generation constraints:
    - Exactly ONE complete sentence
    - 5-9 words maximum
    - No formatting (emojis, hashtags, markdown)
    - Single-line renderability on image overlay

    Returns:
        System prompt string for thought generation
    """
    return """You are an expert at distilling engineering insights into ultra-concise, actionable principles.

Your task is to extract ONE core engineering principle from a LinkedIn post and express it as a single, complete sentence that fits on an image overlay.

CRITICAL CONSTRAINTS:
- Output MUST be EXACTLY ONE complete sentence
- Word count MUST be between 5 and 9 words (no more, no less)
- MUST fit on a SINGLE LINE when rendered on image overlay
- NO formatting: no emojis, no hashtags, no markdown, no quotes, no code blocks
- MUST end with a single period
- Content should be a concrete, actionable engineering principle—not a question or fragment

This thought will appear on a visual overlay card. It must be concise, memorable, and immediately understandable to senior engineers."""


def get_image_thought_prompt() -> str:
    """Get the user prompt for generating image thoughts.

    Returns:
        Prompt string for LLM
    """
    prompt_data = load_linkedin_formatter_prompt()
    rules = prompt_data.get("image_thought_rules", "")

    thought_prompt = f"""Extract ONE engineering principle from the LinkedIn post.

STRICT FORMATTING RULES:
{rules}

Return ONLY the principle. No quotes, no markdown, no emojis."""

    return thought_prompt


def get_linkedin_user_message(topic: str) -> str:
    """Get the user message for drafting minimalist LinkedIn posts.

    This message reinforces the minimalist checklist format with explicit execution rules.
    Prevents drift back to verbose paragraphs or old numbered-list structures.

    Args:
        topic: The topic for the LinkedIn post

    Returns:
        User message string for LLM (minimalist format)
    """
    user_message = f"""Write a clean, minimalist, high-signal LinkedIn post about: {topic}

Follow the exact formatting rules and structure specified in the system prompt.

MANDATORY EXECUTION CHECKLIST:
1. Length: Exactly 150 to 230 words total (~800 to 1,200 characters).
2. Whitespace: Leave a double line break (blank line) between EVERY section, sentence, and mini-header.
3. The Setup: Use exactly 4 or 5 checklist items starting with ☑️ or ✅. Each item must be ultra-short (2 to 5 words max). Do NOT add descriptions or arrow chains under the items.
4. Mini-Headers: You MUST include the exact 3 mini-headers on separate lines, each followed by 1-2 crisp sentences:
   💡 The key difference
   🚀 Why this matters
   🧠 My Take
5. API Safety: NEVER use parentheses (), square brackets [], braces {{}}, or pipe symbols | anywhere in the text.

Generate ONLY the post content. No explanation, no commentary."""

    return user_message
