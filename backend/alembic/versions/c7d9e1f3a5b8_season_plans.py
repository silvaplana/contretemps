"""season plans

Step 7a (spec/core.md §9.1): the plans of each season (name, price, active,
order) and their installments (due date, empty = at registration, and
amount; their sum is the price). Amounts in cents, like the Financier.
New tables only: nothing to carry over.

Revision ID: c7d9e1f3a5b8
Revises: b9d1f3a5c7e8
"""

import sqlalchemy as sa
from alembic import op

revision = "c7d9e1f3a5b8"
down_revision = "b9d1f3a5c7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the tables may already exist.
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "season_plans" not in tables:
        op.create_table(
            "season_plans",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("org_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False),
            sa.Column("season_id", sa.Integer, sa.ForeignKey("saisons.id"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("price", sa.Integer, nullable=False),
            sa.Column("active", sa.Boolean, nullable=False),
            sa.Column("position", sa.Integer, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )
        op.create_index("ix_season_plans_org_season", "season_plans", ["org_id", "season_id"])
    if "season_plan_installments" not in tables:
        op.create_table(
            "season_plan_installments",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "plan_id", sa.Integer, sa.ForeignKey("season_plans.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("position", sa.Integer, nullable=False),
            sa.Column("due_on", sa.Date, nullable=True),
            sa.Column("amount", sa.Integer, nullable=False),
        )
        op.create_index(
            "ix_season_plan_installments_plan_id", "season_plan_installments", ["plan_id"]
        )


def downgrade() -> None:
    op.drop_table("season_plan_installments")
    op.drop_table("season_plans")
