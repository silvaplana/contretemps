"""nf_notes.suggested_person_id: a name read one letter off a person, to confirm

notes-de-frais.md §7 quinquies (Seb, 10 November 2026): when the name read on a
piece is one letter away from exactly one person of the school, the app
proposes that person at the import review and the treasurer confirms; nothing
is decided by the app alone.

Revision ID: a9c1e3f5b7d9
Revises: f6b8d0e2a4c6
Create Date: 2026-11-10 15:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9c1e3f5b7d9'
down_revision: Union[str, Sequence[str], None] = 'f6b8d0e2a4c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'suggested_person_id' not in {c['name'] for c in sa.inspect(bind).get_columns('nf_notes')}:
        with op.batch_alter_table('nf_notes') as batch:
            batch.add_column(sa.Column('suggested_person_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_notes') as batch:
        batch.drop_column('suggested_person_id')
