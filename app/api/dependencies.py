from typing import AsyncGenerator
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings
from app.db import get_db_session


async def get_db() -> AsyncGenerator:
    """Dependency to provide AsyncSession for database operations.

    Yields an async SQLAlchemy session for use in endpoints.
    """
    async with get_db_session() as session:
        yield session


async def get_checkpointer() -> AsyncGenerator[AsyncPostgresSaver, None]:
    """Dependency to provide AsyncPostgresSaver for LangGraph state persistence.

    Yields an initialized AsyncPostgresSaver connected to Supabase.
    """
    checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
    yield checkpointer
