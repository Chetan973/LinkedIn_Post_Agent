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


async def get_checkpointer() -> AsyncPostgresSaver:
    """Get or create singleton AsyncPostgresSaver for LangGraph state persistence.

    Reuses the same checkpointer across all background tasks to avoid
    connection pool exhaustion. Checkpointer is initialized once at app startup.
    """
    global _checkpointer
    if _checkpointer is None:
        libpq_url = _get_libpq_url()
        _checkpointer = AsyncPostgresSaver.from_conn_string(libpq_url)
        await _checkpointer.setup()
        logger.info("Checkpointer initialized and ready")
    return _checkpointer


async def close_checkpointer() -> None:
    """Close the singleton checkpointer connection on app shutdown."""
    global _checkpointer
    if _checkpointer is not None:
        try:
            await _checkpointer.aclose()
            _checkpointer = None
            logger.info("Checkpointer closed")
        except Exception as e:
            logger.error(f"Error closing checkpointer: {str(e)}")


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
