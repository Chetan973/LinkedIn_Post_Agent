# Database Schema - Phase 3

## Generated SQL

This file shows the exact SQL that Alembic will generate when running migrations.

### Migration: 001_initial_migration.py

**Upgrade SQL** (creates schema):
```sql
-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    linkedin_profile_url VARCHAR(500) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX ix_users_email ON users(email);

-- Create posts table
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    topic VARCHAR(255) NOT NULL,
    draft_content TEXT,
    final_content TEXT,
    status VARCHAR(50) DEFAULT 'drafting' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX ix_posts_user_id ON posts(user_id);
```

**Downgrade SQL** (destroys schema):
```sql
-- Drop posts table
DROP INDEX ix_posts_user_id;
DROP TABLE posts;

-- Drop users table
DROP INDEX ix_users_email;
DROP TABLE users;
```

---

## Table: users

```
Column Name         | Type                      | Constraints
--------------------|---------------------------|---------------------------
id                  | SERIAL (auto-increment)   | PRIMARY KEY
email               | VARCHAR(255)              | UNIQUE NOT NULL, INDEX
linkedin_profile_url| VARCHAR(500)              | NOT NULL
created_at          | TIMESTAMP WITH TIME ZONE  | DEFAULT NOW(), NOT NULL
updated_at          | TIMESTAMP WITH TIME ZONE  | DEFAULT NOW(), NOT NULL
```

### Indexes
- `PRIMARY KEY (id)`
- `UNIQUE (email)`
- `INDEX ix_users_email ON email`

### Relationships
- **One-to-Many**: User → Posts (via `posts.user_id`)

### Example Records
```
id | email              | linkedin_profile_url                  | created_at              | updated_at
---|--------------------|------------------------------------|-------------------------|------------------------
1  | john@example.com   | https://linkedin.com/in/john-doe      | 2024-07-19 10:00:00+00  | 2024-07-19 10:00:00+00
2  | jane@tech.com      | https://linkedin.com/in/jane-smith    | 2024-07-19 10:05:00+00  | 2024-07-19 10:05:00+00
```

---

## Table: posts

```
Column Name     | Type                      | Constraints
-----------------|---------------------------|---------------------------
id              | SERIAL (auto-increment)   | PRIMARY KEY
user_id         | INTEGER                   | FOREIGN KEY, NOT NULL, INDEX
topic           | VARCHAR(255)              | NOT NULL
draft_content   | TEXT                      | NULLABLE
final_content   | TEXT                      | NULLABLE
status          | VARCHAR(50)               | DEFAULT 'drafting', NOT NULL
created_at      | TIMESTAMP WITH TIME ZONE  | DEFAULT NOW(), NOT NULL
updated_at      | TIMESTAMP WITH TIME ZONE  | DEFAULT NOW(), NOT NULL
```

### Indexes
- `PRIMARY KEY (id)`
- `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`
- `INDEX ix_posts_user_id ON user_id`

### Status Enum Values
- `drafting` - Initial draft being generated
- `pending_review` - Awaiting human review and feedback
- `published` - Published to LinkedIn

### Relationships
- **Many-to-One**: Post → User (via `user_id`)
- **Cascade Delete**: Deleting user auto-deletes their posts

### Example Records
```
id | user_id | topic                    | draft_content    | final_content | status        | created_at              | updated_at
---|---------|--------------------------|------------------|---------------|---------------|-------------------------|------------------------
1  | 1       | AI Best Practices        | Draft text here  | NULL          | drafting      | 2024-07-19 10:10:00+00  | 2024-07-19 10:10:00+00
2  | 1       | Python Tips              | NULL             | Final text    | published     | 2024-07-19 09:00:00+00  | 2024-07-19 12:00:00+00
3  | 2       | Engineering Culture      | Review feedback  | NULL          | pending_review| 2024-07-19 11:30:00+00  | 2024-07-19 11:35:00+00
```

---

## Relationship Diagram

```
┌─────────────────────┐
│    users (1)        │
├─────────────────────┤
│ id (PK)             │◄──────┐
│ email (UNIQUE)      │       │
│ linkedin_profile_url│       │ (1 : Many)
│ created_at          │       │ (Cascade Delete)
│ updated_at          │       │
└─────────────────────┘       │
                              │
                         (FK: user_id)
                              │
                              │
                    ┌─────────────────────┐
                    │   posts (Many)      │
                    ├─────────────────────┤
                    │ id (PK)             │
                    │ user_id (FK) ───────┘
                    │ topic               │
                    │ draft_content       │
                    │ final_content       │
                    │ status (enum)       │
                    │ created_at          │
                    │ updated_at          │
                    └─────────────────────┘
```

---

## Query Examples

