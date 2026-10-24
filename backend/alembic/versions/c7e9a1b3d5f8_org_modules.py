"""org modules

Modules switched off per organisation (spec/core.md §9 bis.3). No row means
the module is on, so existing schools see no change. The backend's create_all
runs before `alembic upgrade head` in deploy.sh, so the table may already
exist: then there is nothing to do.

Revision ID: c7e9a1b3d5f8
Revises: b5d7f9a1c3e6
"""

import sqlalchemy as sa
from alembic import op

revision = "c7e9a1b3d5f8"
down_revision = "b5d7f9a1c3e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("org_modules"):
        return
    op.create_table(
        "org_modules",
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("module_key", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["ecoles.id"]),
        sa.PrimaryKeyConstraint("org_id", "module_key"),
    )


def downgrade() -> None:
    op.drop_table("org_modules")
