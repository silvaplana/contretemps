"""fin_budget_lines

Budget prévisionnel of the next season (financier.md §8.10, step 6, Seb 20/11):
one planned amount per income or expense account, typed by the treasurer.

Revision ID: e5b8c2f41a07
Revises: d7a2e4b19c63
Create Date: 2026-11-20 19:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b8c2f41a07'
down_revision: Union[str, Sequence[str], None] = 'd7a2e4b19c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('fin_budget_lines'):
        return
    op.create_table(
        'fin_budget_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('season_id', sa.Integer(), nullable=False),
        sa.Column('number', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'season_id', 'number'),
    )
    op.create_index(op.f('ix_fin_budget_lines_org_id'), 'fin_budget_lines', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fin_budget_lines_org_id'), table_name='fin_budget_lines')
    op.drop_table('fin_budget_lines')