### 1. Create a User and Post
```python
# Using SQLAlchemy
from sqlalchemy import select
from app.db import User, Post, PostStatus

async with get_db_session() as session:
    # Create user
    user = User(
        email="engineer@tech.com",
        linkedin_profile_url="https://linkedin.com/in/engineer"
    )
    session.add(user)
    await session.flush()  # Generate ID
    
    # Create post
    post = Post(
        user_id=user.id,
        topic="Building Scalable Microservices",
        status=PostStatus.DRAFTING
    )
    session.add(post)
    await session.commit()
```

### 2. Fetch User with Posts
```python
from sqlalchemy import select
from app.db import User

async with get_db_session() as session:
    result = await session.execute(
        select(User).where(User.email == "engineer@tech.com")
    )
    user = result.scalar_one_or_none()
    
    # Access relationship
    for post in user.posts:
        print(f"Post: {post.topic} - Status: {post.status}")
```

### 3. Get All Published Posts for a User
```python
from sqlalchemy import select
from app.db import Post, PostStatus

async with get_db_session() as session:
    result = await session.execute(
        select(Post)
        .where(
            (Post.user_id == 1) & 
            (Post.status == PostStatus.PUBLISHED)
        )
    )
    published_posts = result.scalars().all()
```

### 4. Update Post Status
```python
async with get_db_session() as session:
    post = await session.get(Post, 1)
    post.status = PostStatus.PENDING_REVIEW
    post.draft_content = "Updated draft..."
    await session.commit()
```

### 5. Delete User and Their Posts (Cascade)
```python
async with get_db_session() as session:
    user = await session.get(User, 1)
    await session.delete(user)
    # All posts with this user_id are automatically deleted
    await session.commit()
```

---

## Indexing Strategy

### Indexes Created
1. **users.email** (UNIQUE)
   - Fast user lookup by email
   - Prevents duplicate accounts
   - Used in login flows

2. **posts.user_id** (Regular)
   - Fast filtering of posts by user
   - Supports relationship queries
   - Used in user dashboard

### Query Performance Implications
```
Operation                                | With Index | Without Index
-----------------------------------------|------------|---------------
SELECT * FROM users WHERE email = 'x'   | O(log n)   | O(n)
SELECT * FROM posts WHERE user_id = 1   | O(log n)   | O(n)
SELECT * FROM users WHERE id = 1        | O(1)       | O(1) (PK lookup)
```

---

## Data Validation Rules

### users Table
- `email`: Required, must be unique, max 255 chars
- `linkedin_profile_url`: Required, must be valid URL, max 500 chars
- Timestamps: Automatically set by database

### posts Table
- `user_id`: Required, must reference existing user, cascade delete
- `topic`: Required, max 255 chars
- `draft_content`: Optional, plain text, up to db max (~1GB per field)
- `final_content`: Optional, plain text, up to db max
- `status`: Required, must be one of: drafting, pending_review, published
- Timestamps: Automatically set by database

---

## Migration History

| Revision | Description | Status |
|----------|-------------|--------|
| 001 | Initial migration: create users and posts tables | Applied |
| (future) | Add columns as needed | Pending |

---

## Scaling Considerations

### Current Schema is Suitable For:
- ✓ Single user or small team (<100 users)
- ✓ Moderate post frequency (3x per week per user)
- ✓ Simple linear workflow

### Future Optimizations:
- Add **partitioning** on `posts.created_at` for large datasets (>1M posts)
- Add **materialized views** for analytics queries
- Add **full-text search index** on draft_content/final_content
- Separate **audit log table** for tracking changes
- Add **rate limiting table** to track API usage per user

---

## Connection Pool Configuration

```python
pool_size=20       # Connections always available
max_overflow=10    # Extra connections under load
pool_pre_ping=True # Test connection before using
pool_recycle=3600  # Recycle connections after 1 hour
```

**Implications**:
- Max concurrent connections: 20 + 10 = 30
- Supports ~60 concurrent HTTP requests (2 DB ops per request)
- Auto-recovers from database restarts

---

## Timezone Handling

All timestamps use `TIMESTAMP WITH TIME ZONE`:
- Stored as UTC in PostgreSQL
- SQLAlchemy returns `datetime` objects with timezone info
- Supports proper timezone conversions across regions

**Example**:
```python
from datetime import datetime, timezone

# Create post
post.created_at  # Returns: 2024-07-19 10:00:00+00:00 (UTC)

# In application code
post.created_at.astimezone()  # Convert to local timezone
```

---

## Backup and Recovery

### Backup Strategy
```bash
# Full database backup
pg_dump -U postgres linkedin_agent > backup.sql

# Point-in-time recovery
pg_restore -U postgres linkedin_agent < backup.sql
```

### Migration Rollback
```bash
# Rollback last migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 001
```

---

**Database Schema Version**: 1.0  
**Last Updated**: 2024-07-19  
**Status**: ✅ Ready for Phase 4
