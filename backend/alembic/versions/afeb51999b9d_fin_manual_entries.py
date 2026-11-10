"""fin_manual_entries: hand-written OD entries of a season (411, 471)

financier.md §8.10 step 4 (Seb, 9 November 2026): what is neither on the
statements nor in the cash box nor carried by a receipt.

Revision ID: afeb51999b9d
Revises: f1a3c5e7b9d2
Create Date: 2026-11-10 02:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'afeb51999b9d'
down_revision: Union[str, Sequence[str], None] = 'f1a3c5e7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("fin_manual_entries"):
        return
    op.create_table(
        "fin_manual_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("debit_account_id", sa.Integer(), sa.ForeignKey("fin_chart_accounts.id"), nullable=False),
        sa.Column("credit_account_id", sa.Integer(), sa.ForeignKey("fin_chart_accounts.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_fin_manual_entries_org_id", "fin_manual_entries", ["org_id"])
    op.create_index("ix_fin_manual_entries_season_id", "fin_manual_entries", ["season_id"])


def downgrade() -> None:
    op.drop_index("ix_fin_manual_entries_season_id", table_name="fin_manual_entries")
    op.drop_index("ix_fin_manual_entries_org_id", table_name="fin_manual_entries")
    op.drop_table("fin_manual_entries")
