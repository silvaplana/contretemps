"""fin_chart_accounts.nature_label: a free nature name chosen by the treasurer

financier.md §8.2 (Seb, 10 November 2026): in the chart of accounts, a nature
can be typed freely (« Immobilisations »…). The computing nature (dépense,
recette, attente) stays in `nature`; `nature_label` is only the name shown.

Revision ID: d2f4a6c8e0b2
Revises: b1d3f5a7c9e1
Create Date: 2026-11-10 19:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2f4a6c8e0b2'
down_revision: Union[str, Sequence[str], None] = 'b1d3f5a7c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existantes = {c['name'] for c in sa.inspect(bind).get_columns('fin_chart_accounts')}
    if 'nature_label' not in existantes:
        with op.batch_alter_table('fin_chart_accounts') as batch:
            batch.add_column(sa.Column('nature_label', sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('fin_chart_accounts') as batch:
        batch.drop_column('nature_label')
