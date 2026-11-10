"""fin_accounts.ledger_number: the bank account's number in the ledger

financier.md §8.1 (Seb, 10 November 2026): the treasurer may give a bank
account the number it had in the previous software (5123 instead of the
rank-based 5121), so that the Balance and the Grand livre read the same.

Revision ID: a7b9c1d3e5f2
Revises: e3f5a7b9c1d3
Create Date: 2026-11-10 13:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b9c1d3e5f2'
down_revision: Union[str, Sequence[str], None] = 'e3f5a7b9c1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c['name'] for c in sa.inspect(bind).get_columns('fin_accounts')}
    if 'ledger_number' not in columns:
        with op.batch_alter_table('fin_accounts') as batch:
            batch.add_column(sa.Column('ledger_number', sa.String(length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('fin_accounts') as batch:
        batch.drop_column('ledger_number')
