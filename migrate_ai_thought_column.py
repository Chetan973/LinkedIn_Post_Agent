"""Migrate ai_thought column from VARCHAR(500) to TEXT in Supabase.

This script updates the database schema to allow longer ai_thought values.
"""

import asyncio
import selectors
from sqlalchemy import text
from app.db.database import get_engine


async def migrate_ai_thought_column():
    """Alter ai_thought column from VARCHAR(500) to TEXT."""
    # Get the configured async engine
    engine = get_engine()

    try:
        async with engine.begin() as conn:
            # Alter the ai_thought column to TEXT type
            print("[MIGRATION] Altering posts.ai_thought column to TEXT...")
            await conn.execute(text("""
                ALTER TABLE posts
                ALTER COLUMN ai_thought TYPE TEXT;
            """))
            print("[OK] ai_thought column updated to TEXT successfully")

            # Verify the change
            result = await conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'posts' AND column_name = 'ai_thought';
            """))
            row = result.fetchone()
            if row:
                print(f"[VERIFIED] Column {row[0]}: {row[1]}")
            else:
                print("[WARNING] Could not verify column type")

    except Exception as e:
        print(f"[ERROR] Migration failed: {str(e)}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    # Use SelectorEventLoop for Windows compatibility
    asyncio.run(
        migrate_ai_thought_column(),
        loop_factory=asyncio.SelectorEventLoop  # type: ignore
    )
