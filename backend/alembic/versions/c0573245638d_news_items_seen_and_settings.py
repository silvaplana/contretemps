"""news items, seen and settings

The news module (spec/modules/actualites.md §7): the news items, when each
member last opened them (« Nouveau ») and the Atelier option « Ouvrir l'appli
sur les actus ». New tables only; nothing existing changes.

Revision ID: c0573245638d
Revises: e548f7e05356
Create Date: 2026-11-06 19:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0573245638d'
down_revision: Union[str, Sequence[str], None] = 'e548f7e05356'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have created them already (see the "has_table" pitfall).
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('news_items'):
        op.create_table(
            'news_items',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('level', sa.String(length=10), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('on_top_until', sa.Date(), nullable=True),
            sa.Column('notify', sa.Boolean(), nullable=False),
            sa.Column('notified_at', sa.DateTime(), nullable=True),
            sa.Column('author_id', sa.Integer(), nullable=True),
            sa.Column('author_name', sa.String(length=100), nullable=False),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['author_id'], ['comptes.id']),
            sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_news_items_org_id', 'news_items', ['org_id'])
        op.create_index('ix_news_items_published_at', 'news_items', ['published_at'])
    if not inspector.has_table('news_seen'):
        op.create_table(
            'news_seen',
            sa.Column('compte_id', sa.Integer(), nullable=False),
            sa.Column('seen_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['compte_id'], ['comptes.id']),
            sa.PrimaryKeyConstraint('compte_id'),
        )
    if not inspector.has_table('news_settings'):
        op.create_table(
            'news_settings',
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('open_on_news', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
            sa.PrimaryKeyConstraint('org_id'),
        )


def downgrade() -> None:
    op.drop_table('news_settings')
    op.drop_table('news_seen')
    op.drop_index('ix_news_items_published_at', table_name='news_items')
    op.drop_index('ix_news_items_org_id', table_name='news_items')
    op.drop_table('news_items')
