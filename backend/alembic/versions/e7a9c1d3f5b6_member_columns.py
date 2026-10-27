"""member columns

The display in Admin (spec/core.md §4.3, level 2): which columns of the
members table are shown, and in which order, per season. Skipped when
`create_all` (deploy.sh) already made the table.

Revision ID: e7a9c1d3f5b6
Revises: d6f8b0c2e4a5
"""

import sqlalchemy as sa
from alembic import op

revision = "e7a9c1d3f5b6"
down_revision = "d6f8b0c2e4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("member_columns"):
        op.create_table(
            "member_columns",
            sa.Column("org_id", sa.Integer(), sa.ForeignKey("ecoles.id"), primary_key=True),
            sa.Column("season_id", sa.Integer(), sa.ForeignKey("saisons.id"), primary_key=True),
            sa.Column("key", sa.String(40), primary_key=True),
            sa.Column("shown", sa.Boolean(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("member_columns")
