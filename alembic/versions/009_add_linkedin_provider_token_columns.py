"""Add LinkedIn provider token and person URN columns for direct API publishing.

Revision ID: 009_add_linkedin_provider_tokens
Revises: 008_add_oauth_tokens
Create Date: 2026-07-27 16:00:00.000000

Adds linkedin_access_token (raw OAuth provider token from LinkedIn for direct API calls)
and linkedin_person_urn (LinkedIn Person URN identifier) to support direct LinkedIn
publishing without needing Supabase intermediary.

These columns are nullable to preserve existing user records without requiring backfill.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_linkedin_provider_tokens'
down_revision: Union[str, Sequence[str], None] = '008_add_oauth_tokens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add LinkedIn provider token and person URN columns to users table."""
    op.add_column(
        'users',
        sa.Column(
            'linkedin_access_token',
            sa.Text(),
            nullable=True,
            comment='Raw OAuth provider token from LinkedIn for direct API publishing'
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'linkedin_person_urn',
            sa.String(length=255),
            nullable=True,
            comment='LinkedIn Person URN (urn:li:person:...) for API publishing'
        )
    )


def downgrade() -> None:
    """Remove LinkedIn provider token and person URN columns from users table."""
    op.drop_column('users', 'linkedin_person_urn')
    op.drop_column('users', 'linkedin_access_token')
