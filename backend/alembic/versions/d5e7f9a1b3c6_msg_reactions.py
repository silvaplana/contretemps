"""msg_reactions: an emoji on a message, like WhatsApp (Seb, 16 November 2026)

Revision ID: d5e7f9a1b3c6
Revises: a1b3c5d7e9f2
Create Date: 2026-11-16 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e7f9a1b3c6'
down_revision: Union[str, Sequence[str], None] = 'a1b3c5d7e9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added it already (see the "has_table" pitfall).
    if sa.inspect(op.get_bind()).has_table('msg_reactions'):
        return
    op.create_table(
        'msg_reactions',
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('comptes.id'), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('emoji', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('msg_reactions')
