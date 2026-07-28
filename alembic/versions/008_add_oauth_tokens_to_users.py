"""Add OAuth token fields to users table for session persistence and auto-refresh.

Revision ID: 008_add_oauth_tokens
Revises: 4de456a8dc17
Create Date: 2026-07-27 15:00:00.000000

Adds persistent OAuth credentials (access_token, refresh_token, token_expires_at)
and full_name field to support LinkedIn OIDC authentication with automatic
token refresh mechanism.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_oauth_tokens'
down_revision: Union[str, Sequence[str], None] = '4de456a8dc17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add OAuth token fields to users table."""
    op.add_column(
        'users',
        sa.Column(
            'full_name',
            sa.String(length=500),
            nullable=True,
            comment='User full name from LinkedIn OIDC profile'
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'access_token',
            sa.Text(),
            nullable=True,
            comment='Current Supabase JWT access token (1 hour validity)'
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'refresh_token',
            sa.Text(),
            nullable=True,
            comment='Supabase refresh token (used for silent re-auth when access_token expires)'
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'token_expires_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when access_token expires; triggers auto-refresh if within threshold'
        )
    )


def downgrade() -> None:
    """Remove OAuth token fields from users table."""
    op.drop_column('users', 'token_expires_at')
    op.drop_column('users', 'refresh_token')
    op.drop_column('users', 'access_token')
    op.drop_column('users', 'full_name')
