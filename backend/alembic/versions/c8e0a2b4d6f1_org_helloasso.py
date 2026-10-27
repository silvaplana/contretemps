"""org helloasso

Step 8a (spec/modules/helloasso.md §2): the HelloAsso connection of an
organisation (client id, encrypted secret, association found, last test).
The module is switched off in every existing school (one `org_modules` row
each): a school ticks it when it collects its memberships on HelloAsso.

Revision ID: c8e0a2b4d6f1
Revises: f4a6b8c0d2e5
"""

import sqlalchemy as sa
from alembic import op

revision = "c8e0a2b4d6f1"
down_revision = "f4a6b8c0d2e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # deploy.sh runs create_all before Alembic: the table may already exist.
    if "org_helloasso" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "org_helloasso",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("org_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False, unique=True),
            sa.Column("client_id", sa.String(200), nullable=False),
            sa.Column("secret_encrypted", sa.Text, nullable=False),
            sa.Column("org_name", sa.String(255), nullable=False),
            sa.Column("org_slug", sa.String(255), nullable=False),
            sa.Column("connected_at", sa.DateTime, nullable=False),
            sa.Column("active", sa.Boolean, nullable=False),
            sa.Column("last_test_at", sa.DateTime, nullable=True),
            sa.Column("last_test_ok", sa.Boolean, nullable=True),
        )
    # Off in existing schools, unless a choice already exists.
    bind.execute(
        sa.text(
            "INSERT INTO org_modules (org_id, module_key, enabled, updated_at) "
            "SELECT id, 'helloasso', :off, CURRENT_TIMESTAMP FROM ecoles "
            "WHERE id NOT IN (SELECT org_id FROM org_modules WHERE module_key = 'helloasso')"
        ),
        {"off": False},
    )


def downgrade() -> None:
    op.execute("DELETE FROM org_modules WHERE module_key = 'helloasso'")
    op.drop_table("org_helloasso")
