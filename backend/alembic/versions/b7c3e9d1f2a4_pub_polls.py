"""pub_polls: a poll on a post, like WhatsApp's (Seb, 13 November 2026)

Revision ID: b7c3e9d1f2a4
Revises: 5a65e0d901d2
Create Date: 2026-11-13 17:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c3e9d1f2a4'
down_revision: Union[str, Sequence[str], None] = '5a65e0d901d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added them already (see the "has_table" pitfall).
    if sa.inspect(op.get_bind()).has_table('pub_polls'):
        return
    op.create_table(
        'pub_polls',
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('pub_posts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('question', sa.String(length=200), nullable=False),
        sa.Column('multiple', sa.Boolean(), nullable=False),
    )
    op.create_table(
        'pub_poll_options',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('pub_polls.post_id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
    )
    op.create_index('ix_pub_poll_options_post_id', 'pub_poll_options', ['post_id'])
    op.create_table(
        'pub_poll_votes',
        sa.Column('option_id', sa.Integer(), sa.ForeignKey('pub_poll_options.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('comptes.id'), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('pub_poll_votes')
    op.drop_index('ix_pub_poll_options_post_id', table_name='pub_poll_options')
    op.drop_table('pub_poll_options')
    op.drop_table('pub_polls')
