"""nf_notes: piece number given at validation

financier.md §8.7 (Seb, 10 November 2026): each validated piece gets a
number per season and journal (AC-2025-001…), shown in the Grand livre and
the FEC. One nullable column, nothing existing changes.

Revision ID: c7d9e1f3a5b7
Revises: bf26dc81d9b0
Create Date: 2026-11-10 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d9e1f3a5b7'
down_revision: Union[str, Sequence[str], None] = 'bf26dc81d9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('nf_notes')}
    if 'piece_number' not in existing:
        with op.batch_alter_table('nf_notes') as batch:
            batch.add_column(sa.Column('piece_number', sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_notes') as batch:
        batch.drop_column('piece_number')
