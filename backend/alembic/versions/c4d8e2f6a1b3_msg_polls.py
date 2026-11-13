"""msg_polls: a poll in a conversation, like WhatsApp's (Seb, 13 November 2026)

Revision ID: c4d8e2f6a1b3
Revises: b7c3e9d1f2a4
Create Date: 2026-11-13 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8e2f6a1b3'
down_revision: Union[str, Sequence[str], None] = 'b7c3e9d1f2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added them already (see the "has_table" pitfall).
    if sa.inspect(op.get_bind()).has_table('msg_polls'):
        return
    op.create_table(
        'msg_polls',
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('question', sa.String(length=200), nullable=False),
        sa.Column('multiple', sa.Boolean(), nullable=False),
    )
    op.create_table(
        'msg_poll_options',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('msg_polls.message_id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
    )
    op.create_index('ix_msg_poll_options_message_id', 'msg_poll_options', ['message_id'])
    op.create_table(
        'msg_poll_votes',
        sa.Column('option_id', sa.Integer(), sa.ForeignKey('msg_poll_options.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('comptes.id'), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('msg_poll_votes')
    op.drop_index('ix_msg_poll_options_message_id', table_name='msg_poll_options')
    op.drop_table('msg_poll_options')
    op.drop_table('msg_polls')
