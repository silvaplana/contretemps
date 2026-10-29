"""Finances: opening balances and season closing (financier.md §8.7)

Revision ID: f6b8c0d2e4a7
Revises: e5a7b9c1d3f6
Create Date: 2026-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6b8c0d2e4a7"
down_revision: str | Sequence[str] | None = "e5a7b9c1d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the tables may already exist.
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "fin_opening_balances" not in existing:
        op.create_table(
            "fin_opening_balances",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("season_id", sa.Integer(), nullable=False),
            sa.Column("number", sa.String(length=10), nullable=False),
            sa.Column("label", sa.String(length=80), nullable=False),
            sa.Column("balance", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("org_id", "season_id", "number"),
        )
        op.create_index(op.f("ix_fin_opening_balances_org_id"), "fin_opening_balances", ["org_id"], unique=False)
    if "fin_closings" not in existing:
        op.create_table(
            "fin_closings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("season_id", sa.Integer(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("result", sa.Integer(), nullable=False),
            sa.Column("balances", sa.JSON(), nullable=False),
            sa.Column("closed_by", sa.Integer(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=False),
            sa.Column("reopened_by", sa.Integer(), nullable=True),
            sa.Column("reopened_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_fin_closings_org_id"), "fin_closings", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fin_closings_org_id"), table_name="fin_closings")
    op.drop_table("fin_closings")
    op.drop_index(op.f("ix_fin_opening_balances_org_id"), table_name="fin_opening_balances")
    op.drop_table("fin_opening_balances")
