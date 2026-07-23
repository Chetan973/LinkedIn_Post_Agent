from typing import Annotated, TypedDict, Optional
from datetime import datetime
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Complete LangGraph state for autonomous LinkedIn agent.

    Fully autonomous workflow with zero human intervention:
    1. Topic Selection (deduplicated, category-diverse)
    2. Content Drafting (3000-3500 words, technical depth)
    3. Thought Generation (20-35 words, image overlay)
    4. Content Validation (char count, formatting)
    5. Image Rendering (PIL template + text overlay)
    6. Publishing to LinkedIn

    All fields track progress for logging, observability, and debugging.
    """

    # Core workflow fields
    messages: Annotated[list[AnyMessage], add_messages]
    post_id: int
    topic: str  # Selected topic from autonomous selection
    selected_category: str  # Category (java_spring, python_async, etc.)
    draft_content: str  # Main post content (3000-3500 chars)
    ai_thought: Optional[str]  # Thought for image overlay (20-35 words)
    char_count: int  # Final content length

    # Image rendering
    image_bytes: Optional[bytes]  # PNG bytes ready for LinkedIn
    image_url: Optional[str]  # Final image URL after upload
    image_size_bytes: int  # Size of rendered image
    image_rendered_at: bool  # Whether image was successfully rendered
    asset_urn: Optional[str]  # LinkedIn asset URN (urn:li:image:...)

    # LLM tracking & observability
    llm_used: str  # "gemini-3.5-flash" or "ollama-gemma3:4b"
    llm_attempt: int  # 1=primary, 2+=fallback attempts
    draft_tokens_used: int  # Tokens used for draft
    thought_tokens_used: int  # Tokens used for thought

    # Validation
    validation_status: str  # "passed", "failed", "pending"
    validation_errors: list[str]  # List of validation issues

    # Execution tracking
    generated_at: Optional[datetime]  # Workflow start time
    draft_generated_at: Optional[datetime]  # Draft generation time
    thought_generated_at: Optional[datetime]  # Thought generation time
    image_rendered_at: Optional[datetime]  # Image rendering time

    # Legacy fields for compatibility
    feedback: Optional[str]  # Human feedback (if needed)
