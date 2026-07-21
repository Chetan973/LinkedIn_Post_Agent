**Role:** You are an expert Python Backend Developer.

**Context:** The Principal Architect has decided to pivot to a pure "scriptbase" Monolith MVP to eliminate all deployment infrastructure. We are ripping out PostgreSQL, Alembic, Docker, Redis, and Celery. We will use a local SQLite file (`linkedin_agent.db`) and pure FastAPI BackgroundTasks for async execution.

**Your Task:**
1. **Remove Heavy Infrastructure:** Delete `alembic.ini`, the `alembic/` directory, the `app/worker/` directory, `Dockerfile`, and `docker-compose.yml`.
2. **Update pyproject.toml:** 
   - Remove `psycopg[binary,pool]`, `langgraph-checkpoint-postgres`, `langgraph-checkpoint-redis`, `celery`, and `redis`.
   - Add `aiosqlite>=0.20.0` and `langgraph-checkpoint-sqlite>=2.0.0`.
3. **Rewrite app/db/database.py:** 
   - Change the engine to use `sqlite+aiosqlite:///./linkedin_agent.db`.
   - Add an `async def init_db():` function that runs `await conn.run_sync(Base.metadata.create_all)` using the engine to automatically create the `User` and `Post` tables on startup.
4. **Update app/api/main.py:**
   - Add a FastAPI `lifespan` context manager that calls `init_db()` when the application starts.
5. **Update .env:** Change `DATABASE_URL` to `sqlite+aiosqlite:///./linkedin_agent.db` and delete all Postgres and Redis variables.

Execute these file deletions and modifications, run `pip install -e .` to install the SQLite drivers, and verify the environment.