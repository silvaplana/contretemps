"""nf_notes batch_id

« Annuler cet import » (Seb, 2026-11-01): each piece keeps the id of the
batch of files it was imported with, so a whole import can be undone.
nf_depenses.date_approximative: the piece only bore a month, the last day
was taken and the piece says so.

Revision ID: b4d6f8a0c2e4
Revises: a7c9e1b3d5f2
Create Date: 2026-11-01 22:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d6f8a0c2e4'
down_revision: Union[str, Sequence[str], None] = 'a7c9e1b3d5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('nf_notes')}
    if 'batch_id' not in colonnes:
        with op.batch_alter_table('nf_notes') as batch_op:
            batch_op.add_column(sa.Column('batch_id', sa.String(length=36), nullable=True))
            batch_op.create_index('ix_nf_notes_batch_id', ['batch_id'])
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('nf_depenses')}
    if 'date_approximative' not in colonnes:
        with op.batch_alter_table('nf_depenses') as batch_op:
            batch_op.add_column(sa.Column('date_approximative', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('nf_depenses') as batch_op:
        batch_op.drop_column('date_approximative')
    with op.batch_alter_table('nf_notes') as batch_op:
        batch_op.drop_index('ix_nf_notes_batch_id')
        batch_op.drop_column('batch_id')
