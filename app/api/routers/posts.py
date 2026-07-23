import logging
import httpx
import time
from typing import Annotated
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.instrumentation import (
    create_context_logger,
    set_correlation_id,
    get_correlation_id,
    log_http_request,
    log_http_response,
)

from app.Services.linkedin import publish_to_linkedin, LinkedInRateLimitError
from app.Services.linkedin_media import upload_image_to_linkedin
from app.api.schemas import PostGenerateRequest, PostResponse
from app.api.dependencies import get_db
from app.api.auth import get_current_user
from app.agent.graph import get_agent_graph
from app.agent.state import AgentState
from app.db import Post, PostStatus, User, get_session_maker
from app.db.database import _get_libpq_url
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)
tracer = create_context_logger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])

# LinkedIn API limits
LINKEDIN_MAX_COMMENTARY_LENGTH = 4000


def truncate_for_linkedin(text: str, max_length: int = LINKEDIN_MAX_COMMENTARY_LENGTH) -> str:
    """Truncate text to LinkedIn's maximum commentary length (4000 chars).

    Attempts to break at sentence boundary if possible. If text contains hashtags
    at the end, preserves them if they fit within the limit.
    """
    if len(text) <= max_length:
        return text

    # Try to break at last newline within limit
    truncated = text[:max_length]
    last_newline = truncated.rfind('\n')
    if last_newline > max_length * 0.8:  # Only use if it's not too far back
        return truncated[:last_newline].rstrip()

    # Try to break at last period within limit
    last_period = truncated.rfind('.')
    if last_period > max_length * 0.8:
        return truncated[:last_period + 1].rstrip()

    # Default: truncate and add ellipsis
    return truncated[:max_length - 3].rstrip() + "..."


