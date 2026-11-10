"""expenses: « Déjà payée », bank line still to find

notes-de-frais.md §7 septies (Seb, 9 November 2026): a validated expense paid
outside the app waits in Pièces › Rapprocher instead of Virements until a bank
line is attached. One nullable column on nf_notes; nothing existing changes.

Revision ID: d4f6a8b0c2e4
Revises: e7a4c2d9b815
Create Date: 2026-11-10 00:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f6a8b0c2e4'
down_revision: Union[str, Sequence[str], None] = 'e7a4c2d9b815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added it already (see the "has_table" pitfall).
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('nf_notes')}
    if 'paid_unmatched_at' not in existing:
        with op.batch_alter_table('nf_notes') as batch:
            batch.add_column(sa.Column('paid_unmatched_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_notes') as batch:
        batch.drop_column('paid_unmatched_at')
