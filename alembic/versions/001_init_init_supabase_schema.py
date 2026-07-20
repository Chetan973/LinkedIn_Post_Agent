"""init_supabase_schema

Revision ID: 001_init
Revises: 
Create Date: 2026-07-20 14:07:41.255494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_init'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('linkedin_profile_url', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'posts',
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('topic', sa.String(255), nullable=False),
        sa.Column('draft_content', sa.Text(), nullable=True),
        sa.Column('final_content', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='drafting'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('post_id'),
    )
    op.create_index('ix_posts_user_id', 'posts', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_posts_user_id', table_name='posts')
    op.drop_table('posts')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
