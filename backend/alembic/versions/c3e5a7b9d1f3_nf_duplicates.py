"""nf_pieces.sha256 and nf_notes.duplicate_of_id: a file deposited twice is flagged at the import review

notes-de-frais.md §7 quinquies (Seb, 10 November 2026): the treasurer's 2024-25
folder held 11 duplicates; the review now says "same file as piece N".

Revision ID: c3e5a7b9d1f3
Revises: a7b9c1d3e5f2
Create Date: 2026-11-10 14:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e5a7b9d1f3'
down_revision: Union[str, Sequence[str], None] = 'a7b9c1d3e5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'sha256' not in {c['name'] for c in inspector.get_columns('nf_pieces')}:
        with op.batch_alter_table('nf_pieces') as batch:
            batch.add_column(sa.Column('sha256', sa.String(length=64), nullable=True))
            batch.create_index('ix_nf_pieces_sha256', ['sha256'])
    if 'duplicate_of_id' not in {c['name'] for c in inspector.get_columns('nf_notes')}:
        with op.batch_alter_table('nf_notes') as batch:
            batch.add_column(sa.Column('duplicate_of_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_notes') as batch:
        batch.drop_column('duplicate_of_id')
    with op.batch_alter_table('nf_pieces') as batch:
        batch.drop_index('ix_nf_pieces_sha256')
        batch.drop_column('sha256')
