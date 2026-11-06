"""nf_notes deferred_at and gap_settlement

« Plus tard » in the import review and « Régler l'écart » on a paid piece
(Seb, 2026-11-06).

Revision ID: c5e7a9b1d3f5
Revises: b4d6f8a0c2e4
Create Date: 2026-11-06 17:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e7a9b1d3f5'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a0c2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('nf_notes')}
    with op.batch_alter_table('nf_notes') as batch_op:
        if 'deferred_at' not in colonnes:
            batch_op.add_column(sa.Column('deferred_at', sa.DateTime(), nullable=True))
        if 'gap_settlement' not in colonnes:
            batch_op.add_column(sa.Column('gap_settlement', sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_notes') as batch_op:
        batch_op.drop_column('gap_settlement')
        batch_op.drop_column('deferred_at')
