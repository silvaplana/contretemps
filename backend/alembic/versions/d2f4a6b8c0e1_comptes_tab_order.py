"""comptes: tab_order, the bottom bar order chosen by the person

spec/core.md §10.4 (Seb, 12 November 2026): Profil › Ma barre du bas lets each
person order their bottom tabs. One nullable JSON column on `comptes` (the
tab keys in order); null = the school's order, so nothing changes for anyone
until they choose.

Revision ID: d2f4a6b8c0e1
Revises: f3b9d2a6c8e1
Create Date: 2026-11-12 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2f4a6b8c0e1'
down_revision: Union[str, Sequence[str], None] = 'f3b9d2a6c8e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added it already (see the "has_table" pitfall).
    if 'tab_order' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('comptes')}:
        with op.batch_alter_table('comptes') as batch:
            batch.add_column(sa.Column('tab_order', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('comptes') as batch:
        batch.drop_column('tab_order')
