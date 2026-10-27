"""member fields

The fields an organisation asks of its members, per season, and the answers
(spec/core.md §4.3): tables `member_fields` and `member_values`. Nothing to
take over yet: the current student fields stay where they are for now.
Skipped when `create_all` (deploy.sh) already made the tables.

Revision ID: d6f8b0c2e4a5
Revises: c5e7a9b1d3f4
"""

import sqlalchemy as sa
from alembic import op

revision = "d6f8b0c2e4a5"
down_revision = "c5e7a9b1d3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("member_fields"):
        op.create_table(
            "member_fields",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), sa.ForeignKey("ecoles.id"), nullable=False),
            sa.Column("season_id", sa.Integer(), sa.ForeignKey("saisons.id"), nullable=False),
            sa.Column("label", sa.String(100), nullable=False),
            sa.Column("required", sa.Boolean(), nullable=False),
            sa.Column("format", sa.String(20), nullable=False),
            sa.Column("choices", sa.JSON(), nullable=True),
            sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
            sa.Column("multiple", sa.Boolean(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("member_sees", sa.Boolean(), nullable=False),
            sa.Column("member_edits", sa.Boolean(), nullable=False),
            sa.Column("others_see", sa.Boolean(), nullable=False),
            sa.Column("for_group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
            sa.Column("removed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_member_fields_org_season", "member_fields", ["org_id", "season_id"])
    if not inspector.has_table("member_values"):
        op.create_table(
            "member_values",
            sa.Column("member_id", sa.Integer(), sa.ForeignKey("comptes.id"), primary_key=True),
            sa.Column("field_id", sa.Integer(), sa.ForeignKey("member_fields.id"), primary_key=True),
            sa.Column("value", sa.JSON(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_member_values_field_id", "member_values", ["field_id"])


def downgrade() -> None:
    op.drop_table("member_values")
    op.drop_table("member_fields")
