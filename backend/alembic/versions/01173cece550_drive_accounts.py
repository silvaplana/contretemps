"""drive accounts

Drives du club (spec/core.md §3, Seb 19 November 2026): the kDrive and
Google Drive of an organisation. The module is off by default; it is
switched on here for the combat schools (ASC La Ciotat) with one
`org_modules` row each, unless a choice already exists.

Revision ID: 01173cece550
Revises: d2f7a4c9e1b6
"""

import sqlalchemy as sa
from alembic import op

revision = "01173cece550"
down_revision = "d2f7a4c9e1b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # deploy.sh runs create_all before Alembic: the table may exist already.
    if "drive_accounts" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "drive_accounts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("organization_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False, index=True),
            sa.Column("name", sa.String(30), nullable=False, server_default="Club"),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("address", sa.String(255), nullable=False),
            sa.Column("drive_ref", sa.String(50), nullable=False, server_default=""),
            sa.Column("secret_encrypted", sa.Text, nullable=False, server_default=""),
            sa.Column("connected_at", sa.DateTime, nullable=False),
            sa.Column("cut_at", sa.DateTime, nullable=True),
        )
    bind.execute(
        sa.text(
            "INSERT INTO org_modules (org_id, module_key, enabled, updated_at) "
            "SELECT id, 'drives', :on, CURRENT_TIMESTAMP FROM ecoles WHERE nature = 'combat' "
            "AND id NOT IN (SELECT org_id FROM org_modules WHERE module_key = 'drives')"
        ),
        {"on": True},
    )


def downgrade() -> None:
    op.execute("DELETE FROM org_modules WHERE module_key = 'drives'")
    op.drop_table("drive_accounts")
