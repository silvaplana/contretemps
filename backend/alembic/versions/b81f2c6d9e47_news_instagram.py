"""news: relay an Instagram account

spec/modules/actualites.md §6 bis: one Instagram account per organization
(key kept encrypted), and on news_items the post an item relays, so it
comes in only once. New table and one nullable column; nothing else changes.

Revision ID: b81f2c6d9e47
Revises: a7d3e91c4b20
Create Date: 2026-11-08 18:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b81f2c6d9e47'
down_revision: Union[str, Sequence[str], None] = 'a7d3e91c4b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # `create_all` may have added them already (see the "has_table" pitfall).
    if not inspector.has_table('news_instagram'):
        op.create_table(
            'news_instagram',
            sa.Column('org_id', sa.Integer(), sa.ForeignKey('ecoles.id'), primary_key=True),
            sa.Column('token_encrypted', sa.Text(), nullable=False),
            sa.Column('username', sa.String(length=100), nullable=False),
            sa.Column('linked_by', sa.Integer(), sa.ForeignKey('comptes.id'), nullable=True),
            sa.Column('linked_by_name', sa.String(length=100), nullable=False),
            sa.Column('linked_at', sa.DateTime(), nullable=False),
            sa.Column('token_refreshed_at', sa.DateTime(), nullable=False),
            sa.Column('last_sync_at', sa.DateTime(), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
        )
    if 'instagram_id' not in {c['name'] for c in inspector.get_columns('news_items')}:
        with op.batch_alter_table('news_items') as batch:
            batch.add_column(sa.Column('instagram_id', sa.String(length=64), nullable=True))
            batch.create_index('ix_news_items_instagram_id', ['instagram_id'])


def downgrade() -> None:
    with op.batch_alter_table('news_items') as batch:
        batch.drop_index('ix_news_items_instagram_id')
        batch.drop_column('instagram_id')
    op.drop_table('news_instagram')
