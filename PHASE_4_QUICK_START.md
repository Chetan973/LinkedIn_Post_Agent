# Phase 4 Quick Start - LangGraph Agent

## 30-Second Overview

Phase 4 implements a LangGraph agent that:
1. **Drafts** LinkedIn posts using GPT-4 (specialized backend engineer voice)
2. **Revises** posts based on user feedback
3. **Routes** based on approval status (approved/rejected/needs_revision)
4. **Persists** all state in Supabase PostgreSQL via AsyncPostgresSaver

---

## Core Components

### 1. Agent State
```python
from app.agent.state import AgentState

state = AgentState(
    messages=[],                    # Message history
    post_id=1,                      # Database reference
    topic="Building Microservices", # User input
    draft_content="",               # LLM output
    feedback="",                    # User feedback
    status="drafting",              # Workflow status
)
```

### 2. Get the Graph
```python
from app.agent.graph import get_graph

# Async context (FastAPI)
graph = await get_graph()

# Sync context (CLI/scripts)
graph = get_graph_sync()
```

### 3. Run the Agent
```python
# Single invocation
result = await graph.ainvoke(state)

# Streaming results
async for event in graph.astream(state):
    print(event)

# Continue from checkpoint (same thread_id)
config = {"configurable": {"thread_id": "session_123"}}
result = await graph.ainvoke(state, config=config)
```

---

## Example FastAPI Endpoints

### Generate Initial Draft
```python
from fastapi import FastAPI, Depends
from sqlalchemy import select
from app.agent.graph import get_graph
from app.agent.state import AgentState
from app.db import get_db_session, Post, PostStatus

app = FastAPI()

@app.post("/posts/generate")
async def generate_post(
    topic: str,
    user_id: int,
    session = Depends(get_db_session),
):
    """Generate a LinkedIn post draft."""
    
    # Create post in database
    post = Post(
        user_id=user_id,
        topic=topic,
        status=PostStatus.DRAFTING,
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)
    
    # Run agent
    graph = await get_graph()
    initial_state = AgentState(
        messages=[],
        post_id=post.post_id,
        topic=topic,
        draft_content="",
        feedback="",
        status="drafting",
    )
    
    result = await graph.ainvoke(initial_state)
    
    # Update database with draft
    stmt = (
        select(Post).where(Post.post_id == post.post_id)
    )
    db_post = (await session.execute(stmt)).scalars().first()
    db_post.draft_content = result["draft_content"]
    db_post.status = PostStatus.PENDING_REVIEW
    await session.commit()
    
    return {
        "post_id": post.post_id,
        "draft": result["draft_content"],
        "status": "drafted",
    }
```

### Submit Review
```python
@app.post("/posts/{post_id}/review")
async def review_post(
    post_id: int,
    status: str,  # "approved", "rejected", "needs_revision"
    feedback: str = "",
    session = Depends(get_db_session),
):
    """Submit review and get revision if needed."""
    
    # Load post from database
    db_post = await session.get(Post, post_id)
    
    if not db_post:
        return {"error": "Post not found"}
    
    # Handle approved posts
    if status == "approved":
        db_post.status = PostStatus.PUBLISHED
        await session.commit()
        return {
            "post_id": post_id,
            "status": "approved",
            "final_content": db_post.draft_content,
        }
    
    # Handle rejection (complete rewrite)
    if status == "rejected":
        graph = await get_graph()
        
        state = AgentState(
            messages=[],
            post_id=post_id,
            topic=db_post.topic,
            draft_content=db_post.draft_content,
            feedback="",
            status="rejected",
        )
        
        # Continue from checkpoint or start fresh
        config = {"configurable": {"thread_id": f"post_{post_id}"}}
        result = await graph.ainvoke(state, config=config)
        
        db_post.draft_content = result["draft_content"]
        await session.commit()
        
        return {
            "post_id": post_id,
            "status": "redrafted",
            "draft": result["draft_content"],
        }
    
    # Handle revision (incorporate feedback)
    if status == "needs_revision":
        graph = await get_graph()
        
        state = AgentState(
            messages=[],
            post_id=post_id,
            topic=db_post.topic,
            draft_content=db_post.draft_content,
            feedback=feedback,
            status="needs_revision",
        )
        
        config = {"configurable": {"thread_id": f"post_{post_id}"}}
        result = await graph.ainvoke(state, config=config)
        
        db_post.draft_content = result["draft_content"]
        await session.commit()
        
        return {
            "post_id": post_id,
            "status": "revised",
            "draft": result["draft_content"],
        }
```

### Get Post Status
```python
@app.get("/posts/{post_id}")
async def get_post(post_id: int, session = Depends(get_db_session)):
    """Get post and its current workflow status."""
    post = await session.get(Post, post_id)
    
    if not post:
        return {"error": "Not found"}
    
    return {
        "post_id": post.post_id,
        "topic": post.topic,
        "draft": post.draft_content,
        "status": post.status,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }
```

---

## Workflow Examples

### Happy Path: Approve on First Draft
```
1. User: "Generate post about 'REST APIs'"
2. System: Creates draft via draft_post node
3. User: Reviews draft
4. User: Submits status="approved"
5. System: Post marked published, workflow ends
```

