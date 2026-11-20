"""fin_year_end_entries

Year-end entries (financier.md §8.14, Seb 20/11): the treasurer's validated
choices on what the app proposes (prepaid expense or income, invoice not yet
received, depreciation). The ledger entries are recomputed from these rows.

Revision ID: b4e7a1c93d26
Revises: a9d3f6c20b18
Create Date: 2026-11-20 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e7a1c93d26'
down_revision: Union[str, Sequence[str], None] = 'a9d3f6c20b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('fin_year_end_entries'):
        return
    op.create_table(
        'fin_year_end_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('season_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('text', sa.String(length=400), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('keep', sa.Boolean(), nullable=False),
        sa.Column('years', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['fin_chart_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'season_id', 'key', name='uq_fin_year_end_entries_key'),
    )
    op.create_index(op.f('ix_fin_year_end_entries_org_id'), 'fin_year_end_entries', ['org_id'], unique=False)
    op.create_index(op.f('ix_fin_year_end_entries_season_id'), 'fin_year_end_entries', ['season_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fin_year_end_entries_season_id'), table_name='fin_year_end_entries')
    op.drop_index(op.f('ix_fin_year_end_entries_org_id'), table_name='fin_year_end_entries')
    op.drop_table('fin_year_end_entries')
