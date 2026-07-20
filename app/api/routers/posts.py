from typing import Annotated
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.api.schemas import PostGenerateRequest, PostReviewRequest, PostResponse
from app.api.dependencies import get_db, get_checkpointer
from app.agent.graph import get_agent_graph
from app.agent.state import AgentState
from app.db import Post, PostStatus

router = APIRouter(prefix="/posts", tags=["posts"])


async def run_agent(post_id: int, topic: str, checkpointer: AsyncPostgresSaver, db: AsyncSession):
    """Background task to run the agent and generate initial draft.

    Executes the LangGraph agent starting from draft_post node,
    updates the Post record with the generated draft content.
    """
    try:
        # Get the compiled graph
        graph = get_agent_graph(checkpointer=checkpointer)

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

        # Run the agent
        result = await graph.ainvoke(initial_state, config=config)

        # Update the Post record with the draft
        stmt = select(Post).where(Post.post_id == post_id)
        db_post = (await db.execute(stmt)).scalars().first()

        if db_post:
            db_post.draft_content = result.get("draft_content", "")
            db_post.status = PostStatus.PENDING_REVIEW
            await db.commit()

    except Exception as e:
        # Log error and mark post as failed
        print(f"Error running agent for post {post_id}: {str(e)}")
        stmt = select(Post).where(Post.post_id == post_id)
        db_post = (await db.execute(stmt)).scalars().first()
        if db_post:
            db_post.status = "error"
            await db.commit()


async def resume_agent(post_id: int, feedback: str, status: str, checkpointer: AsyncPostgresSaver, db: AsyncSession):
    """Background task to resume the agent with user feedback.

    Continues the LangGraph agent execution from where it paused,
    applies user feedback and updates the Post record.
    """
    try:
        # Get the compiled graph
        graph = get_agent_graph(checkpointer=checkpointer)

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

        # Resume the agent
        result = await graph.ainvoke(agent_state, config=config)

        # Update the Post record
        stmt = select(Post).where(Post.post_id == post_id)
        db_post = (await db.execute(stmt)).scalars().first()

        if db_post:
            db_post.draft_content = result.get("draft_content", db_post.draft_content)
            db_post.status = result.get("status", status)
            await db.commit()

    except Exception as e:
        # Log error
        print(f"Error resuming agent for post {post_id}: {str(e)}")


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_post(
    request: PostGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    checkpointer: Annotated[AsyncPostgresSaver, Depends(get_checkpointer)],
):
    """Generate a new LinkedIn post draft.

    Creates a Post record in the database and asynchronously runs the LangGraph
    agent to generate the initial draft. Returns immediately with 202 Accepted.
    """
    # Create new Post record
    post = Post(
        topic=request.topic,
        draft_content="",
        status=PostStatus.DRAFTING,
        user_id=1,  # TODO: Get from authenticated user
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    # Add background task to run agent
    background_tasks.add_task(run_agent, post.post_id, request.topic, checkpointer, db)

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
    checkpointer: Annotated[AsyncPostgresSaver, Depends(get_checkpointer)],
):
    """Submit review feedback for a post.

    Updates the Post record with feedback and asynchronously resumes the agent
    to incorporate the feedback. Returns 202 Accepted.
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
    background_tasks.add_task(resume_agent, post_id, request.feedback, request.status, checkpointer, db)

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
