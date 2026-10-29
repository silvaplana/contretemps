"""Finances accounting: chart of accounts, operation accounts, cash, level (financier.md §8)

Revision ID: d4f6a8b0c2e5
Revises: c7e2a94d1f38
Create Date: 2026-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6a8b0c2e5"
down_revision: str | Sequence[str] | None = "c7e2a94d1f38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the tables may already exist.
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "fin_settings" not in existing:
        op.create_table(
            "fin_settings",
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("level", sa.String(length=10), nullable=False),
            sa.PrimaryKeyConstraint("org_id"),
        )
    if "fin_chart_accounts" not in existing:
        op.create_table(
            "fin_chart_accounts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("number", sa.String(length=10), nullable=False),
            sa.Column("label", sa.String(length=80), nullable=False),
            sa.Column("nature", sa.String(length=10), nullable=False),
            sa.Column("event", sa.String(length=40), nullable=True),
            sa.Column("keywords", sa.JSON(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("org_id", "number", name="uq_fin_chart_accounts_org_number"),
        )
        op.create_index(op.f("ix_fin_chart_accounts_org_id"), "fin_chart_accounts", ["org_id"], unique=False)
    if "fin_operation_accounts" not in existing:
        op.create_table(
            "fin_operation_accounts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("operation_id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("confirmed_by", sa.Integer(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["fin_chart_accounts.id"]),
            sa.ForeignKeyConstraint(["operation_id"], ["fin_operations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_fin_operation_accounts_account_id"), "fin_operation_accounts", ["account_id"], unique=False)
        op.create_index(op.f("ix_fin_operation_accounts_operation_id"), "fin_operation_accounts", ["operation_id"], unique=False)
    if "fin_cash_lines" not in existing:
        op.create_table(
            "fin_cash_lines",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=True),
            sa.Column("transfer_operation_id", sa.Integer(), nullable=True),
            sa.Column("doc_node_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["fin_chart_accounts.id"]),
            sa.ForeignKeyConstraint(["transfer_operation_id"], ["fin_operations.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_fin_cash_lines_date"), "fin_cash_lines", ["date"], unique=False)
        op.create_index(op.f("ix_fin_cash_lines_org_id"), "fin_cash_lines", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_table("fin_cash_lines")
    op.drop_table("fin_operation_accounts")
    op.drop_table("fin_chart_accounts")
    op.drop_table("fin_settings")
