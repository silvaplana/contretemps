"""mail accounts

Mail sub-module, step 1 (spec/modules/mail.md §9): the Gmail mailbox of an
organisation (address, encrypted app password). The module is off by
default (Module.enabled_by_default=False); it is switched on here for the
combat schools (ASC La Ciotat, Seb 18 November 2026) with one `org_modules`
row each, unless a choice already exists.

Revision ID: e4a6c8b0d2f3
Revises: f6b8d0a2c4e6
"""

import sqlalchemy as sa
from alembic import op

revision = "e4a6c8b0d2f3"
down_revision = "f6b8d0a2c4e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # deploy.sh runs create_all before Alembic: the table may exist already.
    if "mail_accounts" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "mail_accounts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("organization_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False, unique=True),
            sa.Column("address", sa.String(255), nullable=False),
            sa.Column("app_password_encrypted", sa.Text, nullable=False),
            sa.Column("connected_at", sa.DateTime, nullable=False),
            sa.Column("cut_at", sa.DateTime, nullable=True),
        )
    # On for the combat schools (ASC), unless a choice already exists. The
    # Messagerie it needs is on everywhere already.
    bind.execute(
        sa.text(
            "INSERT INTO org_modules (org_id, module_key, enabled, updated_at) "
            "SELECT id, 'mail', :on, CURRENT_TIMESTAMP FROM ecoles WHERE nature = 'combat' "
            "AND id NOT IN (SELECT org_id FROM org_modules WHERE module_key = 'mail')"
        ),
        {"on": True},
    )


def downgrade() -> None:
    op.execute("DELETE FROM org_modules WHERE module_key = 'mail'")
    op.drop_table("mail_accounts")
