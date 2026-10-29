"""Finances: written financial reports (financier.md §8.6)

Revision ID: e5a7b9c1d3f6
Revises: d4f6a8b0c2e5
Create Date: 2026-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a7b9c1d3f6"
down_revision: str | Sequence[str] | None = "d4f6a8b0c2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the table may already exist.
    if "fin_written_reports" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "fin_written_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=40), nullable=False),
        sa.Column("served_by", sa.String(length=60), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["fin_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fin_written_reports_report_id"), "fin_written_reports", ["report_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fin_written_reports_report_id"), table_name="fin_written_reports")
    op.drop_table("fin_written_reports")
