"""écoles : police du slogan

Voir spec/SPEC.md §5.1.1 (demande du 2026-10-15) : comme le nom, le slogan
peut avoir sa propre police.

Revision ID: d5f7b9c1e3a4
Revises: c4e6a8b0d2f3
Create Date: 2026-10-15 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd5f7b9c1e3a4'
down_revision: Union[str, Sequence[str], None] = 'c4e6a8b0d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if 'police_slogan' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('ecoles')}:
        op.add_column('ecoles', sa.Column('police_slogan', sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('ecoles') as batch:
        batch.drop_column('police_slogan')
