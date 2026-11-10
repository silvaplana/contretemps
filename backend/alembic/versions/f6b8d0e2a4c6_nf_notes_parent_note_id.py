"""nf_notes.parent_note_id: a "Reste dû" piece settles its parent invoice

financier.md §8.7 (Seb, 10 November 2026): an invoice paid in two bank
transactions (De Luca 296 = 140 + 156) is one charge and one third-party
invoice line; the rest-due piece is only a second payment, lettered with the
invoice when the sum matches.

Revision ID: f6b8d0e2a4c6
Revises: e5a7c9d1f3b5
Create Date: 2026-11-10 15:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6b8d0e2a4c6'
down_revision: Union[str, Sequence[str], None] = 'e5a7c9d1f3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'parent_note_id' not in {c['name'] for c in sa.inspect(bind).get_columns('nf_notes')}:
        with op.batch_alter_table('nf_notes') as batch:
            batch.add_column(sa.Column('parent_note_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_notes') as batch:
        batch.drop_column('parent_note_id')
