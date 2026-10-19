"""messages edit delete forward reply

Actions on a message (spec/modules/messagerie-instantanee.md §4.2): edited_at,
deleted_at, forwarded and reply_to_id on `messages`. Written by hand: the
autogenerate output also carried unrelated drift (nf_ tables, comptes.email...).

Revision ID: fd4abbeaf71e
Revises: b2d4f6a8c0e1
Create Date: 2026-10-19 12:12:19.846061

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd4abbeaf71e'
down_revision: Union[str, Sequence[str], None] = 'b2d4f6a8c0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode: SQLite cannot add a foreign key with a plain ALTER TABLE.
    with op.batch_alter_table('messages') as batch:
        batch.add_column(sa.Column('edited_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column('forwarded', sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(sa.Column('reply_to_id', sa.Integer(), nullable=True))
        batch.create_foreign_key(
            'fk_messages_reply_to_id', 'messages', ['reply_to_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('messages') as batch:
        batch.drop_constraint('fk_messages_reply_to_id', type_='foreignkey')
        batch.drop_column('reply_to_id')
        batch.drop_column('forwarded')
        batch.drop_column('deleted_at')
        batch.drop_column('edited_at')
