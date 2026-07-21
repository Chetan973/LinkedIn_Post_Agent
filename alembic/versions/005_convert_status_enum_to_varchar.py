"""Convert status column from PostgreSQL ENUM to VARCHAR

Revision ID: 005_convert_enum_to_varchar
Revises: 004_three_statuses
Create Date: 2026-07-21 13:00:00.000000

Converts the status column from PostgreSQL ENUM type to VARCHAR to allow
flexible status values without enum constraint changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_convert_enum_to_varchar'
down_revision: Union[str, Sequence[str], None] = '004_three_statuses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert status from ENUM to VARCHAR."""
    # Cast the column from enum to varchar
    op.alter_column(
        'posts',
        'status',
        type_=sa.String(),
        existing_type=sa.Enum('queued', 'published', 'failed', 'drafting',
                             'pending_review', 'failed_draft', 'failed_publish',
                             'retry_scheduled', name='poststatus'),
        postgresql_using='status::text'
    )


def downgrade() -> None:
    """Convert status back to ENUM (may fail if new values exist)."""
    op.alter_column(
        'posts',
        'status',
        type_=sa.Enum('queued', 'published', 'failed', 'drafting',
                     'pending_review', 'failed_draft', 'failed_publish',
                     'retry_scheduled', name='poststatus'),
        existing_type=sa.String(),
        postgresql_using='status::poststatus'
    )
