import logging
from typing import Annotated
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.Services.linkedin import publish_to_linkedin, LinkedInRateLimitError
from app.api.schemas import PostGenerateRequest, PostReviewRequest, PostResponse
from app.api.dependencies import get_db
from app.agent.graph import get_agent_graph
from app.agent.state import AgentState
from app.db import Post, PostStatus, get_session_maker
from app.db.database import _get_libpq_url
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])


async def run_agent(post_id: int, topic: str):
    """Background task to run the LinkedIn post agent fully automated.

    Executes the LangGraph agent, generates the post content, automatically
    publishes it to your LinkedIn profile, and updates the database status.
    Separates concerns: save draft → publish → update status.
    """
    session_maker = get_session_maker()
    draft_content = ""

    try:
        logger.info(f"Starting agent for post {post_id} with topic: {topic[:50]}")

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
                status="drafting",
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
            logger.error(f"Agent produced no draft content for post {post_id}")
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = PostStatus.DRAFTING.value
                    db_post.error_reason = "Agent failed to generate content"
                    await db.commit()
            return

        # Step 1: Save draft content FIRST (separate transaction)
        async with session_maker() as db:
            stmt = select(Post).where(Post.post_id == post_id)
            db_post = (await db.execute(stmt)).scalars().first()
            if db_post:
                db_post.draft_content = draft_content
                await db.commit()
                logger.info(f"Draft content saved for post {post_id}")

        # Step 2: Publish to LinkedIn independently
        try:
            result = await publish_to_linkedin(draft_content)
            linkedin_post_id = result.get("linkedin_post_id")
            logger.info(f"Post {post_id} successfully published to LinkedIn with ID {linkedin_post_id}")

            # Step 3: Update DB with LinkedIn post ID and success status
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
                    logger.info(f"Post {post_id} marked as published in DB")

        except LinkedInRateLimitError as e:
            logger.warning(f"Rate limit error for post {post_id}: {str(e)}")
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = "retry_scheduled"
                    db_post.error_reason = f"Rate limited: {str(e)}"
                    await db.commit()

        except Exception as pub_error:
            logger.error(f"Failed to publish post {post_id} to LinkedIn: {str(pub_error)}")
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = "failed_publish"
                    db_post.error_reason = str(pub_error)
                    await db.commit()

    except Exception as e:
        logger.error(f"Error running agent for post {post_id}: {str(e)}", exc_info=True)
        try:
            async with session_maker() as db:
                stmt = select(Post).where(Post.post_id == post_id)
                db_post = (await db.execute(stmt)).scalars().first()
                if db_post:
                    db_post.status = "failed_draft"
                    db_post.error_reason = str(e)
                    await db.commit()
        except Exception as db_error:
            logger.error(f"Error updating error status for post {post_id}: {str(db_error)}")


async def resume_agent(post_id: int, feedback: str, status: str):
    """Background task to resume the agent with user feedback.

    Continues the LangGraph agent execution from where it paused,
    applies user feedback and updates the Post record.
    """
    session_maker = get_session_maker()

    try:
        logger.info(f"Resuming agent for post {post_id} with status: {status}")

        # Get checkpointer via context manager for this task
        libpq_url = _get_libpq_url()
        async with AsyncPostgresSaver.from_conn_string(libpq_url) as checkpointer:
            # State with user feedback
            agent_state = AgentState(
                messages=[],
                post_id=post_id,
                topic="",
                draft_content="",
                feedback=feedback,
                status=status,
            )

            # Configure with thread_id as post_id for checkpointing
            config = {"configurable": {"thread_id": str(post_id)}}

            # Get the compiled graph with the checkpointer
            graph = get_agent_graph(checkpointer=checkpointer)

            # Resume the agent execution
            result = await graph.ainvoke(agent_state, config=config)
            draft_content = result.get("draft_content", "")

        # Update the Post record
        async with session_maker() as db:
            stmt = select(Post).where(Post.post_id == post_id)
            db_post = (await db.execute(stmt)).scalars().first()

            if db_post and draft_content:
                db_post.draft_content = draft_content
                db_post.status = result.get("status", status)
                await db.commit()
                logger.info(f"Post {post_id} resumed and updated")

    except Exception as e:
        logger.error(f"Error resuming agent for post {post_id}: {str(e)}", exc_info=True)


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

    # Create new Post record
    post = Post(
        topic=request.topic,
        draft_content="",
        status=PostStatus.DRAFTING,
        user_id=1,  # TODO: Get from authenticated user
        idempotency_key=request.idempotency_key,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    logger.info(f"Created post {post.post_id} for topic: {request.topic[:50]}")

    # Add background task to run agent
    background_tasks.add_task(run_agent, post.post_id, request.topic)

    return {
        "post_id": post.post_id,
        "status": "queued",
        "message": "Post generation started. Check back later for results.",
    }


@router.post("/{post_id}/review", status_code=status.HTTP_202_ACCEPTED)
async def review_post(
    post_id: int,
    request: PostReviewRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit review feedback for a post.

    Updates the Post record with feedback and asynchronously resumes the agent
    to incorporate the feedback. Returns 202 Accepted.
    Background task creates its own database and checkpointer instances.
    """
    # Get the post
    stmt = select(Post).where(Post.post_id == post_id)
    db_post = (await db.execute(stmt)).scalars().first()

    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Update feedback in database
    db_post.status = request.status
    await db.commit()

    # Add background task to resume agent
    # Task will create its own database session and checkpointer
    background_tasks.add_task(resume_agent, post_id, request.feedback, request.status)

    return {
        "post_id": post_id,
        "status": "processing",
        "message": "Review submitted. Processing feedback...",
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
        status=db_post.status.value if isinstance(db_post.status, PostStatus) else db_post.status,
        draft_content=db_post.draft_content,
    )
