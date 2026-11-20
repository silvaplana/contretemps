"""nf_notes invoice_number

The supplier's invoice number read on the piece: found in the bank label, it
counts like the name when matching a piece to its payment (financier.md
§8.3 bis, Seb 20/11).

Revision ID: c3f1a9d27e54
Revises: 66a7b5b78c80
Create Date: 2026-11-20 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f1a9d27e54'
down_revision: Union[str, Sequence[str], None] = '66a7b5b78c80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('nf_notes')}
    if 'invoice_number' not in colonnes:
        with op.batch_alter_table('nf_notes') as batch_op:
            batch_op.add_column(sa.Column('invoice_number', sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_notes') as batch_op:
        batch_op.drop_column('invoice_number')
