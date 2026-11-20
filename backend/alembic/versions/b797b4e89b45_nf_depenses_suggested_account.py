"""nf_depenses suggested_account

Reading a piece when no account of the chart fits (financier.md §8.2 bis):
the account the reading proposes to create (« 6064 Fournitures de danse »),
kept on the expense line until the treasurer creates it or picks another.

Revision ID: b797b4e89b45
Revises: d4e8a2c6f1b3
Create Date: 2026-11-20 00:35:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b797b4e89b45'
down_revision: Union[str, Sequence[str], None] = 'd4e8a2c6f1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('nf_depenses')}
    if 'suggested_account' not in colonnes:
        with op.batch_alter_table('nf_depenses') as batch_op:
            batch_op.add_column(sa.Column('suggested_account', sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_depenses') as batch_op:
        batch_op.drop_column('suggested_account')
