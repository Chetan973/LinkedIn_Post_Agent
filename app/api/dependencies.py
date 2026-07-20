from typing import AsyncGenerator
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings
from app.db import get_db_session


async def get_db() -> AsyncGenerator:
    """Dependency to provide AsyncSession for database operations.

    Yields an async SQLAlchemy session for use in endpoints.
    """
    async for session in get_db_session():
        yield session


async def get_checkpointer() -> AsyncPostgresSaver:
    """Dependency to provide AsyncPostgresSaver for LangGraph state persistence.

    Returns an initialized AsyncPostgresSaver connected to Supabase.
    No cleanup needed, so we return it directly instead of yielding.
    """
    return AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
