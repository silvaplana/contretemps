"""finances: general assemblies

Tables of the Assemblée générale sub-module (spec/modules/financier.md §5):
one assembly per row, per organisation and season, and its PowerPoint
files. Created only when missing (create_all runs before
`alembic upgrade head` in deploy.sh).

Revision ID: c9d1e3f5a7b2
Revises: b7e2d4f6a8c1
"""

import sqlalchemy as sa
from alembic import op

revision = "c9d1e3f5a7b2"
down_revision = "b7e2d4f6a8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("fin_assemblies"):
        op.create_table(
            "fin_assemblies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("season_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("state", sa.String(length=20), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("model", sa.String(length=40), nullable=False),
            sa.Column("ai_cost_usd", sa.Float(), nullable=False),
            sa.Column("result", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=10), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("run_started_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_fin_assemblies_org_id", "fin_assemblies", ["org_id"])
        op.create_index("ix_fin_assemblies_season_id", "fin_assemblies", ["season_id"])
    if not inspector.has_table("fin_assembly_files"):
        op.create_table(
            "fin_assembly_files",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assembly_id", sa.Integer(), sa.ForeignKey("fin_assemblies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("origin", sa.String(length=10), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("source", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_fin_assembly_files_assembly_id", "fin_assembly_files", ["assembly_id"])


def downgrade() -> None:
    op.drop_table("fin_assembly_files")
    op.drop_table("fin_assemblies")
