"""conversations: created_at

When a conversation was created, to rank one with no message yet in the list
(spec/modules/messagerie-instantanee.md §4.8). Left empty for existing rows. The
backend's create_all runs before `alembic upgrade head` in deploy.sh but never
adds a column to an existing table: the column is added only when missing.

Revision ID: 4d2a6c8e1b3f
Revises: 2b7d9e1f3a5c
"""

import sqlalchemy as sa
from alembic import op

revision = "4d2a6c8e1b3f"
down_revision = "2b7d9e1f3a5c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("conversations")}
    if "created_at" not in existing:
        with op.batch_alter_table("conversations") as batch:
            batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("created_at")
