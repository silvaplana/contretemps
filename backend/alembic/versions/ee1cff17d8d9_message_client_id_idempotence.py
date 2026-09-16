"""message client id idempotence

Revision ID: ee1cff17d8d9
Revises: ab42c998b6cd
Create Date: 2026-09-17 01:04:39.586595

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee1cff17d8d9'
down_revision: Union[str, Sequence[str], None] = 'ab42c998b6cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('client_id', sa.String(length=64), nullable=True))
    op.create_index(
        'ix_messages_client_id', 'messages', ['client_id'], unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_messages_client_id', table_name='messages')
    op.drop_column('messages', 'client_id')
