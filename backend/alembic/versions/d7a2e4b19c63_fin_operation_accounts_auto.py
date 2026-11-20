"""fin_operation_accounts auto

Automatic categorisation (financier.md §8.4, Seb 20/11): a line written by
the app when the proposal is sure is marked `auto`, editable, to be validated
in Bilan › Préparer.

Revision ID: d7a2e4b19c63
Revises: c3f1a9d27e54
Create Date: 2026-11-20 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a2e4b19c63'
down_revision: Union[str, Sequence[str], None] = 'c3f1a9d27e54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('fin_operation_accounts')}
    if 'auto' not in colonnes:
        with op.batch_alter_table('fin_operation_accounts') as batch_op:
            batch_op.add_column(sa.Column('auto', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('fin_operation_accounts') as batch_op:
        batch_op.drop_column('auto')
