"""Add image_url column to posts table for AI-generated images

Revision ID: 006_add_image_url
Revises: 005_convert_enum_to_varchar
Create Date: 2026-07-21 14:00:00.000000

Adds support for storing generated image URLs with each post.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_image_url'
down_revision: Union[str, Sequence[str], None] = '005_convert_enum_to_varchar'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add image_url column to posts table."""
    op.add_column(
        'posts',
        sa.Column('image_url', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Remove image_url column from posts table."""
    op.drop_column('posts', 'image_url')
