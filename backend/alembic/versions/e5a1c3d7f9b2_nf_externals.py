"""People outside the organisation, paid by expense notes or fees (notes-de-frais.md §7 quater)

Revision ID: e5a1c3d7f9b2
Revises: a7c9e1f3b5d8
Create Date: 2026-10-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a1c3d7f9b2"
down_revision: str | Sequence[str] | None = "a7c9e1f3b5d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the table may already exist.
    if "nf_externals" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nf_externals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_nf_externals_org_id"), "nf_externals", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_nf_externals_org_id"), table_name="nf_externals")
    op.drop_table("nf_externals")
