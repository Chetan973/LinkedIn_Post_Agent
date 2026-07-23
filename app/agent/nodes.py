import asyncio
import logging
from langchain_core.messages import HumanMessage, AIMessage
from app.agent.state import AgentState
from app.core.config import settings
from app.Services.llm_fallback import FallbackLLM
from app.Services.image_generation import generate_post_image
from app.core.instrumentation import create_context_logger, get_correlation_id

logger = logging.getLogger(__name__)
tracer = create_context_logger(__name__)

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
- 2-3 well-crafted paragraphs
- Lead with the core technical insight
- Include specific technical details (not generic)
- Reference relevant systems, patterns, or technologies
- End with a thought-provoking question or call-to-action
- Use relevant hashtags (#backend #engineering #systems etc.)
- Professional, authoritative, yet approachable tone

Focus on:
- Technical depth over breadth
- Real-world applicability
- Advanced audience (not entry-level)
- Original perspectives and insights
- Problem-solving and innovation"""


async def draft_post(state: AgentState) -> dict:
    """Draft a highly technical LinkedIn post based on the given topic.

    Produces original, deep technical content with technical motive thoughts
    suited for advanced backend engineering audiences.
    Enforces max concurrent LLM calls to prevent rate limit exhaustion.
    Uses Gemini 3.5 Flash with automatic Ollama fallback.
    """
    async with llm_semaphore:
        llm = FallbackLLM(temperature=0.7)

        user_message = f"""Write a HIGHLY TECHNICAL LinkedIn post about the following topic.
Focus on TECHNICAL MOTIVE THOUGHTS and deep engineering insights.

Topic: {state['topic']}

Requirements:
- Write for an ADVANCED backend engineering audience
- Include specific technical details and engineering principles
- Share lessons learned or insights from real-world systems
- Use precise technical terminology
- 2-3 well-crafted paragraphs
- Include hashtags and a call-to-action
- Professional, authoritative tone

Make this a standout technical post that demonstrates deep expertise and original thinking."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await llm.ainvoke(messages)
            # Ensure draft_text is a string, not a dict or complex object
            draft_text = response.content if isinstance(response.content, str) else str(response.content)
            logger.info(f"Draft post created successfully for topic: {state['topic'][:50]}")
        except Exception as e:
            logger.error(f"Error drafting post for topic {state['topic']}: {str(e)}")
            raise

        return {
            "draft_content": draft_text,
            "messages": [
                HumanMessage(content=user_message),
                AIMessage(content=draft_text),
            ],
        }


async def revise_post(state: AgentState) -> dict:
    """Revise the draft post based on user feedback.

    Applies human feedback while maintaining technical depth and professional quality.
    Enforces max concurrent LLM calls to prevent rate limit exhaustion.
    Uses Gemini 3.5 Flash with automatic Ollama fallback.
    """
    async with llm_semaphore:
        llm = FallbackLLM(temperature=0.7)

        revision_prompt = f"""Please revise the following LinkedIn post based on the feedback provided.
Maintain the highly technical nature and technical motive thoughts.

Original Post:
{state['draft_content']}

User Feedback:
{state['feedback']}

Revise the post to address the feedback while:
- Preserving technical depth and accuracy
- Maintaining the advanced audience focus
- Keeping the professional, authoritative tone
- Ensuring the post remains engaging and actionable"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": revision_prompt},
        ]

        try:
            response = await llm.ainvoke(messages)
            # Ensure revised_text is a string, not a dict or complex object
            revised_text = response.content if isinstance(response.content, str) else str(response.content)
            logger.info("Post revision completed successfully")
        except Exception as e:
            logger.error(f"Error revising post: {str(e)}")
            raise

        return {
            "draft_content": revised_text,
            "messages": [
                HumanMessage(content=revision_prompt),
                AIMessage(content=revised_text),
            ],
        }


async def generate_image(state: AgentState) -> dict:
    """Generate an AI image using DALL-E 3 based on the post topic.

    Creates a professional image relevant to the post topic using OpenAI's
    DALL-E 3 model. Falls back gracefully if image generation is disabled
    or fails (so text-only posts can still be published).
    """
    cid = get_correlation_id()
    post_id = state.get("post_id", "unknown")

    tracer.info(
        f"[{cid}] ENTER generate_image node",
        extra={"post_id": post_id}
    )

    topic = state.get("topic", "")

    try:
        tracer.info(
            f"[{cid}] Calling generate_post_image()",
            extra={"topic": topic[:50]}
        )

        image_url = await generate_post_image(topic)

        tracer.info(
            f"[{cid}] Image URL returned from generate_post_image()",
            extra={
                "image_url": image_url[:100] if image_url else None,
                "is_none": image_url is None,
                "is_empty": image_url == ""
            }
        )

        if not image_url:
            tracer.warning(f"[{cid}] generate_post_image() returned empty/None")
            return {
                "image_url": None,
                "messages": [
                    HumanMessage(content=f"Generate image for: {topic}"),
                    AIMessage(content="Image URL was None/empty"),
                ],
            }

        tracer.info(
            f"[{cid}] EXIT generate_image - image URL acquired",
            extra={"image_url_length": len(image_url)}
        )

        return {
            "image_url": image_url,
            "messages": [
                HumanMessage(content=f"Generate image for: {topic}"),
                AIMessage(content=f"Image generated: {image_url}"),
            ],
        }

    except ValueError as e:
        # OpenAI API key not configured - skip image generation
        tracer.warning(
            f"[{cid}] ValueError in image generation (API not configured)",
            exc_info=True
        )
        return {
            "image_url": None,
            "messages": [
                HumanMessage(content=f"Generate image for: {topic}"),
                AIMessage(content="Image generation skipped (API not configured)"),
            ],
        }

    except Exception as e:
        # Image generation failed - log but don't fail the workflow
        tracer.error(
            f"[{cid}] Exception in image generation - proceeding without image",
            exc_info=True
        )
        return {
            "image_url": None,
            "messages": [
                HumanMessage(content=f"Generate image for: {topic}"),
                AIMessage(content=f"Image generation failed: {str(e)}"),
            ],
        }