async def run_agent(post_id: int):
    """Background task to run the LinkedIn post agent in fully automated mode.

    Complete lifecycle:
    1. Select topic (autonomous, deduplicated)
    2. Draft content (3000-3500 chars)
    3. Generate thought (20-35 words for image)
    4. Validate content
    5. Render image
    6. Publish to LinkedIn
    7. Update status

    All steps execute without human intervention. Topic selection happens
    inside the agent. Errors immediately mark post as FAILED.
    """
    cid = f"POST-{post_id}"
    set_correlation_id(cid)

    tracer.info(
        f"[{cid}] ENTER run_agent (BACKGROUND TASK)",
        extra={"post_id": post_id}
    )

    session_maker = get_session_maker()
    draft_content = ""
    topic = "[pending selection]"

    try:
        tracer.info(f"[{cid}] Starting fully autonomous agent workflow")

        # Get checkpointer via context manager for this task
        libpq_url = _get_libpq_url()
        async with AsyncPostgresSaver.from_conn_string(libpq_url) as checkpointer:
            # Initial state for the agent (topic will be selected by first node)
            initial_state = AgentState(
                messages=[],
                post_id=post_id,
                topic="",  # Will be selected by topic_selection_node
                selected_category="",
                draft_content="",
                ai_thought=None,
                char_count=0,
                llm_used="",
                llm_attempt=0,
                draft_tokens_used=0,
                thought_tokens_used=0,
                validation_status="pending",
                validation_errors=[],
                image_bytes=None,
                image_url=None,
                image_rendered_at=False,
                asset_urn=None,
            )

            # Configure with thread_id as post_id for checkpointing
            config = {"configurable": {"thread_id": str(post_id)}}

            # Get the compiled graph with the checkpointer
            tracer.info(f"[{cid}] Getting compiled graph...")
            graph = get_agent_graph(checkpointer=checkpointer)
            tracer.info(f"[{cid}] Graph obtained, invoking ainvoke()...")

            # Run the agent end-to-end automatically (draft content + image generation)
            tracer.info(f"[{cid}] Calling graph.ainvoke()...")
            invoke_start = time.time()
            result = await graph.ainvoke(initial_state, config=config)
            invoke_elapsed = int((time.time() - invoke_start) * 1000)

            tracer.info(
                f"[{cid}] graph.ainvoke() returned",
                extra={
                    "result_keys": list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                    "elapsed_ms": invoke_elapsed
                }
            )

            draft_content = result.get("draft_content", "")
            image_url = result.get("image_url")

            tracer.info(
                f"[{cid}] Extracted values from graph result",
                extra={
                    "image_url": image_url,
                    "image_url_type": type(image_url).__name__ if image_url else None,
                    "draft_content_length": len(draft_content) if draft_content else 0
                }
            )

        # Checkpointer context closes here - all remaining work is DB operations
        tracer.info(f"[{cid}] Checkpointer context closed")

        # Extract all results from workflow
        topic = result.get("topic", "")
        draft_content = result.get("draft_content", "")
        thought = result.get("ai_thought")
        char_count = result.get("char_count", 0)
        llm_used = result.get("llm_used", "")
        llm_attempt = result.get("llm_attempt", 0)
        selected_category = result.get("selected_category", "")
        validation_status = result.get("validation_status", "pending")
        image_bytes = result.get("image_bytes")

        tracer.info(
            f"[{cid}] All values extracted from result",
            extra={
                "topic": topic[:30],
                "has_image_url": bool(image_url),
                "has_draft": bool(draft_content),
                "has_image_bytes": bool(image_bytes)
            }
        )

        # Ensure ai_thought is a string (prevent object stringification)
        if thought is not None and not isinstance(thought, str):
            logger.warning(
                f"ai_thought is {type(thought)}, converting to string. "
                f"First 100 chars: {str(thought)[:100]}"
            )
            thought = str(thought)

        # Ensure draft_content is a string
        if draft_content and not isinstance(draft_content, str):
            logger.warning(f"draft_content is {type(draft_content)}, converting to string")
            draft_content = str(draft_content)

        if not draft_content:
            logger.error(f"[POST {post_id}] Agent produced no draft content")
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.topic = topic  # Save selected topic
                    db_post.status = PostStatus.FAILED.value
                    db_post.error_reason = "Content generation failed: no draft content produced"
                    await db.commit()
            return

        # Step 1: Save workflow results (intermediate checkpoint)
        async with session_maker() as db:
            stmt = select(Post).where(Post.post_id == post_id)
            db_post = (await db.execute(stmt)).scalars().first()
            if db_post:
                db_post.topic = topic  # Update with selected topic
                db_post.draft_content = draft_content
                db_post.ai_thought = thought
                db_post.category = selected_category
                db_post.char_count = char_count
                db_post.llm_used = llm_used
                db_post.llm_fallback_used = (llm_attempt == 2)
                await db.commit()
                logger.info(
                    f"[POST {post_id}] Workflow results saved: "
                    f"topic='{topic}', category={selected_category}, "
                    f"llm={llm_used}, chars={char_count}"
                )

        # Step 2: Validate and truncate content for LinkedIn
        if len(draft_content) > LINKEDIN_MAX_COMMENTARY_LENGTH:
            logger.warning(
                f"[POST {post_id}] Content length {len(draft_content)} exceeds "
                f"LinkedIn limit of {LINKEDIN_MAX_COMMENTARY_LENGTH}. Will truncate."
            )

        # Step 3: Publish to LinkedIn with optional image (no approval needed)
        tracer.info(f"[{cid}] STEP 3: Publishing to LinkedIn...")
        try:
            linkedin_post_id = None

            # If image was generated, upload it to LinkedIn and create image post
            if image_url:
                tracer.info(f"[{cid}] Image URL received, starting image post flow")
                tracer.info(
                    f"[{cid}] Image path preview: {image_url}",
                    extra={"image_url_length": len(image_url)}
                )

                try:
                    tracer.info(f"[{cid}] Calling upload_image_to_linkedin()...")
                    # 1. Upload image to LinkedIn Images API
                    upload_start = time.time()
                    _, image_urn = await upload_image_to_linkedin(
                        image_url=image_url,
                        post_text=draft_content,
                        access_token=settings.LINKEDIN_ACCESS_TOKEN,
                        person_urn=settings.LINKEDIN_PERSON_URN,
                    )
                    upload_elapsed = int((time.time() - upload_start) * 1000)
                    tracer.info(
                        f"[{cid}] upload_image_to_linkedin() returned",
                        extra={
                            "image_urn": image_urn,
                            "elapsed_ms": upload_elapsed,
                            "urn_is_none": image_urn is None
                        }
                    )

                    if not image_urn:
                        tracer.error(f"[{cid}] Image upload returned empty URN")
                        raise Exception("Image upload failed: no URN returned")

                    tracer.info(
                        f"[{cid}] Image URN acquired",
                        extra={"image_urn": image_urn}
                    )

                    # 2. Publish post using modern REST API schema
                    tracer.info(f"[{cid}] Creating httpx client for image post...")
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        tracer.info(f"[{cid}] httpx client created")

                        headers = {
                            "Authorization": f"Bearer {settings.LINKEDIN_ACCESS_TOKEN}",
                            "Content-Type": "application/json",
                            "X-Restli-Protocol-Version": "2.0.0",
                            "LinkedIn-Version": "202606"
                        }

                        owner_urn = settings.LINKEDIN_PERSON_URN
                        if not owner_urn.startswith("urn:li:person:"):
                            owner_urn = f"urn:li:person:{owner_urn}"

                        # Truncate content to LinkedIn's 4000 char limit
                        linkedin_text = truncate_for_linkedin(draft_content)

                        # LinkedIn REST API payload for image posts
                        # IMPORTANT: content.media MUST be a dictionary, not an array
                        post_payload = {
                            "author": owner_urn,
                            "commentary": linkedin_text,
                            "visibility": "PUBLIC",
                            "distribution": {
                                "feedDistribution": "MAIN_FEED",
                                "targetEntities": [],
                                "thirdPartyDistributionChannels": []
                            },
                            "lifecycleState": "PUBLISHED",
                            "content": {
                                "media": {
                                    "id": image_urn
                                }
                            }
                        }

                        tracer.info(
                            f"[{cid}] Image post payload built",
                            extra={
                                "payload_keys": list(post_payload.keys()),
                                "has_content": "content" in post_payload,
                                "image_urn_in_payload": image_urn
                            }
                        )

                        tracer.info(f"[{cid}] Posting to LinkedIn /rest/posts endpoint...")
                        log_http_request(
                            method="POST",
                            url="https://api.linkedin.com/rest/posts",
                            headers=headers,
                            payload=post_payload
                        )

                        # DEBUG: Print payload before POST
                        print("=" * 80)
                        print("CREATING LINKEDIN POST")
                        print(post_payload)
                        print("=" * 80)

                        post_start = time.time()
                        response = await client.post(
                            "https://api.linkedin.com/rest/posts",
                            headers=headers,
                            json=post_payload,
                            timeout=30.0
                        )
                        post_elapsed = int((time.time() - post_start) * 1000)

                        # DEBUG: Print response after POST
                        print("=" * 80)
                        print("LINKEDIN POST RESPONSE")
                        print(f"Status: {response.status_code}")
                        print(f"Text: {response.text}")
                        print("=" * 80)

                        tracer.info(
                            f"[{cid}] Response received",
                            extra={
                                "status_code": response.status_code,
                                "elapsed_ms": post_elapsed,
                                "headers": dict(response.headers)
                            }
                        )

                        log_http_response(
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            body=response.text,
                            elapsed_ms=post_elapsed
                        )

                        if response.status_code in [200, 201]:
                            linkedin_post_id = response.headers.get("x-restli-id", "unknown")
                            tracer.info(
                                f"[{cid}] Image post published SUCCESSFULLY",
                                extra={
                                    "linkedin_post_id": linkedin_post_id,
                                    "status": response.status_code
                                }
                            )
                        else:
                            tracer.error(
                                f"[{cid}] Failed to publish image post",
                                extra={
                                    "status": response.status_code,
                                    "response_body": response.text[:500]
                                }
                            )
                            raise Exception(f"Failed to publish image post: {response.status_code} - {response.text}")

                except Exception as img_error:
                    tracer.error(
                        f"[{cid}] Image upload/publishing FAILED",
                        exc_info=True,
                        extra={"error": str(img_error)}
                    )
                    tracer.warning(f"[{cid}] Falling back to text-only post due to image error")

                    # Fall back to text-only post
                    tracer.info(f"[{cid}] Attempting text-only fallback...")
                    try:
                        linkedin_text = truncate_for_linkedin(draft_content)
                        result = await publish_to_linkedin(linkedin_text)
                        linkedin_post_id = result.get("linkedin_post_id")
                        tracer.info(
                            f"[{cid}] Text-only fallback succeeded",
                            extra={"linkedin_post_id": linkedin_post_id}
                        )
                    except Exception as fallback_error:
                        tracer.error(
                            f"[{cid}] Text-only fallback also failed",
                            exc_info=True
                        )
                        raise
            else:
                # No image, publish as text-only
                tracer.info(f"[{cid}] No image URL, publishing text-only post")
                linkedin_text = truncate_for_linkedin(draft_content)
                tracer.info(f"[{cid}] Calling publish_to_linkedin() for text-only...")
                result = await publish_to_linkedin(linkedin_text)
                linkedin_post_id = result.get("linkedin_post_id")
                tracer.info(
                    f"[{cid}] Text-only post published",
                    extra={"linkedin_post_id": linkedin_post_id}
                )

            tracer.info(
                f"[{cid}] Publishing phase complete",
                extra={"linkedin_post_id": linkedin_post_id}
            )

            tracer.info(f"[{cid}] STEP 4: Updating database...")

            # Step 4: Mark as PUBLISHED and save final metadata
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    tracer.info(
                        f"[{cid}] Post record found, updating status",
                        extra={
                            "current_status": db_post.status,
                            "new_status": PostStatus.PUBLISHED.value
                        }
                    )

                    db_post.status = PostStatus.PUBLISHED.value
                    db_post.final_content = draft_content
                    db_post.image_url = image_url
                    db_post.linkedin_post_id = linkedin_post_id
                    db_post.published_at = datetime.now(timezone.utc)
                    db_post.error_reason = None

                    # Save LLM tracking if not already saved
                    if not db_post.llm_used:
                        db_post.llm_used = llm_used
                        db_post.llm_fallback_used = (llm_attempt == 2)

                    await db.commit()
                    tracer.info(
                        f"[{cid}] EXIT run_agent - status updated to PUBLISHED",
                        extra={
                            "linkedin_post_id": linkedin_post_id,
                            "image_url": image_url
                        }
                    )
                else:
                    tracer.error(f"[{cid}] Post record not found in database!")
        except LinkedInRateLimitError as e:
            tracer.error(
                f"[{cid}] LinkedIn rate limit exceeded",
                exc_info=True
            )
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.FAILED.value
                    db_post.error_reason = f"LinkedIn rate limit: {str(e)}"
                    await db.commit()
                    tracer.info(f"[{cid}] Status updated to FAILED (rate limit)")

        except Exception as pub_error:
            tracer.error(
                f"[{cid}] Publishing failed",
                exc_info=True,
                extra={"error": str(pub_error)}
            )
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.FAILED.value
                    db_post.error_reason = f"Publishing error: {str(pub_error)}"
                    await db.commit()
                    tracer.info(f"[{cid}] Status updated to FAILED (publishing error)")

    except Exception as e:
        tracer.error(
            f"[{cid}] EXCEPTION run_agent - agent execution failed",
            exc_info=True,
            extra={"error": str(e)}
        )
        try:
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.FAILED.value
                    db_post.error_reason = str(e)
                    await db.commit()
                    tracer.info(f"[{cid}] Status updated to FAILED (exception)")
        except Exception as db_error:
            tracer.error(
                f"[{cid}] Failed to update error status in database",
                exc_info=True
            )


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_post(
    request: PostGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Generate a new LinkedIn post with autonomous topic selection.

    Creates a Post record with placeholder topic (will be selected by agent).
    Returns immediately with 202 Accepted. Topic selection happens autonomously
    inside the LangGraph workflow to prevent duplicates and maintain diversity.

    This endpoint requires LinkedIn OAuth authentication via Supabase Auth.
    The frontend must pass the Supabase JWT in the Authorization header.

    Idempotency: If an idempotency_key is provided and a post with that key
    already exists, returns the existing post without creating a duplicate.

    Args:
        request: Optional idempotency key for request deduplication
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Authenticated user from Supabase JWT
    """
    # Check for idempotency if key is provided
    if request.idempotency_key:
        stmt = select(Post).where(Post.idempotency_key == request.idempotency_key)
        existing_post = (await db.execute(stmt)).scalars().first()
        if existing_post:
            logger.info(f"Duplicate request detected. Returning existing post {existing_post.post_id}")
            return {
                "post_id": existing_post.post_id,
                "status": existing_post.status,
                "message": "Post already queued or processing",
            }

    # Create new Post record with placeholder topic
    # Topic will be selected by topic_selection_node inside the agent
    post = Post(
        topic="[autonomous selection pending]",
        draft_content="",
        status=PostStatus.QUEUED.value,
        user_id=current_user.user_id,  # Use authenticated user
        idempotency_key=request.idempotency_key,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    logger.info(f"[POST {post.post_id}] Created with autonomous topic selection")

    # Schedule background task (topic selection happens inside agent)
    background_tasks.add_task(run_agent, post.post_id)

    return {
        "post_id": post.post_id,
        "status": PostStatus.QUEUED.value,
        "message": "Post queued for generation and publishing. Check status with GET /{post_id}",
    }


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the current state of a post.

    Returns the Post record with all current data including draft content and status.
    """
    stmt = select(Post).where(Post.post_id == post_id)
    db_post = (await db.execute(stmt)).scalars().first()

    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    return PostResponse(
        post_id=db_post.post_id,
        topic=db_post.topic,
        status=db_post.status,
        draft_content=db_post.draft_content,
        final_content=db_post.final_content,
        image_url=db_post.image_url,
        linkedin_post_id=db_post.linkedin_post_id,
        error_reason=db_post.error_reason,
    )