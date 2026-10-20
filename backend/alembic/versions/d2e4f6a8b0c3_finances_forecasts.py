"""finances: forecasts

Table of the Prévisionnel sub-module (spec/modules/financier.md §6): one
forecast per row, per organisation and season. Created only when missing
(create_all runs before `alembic upgrade head` in deploy.sh).

Revision ID: d2e4f6a8b0c3
Revises: c9d1e3f5a7b2
"""

import sqlalchemy as sa
from alembic import op

revision = "d2e4f6a8b0c3"
down_revision = "c9d1e3f5a7b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("fin_forecasts"):
        op.create_table(
            "fin_forecasts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("season_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("state", sa.String(length=20), nullable=False),
            sa.Column("start_date", sa.String(length=10), nullable=True),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("model", sa.String(length=40), nullable=False),
            sa.Column("ai_cost_usd", sa.Float(), nullable=False),
            sa.Column("result", sa.Text(), nullable=True),
            sa.Column("params", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=10), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("run_started_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_fin_forecasts_org_id", "fin_forecasts", ["org_id"])
        op.create_index("ix_fin_forecasts_season_id", "fin_forecasts", ["season_id"])


def downgrade() -> None:
    op.drop_table("fin_forecasts")
