"""fin_bank_connections: when the expiry reminder was sent

financier.md §3.5 (Seb, 10 November 2026): the treasurer is warned a week
before the bank access expires; one nullable column, nothing existing changes.

Revision ID: bf26dc81d9b0
Revises: afeb51999b9d
Create Date: 2026-11-10 10:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bf26dc81d9b0'
down_revision: Union[str, Sequence[str], None] = 'afeb51999b9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('fin_bank_connections')}
    if 'expiry_reminded_at' not in existing:
        with op.batch_alter_table('fin_bank_connections') as batch:
            batch.add_column(sa.Column('expiry_reminded_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('fin_bank_connections') as batch:
        batch.drop_column('expiry_reminded_at')
