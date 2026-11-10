"""fin_settings: memorized copy of the chart of accounts

financier.md §8.7 (Seb, 10 November 2026): « Mémoriser le plan comptable »
keeps a copy of the chart that « Repartir à zéro sur cette saison » puts
back. Two nullable columns, nothing existing changes.

Revision ID: d2e4f6a8b0c2
Revises: c7d9e1f3a5b7
Create Date: 2026-11-10 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2e4f6a8b0c2'
down_revision: Union[str, Sequence[str], None] = 'c7d9e1f3a5b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('fin_settings')}
    with op.batch_alter_table('fin_settings') as batch:
        if 'chart_snapshot' not in existing:
            batch.add_column(sa.Column('chart_snapshot', sa.JSON(), nullable=True))
        if 'chart_snapshot_at' not in existing:
            batch.add_column(sa.Column('chart_snapshot_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('fin_settings') as batch:
        batch.drop_column('chart_snapshot_at')
        batch.drop_column('chart_snapshot')
