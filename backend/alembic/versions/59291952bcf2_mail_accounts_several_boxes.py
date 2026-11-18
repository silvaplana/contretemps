"""mail accounts: several boxes per organization

Mail sub-module (spec/modules/mail.md §4 bis, §9): a school can connect
several mailboxes (Seb, 18 November 2026). `organization_id` is no longer
unique and each box gets a short name; the existing box becomes « Club ».
SQLite cannot drop the unnamed unique constraint, so the table is rebuilt
from the definition below (rows are copied as they are).

Revision ID: 59291952bcf2
Revises: a3e5c7d9f1b2
"""

import sqlalchemy as sa
from alembic import op

revision = "59291952bcf2"
down_revision = "a3e5c7d9f1b2"
branch_labels = None
depends_on = None


def _table(unique: bool) -> sa.Table:
    return sa.Table(
        "mail_accounts",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("organization_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False, unique=unique),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False, server_default="gmail"),
        sa.Column("app_password_encrypted", sa.Text, nullable=False),
        sa.Column("connected_at", sa.DateTime, nullable=False),
        sa.Column("cut_at", sa.DateTime, nullable=True),
    )


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: a new database already has
    # the new table.
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("mail_accounts")}
    if "name" in columns:
        return
    with op.batch_alter_table("mail_accounts", recreate="always", copy_from=_table(unique=False)) as batch:
        batch.add_column(sa.Column("name", sa.String(length=30), nullable=False, server_default="Club"))
        batch.create_index("ix_mail_accounts_organization_id", ["organization_id"])


def downgrade() -> None:
    # Back to one box per school: keep the first one.
    op.execute("DELETE FROM mail_accounts WHERE id NOT IN (SELECT MIN(id) FROM mail_accounts GROUP BY organization_id)")
    with op.batch_alter_table("mail_accounts") as batch:
        batch.drop_index("ix_mail_accounts_organization_id")
        batch.drop_column("name")
    with op.batch_alter_table("mail_accounts", recreate="always", copy_from=_table(unique=True)):
        pass