### Revision Path: Two Feedback Rounds
```
1. User: "Generate post about 'REST APIs'"
2. System: Creates initial draft
3. User: "Needs revision: add more about performance"
4. System: Calls revise_post with feedback
5. User: "Looks good, needs small fix to title"
6. System: Calls revise_post again
7. User: "Approved!"
8. System: Post published
```

### Rejection Path: Complete Rewrite
```
1. User: "Generate post about 'REST APIs'"
2. System: Creates draft
3. User: Reviews and rejects (status="rejected")
4. System: Calls draft_post again for new draft
5. User: Reviews revised draft
6. User: "Approved!"
7. System: Post published
```

---

## Message Flow Diagram

```
┌─────────────────────────────────────────────────┐
│  FastAPI Endpoint: POST /posts/generate         │
│  Input: topic, user_id                          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │ Create Post in DB   │
         │ (status=DRAFTING)   │
         └──────────┬──────────┘
                    │
                    ▼
         ┌──────────────────────────────┐
         │ Get Graph                    │
         │ (await get_graph())          │
         └──────────┬───────────────────┘
                    │
                    ▼
         ┌──────────────────────────────┐
         │ Call draft_post Node         │
         │ (GPT-4 generates content)    │
         └──────────┬───────────────────┘
                    │
                    ▼
         ┌──────────────────────────────┐
         │ Save State to Supabase       │
         │ (AsyncPostgresSaver)         │
         └──────────┬───────────────────┘
                    │
                    ▼
         ┌──────────────────────────────┐
         │ Update Post in DB            │
         │ (draft_content, status)      │
         └──────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────────┐
    │  Return to User                       │
    │  {post_id, draft, status:"drafted"}   │
    └───────────────────────────────────────┘
```

---

## Key Methods

### get_graph()
```python
async def get_graph():
    """Create and return compiled StateGraph.
    
    Returns compiled graph with AsyncPostgresSaver for Supabase.
    Use in async FastAPI endpoints.
    """
```

### get_graph_sync()
```python
def get_graph_sync():
    """Synchronous wrapper for get_graph().
    
    Use in sync contexts or CLI scripts.
    """
```

### graph.ainvoke(state, config)
```python
# Single execution
result = await graph.ainvoke(state)

# With checkpoint/thread management
config = {"configurable": {"thread_id": "session_123"}}
result = await graph.ainvoke(state, config=config)
```

### graph.astream(state)
```python
# Stream events (for real-time UI updates)
async for event in graph.astream(state):
    if "draft_post" in event:
        print("Drafting...")
    elif "revise_post" in event:
        print("Revising...")
```

---

## Status Values

| Status | Next Node | Use Case |
|--------|-----------|----------|
| `"drafting"` | → draft_post | Initial creation |
| `"drafted"` | → User review | Ready for feedback |
| `"needs_revision"` | → revise_post | Apply feedback |
| `"revised"` | → User review | After revision |
| `"rejected"` | → draft_post | Complete rewrite |
| `"approved"` | → END | Workflow complete |

---

## Debugging Tips

### View Checkpointed State
```python
# The graph saves state to Supabase
# To debug: query checkpoint tables
from app.db.database import get_engine
from sqlalchemy import text

async def debug_checkpoints():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM checkpoint LIMIT 5")
        )
        print(result.fetchall())
```

### Trace Agent Decisions
```python
# Enable LangChain debugging
import langchain
langchain.debug = True

# Run agent
result = await graph.ainvoke(state)

# Trace will print all LLM calls and routing decisions
```

### Inspect State
```python
# After invocation
print(f"Status: {result['status']}")
print(f"Draft: {result['draft_content'][:100]}...")
print(f"Messages: {len(result['messages'])}")
```

---

## Common Patterns

### Streaming Responses
```python
@app.post("/posts/generate-stream")
async def generate_post_stream(topic: str):
    """Stream draft generation in real-time."""
    graph = await get_graph()
    state = AgentState(
        messages=[],
        post_id=0,
        topic=topic,
        draft_content="",
        feedback="",
        status="drafting",
    )
    
    async def event_generator():
        async for event in graph.astream(state):
            # Yield events to client for live updates
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Batch Processing
```python
async def generate_multiple_posts(topics: list[str], user_id: int):
    """Generate drafts for multiple topics."""
    graph = await get_graph()
    results = []
    
    for topic in topics:
        state = AgentState(
            messages=[],
            post_id=0,
            topic=topic,
            draft_content="",
            feedback="",
            status="drafting",
        )
        
        result = await graph.ainvoke(state)
        results.append(result)
    
    return results
```

---

## Next Steps

1. **Update FastAPI** - Add endpoints from above examples
2. **Test Workflow** - Generate draft → review → approve
3. **Add Monitoring** - Track agent performance
4. **Optimize Prompts** - Refine LLM instructions

---

## Reference Files

- `app/agent/state.py` - State definition
- `app/agent/nodes.py` - draft_post, revise_post
- `app/agent/edges.py` - route_post_state
- `app/agent/graph.py` - Graph compilation
- `PHASE_4_LANGGRAPH_AGENT.md` - Full documentation

