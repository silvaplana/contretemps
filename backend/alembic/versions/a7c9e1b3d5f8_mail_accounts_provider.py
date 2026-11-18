"""mail accounts provider

Mail sub-module (spec/modules/mail.md §4, §9): the mailbox can be a Gmail or an
Infomaniak one (Seb, 18 November 2026). Existing rows are Gmail.

Revision ID: a7c9e1b3d5f8
Revises: e4a6c8b0d2f3
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c9e1b3d5f8"
down_revision = "e4a6c8b0d2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mail_accounts") as batch:
        batch.add_column(sa.Column("provider", sa.String(length=20), nullable=False, server_default="gmail"))


def downgrade() -> None:
    with op.batch_alter_table("mail_accounts") as batch:
        batch.drop_column("provider")
