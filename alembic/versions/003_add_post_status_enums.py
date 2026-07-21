"""Add new post status enum values

Revision ID: 003_add_status_enums
Revises: 002_add_missing
Create Date: 2026-07-21 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_status_enums'
down_revision: Union[str, Sequence[str], None] = '002_add_missing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new status enum values to posts table.

    Note: The status column is currently a VARCHAR string, not a PostgreSQL ENUM type.
    This migration is a no-op since the database will accept any string value.
    The constraint is at the application level via SQLAlchemy's Enum type.
    """
    # Since the database uses VARCHAR for status, not ENUM,
    # no schema migration is needed. The new values will work automatically.
    pass


def downgrade() -> None:
    """No-op downgrade."""
    pass
