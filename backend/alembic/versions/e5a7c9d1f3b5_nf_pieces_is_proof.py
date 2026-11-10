"""nf_pieces.is_proof: the page that proves the transfer paying a piece

notes-de-frais.md §7 quinquies (Seb, 10 November 2026): a CIC transfer notice
is proof of payment, never an accounting piece; filed next to the invoice as
"<invoice name> - Virement".

Revision ID: e5a7c9d1f3b5
Revises: c3e5a7b9d1f3
Create Date: 2026-11-10 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a7c9d1f3b5'
down_revision: Union[str, Sequence[str], None] = 'c3e5a7b9d1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'is_proof' not in {c['name'] for c in sa.inspect(bind).get_columns('nf_pieces')}:
        with op.batch_alter_table('nf_pieces') as batch:
            batch.add_column(sa.Column('is_proof', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('nf_pieces') as batch:
        batch.drop_column('is_proof')
