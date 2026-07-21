"""
Utility script to fix posts with invalid status values in the database.

This script updates any posts with old/invalid status values to valid enum values.
Run this after updating the models to add new status values.

Usage:
    python scripts/fix_post_statuses.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from app.db import Post, PostStatus, get_session_maker


async def fix_invalid_statuses():
    """Fix any invalid status values in the posts table."""
    session_maker = get_session_maker()

    # Map of invalid statuses to valid replacements
    status_mappings = {
        'failed_draft': PostStatus.FAILED_DRAFT.value,
        'failed_publish': PostStatus.FAILED_PUBLISH.value,
        'retry_scheduled': PostStatus.RETRY_SCHEDULED.value,
    }

    async with session_maker() as db:
        for old_status, new_status in status_mappings.items():
            # Find posts with the old status
            stmt = select(Post).where(Post.status == old_status)
            result = await db.execute(stmt)
            posts = result.scalars().all()

            if posts:
                print(f"Found {len(posts)} posts with status '{old_status}'")
                print(f"  → Updating to '{new_status}'")

                # Update them
                for post in posts:
                    post.status = new_status

                await db.commit()
                print(f"  ✓ Updated {len(posts)} posts")
            else:
                print(f"No posts with status '{old_status}' found")

    # Verify all statuses are valid
    async with session_maker() as db:
        stmt = select(Post.status).distinct()
        result = await db.execute(stmt)
        current_statuses = set(row[0] for row in result.all() if row[0])

        valid_statuses = {status.value for status in PostStatus}
        invalid_statuses = current_statuses - valid_statuses

        if invalid_statuses:
            print(f"\n⚠️  ERROR: Found invalid statuses still in database: {invalid_statuses}")
            return False
        else:
            print(f"\n✓ All posts have valid statuses: {sorted(current_statuses)}")
            return True


if __name__ == "__main__":
    try:
        success = asyncio.run(fix_invalid_statuses())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
