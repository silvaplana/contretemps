"""ffst: club login and copy of the last reading of the site

Step 1 of spec/modules/ffst.md §10. `ffst_connections`: the club login on
the FFST site (password encrypted), one row per school at most.
`ffst_snapshots`: the three lists as last read, replaced whole at each
reading. The module is off in existing schools (like HelloAsso).

Revision ID: d3f5a7c9e1b2
Revises: b7d2a9c4e1f3
"""

import sqlalchemy as sa
from alembic import op

revision = "d3f5a7c9e1b2"
down_revision = "b7d2a9c4e1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    # deploy.sh runs create_all before Alembic: the tables may exist already.
    if "ffst_connections" not in tables:
        op.create_table(
            "ffst_connections",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("org_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False, unique=True),
            sa.Column("login_part1", sa.String(20), nullable=False),
            sa.Column("login_part2", sa.String(20), nullable=False),
            sa.Column("login_part3", sa.String(20), nullable=False),
            sa.Column("password_encrypted", sa.Text, nullable=False),
            sa.Column("connected_at", sa.DateTime, nullable=False),
            sa.Column("last_test_at", sa.DateTime, nullable=True),
            sa.Column("last_test_ok", sa.Boolean, nullable=True),
        )
    if "ffst_snapshots" not in tables:
        op.create_table(
            "ffst_snapshots",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("org_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False),
            sa.Column("list_name", sa.String(20), nullable=False),
            sa.Column("rows", sa.JSON, nullable=False),
            sa.Column("read_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("org_id", "list_name"),
        )
    # Off in existing schools, unless a choice already exists.
    bind.execute(
        sa.text(
            "INSERT INTO org_modules (org_id, module_key, enabled, updated_at) "
            "SELECT id, 'ffst', :off, CURRENT_TIMESTAMP FROM ecoles "
            "WHERE id NOT IN (SELECT org_id FROM org_modules WHERE module_key = 'ffst')"
        ),
        {"off": False},
    )


def downgrade() -> None:
    op.execute("DELETE FROM org_modules WHERE module_key = 'ffst'")
    op.drop_table("ffst_snapshots")
    op.drop_table("ffst_connections")
