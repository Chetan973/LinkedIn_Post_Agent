# Phase 3 - Quick Reference Guide

## File Locations & Imports

### Configuration
```python
from app.core.config import settings
# Provides: DATABASE_URL, LANGCHAIN_API_KEY, PROJECT_NAME, etc.
```

### Database Engine & Sessions
```python
from app.db import get_engine, get_async_session_maker, get_db_session
# get_engine(): AsyncEngine - lazy-loaded on first call
# get_async_session_maker(): async_sessionmaker - creates new factory
# get_db_session(): AsyncGenerator - FastAPI dependency injection
```

### Models
```python
from app.db import User, Post, PostStatus, Base
# User: Database model for LinkedIn users
# Post: Database model for content posts
# PostStatus: Enum with DRAFTING, PENDING_REVIEW, PUBLISHED
# Base: SQLAlchemy DeclarativeBase
```

### Agent State
```python
from app.agent.state import AgentState
# TypedDict for LangGraph workflow state
# Fields: messages, post_id, topic, feedback, status
```

---

## Common Operations

### 1. Create a Session
```python
async def my_endpoint():
    async with get_db_session() as session:
        # Do database work
        pass
```

### 2. Create User
```python
from app.db import User, get_db_session

user = User(
    email="user@example.com",
    linkedin_profile_url="https://linkedin.com/in/user"
)
async with get_db_session() as session:
    session.add(user)
    await session.commit()
```

### 3. Create Post
```python
from app.db import Post, PostStatus, get_db_session

post = Post(
    user_id=1,
    topic="My Topic",
    status=PostStatus.DRAFTING
)
async with get_db_session() as session:
    session.add(post)
    await session.commit()
```

### 4. Query User
```python
from sqlalchemy import select
from app.db import User, get_db_session

async with get_db_session() as session:
    result = await session.execute(
        select(User).where(User.email == "user@example.com")
    )
    user = result.scalar_one_or_none()
```

### 5. Query Post
```python
from sqlalchemy import select
from app.db import Post, get_db_session

async with get_db_session() as session:
    post = await session.get(Post, post_id)
```

### 6. Update Post
```python
async with get_db_session() as session:
    post = await session.get(Post, post_id)
    post.draft_content = "New content"
    post.status = PostStatus.PENDING_REVIEW
    await session.commit()
```

### 7. Use in FastAPI Route
```python
from fastapi import FastAPI, Depends
from app.db import get_db_session, Post

app = FastAPI()

@app.get("/posts/{post_id}")
async def get_post(post_id: int, session = Depends(get_db_session)):
    post = await session.get(Post, post_id)
    return {"id": post.id, "topic": post.topic, "status": post.status}
```

---

## Database Migrations

### Check Migration Status
```bash
.venv\Scripts\activate
alembic current
```

### Apply Migrations
```bash
alembic upgrade head
```

### Rollback Last Migration
```bash
alembic downgrade -1
```

### Create New Migration (after model changes)
```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### View Migration History
```bash
alembic history --verbose
```

---

## LangGraph State Usage

### Initialize State
```python
from app.agent.state import AgentState
from langchain_core.messages import HumanMessage

state: AgentState = {
    "messages": [HumanMessage(content="Draft a post about Python")],
    "post_id": 1,
    "topic": "Python Best Practices",
    "feedback": "",
    "status": "drafting"
}
```

### Update Messages (auto-merges)
```python
from langchain_core.messages import AIMessage

# Messages automatically merged using add_messages
state["messages"].append(AIMessage(content="Generated content"))
# Result: list contains both messages
```

### Access State in Node
```python
def my_node(state: AgentState):
    topic = state["topic"]
    post_id = state["post_id"]
    # Do work
    state["feedback"] = "User feedback"
    return state
```

---

## Environment Variables

### Required in .env
```
DATABASE_URL=postgresql+psycopg://postgres:Postgre$ql134@localhost:5432/linkedin_agent
LANGCHAIN_API_KEY=lsv2_pt_...
```

### Optional
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=linkedin-content-agent
OPENAI_API_KEY=sk-...
```

---

## Error Handling

### Connection Error
```python
from sqlalchemy.exc import SQLAlchemyError

try:
    async with get_db_session() as session:
        # database work
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    # Handle gracefully
```

### Invalid Status
```python
from app.db import PostStatus

try:
    post.status = "invalid_status"  # ValueError!
except ValueError:
    post.status = PostStatus.DRAFTING
```

---

## Type Hints

### Async Functions with Database
```python
from app.db import Post
from sqlalchemy.ext.asyncio import AsyncSession

async def update_post(
    session: AsyncSession,
    post_id: int,
    content: str
) -> Post:
    post = await session.get(Post, post_id)
    post.draft_content = content
    await session.commit()
    return post
```

### Optional User
```python
from typing import Optional
from app.db import User

async def get_user_profile(
    email: str
) -> Optional[User]:
    async with get_db_session() as session:
        # query
        return user or None
```

---

## Testing

### Create Test Database
```sql
CREATE DATABASE linkedin_agent_test;
```

### Test Setup
```python
@pytest.fixture
async def test_db():
    # Use test database URL
    async with AsyncSession(get_engine()) as session:
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield session
        # Drop tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
```

---

## Performance Tips

### 1. Use Bulk Operations
```python
# Instead of looping
posts_data = [{"user_id": 1, "topic": "x"}, ...]
async with get_db_session() as session:
    session.add_all([Post(**p) for p in posts_data])
    await session.commit()
```

### 2. Load Relationships Eagerly
```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db import User, Post

# Load user with posts
result = await session.execute(
    select(User)
    .where(User.id == 1)
    .options(selectinload(User.posts))
)
```

### 3. Use Pagination
```python
async def get_posts_page(page: int = 1, size: int = 20):
    async with get_db_session() as session:
        result = await session.execute(
            select(Post)
            .offset((page - 1) * size)
            .limit(size)
        )
        return result.scalars().all()
```

---

## Debugging

### Enable SQL Logging
```python
# In app/db/database.py, change echo to True
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True  # Logs all SQL
)
```

### Check Migration Status
```bash
alembic current
alembic history
```

### Test Connection
```python
from app.db import get_engine
import asyncio

async def test_connection():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")
        print("Connected!")

asyncio.run(test_connection())
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No module named 'app'" | Run from project root |
| "Relation 'users' does not exist" | Run `alembic upgrade head` |
| "psycopg_c not found" | Lazy loading defers connection, only appears on actual DB use |
| "Extra inputs are not permitted" | Already fixed in config.py with `extra="ignore"` |
| "Foreign key violation" | Check user_id exists before creating post |
| "Duplicate email" | Email field is unique, check before inserting |

---

## Files Modified/Created in Phase 3

```
NEW:
├── app/core/config.py
├── app/db/__init__.py
├── app/db/database.py
├── app/db/models.py
├── app/agent/state.py
├── alembic.ini
├── alembic/env.py
├── alembic/versions/__init__.py
├── alembic/versions/001_initial_migration.py
├── verify_setup.py
├── PHASE_3_SUMMARY.md
├── DATABASE_SCHEMA.md
└── PHASE_3_QUICK_REFERENCE.md (this file)
```

---

**Last Updated**: 2024-07-19  
**Phase 3 Status**: ✅ COMPLETE
