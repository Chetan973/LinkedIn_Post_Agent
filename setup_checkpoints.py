"""Initialize LangGraph checkpoint tables in PostgreSQL."""

import asyncio
import selectors
from app.db.database import _get_libpq_url
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


async def setup_checkpoints():
    """Create checkpoint tables for LangGraph."""
    libpq_url = _get_libpq_url()

    async with AsyncPostgresSaver.from_conn_string(libpq_url) as checkpointer:
        await checkpointer.setup()
        print("Checkpoint tables created successfully")


if __name__ == "__main__":
    # Use SelectorEventLoop for Windows compatibility
    asyncio.run(
        setup_checkpoints(),
        loop_factory=asyncio.SelectorEventLoop  # type: ignore
    )
