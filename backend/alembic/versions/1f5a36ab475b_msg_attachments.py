"""msg attachments

Photos and files of the messages (spec/modules/messagerie-instantanee.md §4.3-4.4).
Written from the autogenerate output, without its unrelated drift (nf_ tables...).

Revision ID: 1f5a36ab475b
Revises: c3e5a7b9d1f2
Create Date: 2026-10-19 12:47:02.674858

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f5a36ab475b'
down_revision: Union[str, Sequence[str], None] = 'c3e5a7b9d1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('msg_attachments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('uploader_id', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
    sa.ForeignKeyConstraint(['uploader_id'], ['comptes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_msg_attachments_message_id'), 'msg_attachments', ['message_id'], unique=False)
    op.create_index(op.f('ix_msg_attachments_sha256'), 'msg_attachments', ['sha256'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_msg_attachments_sha256'), table_name='msg_attachments')
    op.drop_index(op.f('ix_msg_attachments_message_id'), table_name='msg_attachments')
    op.drop_table('msg_attachments')
