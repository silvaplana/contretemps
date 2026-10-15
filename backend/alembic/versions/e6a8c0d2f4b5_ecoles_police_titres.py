"""écoles : police des titres de l'appli

Voir spec/SPEC.md §5.1.1 (demande du 2026-10-15) : les titres peuvent avoir
leur propre police, distincte de celle des textes.

Revision ID: e6a8c0d2f4b5
Revises: d5f7b9c1e3a4
Create Date: 2026-10-15 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e6a8c0d2f4b5'
down_revision: Union[str, Sequence[str], None] = 'd5f7b9c1e3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if 'police_titres' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('ecoles')}:
        op.add_column('ecoles', sa.Column('police_titres', sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('ecoles') as batch:
        batch.drop_column('police_titres')
