"""season adjustments

Step 7b (spec/core.md §9.2): the options and promo codes of each season
(an amount added or taken off, in cents or hundredths of a percent; ticked
by the person or obtained with a code) and the plans each applies to (no
row = all plans). New tables only: nothing to carry over.

Revision ID: d2e4f6a8b0c1
Revises: c7d9e1f3a5b8
"""

import sqlalchemy as sa
from alembic import op

revision = "d2e4f6a8b0c1"
down_revision = "c7d9e1f3a5b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the tables may already exist.
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "season_adjustments" not in tables:
        op.create_table(
            "season_adjustments",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("org_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False),
            sa.Column("season_id", sa.Integer, sa.ForeignKey("saisons.id"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("amount", sa.Integer, nullable=False),
            sa.Column("unit", sa.String(3), nullable=False),
            sa.Column("mode", sa.String(10), nullable=False),
            sa.Column("code", sa.String(50), nullable=True),
            sa.Column("shown", sa.Boolean, nullable=False),
            sa.Column("max_uses", sa.Integer, nullable=True),
            sa.Column("until", sa.Date, nullable=True),
            sa.Column("quantity", sa.Integer, nullable=True),
            sa.Column("active", sa.Boolean, nullable=False),
            sa.Column("position", sa.Integer, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )
        op.create_index("ix_season_adjustments_org_season", "season_adjustments", ["org_id", "season_id"])
    if "season_adjustment_plans" not in tables:
        op.create_table(
            "season_adjustment_plans",
            sa.Column(
                "adjustment_id", sa.Integer, sa.ForeignKey("season_adjustments.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "plan_id", sa.Integer, sa.ForeignKey("season_plans.id", ondelete="CASCADE"), primary_key=True
            ),
        )
        op.create_index("ix_season_adjustment_plans_plan_id", "season_adjustment_plans", ["plan_id"])


def downgrade() -> None:
    op.drop_table("season_adjustment_plans")
    op.drop_table("season_adjustments")
