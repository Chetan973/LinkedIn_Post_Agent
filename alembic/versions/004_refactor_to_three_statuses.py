"""Refactor PostStatus to three-status automated lifecycle: QUEUED, PUBLISHED, FAILED

Revision ID: 004_three_statuses
Revises: 003_add_status_enums
Create Date: 2026-07-21 12:00:00.000000

This migration:
1. Maps all old status values to the new three-status model
2. Updates the schema to reflect the simplified automated workflow
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_three_statuses'
down_revision: Union[str, Sequence[str], None] = '003_add_status_enums'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate to three-status model.

    Mapping logic:
    - 'drafting', 'pending_review' → 'queued' (in progress/waiting)
    - 'published' → 'published' (success)
    - 'failed_draft', 'failed_publish', 'retry_scheduled' → 'failed' (any error)
    """
    # Map old status values to new ones
    op.execute("""
        UPDATE posts SET status = 'queued'
        WHERE status IN ('drafting', 'pending_review');
    """)

    op.execute("""
        UPDATE posts SET status = 'failed'
        WHERE status IN ('failed_draft', 'failed_publish', 'retry_scheduled');
    """)

    # Ensure all posts have valid status values
    op.execute("""
        UPDATE posts SET status = 'failed'
        WHERE status NOT IN ('queued', 'published', 'failed');
    """)


def downgrade() -> None:
    """Downgrade: map back to old statuses (limited, data loss expected).

    Note: Mapping back is lossy - we can only restore to a subset of old statuses:
    - 'queued' → 'drafting'
    - 'published' → 'published'
    - 'failed' → 'failed_draft' (arbitrary choice)
    """
    op.execute("""
        UPDATE posts SET status = 'drafting'
        WHERE status = 'queued';
    """)

    op.execute("""
        UPDATE posts SET status = 'failed_draft'
        WHERE status = 'failed';
    """)
