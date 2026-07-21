import logging
from typing import Annotated
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.Services.linkedin import publish_to_linkedin, LinkedInRateLimitError
from app.api.schemas import PostGenerateRequest, PostResponse
from app.api.dependencies import get_db
from app.agent.graph import get_agent_graph
from app.agent.state import AgentState
from app.db import Post, PostStatus, get_session_maker
from app.db.database import _get_libpq_url
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])


async def run_agent(post_id: int, topic: str):
    """Background task to run the LinkedIn post agent in fully automated mode.

    Complete lifecycle: Generate content → Publish to LinkedIn → Update status.
    All steps execute without human intervention. Errors immediately mark post as FAILED.
    """
    session_maker = get_session_maker()
    draft_content = ""

    try:
        logger.info(f"[POST {post_id}] Starting fully automated agent for topic: {topic[:50]}")

        # Get checkpointer via context manager for this task
        libpq_url = _get_libpq_url()
        async with AsyncPostgresSaver.from_conn_string(libpq_url) as checkpointer:
            # Initial state for the agent
            initial_state = AgentState(
                messages=[],
                post_id=post_id,
                topic=topic,
                draft_content="",
                feedback="",
                status="",
            )

            # Configure with thread_id as post_id for checkpointing
            config = {"configurable": {"thread_id": str(post_id)}}

            # Get the compiled graph with the checkpointer
            graph = get_agent_graph(checkpointer=checkpointer)

            # Run the agent end-to-end automatically
            result = await graph.ainvoke(initial_state, config=config)
            draft_content = result.get("draft_content", "")

        # Checkpointer context closes here - all remaining work is DB operations
        if not draft_content:
            logger.error(f"[POST {post_id}] Agent produced no draft content")
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.FAILED.value
                    db_post.error_reason = "Content generation failed: no draft content produced"
                    await db.commit()
            return

        # Step 1: Save draft content (intermediate checkpoint)
        async with session_maker() as db:
            stmt = select(Post).where(Post.post_id == post_id)
            db_post = (await db.execute(stmt)).scalars().first()
            if db_post:
                db_post.draft_content = draft_content
                await db.commit()
                logger.info(f"[POST {post_id}] Draft content saved")

        # Step 2: Publish to LinkedIn automatically (no approval needed)
        try:
            result = await publish_to_linkedin(draft_content)
            linkedin_post_id = result.get("linkedin_post_id")
            logger.info(f"[POST {post_id}] Successfully published to LinkedIn: {linkedin_post_id}")

            # Step 3: Mark as PUBLISHED
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.PUBLISHED.value
                    db_post.final_content = draft_content
                    db_post.linkedin_post_id = linkedin_post_id
                    db_post.published_at = datetime.now(timezone.utc)
                    db_post.error_reason = None
                    await db.commit()
                    logger.info(f"[POST {post_id}] Status updated to PUBLISHED")

        except LinkedInRateLimitError as e:
            logger.error(f"[POST {post_id}] LinkedIn rate limit exceeded: {str(e)}")
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.FAILED.value
                    db_post.error_reason = f"LinkedIn rate limit: {str(e)}"
                    await db.commit()

        except Exception as pub_error:
            logger.error(f"[POST {post_id}] Publishing failed: {str(pub_error)}")
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.FAILED.value
                    db_post.error_reason = f"Publishing error: {str(pub_error)}"
                    await db.commit()

    except Exception as e:
        logger.error(f"[POST {post_id}] Agent execution failed: {str(e)}", exc_info=True)
        try:
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.FAILED.value
                    db_post.error_reason = str(e)
                    await db.commit()
                    logger.info(f"[POST {post_id}] Status updated to FAILED")
        except Exception as db_error:
            logger.error(f"[POST {post_id}] Failed to update error status: {str(db_error)}")




@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_post(
    request: PostGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a new LinkedIn post draft.

    Creates a Post record in the database and asynchronously runs the LangGraph
    agent to generate the initial draft. Returns immediately with 202 Accepted.

    Idempotency: If an idempotency_key is provided and a post with that key
    already exists, returns the existing post without creating a duplicate.
    """
    # Check for idempotency if key is provided
    if request.idempotency_key:
        stmt = select(Post).where(Post.idempotency_key == request.idempotency_key)
        existing_post = (await db.execute(stmt)).scalars().first()
        if existing_post:
            logger.info(f"Duplicate post request detected. Returning existing post {existing_post.post_id}")
            return {
                "post_id": existing_post.post_id,
                "status": existing_post.status,
                "message": "Post already queued or processing",
            }

    # Create new Post record with QUEUED status
    post = Post(
        topic=request.topic,
        draft_content="",
        status=PostStatus.QUEUED.value,
        user_id=1,  # TODO: Get from authenticated user
        idempotency_key=request.idempotency_key,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    logger.info(f"[POST {post.post_id}] Created for topic: {request.topic[:50]}")

    # Schedule background task to run fully automated agent
    background_tasks.add_task(run_agent, post.post_id, request.topic)

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
    )
