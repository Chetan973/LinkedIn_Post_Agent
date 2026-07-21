"""Add missing post columns

Revision ID: 002_add_missing
Revises: 001_init
Create Date: 2026-07-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_missing'
down_revision: Union[str, Sequence[str], None] = '001_init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to posts table."""
    # Add idempotency_key column
    op.add_column(
        'posts',
        sa.Column('idempotency_key', sa.String(255), nullable=True)
    )
    op.create_index('ix_posts_idempotency_key', 'posts', ['idempotency_key'], unique=True)

    # Add linkedin_post_id column
    op.add_column(
        'posts',
        sa.Column('linkedin_post_id', sa.String(255), nullable=True)
    )
    op.create_index('ix_posts_linkedin_post_id', 'posts', ['linkedin_post_id'], unique=True)

    # Add published_at column
    op.add_column(
        'posts',
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add error_reason column
    op.add_column(
        'posts',
        sa.Column('error_reason', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Remove added columns from posts table."""
    op.drop_column('posts', 'error_reason')
    op.drop_column('posts', 'published_at')
    op.drop_index('ix_posts_linkedin_post_id', table_name='posts')
    op.drop_column('posts', 'linkedin_post_id')
    op.drop_index('ix_posts_idempotency_key', table_name='posts')
    op.drop_column('posts', 'idempotency_key')
