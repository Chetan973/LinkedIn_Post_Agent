from typing import AsyncGenerator, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


def _get_libpq_url() -> str:
    """Convert SQLAlchemy async URL to standard libpq format for AsyncPostgresSaver.

    AsyncPostgresSaver.from_conn_string() expects standard PostgreSQL libpq format,
    not SQLAlchemy driver-prefixed URLs.
    """
    url = settings.DATABASE_URL
    # Remove SQLAlchemy driver prefixes to get standard postgres:// format
    url = url.replace("postgresql+psycopg_async://", "postgresql://")
    url = url.replace("postgresql+psycopg://", "postgresql://")
    return url


def get_engine() -> AsyncEngine:
    """Get or create the async engine for PostgreSQL with optimized connection pooling."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=25,                    # Increased from 10
            max_overflow=25,                 # Increased from 20
            pool_recycle=3600,               # Recycle stale connections every hour
            pool_pre_ping=True,              # Health check before reuse
        )
    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create the async session maker."""
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_maker


def get_checkpointer_factory():
    """Get factory function for creating AsyncPostgresSaver instances.

    Returns a callable that creates checkpointers with the correct libpq URL.
    This is used by background tasks to create checkpointers efficiently.
    """
    libpq_url = _get_libpq_url()

    async def create_checkpointer():
        """Create and setup AsyncPostgresSaver for this task."""
        checkpointer = AsyncPostgresSaver.from_conn_string(libpq_url)
        # from_conn_string() returns context manager, use directly in tasks
        return checkpointer

    return create_checkpointer


async def close_checkpointer() -> None:
    """No-op for backward compatibility."""
    logger.info("Checkpointer cleanup (no singleton to close)")


async def init_db() -> None:
    """Initialize database by creating all tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for dependency injection."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
