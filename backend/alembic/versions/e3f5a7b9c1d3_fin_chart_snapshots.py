"""fin_chart_snapshots: a journal of memorized charts of accounts

financier.md §8.7 (Seb, 10 November 2026): every « Mémoriser le plan
comptable » becomes a row with a date and a comment; « Repartir à zéro »
puts one of them back. The single copy kept on fin_settings by d2e4f6a8b0c2
moves into the first row, then its two columns go.

Revision ID: e3f5a7b9c1d3
Revises: d2e4f6a8b0c2
Create Date: 2026-11-10 13:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3f5a7b9c1d3'
down_revision: Union[str, Sequence[str], None] = 'd2e4f6a8b0c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('fin_chart_snapshots'):
        op.create_table(
            'fin_chart_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('taken_at', sa.DateTime(), nullable=False),
            sa.Column('comment', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('accounts', sa.JSON(), nullable=False),
        )
        op.create_index('ix_fin_chart_snapshots_org_id', 'fin_chart_snapshots', ['org_id'])
    columns = {c['name'] for c in inspector.get_columns('fin_settings')}
    if 'chart_snapshot' in columns:
        rows = bind.execute(
            sa.text("SELECT org_id, chart_snapshot, chart_snapshot_at FROM fin_settings WHERE chart_snapshot IS NOT NULL")
        ).fetchall()
        for org_id, accounts, taken_at in rows:
            bind.execute(
                sa.text("INSERT INTO fin_chart_snapshots (org_id, taken_at, comment, accounts) VALUES (:org, :at, :c, :acc)"),
                {"org": org_id, "at": taken_at, "c": "Plan de départ", "acc": accounts},
            )
        with op.batch_alter_table('fin_settings') as batch:
            batch.drop_column('chart_snapshot_at')
            batch.drop_column('chart_snapshot')


def downgrade() -> None:
    with op.batch_alter_table('fin_settings') as batch:
        batch.add_column(sa.Column('chart_snapshot', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('chart_snapshot_at', sa.DateTime(), nullable=True))
    op.drop_index('ix_fin_chart_snapshots_org_id', table_name='fin_chart_snapshots')
    op.drop_table('fin_chart_snapshots')
