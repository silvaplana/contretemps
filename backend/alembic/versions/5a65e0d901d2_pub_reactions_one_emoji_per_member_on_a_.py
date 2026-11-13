"""pub_reactions: one emoji per member on a post

Revision ID: 5a65e0d901d2
Revises: 56a8fb4f46df
Create Date: 2026-11-13 15:37:15.994040

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a65e0d901d2'
down_revision: Union[str, Sequence[str], None] = '56a8fb4f46df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added it already (see the "has_table" pitfall).
    if sa.inspect(op.get_bind()).has_table('pub_reactions'):
        return
    op.create_table(
        'pub_reactions',
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('pub_posts.id'), primary_key=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('comptes.id'), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('emoji', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('pub_reactions')
