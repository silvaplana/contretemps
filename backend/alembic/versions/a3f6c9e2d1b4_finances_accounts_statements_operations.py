"""finances: accounts, statements, operations

Tables of the Comptes sub-module (spec/modules/financier.md §3), one set for
all organisations, filtered by org_id. The backend's create_all runs before
`alembic upgrade head` in deploy.sh, so each table is created only when
missing.

Revision ID: a3f6c9e2d1b4
Revises: 4d2a6c8e1b3f
"""

import sqlalchemy as sa
from alembic import op

revision = "a3f6c9e2d1b4"
down_revision = "4d2a6c8e1b3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("fin_accounts"):
        op.create_table(
            "fin_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("number", sa.String(length=34), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.UniqueConstraint("org_id", "number", name="uq_fin_accounts_org_number"),
        )
        op.create_index("ix_fin_accounts_org_id", "fin_accounts", ["org_id"])
    if not inspector.has_table("fin_statements"):
        op.create_table(
            "fin_statements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("account_id", sa.Integer(), sa.ForeignKey("fin_accounts.id"), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("start_balance", sa.Integer(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("end_balance", sa.Integer(), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("imported_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("account_id", "start_date", "end_date", name="uq_fin_statements_period"),
        )
        op.create_index("ix_fin_statements_account_id", "fin_statements", ["account_id"])
    if not inspector.has_table("fin_operations"):
        op.create_table(
            "fin_operations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("account_id", sa.Integer(), sa.ForeignKey("fin_accounts.id"), nullable=False),
            sa.Column("statement_id", sa.Integer(), sa.ForeignKey("fin_statements.id", ondelete="CASCADE"), nullable=True),
            sa.Column("source", sa.String(length=10), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("value_date", sa.Date(), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("details", sa.Text(), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("transfer_id", sa.Integer(), sa.ForeignKey("fin_operations.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_fin_operations_account_id", "fin_operations", ["account_id"])
        op.create_index("ix_fin_operations_date", "fin_operations", ["date"])


def downgrade() -> None:
    op.drop_table("fin_operations")
    op.drop_table("fin_statements")
    op.drop_table("fin_accounts")
