# Database Setup Guide - Supabase PostgreSQL + Alembic

This guide walks you through setting up your async PostgreSQL database layer with Supabase, SQLAlchemy 2.0+, and Alembic migrations.

## ✅ What's Been Configured

### 1. **Dependencies Updated** (`pyproject.toml`)
- ✅ Removed SQLite dependencies (`aiosqlite`)
- ✅ Added `psycopg[binary,pool]>=3.2.0` (async PostgreSQL driver)
- ✅ Added `alembic>=1.13.0` (database migrations)
- ✅ Added `langgraph-checkpoint-postgres>=2.0.0` (for LangGraph checkpointing)

### 2. **Async Database Engine** (`app/db/database.py`)
```python
# Async PostgreSQL connection with connection pooling
- AsyncEngine with pool_size=10, max_overflow=20
- async_sessionmaker with expire_on_commit=False
- get_db_session() for dependency injection in FastAPI
- init_db() to create tables programmatically
```

### 3. **SQLAlchemy 2.0 Models** (`app/db/models.py`)

**User Model:**
- `user_id` (BigInteger, Primary Key, auto-increment)
- `email` (String(255), unique, indexed)
- `linkedin_profile_url` (String(500))
- `created_at` / `updated_at` (DateTime with timezone)

**Post Model:**
- `post_id` (BigInteger, Primary Key, auto-increment)
- `user_id` (BigInteger, Foreign Key → users.user_id, indexed)
- `topic`, `draft_content`, `final_content` (String/Text)
- `status` (Enum: drafting, pending_review, published)
- `created_at` / `updated_at` (DateTime with timezone)

### 4. **Alembic Migration System** (`alembic/`)
- ✅ Async template configuration
- ✅ Auto-detection of `Base.metadata`
- ✅ Windows event loop compatibility fix
- ✅ Initial migration file: `001_init_init_supabase_schema.py`

---

## 🚀 Quick Start

### Step 1: Set Up Supabase

1. Go to [supabase.com](https://supabase.com) and sign up
2. Create a new project
3. Navigate to **Settings** → **Database**
4. Copy your connection string (look for PostgreSQL connection):
   ```
   postgresql://postgres:[password]@[project-ref].supabase.co:5432/postgres
   ```

### Step 2: Update Environment Variables

Edit `.env` with your Supabase credentials:
```bash
# Use the async driver (postgresql+psycopg_async://)
DATABASE_URL=postgresql+psycopg_async://postgres:[YOUR_PASSWORD]@[project-ref].supabase.co:5432/postgres
```

**Note:** The connection string format must use `postgresql+psycopg_async://` (not `postgresql://`)

### Step 3: Run Migrations

Install dependencies and apply migrations:
```bash
# Install latest dependencies
pip install -e . --upgrade

# Apply migrations to your database
alembic upgrade head
```

This will create the `users` and `posts` tables in your Supabase database.

### Step 4: Use in Your Application

```python
from fastapi import FastAPI, Depends
from app.db import get_db_session, init_db, User, Post
from sqlalchemy import select

app = FastAPI()

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    await init_db()

# Use in endpoints
@app.post("/users/")
async def create_user(email: str, linkedin_url: str, session = Depends(get_db_session)):
    user = User(email=email, linkedin_profile_url=linkedin_url)
    session.add(user)
    await session.commit()
    return user

@app.get("/users/{user_id}")
async def get_user(user_id: int, session = Depends(get_db_session)):
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().first()
```

---

## 🔧 Common Alembic Commands

### Generate New Migrations
When you modify models, auto-generate a migration:
```bash
alembic revision --autogenerate -m "description_of_change"
```

**Note:** For this to work, you need a valid DATABASE_URL set up.

### Apply Migrations
```bash
# Apply all pending migrations
alembic upgrade head

# Apply N specific migrations
alembic upgrade +2

# Apply to a specific revision
alembic upgrade 001_init
```

### Rollback Migrations
```bash
# Rollback one migration
alembic downgrade -1

# Rollback all migrations
alembic downgrade base
```

### View Migration History
```bash
alembic history
alembic current
```

---

## 🔍 Connection Details

### Connection String Format
```
postgresql+psycopg_async://[user]:[password]@[host]:[port]/[database]
```

### Supabase Specifics
- **Host:** `[project-ref].supabase.co`
- **Port:** `5432`
- **User:** `postgres`
- **Database:** `postgres` (default)
- **Password:** Found in Supabase dashboard

### Local PostgreSQL (Alternative)
If using local PostgreSQL instead of Supabase:
```bash
# Create database
createdb linkedin_agent

# Update .env
DATABASE_URL=postgresql+psycopg_async://postgres:password@localhost:5432/linkedin_agent
```

---

## ⚠️ Troubleshooting

### Connection Timeout
- Verify DATABASE_URL is correct
- Check that Supabase project is running
- Ensure network allows PostgreSQL connections (port 5432)

### Event Loop Error (Windows)
- Already handled in `alembic/env.py` with `WindowsSelectorEventLoopPolicy`
- If you get async errors, restart Python and ensure `psycopg` is version 3.2+

### Migration Failed
- Run `alembic current` to see current schema version
- Check `alembic/versions/` for migration files
- Ensure database user has CREATE/ALTER permissions

### Models Not Found During Migration
- Ensure `PYTHONPATH` includes project root
- Check `alembic/env.py` imports `app.db.models.Base`
- Verify `app/__init__.py` exists (package marker)

---

## 📋 Project Structure

```
.
├── app/
│   ├── db/
│   │   ├── __init__.py          # Exports: Base, User, Post, PostStatus, etc.
│   │   ├── database.py          # Engine, session factory, get_db_session()
│   │   └── models.py            # SQLAlchemy 2.0 models
│   ├── core/
│   │   └── config.py            # Settings with DATABASE_URL
│   └── ...
├── alembic/
│   ├── env.py                   # Migration runner (async, Windows-compatible)
│   ├── versions/
│   │   └── 001_init_init_supabase_schema.py  # Initial schema
│   └── alembic.ini              # Alembic config
├── .env                         # Environment variables (keep secret)
├── .env.example                 # Example configuration
└── pyproject.toml               # Project dependencies
```

---

## 🎯 Next Steps

1. ✅ Update `.env` with Supabase credentials
2. ✅ Run `pip install -e . --upgrade`
3. ✅ Run `alembic upgrade head`
4. ✅ Test connection with `python verify_setup.py` (if available)
5. ✅ Start using the database in your FastAPI endpoints

---

## 📚 Resources

- [Supabase Docs](https://supabase.com/docs)
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic Migrations](https://alembic.sqlalchemy.org/)
- [Psycopg 3 Async](https://www.psycopg.org/psycopg3/docs/basic/index.html)

