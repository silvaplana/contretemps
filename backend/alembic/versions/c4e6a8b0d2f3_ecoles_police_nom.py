"""écoles : police du nom de l'école

Voir spec/SPEC.md §5.1.1 (demande du 2026-10-15) : le nom de l'école écrit
en texte peut avoir sa propre police (ex. Great Vibes).

Revision ID: c4e6a8b0d2f3
Revises: b3d5f7a9c1e2
Create Date: 2026-10-15 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4e6a8b0d2f3'
down_revision: Union[str, Sequence[str], None] = 'b3d5f7a9c1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if 'police_nom' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('ecoles')}:
        op.add_column('ecoles', sa.Column('police_nom', sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('ecoles') as batch:
        batch.drop_column('police_nom')
