# Database Setup - Quick Reference

## Configuration

### Environment Variable (`.env`)
```bash
DATABASE_URL=postgresql+psycopg_async://postgres:[PASSWORD]@[HOST]:5432/[DATABASE]

# For Supabase:
DATABASE_URL=postgresql+psycopg_async://postgres:[PASSWORD]@[project-ref].supabase.co:5432/postgres

# For Local PostgreSQL:
DATABASE_URL=postgresql+psycopg_async://postgres:password@localhost:5432/linkedin_agent
```

---

## Core Database Module

### Import Everything
```python
from app.db import (
    Base,                  # SQLAlchemy DeclarativeBase
    User,                  # User model
    Post,                  # Post model
    PostStatus,           # Enum: DRAFTING, PENDING_REVIEW, PUBLISHED
    get_engine,           # Factory: AsyncEngine
    get_session_maker,    # Factory: async_sessionmaker
    get_db_session,       # FastAPI dependency: AsyncSession generator
    init_db,              # Initialize database
)
```

---

## FastAPI Integration

### Startup Event
```python
from fastapi import FastAPI
from app.db import init_db

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await init_db()  # Creates all tables from models
```

### Dependency Injection
```python
from fastapi import FastAPI, Depends
from app.db import get_db_session, User
from sqlalchemy import select

app = FastAPI()

@app.post("/users/")
async def create_user(
    email: str,
    linkedin_url: str,
    session = Depends(get_db_session)  # Injected AsyncSession
):
    user = User(
        email=email,
        linkedin_profile_url=linkedin_url
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    session = Depends(get_db_session)
):
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().first()
```

---

## Database Models

### User Model
```python
class User(Base):
    __tablename__ = "users"
    
    user_id: Mapped[int]                    # BigInteger, PK
    email: Mapped[str]                      # String(255), unique
    linkedin_profile_url: Mapped[str]       # String(500)
    created_at: Mapped[datetime]            # DateTime(timezone=True)
    updated_at: Mapped[datetime]            # DateTime(timezone=True)
    
    posts: Mapped[list["Post"]]             # Relationship
```

### Post Model
```python
class Post(Base):
    __tablename__ = "posts"
    
    post_id: Mapped[int]                    # BigInteger, PK
    user_id: Mapped[int]                    # BigInteger, FK
    topic: Mapped[str]                      # String(255)
    draft_content: Mapped[Optional[str]]    # Text
    final_content: Mapped[Optional[str]]    # Text
    status: Mapped[PostStatus]              # Enum
    created_at: Mapped[datetime]            # DateTime(timezone=True)
    updated_at: Mapped[datetime]            # DateTime(timezone=True)
    
    user: Mapped[User]                      # Relationship
```

### PostStatus Enum
```python
class PostStatus(str, Enum):
    DRAFTING = "drafting"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
```

---

## Alembic Commands

### Setup
```bash
# Already done - Alembic is initialized
# Run this if you need to reinitialize:
# alembic init -t async alembic
```

### Migrations
```bash
# Apply all pending migrations
alembic upgrade head

# Apply one specific migration
alembic upgrade 001_init

# Rollback one step
alembic downgrade -1

# View current state
alembic current

# View all migrations
alembic history

# Generate new migration (requires valid DATABASE_URL)
alembic revision --autogenerate -m "describe_change"
```

---

## Common Patterns

### Create a User with Posts
```python
from app.db import User, Post, PostStatus, get_session_maker

async def create_user_with_posts():
    async with get_session_maker() as session:
        user = User(
            email="user@example.com",
            linkedin_profile_url="https://linkedin.com/in/user"
        )
        
        post1 = Post(
            user=user,
            topic="AI in Business",
            draft_content="...",
            status=PostStatus.DRAFTING
        )
        
        post2 = Post(
            user=user,
            topic="Machine Learning",
            draft_content="...",
            status=PostStatus.DRAFTING
        )
        
        session.add_all([user, post1, post2])
        await session.commit()
        return user.user_id
```

### Query Users
```python
from sqlalchemy import select
from app.db import User, Post, get_session_maker

async def get_all_users():
    async with get_session_maker() as session:
        stmt = select(User).order_by(User.created_at)
        result = await session.execute(stmt)
        return result.scalars().all()

async def get_user_with_posts(user_id: int):
    async with get_session_maker() as session:
        user = await session.get(User, user_id)
        # Relationship automatically loaded if configured
        return user.posts  # List of posts
```

### Update Post Status
```python
from sqlalchemy import select, update
from app.db import Post, PostStatus, get_session_maker

async def publish_post(post_id: int):
    async with get_session_maker() as session:
        stmt = (
            update(Post)
            .where(Post.post_id == post_id)
            .values(status=PostStatus.PUBLISHED)
        )
        await session.execute(stmt)
        await session.commit()
```

---

## Engine Configuration

### Async Engine Settings
```python
create_async_engine(
    DATABASE_URL,
    echo=False,                    # SQL logging (set to True for debugging)
    pool_size=10,                  # Base pool size
    max_overflow=20,               # Additional connections when busy
    pool_pre_ping=True,            # Validate connections before use
    connect_args={
        "timeout": 30,             # Connection timeout (seconds)
    }
)
```

### Session Settings
```python
async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,        # Session usable after commit
    autoflush=False,               # Manual flush control
)
```

---

## Troubleshooting

### "Cannot connect to database"
1. Check `DATABASE_URL` is correct
2. Verify database credentials
3. Ensure PostgreSQL is running (local) or Supabase project is active
4. Check network access (port 5432)

### "Psycopg cannot use ProactorEventLoop"
- Already fixed in `alembic/env.py`
- If manual issue, use: `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`

### "Table does not exist"
- Run: `alembic upgrade head`
- Or: `await init_db()` in application startup

### "Foreign key constraint failed"
- Ensure user exists before creating posts
- Use cascade delete (already configured)

---

## Migration Structure

### Initial Migration File Location
```
alembic/versions/001_init_init_supabase_schema.py
```

### Creates Tables
- `users` - User data
- `posts` - LinkedIn post drafts

### Indexes Created
- `users.email` - Unique index for email lookup
- `posts.user_id` - Foreign key index

---

## Performance Tips

1. **Connection Pooling**
   - Set `pool_size=20` for high-traffic endpoints
   - Increase `max_overflow` as needed

2. **Query Optimization**
   - Use `select()` for efficient queries
   - Add indexes on frequently filtered columns
   - Use `expire_on_commit=False` to avoid extra queries

3. **Batch Operations**
   - Use `session.add_all()` for bulk inserts
   - Commit once after all additions

4. **Lazy Loading**
   - Configure relationships for optimal loading strategy
   - Use `selectinload` or `joinedload` for related data

---

## Key Files

| File | Purpose |
|------|---------|
| `app/db/database.py` | Async engine, session factory |
| `app/db/models.py` | User, Post, PostStatus definitions |
| `app/db/__init__.py` | Public exports |
| `app/core/config.py` | DATABASE_URL configuration |
| `alembic/env.py` | Migration runner |
| `alembic.ini` | Migration settings |
| `alembic/versions/` | Migration files |

